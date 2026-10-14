"""Generate a PostgreSQL seed file from PHASE_2_PIPELINE_PAYLOADS.md."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "PHASE_2_PIPELINE_PAYLOADS.md"
OUTPUT_PATH = ROOT / "backend" / "db" / "seeds" / "phase2_pipeline_payloads.sql"


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def sql_text_array(values: list[Any]) -> str:
    if not values:
        return "ARRAY[]::text[]"
    items = ", ".join(sql_literal(value) for value in values)
    return f"ARRAY[{items}]::text[]"


def sql_jsonb(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return f"{sql_literal(encoded)}::jsonb"


def collect_memories(markdown: str) -> list[dict[str, Any]]:
    memories: dict[str, dict[str, Any]] = {}
    for match in re.finditer(r"```json\s*(.*?)```", markdown, re.DOTALL):
        raw_block = match.group(1).strip()
        try:
            parsed = json.loads(raw_block)
        except json.JSONDecodeError:
            continue

        candidates = parsed if isinstance(parsed, list) else [parsed]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("memory_id"):
                memories[candidate["memory_id"]] = candidate

    return list(memories.values())


def values_row(memory: dict[str, Any]) -> str:
    system = memory["system"]
    content = memory["content"]
    semantics = memory["semantics"]
    temporal = memory["temporal"]
    processing = memory["processing"]

    values = [
        memory["memory_id"],
        memory["schema_version"],
        system["owner_id"],
        system.get("group_id"),
        system["media_type"],
        system["created_at"],
        system["privacy"],
        system.get("allowed_users", []),
        content.get("raw_text"),
        content["clean_text"],
        content["description"],
        content["summary"],
        semantics["sentiment"],
        temporal.get("mentioned_dates", []),
        temporal.get("inferred_time"),
        temporal.get("time_of_day"),
        processing["status"],
        processing["source_modality"],
        processing["transcription_required"],
        processing["image_understanding_required"],
        processing["llm_provider"],
        processing["llm_model"],
        processing.get("errors", []),
    ]

    rendered = []
    for index, value in enumerate(values):
        if index in {7, 13, 22}:
            rendered.append(sql_text_array(value))
        else:
            rendered.append(sql_literal(value))
    return "(" + ", ".join(rendered) + ")"


def relation_rows(memories: list[dict[str, Any]]) -> dict[str, list[tuple[Any, ...]]]:
    rows: dict[str, list[tuple[Any, ...]]] = {
        "entities": [],
        "topics": [],
        "activities": [],
        "moods": [],
        "attributes": [],
    }
    entity_map = {
        "people": "person",
        "places": "place",
        "locations": "location",
        "events": "event",
        "organizations": "organization",
    }

    for memory in memories:
        memory_id = memory["memory_id"]
        for source_key, entity_type in entity_map.items():
            for value in memory.get("entities", {}).get(source_key, []):
                rows["entities"].append((memory_id, entity_type, value))

        for topic in memory.get("semantics", {}).get("topics", []):
            rows["topics"].append((memory_id, topic))
        for activity in memory.get("semantics", {}).get("activities", []):
            rows["activities"].append((memory_id, activity))
        for mood in memory.get("semantics", {}).get("mood", []):
            rows["moods"].append((memory_id, mood))
        for attribute in memory.get("additional_attributes", []):
            rows["attributes"].append(
                (
                    memory_id,
                    attribute["key"],
                    attribute["value"],
                    attribute["confidence"],
                    attribute["source"],
                )
            )

    return rows


def insert_rows(table: str, columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    if not rows:
        return f"-- No rows for {table}.\n"
    rendered_rows = []
    for row in rows:
        rendered_values = []
        for value in row:
            if table == "memory_attributes" and len(rendered_values) == 2:
                rendered_values.append(sql_jsonb(value))
            else:
                rendered_values.append(sql_literal(value))
        rendered_rows.append("(" + ", ".join(rendered_values) + ")")
    return (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n"
        + ",\n".join(rendered_rows)
        + "\nON CONFLICT DO NOTHING;\n"
    )


def build_sql(memories: list[dict[str, Any]]) -> str:
    rows = relation_rows(memories)
    text_count = sum(1 for memory in memories if memory["system"]["media_type"] == "text")
    image_count = sum(1 for memory in memories if memory["system"]["media_type"] == "image")

    return "\n".join(
        [
            "-- Generated by backend/tools/build_phase2_seed.py.",
            f"-- Source: {SOURCE_PATH.name}",
            f"-- Memories: {len(memories)} total, {text_count} text, {image_count} image.",
            "",
            "BEGIN;",
            "",
            "TRUNCATE TABLE",
            "    memory_embeddings,",
            "    memory_embedding_jobs,",
            "    memory_graph_jobs,",
            "    memory_attributes,",
            "    memory_moods,",
            "    memory_activities,",
            "    memory_topics,",
            "    memory_entities,",
            "    memories",
            "RESTART IDENTITY CASCADE;",
            "",
            "INSERT INTO memories (",
            "    memory_id, schema_version, owner_id, group_id, media_type, created_at,",
            "    privacy, allowed_users, raw_text, clean_text, description, summary,",
            "    sentiment, mentioned_dates, inferred_time, time_of_day,",
            "    processing_status, source_modality, transcription_required,",
            "    image_understanding_required, llm_provider, llm_model, processing_errors",
            ") VALUES",
            ",\n".join(values_row(memory) for memory in memories),
            "ON CONFLICT (memory_id) DO NOTHING;",
            "",
            insert_rows(
                "memory_entities",
                ["memory_id", "entity_type", "entity_value"],
                rows["entities"],
            ),
            insert_rows("memory_topics", ["memory_id", "topic"], rows["topics"]),
            insert_rows(
                "memory_activities",
                ["memory_id", "activity"],
                rows["activities"],
            ),
            insert_rows("memory_moods", ["memory_id", "mood"], rows["moods"]),
            insert_rows(
                "memory_attributes",
                ["memory_id", "key", "value_json", "confidence", "source"],
                rows["attributes"],
            ),
            "COMMIT;",
            "",
        ]
    )


def main() -> None:
    markdown = SOURCE_PATH.read_text(encoding="utf-8")
    memories = collect_memories(markdown)
    if not memories:
        raise RuntimeError(f"No MemoryV1 payloads found in {SOURCE_PATH}")

    OUTPUT_PATH.write_text(build_sql(memories), encoding="utf-8")
    print(f"Wrote {len(memories)} memories to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
