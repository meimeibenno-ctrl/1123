"""Miaoli County weather app powered by Open-Meteo."""

from __future__ import annotations

import threading
import time
from datetime import date
from typing import Any

import requests
from flask import Flask, render_template, request

app = Flask(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_SECONDS = 10 * 60
REQUEST_TIMEOUT_SECONDS = 8

# Coordinates are representative points in each township/city.
TOWNS: dict[str, dict[str, float | str]] = {
    "miaoli": {"name": "苗栗市", "latitude": 24.5602, "longitude": 120.8214},
    "toufen": {"name": "頭份市", "latitude": 24.6847, "longitude": 120.9074},
    "zhunan": {"name": "竹南鎮", "latitude": 24.6850, "longitude": 120.8788},
    "houlong": {"name": "後龍鎮", "latitude": 24.6126, "longitude": 120.7867},
    "tongxiao": {"name": "通霄鎮", "latitude": 24.4891, "longitude": 120.6780},
    "yuanli": {"name": "苑裡鎮", "latitude": 24.4417, "longitude": 120.6519},
    "zhuolan": {"name": "卓蘭鎮", "latitude": 24.3094, "longitude": 120.8245},
    "zaoqiao": {"name": "造橋鄉", "latitude": 24.6372, "longitude": 120.8628},
    "xihu": {"name": "西湖鄉", "latitude": 24.5568, "longitude": 120.7591},
    "touya": {"name": "頭屋鄉", "latitude": 24.5736, "longitude": 120.8468},
    "gongguan": {"name": "公館鄉", "latitude": 24.5000, "longitude": 120.8223},
    "tongluo": {"name": "銅鑼鄉", "latitude": 24.4869, "longitude": 120.7866},
    "sanyi": {"name": "三義鄉", "latitude": 24.3503, "longitude": 120.7670},
    "dahu": {"name": "大湖鄉", "latitude": 24.4224, "longitude": 120.8635},
    "shitan": {"name": "獅潭鄉", "latitude": 24.5393, "longitude": 120.9217},
    "sanwan": {"name": "三灣鄉", "latitude": 24.6522, "longitude": 120.9516},
    "nanzhuang": {"name": "南庄鄉", "latitude": 24.5962, "longitude": 120.9997},
    "taian": {"name": "泰安鄉", "latitude": 24.4422, "longitude": 120.9043},
}

WEATHER_CODES = {
    0: "晴朗", 1: "大致晴朗", 2: "局部多雲", 3: "陰天",
    45: "有霧", 48: "霧凇",
    51: "毛毛雨", 53: "中度毛毛雨", 55: "濃毛毛雨",
    56: "凍毛毛雨", 57: "濃凍毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "凍雨", 67: "強凍雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "短暫陣雨", 81: "中度陣雨", 82: "強陣雨",
    85: "短暫陣雪", 86: "強陣雪",
    95: "雷雨", 96: "雷雨伴隨冰雹", 99: "強雷雨伴隨冰雹",
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


class WeatherDataError(Exception):
    """Raised when Open-Meteo data cannot be fetched or interpreted."""


def weather_description(code: int) -> str:
    return WEATHER_CODES.get(code, "天氣狀況未知")


def _number(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _fetch_weather(town_id: str) -> dict[str, Any]:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(town_id)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    town = TOWNS[town_id]
    params = {
        "latitude": town["latitude"],
        "longitude": town["longitude"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 5,
        "timezone": "Asia/Taipei",
    }
    try:
        response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        current = payload["current"]
        daily = payload["daily"]
        required_current = ("temperature_2m", "apparent_temperature", "relative_humidity_2m", "wind_speed_10m", "weather_code")
        required_daily = ("time", "weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max")
        if any(key not in current for key in required_current) or any(key not in daily for key in required_daily):
            raise ValueError("API response is missing required fields")

        forecast = []
        for index, day in enumerate(daily["time"][:5]):
            forecast.append({
                "date": date.fromisoformat(day).strftime("%m/%d"),
                "weekday": ("一", "二", "三", "四", "五", "六", "日")[date.fromisoformat(day).weekday()],
                "code": daily["weather_code"][index],
                "description": weather_description(int(daily["weather_code"][index])),
                "high": _number(daily["temperature_2m_max"][index]),
                "low": _number(daily["temperature_2m_min"][index]),
                "rain": _number(daily["precipitation_probability_max"][index]),
            })
        if len(forecast) != 5:
            raise ValueError("API response does not include five forecast days")

        result = {
            "current": {
                "temperature": _number(current["temperature_2m"]),
                "feels_like": _number(current["apparent_temperature"]),
                "humidity": _number(current["relative_humidity_2m"]),
                "wind": _number(current["wind_speed_10m"]),
                "code": int(current["weather_code"]),
                "description": weather_description(int(current["weather_code"])),
            },
            "forecast": forecast,
            "updated": current.get("time"),
        }
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError) as exc:
        raise WeatherDataError("目前無法取得最新天氣資料，請稍後再試。") from exc

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
