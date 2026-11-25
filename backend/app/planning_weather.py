import math
import os
import time
from collections import OrderedDict, deque
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

_cache = OrderedDict()
_calls = deque()


async def forecast(date, lat, lon, zone):
    empty = {"available": False, "message": "尚無可用天氣預報"}
    endpoint = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
    if not endpoint or date is None or lat is None or lon is None:
        return empty
    distance = (date - datetime.now(ZoneInfo(zone)).date()).days
    if not 0 <= distance < 16:
        return empty
    key = (endpoint, date, round(lat, 3), round(lon, 3), zone)
    now = time.monotonic()
    if key in _cache and _cache[key][0] > now:
        _cache.move_to_end(key)
        return _cache[key][1]
    while _calls and _calls[0] < now - 86400:
        _calls.popleft()
    if (
        len(_calls) >= 9900
        or (len(_calls) >= 4900 and _calls[-4900] >= now - 3600)
        or (len(_calls) >= 590 and _calls[-590] >= now - 60)
    ):
        return empty
    _calls.append(now)
    params = {
        "latitude": key[2],
        "longitude": key[3],
        "start_date": date.isoformat(),
        "end_date": date.isoformat(),
        "timezone": zone,
        "daily": "weather_code,temperature_2m_min,temperature_2m_max,precipitation_probability_max",
    }
    result = empty
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            daily = response.json()["daily"]
        if daily["time"][0] == date.isoformat():
            values = {
                field: daily[key][0]
                for field, key in [
                    ("code", "weather_code"),
                    ("min", "temperature_2m_min"),
                    ("max", "temperature_2m_max"),
                    ("rain", "precipitation_probability_max"),
                ]
            }
            if all(isinstance(v, (int, float)) and math.isfinite(v) for v in values.values()):
                result = {"available": True, **values}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
        pass
    _cache[key] = (now + (3600 if result["available"] else 60), result)
    if len(_cache) > 512:
        _cache.popitem(last=False)
    return result
