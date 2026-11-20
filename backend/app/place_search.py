"""On-demand search for geolocated Wikipedia entries, with an optional operator endpoint."""

import asyncio
import os
import time
from collections import OrderedDict
from urllib.parse import quote

import httpx

from app.core import fail

_cache = OrderedDict()
_last_search = OrderedDict()
_gate = asyncio.Lock()
_next_request = 0.0


async def search_public_places(query: str, user_id: str):
    global _next_request
    query = query.strip()
    if not query:
        fail(422, "invalid_query", "請輸入地點名稱。")
    now = time.monotonic()
    async with _gate:
        while _last_search and next(iter(_last_search.values())) <= now - 2:
            _last_search.popitem(last=False)
        if user_id in _last_search:
            fail(429, "search_rate", "請稍候再搜尋。")
        _last_search[user_id] = now
        cached = _cache.get(query)
        if cached and cached[0] > now:
            _cache.move_to_end(query)
            return cached[1]
        if now < _next_request:
            fail(429, "search_rate", "搜尋服務忙碌，請稍候再試。")
        _next_request = now + 1

    endpoint = os.getenv("WIKI_API_URL", "https://zh.wikipedia.org/w/api.php")
    if not endpoint:
        fail(503, "search_disabled", "部署者已停用外部地點搜尋，請手動新增。")
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "0",
        "gsrlimit": "12",
        "prop": "coordinates",
        "colimit": "max",
    }
    contact = os.getenv("PUBLIC_ORIGIN", "http://localhost:3000")
    try:
        async with httpx.AsyncClient(
            timeout=4, headers={"User-Agent": f"WayToGo/1.0 ({contact})"}
        ) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
        if "error" in data:
            raise ValueError("Provider error")
        results = []
        for page in sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0)):
            coords = page.get("coordinates")
            if coords:
                results.append(
                    {
                        "name": page["title"],
                        "latitude": coords[0]["lat"],
                        "longitude": coords[0]["lon"],
                        "source": f"{endpoint.split('/w/api.php')[0]}/wiki/{quote(page['title'])}",
                    }
                )
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        fail(503, "search_unavailable", "目前無法連線至地點搜尋服務。仍可手動填寫景點。")
    _cache[query] = (now + 3600, results)
    if len(_cache) > 256:
        _cache.popitem(last=False)
    return results
