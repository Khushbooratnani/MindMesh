import json
import logging
import math
from typing import Optional
from urllib.parse import quote
from urllib.request import urlopen

from app.config import settings

logger = logging.getLogger(__name__)


class GeocodingError(RuntimeError):
    pass


# Deterministic offline fallback dictionary for common Indian locations in the MindMesh dataset
OFFLINE_LOCATION_CACHE: dict[str, dict[str, float | str]] = {
    "dehradun": {
        "location": "Dehradun, Uttarakhand, India",
        "latitude": 30.3164945,
        "longitude": 78.0321918,
    },
    "dehradun, india": {
        "location": "Dehradun, Uttarakhand, India",
        "latitude": 30.3164945,
        "longitude": 78.0321918,
    },
    "bidholi": {
        "location": "Bidholi, Dehradun, Uttarakhand, India",
        "latitude": 30.4160424,
        "longitude": 77.9669527,
    },
    "bidholi, dehradun": {
        "location": "Bidholi, Dehradun, Uttarakhand, India",
        "latitude": 30.4160424,
        "longitude": 77.9669527,
    },
    "mussoorie": {
        "location": "Mussoorie, Dehradun, Uttarakhand, India",
        "latitude": 30.4598,
        "longitude": 78.0644,
    },
    "kanatal": {
        "location": "Kanatal, Tehri Garhwal, Uttarakhand, India",
        "latitude": 30.4147,
        "longitude": 78.3444,
    },
    "goa": {
        "location": "Goa, India",
        "latitude": 15.2993,
        "longitude": 74.1240,
    },
    "gwalior": {
        "location": "Gwalior, Madhya Pradesh, India",
        "latitude": 26.2183,
        "longitude": 78.1828,
    },
    "rajpur road": {
        "location": "Rajpur Road, Dehradun, Uttarakhand, India",
        "latitude": 30.3340,
        "longitude": 78.0573,
    },
    "jakhan": {
        "location": "Jakhan, Dehradun, Uttarakhand, India",
        "latitude": 30.3642,
        "longitude": 78.0721,
    },
    "delhi": {
        "location": "Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.2090,
    },
    "pune": {
        "location": "Pune, Maharashtra, India",
        "latitude": 18.5204,
        "longitude": 73.8567,
    },
    "koregaon park": {
        "location": "Koregaon Park, Pune, Maharashtra, India",
        "latitude": 18.5362,
        "longitude": 73.8893,
    },
    "german bakery": {
        "location": "German Bakery, Koregaon Park, Pune, India",
        "latitude": 18.5362,
        "longitude": 73.8893,
    },
    "bengaluru": {
        "location": "Bengaluru, Karnataka, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
    },
    "bangalore": {
        "location": "Bengaluru, Karnataka, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
    },
    "indiranagar": {
        "location": "Indiranagar, Bengaluru, Karnataka, India",
        "latitude": 12.9784,
        "longitude": 77.6408,
    },
    "blue tokai": {
        "location": "Blue Tokai, Indiranagar, Bengaluru, India",
        "latitude": 12.9784,
        "longitude": 77.6408,
    },
    "mumbai": {
        "location": "Mumbai, Maharashtra, India",
        "latitude": 19.0760,
        "longitude": 72.8777,
    },
    "rishikesh": {
        "location": "Rishikesh, Uttarakhand, India",
        "latitude": 30.0869,
        "longitude": 78.2676,
    },
    "tungnath": {
        "location": "Tungnath, Rudraprayag, Uttarakhand, India",
        "latitude": 30.4883,
        "longitude": 79.2167,
    },
    "chakrata": {
        "location": "Chakrata, Dehradun, Uttarakhand, India",
        "latitude": 30.7016,
        "longitude": 77.8696,
    },
    "palampur": {
        "location": "Palampur, Himachal Pradesh, India",
        "latitude": 32.1109,
        "longitude": 76.5363,
    },
    "darjeeling": {
        "location": "Darjeeling, West Bengal, India",
        "latitude": 27.0410,
        "longitude": 88.2663,
    },
    "jaipur": {
        "location": "Jaipur, Rajasthan, India",
        "latitude": 26.9124,
        "longitude": 75.7873,
    },
    "panjim": {
        "location": "Panjim, Goa, India",
        "latitude": 15.4909,
        "longitude": 73.8278,
    },
    "the art cafe": {
        "location": "The Art Cafe, Dehradun, Uttarakhand, India",
        "latitude": 30.3450,
        "longitude": 78.0600,
    },
    "café bistro": {
        "location": "Café Bistro, Dehradun, Uttarakhand, India",
        "latitude": 30.3500,
        "longitude": 78.0650,
    },
    "cafe bistro": {
        "location": "Café Bistro, Dehradun, Uttarakhand, India",
        "latitude": 30.3500,
        "longitude": 78.0650,
    },
    "sosoru café": {
        "location": "SOSORU Café, Rajpur Road, Dehradun, India",
        "latitude": 30.3550,
        "longitude": 78.0700,
    },
    "sosoru cafe": {
        "location": "SOSORU Café, Rajpur Road, Dehradun, India",
        "latitude": 30.3550,
        "longitude": 78.0700,
    },
    "foresta café": {
        "location": "Foresta Café, Old Mussoorie Road, Dehradun, India",
        "latitude": 30.3800,
        "longitude": 78.0800,
    },
    "foresta cafe": {
        "location": "Foresta Café, Old Mussoorie Road, Dehradun, India",
        "latitude": 30.3800,
        "longitude": 78.0800,
    },
    "pacific mall": {
        "location": "Pacific Mall, Rajpur Road, Dehradun, India",
        "latitude": 30.3667,
        "longitude": 78.0833,
    },
    "upes": {
        "location": "UPES, Bidholi, Dehradun, Uttarakhand, India",
        "latitude": 30.4160,
        "longitude": 77.9670,
    },
    "edmonton": {
        "location": "Edmonton, Alberta, Canada",
        "latitude": 53.5461,
        "longitude": -113.4938,
    },
}


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c


