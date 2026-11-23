"""Miaoli County weather app powered by Taiwan's CWA Open Data API."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from flask import Flask, render_template, request

app = Flask(__name__)

CWA_API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-015"
CACHE_TTL_SECONDS = 10 * 60
REQUEST_TIMEOUT_SECONDS = 8
TAIPEI = ZoneInfo("Asia/Taipei")

# CWA forecast location names are the same as the township/city names below.
TOWNS: dict[str, dict[str, str]] = {
    "miaoli": {"name": "苗栗市"},
    "toufen": {"name": "頭份市"},
    "zhunan": {"name": "竹南鎮"},
    "houlong": {"name": "後龍鎮"},
    "tongxiao": {"name": "通霄鎮"},
    "yuanli": {"name": "苑裡鎮"},
    "zhuolan": {"name": "卓蘭鎮"},
    "zaoqiao": {"name": "造橋鄉"},
    "xihu": {"name": "西湖鄉"},
    "touya": {"name": "頭屋鄉"},
    "gongguan": {"name": "公館鄉"},
    "tongluo": {"name": "銅鑼鄉"},
    "sanyi": {"name": "三義鄉"},
    "dahu": {"name": "大湖鄉"},
    "shitan": {"name": "獅潭鄉"},
    "sanwan": {"name": "三灣鄉"},
    "nanzhuang": {"name": "南庄鄉"},
    "taian": {"name": "泰安鄉"},
}

# Keep names flexible in case the CWA API changes its display language.
ELEMENT_NAMES = {
    "weather": ("天氣現象", "Wx", "Weather"),
    "temperature": ("溫度", "T", "Temperature"),
    "feels_like": ("體感溫度", "AT", "ApparentTemperature"),
    "humidity": ("相對濕度", "RH", "RelativeHumidity"),
    "wind": ("風速", "WindSpeed"),
    "rain": ("12小時降雨機率", "降雨機率", "PoP", "ProbabilityOfPrecipitation"),
    "high": ("最高溫度", "MaxT", "MaxTemperature"),
    "low": ("最低溫度", "MinT", "MinTemperature"),
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


class WeatherDataError(Exception):
    """Raised when CWA data cannot be fetched or interpreted."""


def _parse_number(value: Any) -> float | None:
    if value is None or value in ("", "-", "--", "無資料"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_number(value: float | None) -> int | float | None:
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _weather_symbol(description: str) -> str:
    if "雷" in description:
        return "ϟ"
    if "雪" in description:
        return "❄"
    if any(word in description for word in ("雨", "陣雨", "毛毛雨")):
        return "☂"
    if "晴" in description:
        return "☀" if "多雲" not in description else "⛅"
    if "雲" in description:
        return "⛅" if "晴" in description else "☁"
    if "霧" in description:
        return "☁"
    return "☼"


def _weather_elements(location: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for item in location.get("weatherElement", []):
        name = item.get("elementName")
        for key, aliases in ELEMENT_NAMES.items():
            if name in aliases:
                found[key] = item.get("time", [])
                break
    return found


def _period_value(periods: list[dict[str, Any]], now: datetime) -> tuple[float | None, str | None, datetime | None]:
    parsed: list[tuple[datetime, datetime, float | None, str | None]] = []
    for period in periods:
        try:
            start = datetime.fromisoformat(period["startTime"])
            end = datetime.fromisoformat(period["endTime"])
        except (KeyError, TypeError, ValueError):
            continue
        values = period.get("elementValue", [])
        raw = values[0].get("value") if values and isinstance(values[0], dict) else None
        parsed.append((start, end, _parse_number(raw), str(raw) if raw not in (None, "-") else None))
    if not parsed:
        return None, None, None
    active = next((item for item in parsed if item[0] <= now < item[1]), None)
    if active is None:
        active = next((item for item in parsed if item[0] >= now), parsed[0])
    return active[2], active[3], active[0]


def _forecast_days(elements: dict[str, list[dict[str, Any]]], now: datetime) -> list[dict[str, Any]]:
    # The 7-day CWA product is published in 12-hour intervals. Group those
    # intervals by their start date to show an easy-to-read daily summary.
    by_date: dict[str, list[datetime]] = {}
    for period in elements.get("high", []) + elements.get("weather", []):
        try:
            start = datetime.fromisoformat(period["startTime"])
        except (KeyError, TypeError, ValueError):
            continue
        if start.date() >= now.date():
            by_date.setdefault(start.date().isoformat(), []).append(start)
    dates = sorted(by_date)[:5]

    def daily_values(key: str, day: str) -> list[float]:
        values = []
        for period in elements.get(key, []):
            try:
                period_day = datetime.fromisoformat(period["startTime"]).date().isoformat()
            except (KeyError, TypeError, ValueError):
                continue
            if period_day == day:
                raw_values = period.get("elementValue", [])
                value = _parse_number(raw_values[0].get("value")) if raw_values else None
                if value is not None:
                    values.append(value)
        return values

    result = []
    for day in dates:
        description = "天氣資料待更新"
        # Prefer the daytime description; use the first available interval otherwise.
        weather_periods = elements.get("weather", [])
        day_periods = []
        for period in weather_periods:
            try:
                start = datetime.fromisoformat(period["startTime"])
            except (KeyError, TypeError, ValueError):
                continue
            if start.date().isoformat() == day:
                values = period.get("elementValue", [])
                value = str(values[0].get("value", "")) if values else ""
                day_periods.append((start, value))
        if day_periods:
            daytime = next((item for item in day_periods if 6 <= item[0].hour < 18), day_periods[0])
            description = daytime[1] or description

        highs = daily_values("high", day)
        lows = daily_values("low", day)
        rains = daily_values("rain", day)
        date_value = datetime.fromisoformat(day).date()
        result.append({
            "date": date_value.strftime("%m/%d"),
            "weekday": ("一", "二", "三", "四", "五", "六", "日")[date_value.weekday()],
            "description": description,
            "symbol": _weather_symbol(description),
            "high": _display_number(max(highs)) if highs else None,
            "low": _display_number(min(lows)) if lows else None,
            "rain": _display_number(max(rains)) if rains else None,
        })
    if len(result) < 5:
        raise ValueError("CWA response does not include five forecast days")
    return result


def _fetch_weather(town_id: str) -> dict[str, Any]:
    now_monotonic = time.monotonic()
    with _cache_lock:
        cached = _cache.get(town_id)
        if cached and now_monotonic - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    api_key = os.getenv("CWA_API_KEY", "").strip()
    if not api_key:
        raise WeatherDataError("請先設定中央氣象署 API 授權碼（環境變數 CWA_API_KEY），即可查詢天氣資料。")

    now = datetime.now(TAIPEI)
    params = {
        "Authorization": api_key,
        "format": "JSON",
        "LocationName": TOWNS[town_id]["name"],
        "ElementName": ",".join(name for aliases in ELEMENT_NAMES.values() for name in aliases[:1]),
    }
    try:
        response = requests.get(CWA_API_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        locations = payload.get("records", {}).get("locations", [])
        location = next(
            item for group in locations for item in group.get("location", [])
            if item.get("locationName") == TOWNS[town_id]["name"]
        )
        elements = _weather_elements(location)
        if "weather" not in elements or "high" not in elements or "low" not in elements:
            raise ValueError("CWA response is missing forecast elements")

        temperature, _, current_start = _period_value(elements.get("temperature", []), now)
        feels_like, _, _ = _period_value(elements.get("feels_like", []), now)
        humidity, _, _ = _period_value(elements.get("humidity", []), now)
        wind, _, _ = _period_value(elements.get("wind", []), now)
        _, description, _ = _period_value(elements.get("weather", []), now)
        if not description:
            description = "天氣資料待更新"
        result = {
            "current": {
                "temperature": _display_number(temperature),
                "feels_like": _display_number(feels_like),
                "humidity": _display_number(humidity),
                "wind": _display_number(wind),
                "description": description,
                "symbol": _weather_symbol(description),
            },
            "forecast": _forecast_days(elements, now),
            "updated": current_start.isoformat(timespec="minutes") if current_start else None,
            "source_note": "中央氣象署鄉鎮預報",
        }
    except (requests.RequestException, ValueError, TypeError, KeyError, StopIteration, IndexError) as exc:
        raise WeatherDataError("目前無法取得中央氣象署天氣資料，請檢查授權碼或稍後再試。") from exc

    with _cache_lock:
        _cache[town_id] = (time.monotonic(), result)
    return result


@app.get("/")
def index():
    town_id = request.args.get("town", "miaoli")
    if town_id not in TOWNS:
        town_id = "miaoli"
    town = TOWNS[town_id]
    weather = None
    error = None
    try:
        weather = _fetch_weather(town_id)
    except WeatherDataError as exc:
        error = str(exc)
    return render_template("index.html", towns=TOWNS, town_id=town_id, town=town, weather=weather, error=error)


if __name__ == "__main__":
    app.run(debug=False)
