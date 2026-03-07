import requests
import math

# ─── Fórmula de Stull para temperatura de bulbo húmedo ────────────────────────
def wet_bulb(T: float, RH: float) -> float:
    return (T * math.atan(0.151977 * math.pow(RH + 8.313659, 0.5))
            + math.atan(T + RH)
            - math.atan(RH - 1.676331)
            + 0.00391838 * math.pow(RH, 1.5) * math.atan(0.023101 * RH)
            - 4.686035)

def delta_t(T: float, RH: float) -> float:
    return round(T - wet_bulb(T, RH), 1)

def application_verdict(wind: float, T: float, RH: float, precip: float) -> str:
    """Retorna 'ok' | 'caution' | 'no' para cada hora del pronóstico."""
    dT = delta_t(T, RH)
    if precip > 0:
        return 'no'
    if wind < 4 or wind > 18 or dT > 10 or T < 10:
        return 'no'
    if wind > 15 or dT > 6 or T > 30 or RH > 85:
        return 'caution'
    return 'ok'


def get_weather_data(lat: float, lon: float) -> dict:
    """Retorna clima actual + pronóstico horario de 7 días con ventanas de aplicación."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        # ── Clima actual ──────────────────────────────────────────────────────
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "dew_point_2m",
            "precipitation",
        ],
        # ── Pronóstico horario (7 días) ───────────────────────────────────────
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "precipitation",
            "precipitation_probability",
            "weather_code",
        ],
        "forecast_days": 7,
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        current = data["current"]
        units   = data["current_units"]
        hourly  = data["hourly"]

        # ── Datos actuales ────────────────────────────────────────────────────
        current_data = {
            "temperature":    current["temperature_2m"],
            "temp_unit":      units["temperature_2m"],
            "humidity":       current["relative_humidity_2m"],
            "hum_unit":       units["relative_humidity_2m"],
            "wind_speed":     current["wind_speed_10m"],
            "wind_unit":      units["wind_speed_10m"],
            "wind_direction": current["wind_direction_10m"],
            "dew_point":      current["dew_point_2m"],
            "precipitation":  current["precipitation"],
            "precip_unit":    units["precipitation"],
        }

        # ── Pronóstico por día (resumen de 7 días) ────────────────────────────
        # Agrupamos horas en días (24 horas c/u)
        n = len(hourly["time"])
        daily_forecasts = []
        for day_idx in range(7):
            start = day_idx * 24
            end   = min(start + 24, n)
            if start >= n:
                break

            hours_data = []
            for h in range(start, end):
                T   = hourly["temperature_2m"][h]
                RH  = hourly["relative_humidity_2m"][h]
                ws  = hourly["wind_speed_10m"][h]
                pp  = hourly["precipitation"][h]
                dT  = delta_t(T, RH)
                verdict = application_verdict(ws, T, RH, pp)

                hours_data.append({
                    "time":         hourly["time"][h],
                    "hour":         hourly["time"][h][11:16],   # "HH:MM"
                    "temp":         round(T, 1),
                    "humidity":     round(RH),
                    "wind":         round(ws, 1),
                    "precipitation":round(pp, 1),
                    "precip_prob":  hourly["precipitation_probability"][h] if "precipitation_probability" in hourly else 0,
                    "weather_code": hourly["weather_code"][h],
                    "delta_t":      dT,
                    "verdict":      verdict,
                })

            # Temperatura máx/mín del día
            temps = [h["temp"] for h in hours_data]
            winds = [h["wind"] for h in hours_data]
            precips = [h["precipitation"] for h in hours_data]
            # Ventanas "ok" y "caution" del día
            ok_hours     = sum(1 for h in hours_data if h["verdict"] == "ok")
            caution_hours= sum(1 for h in hours_data if h["verdict"] == "caution")
            day_verdict  = "ok" if ok_hours > 0 else ("caution" if caution_hours > 0 else "no")

            date_str = hourly["time"][start][:10]   # "YYYY-MM-DD"

            daily_forecasts.append({
                "date":          date_str,
                "temp_max":      round(max(temps), 1),
                "temp_min":      round(min(temps), 1),
                "wind_max":      round(max(winds), 1),
                "wind_avg":      round(sum(winds) / len(winds), 1),
                "precip_total":  round(sum(precips), 1),
                "ok_hours":      ok_hours,
                "caution_hours": caution_hours,
                "verdict":       day_verdict,
                "hours":         hours_data,
            })

        return {
            **current_data,
            "forecast": daily_forecasts,
        }

    except Exception as e:
        print(f"Error al obtener datos del clima: {e}")
        return None
