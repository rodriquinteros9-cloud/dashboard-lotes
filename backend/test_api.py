import requests
import json
import datetime

url = "http://127.0.0.1:8000/api/timeseries/benchmark"
payload = {
    "lotes": [
        {
            "id": "lote_0",
            "name": "Lote 1",
            "coordinates": [[[-63.25, -31.68], [-63.24, -31.68], [-63.24, -31.67], [-63.25, -31.67], [-63.25, -31.68]]],
            "area_ha": 10.5,
            "center_lat": -31.675,
            "center_lon": -63.245
        }
    ],
    "fecha_inicio": (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
    "fecha_fin": datetime.date.today().strftime("%Y-%m-%d"),
    "indice": "NDVI"
}

resp = requests.post(url, json=payload)
print(resp.status_code)
data = resp.json()
print(json.dumps(data, indent=2))
