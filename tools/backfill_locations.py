#!/usr/bin/env python3
"""Backfill conservative, recognized location entities into PostGIS."""
import argparse
import json
import time
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import psycopg

DB_URL = "postgresql://postgres:postgres@127.0.0.1:5433/mindmesh"
ALIASES = {
    "Bilholi road": "Bidholi Road, Dehradun, Uttarakhand, India",
    "Chakrata": "Chakrata, Uttarakhand, India",
    "Dehradun": "Dehradun, Uttarakhand, India",
    "Dotsagar Waterfall": "Dudhsagar Falls, Goa, India",
    "Gadi Gain": "Gadi Gaon, Dehradun, Uttarakhand, India",
    "Jaipur": "Jaipur, Rajasthan, India",
    "Jim Corbett": "Jim Corbett National Park, Uttarakhand, India",
    "Koregao Park": "Koregaon Park, Pune, Maharashtra, India",
    "Mall road": "Mall Road, Mussoorie, Uttarakhand, India",
    "Masori": "Mussoorie, Uttarakhand, India",
    "Old Mussoorie Road, Dehradun": "Old Mussoorie Road, Dehradun, Uttarakhand, India",
    "Pacific Mall, Rajpur Road, Tharadun": "Pacific Mall, Rajpur Road, Dehradun, Uttarakhand, India",
    "Pune": "Pune, Maharashtra, India",
    "Rajpur Road": "Rajpur Road, Dehradun, Uttarakhand, India",
    "Sahastradhara": "Sahastradhara, Dehradun, Uttarakhand, India",
    "Tiger Falls": "Tiger Falls, Chakrata, Uttarakhand, India",
    "UPES": "UPES, Bidholi, Dehradun, Uttarakhand, India",
    "Yamunanagar": "Yamunanagar, Haryana, India",
}


def geocode(query, api_key):
    request = Request(
        "https://us1.locationiq.com/v1/search?key=" + quote(api_key) + "&format=json&limit=1&q=" + quote(query),
        headers={"User-Agent": "MindMesh-Phase3/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        results = json.loads(response.read())
    if not results:
        return None
    result = results[0]
    return float(result["lat"]), float(result["lon"]), result["display_name"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write locations and links to PostgreSQL")
    args = parser.parse_args()
    api_key = os.getenv("LOCATIONIQ_API_KEY") or _read_env_key()
    if not api_key:
        raise SystemExit("Set LOCATIONIQ_API_KEY before running the geocoder.")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT entity_value
                FROM memory_entities
                WHERE entity_type IN ('location', 'place')
                  AND entity_value = ANY(%s)
                """,
                (list(ALIASES),),
            )
            source_names = [row[0] for row in cur.fetchall()]
            for source_name in source_names:
                result = geocode(ALIASES[source_name], api_key)
                if not result:
                    print(source_name, "NOT FOUND")
                    continue
                latitude, longitude, display_name = result
                print(source_name, "->", display_name, latitude, longitude)
                if args.apply:
                    normalized = ALIASES[source_name].lower()
                    cur.execute("""
                        INSERT INTO locations (normalized_name, display_name, latitude, longitude, point, source, confidence)
                        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s)
                        ON CONFLICT (normalized_name) DO UPDATE SET display_name=EXCLUDED.display_name, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, point=EXCLUDED.point, updated_at=now()
                        RETURNING location_id
                    """, (normalized, display_name, latitude, longitude, longitude, latitude, "nominatim", 0.85))
                    location_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO memory_locations (memory_id, location_id, source, confidence, is_primary)
                        SELECT memory_id, %s, 'entity_backfill', 0.85, FALSE
                        FROM memory_entities
                        WHERE entity_type IN ('location', 'place') AND entity_value=%s
                        ON CONFLICT DO NOTHING
                    """, (location_id, source_name))
                time.sleep(0.5)
        if not args.apply:
            conn.rollback()
    print("Applied" if args.apply else "Dry run only")


def _read_env_key():
    env_path = Path("backend/.env")
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("LOCATIONIQ_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value if value and not value.startswith("replace_with_") else None
    return None


if __name__ == "__main__":
    main()
