import json
from urllib.parse import quote
from urllib.request import urlopen

from app.config import settings


class GeocodingError(RuntimeError):
    pass


class LocationIQGeocoder:
    def geocode(self, query: str) -> dict[str, float | str]:
        if not settings.locationiq_api_key:
            raise GeocodingError("LOCATIONIQ_API_KEY is not configured")
        url = (
            "https://us1.locationiq.com/v1/search?key="
            + quote(settings.locationiq_api_key)
            + "&format=json&limit=1&q=" + quote(query)
        )
        try:
            with urlopen(url, timeout=10) as response:
                results = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise GeocodingError(f"LocationIQ request failed: {exc}") from exc
        if not results:
            raise GeocodingError(f"No location found for {query!r}")
        result = results[0]
        return {
            "location": result.get("display_name", query),
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
        }
