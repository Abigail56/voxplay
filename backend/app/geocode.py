"""Turn "Yaba, Lagos" + Nigeria into a point on the map, and a GPS point into a place name.

Uses Nominatim, OpenStreetMap's free geocoder (https://nominatim.org). Its usage
policy asks for at most 1 request a second and a User-Agent that names the app,
so requests are spaced out and every answer is cached in the shared store for
30 days. Only the place text a player typed (or the GPS point they chose to
share) is sent, never anything about who they are.

Pins go on the *place* (the neighbourhood, town or area), never on a player's
exact GPS position: an exact point is usually someone's home.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Protocol

from .store import Store

CACHE_SECONDS = 30 * 24 * 3600


class GeocoderUnavailable(Exception):
    """OpenStreetMap didn't answer (network trouble, rate limit): not the same as "no such place"."""


@dataclass(frozen=True)
class Place:
    name: str  # short and readable, e.g. "Yaba, Lagos"
    country: str  # ISO code, upper case, e.g. "NG"
    lat: float
    lon: float


class Geocoder(Protocol):
    async def search(self, query: str, country: str) -> Place | None: ...

    async def reverse(self, lat: float, lon: float) -> Place | None: ...


def short_name(address: dict, fallback: str) -> str:
    """'Yaba, Lagos' from Nominatim's address parts: the local area, then the town or state."""
    local = next(
        (address[k] for k in ("suburb", "neighbourhood", "quarter", "village", "town", "city_district", "city", "county") if address.get(k)),
        None,
    )
    wider = next(
        (address[k] for k in ("city", "town", "state", "region", "county") if address.get(k) and address.get(k) != local),
        None,
    )
    parts = [p for p in (local, wider) if p]
    return ", ".join(parts) if parts else fallback


class NominatimGeocoder:
    URL = "https://nominatim.openstreetmap.org"

    def __init__(self, store: Store, user_agent: str) -> None:
        import httpx

        self.store = store
        self._http = httpx.AsyncClient(headers={"User-Agent": user_agent}, timeout=10)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def _get(self, path: str, params: dict) -> dict | list | None:
        key = "geo:" + path + ":" + json.dumps(params, sort_keys=True)
        cached = await self.store.get(key)
        if cached is not None:
            return json.loads(cached)
        async with self._lock:  # at most one request a second, from this instance
            wait = 1.0 - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self._http.get(f"{self.URL}/{path}", params={**params, "format": "jsonv2", "addressdetails": 1})
                r.raise_for_status()
                data = r.json()
            except Exception as exc:  # failures aren't cached, so the next try asks again
                raise GeocoderUnavailable(str(exc)) from exc
            finally:
                self._last = time.monotonic()
        await self.store.put(key, json.dumps(data), CACHE_SECONDS)
        return data

    async def search(self, query: str, country: str) -> Place | None:
        data = await self._get("search", {"q": query, "countrycodes": country.lower(), "limit": 1})
        if not data:
            return None
        hit = data[0]
        address = hit.get("address", {})
        return Place(
            name=short_name(address, query),
            country=(address.get("country_code") or country).upper(),
            lat=round(float(hit["lat"]), 5),
            lon=round(float(hit["lon"]), 5),
        )

    async def reverse(self, lat: float, lon: float) -> Place | None:
        # zoom 14 = neighbourhood level: the answer (and its point) is the area, not the house.
        data = await self._get("reverse", {"lat": round(lat, 4), "lon": round(lon, 4), "zoom": 14})
        if not data or "error" in data:
            return None
        address = data.get("address", {})
        if not address.get("country_code"):
            return None
        return Place(
            name=short_name(address, data.get("name") or "Somewhere"),
            country=address["country_code"].upper(),
            lat=round(float(data["lat"]), 5),
            lon=round(float(data["lon"]), 5),
        )

    async def close(self) -> None:
        await self._http.aclose()