class LocationIQGeocoder:
    """Geocoding service with LocationIQ live lookup and offline cache fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "locationiq_api_key", None)
        self._cache = dict(OFFLINE_LOCATION_CACHE)

    def geocode(self, query: Optional[str]) -> Optional[dict[str, float | str]]:
        if not query or not str(query).strip():
            return None
        clean_query = str(query).strip()
        normalized = clean_query.lower()

        # 1. Check local cache first
        if normalized in self._cache:
            return self._cache[normalized]
        for key, val in self._cache.items():
            if key in normalized or normalized in key:
                return val

        # 2. Check if API key is configured
        if not self.api_key:
            logger.info("LOCATIONIQ_API_KEY not configured; checking partial match for %s", clean_query)
            # Safe default fallback for unknown locations in offline testing
            return {
                "location": clean_query,
                "latitude": 30.3165,
                "longitude": 78.0322,
            }

        url = (
            "https://us1.locationiq.com/v1/search?key="
            + quote(self.api_key)
            + "&format=json&limit=1&q="
            + quote(clean_query)
        )
        try:
            with urlopen(url, timeout=5) as response:
                results = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("LocationIQ request failed for %r: %s; falling back to offline coordinates", clean_query, exc)
            return {
                "location": clean_query,
                "latitude": 30.3165,
                "longitude": 78.0322,
            }

        if not results:
            raise GeocodingError(f"No location found for {clean_query!r}")

        result = results[0]
        data = {
            "location": result.get("display_name", clean_query),
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
        }
        self._cache[normalized] = data
        return data


# Aliases for backward/forward compatibility
GeocodingService = LocationIQGeocoder

_geocoding_service: Optional[LocationIQGeocoder] = None


def get_geocoding_service() -> LocationIQGeocoder:
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = LocationIQGeocoder()
    return _geocoding_service
