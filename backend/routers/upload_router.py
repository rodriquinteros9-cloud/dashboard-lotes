from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import json
import datetime
import geopandas as gpd
from services.gis_service import load_spatial_data_from_bytes, calculate_metrics
from services.ee_service import get_timeseries, invalidate_cache
from services.idecor_service import fetch_soil_data_from_wfs, calculate_ip_ponderado

router = APIRouter()

def _precompute_ranking(geojson_dict: dict):
    """Pre-cómputa el ranking IDECOR en background para calentar el caché WFS."""
    try:
        features = geojson_dict.get("features", [])
        print(f"[PreCompute] Iniciando pre-cómputo de ranking IDECOR para {len(features)} lotes...")
        gdf = gpd.GeoDataFrame.from_features(features)
        gdf.set_crs(epsg=4326, inplace=True)
        # Esta llamada va a cachear el WFS en memoria (7 días TTL)
        fetch_soil_data_from_wfs(gdf)
        print("[PreCompute] Ranking IDECOR cacheado.")
    except Exception as e:
        print(f"[PreCompute] Error pre-computando ranking: {e}")


def _precompute_timeseries_for_lotes(geojson_dict: dict):
    """
    Tarea de fondo: pre-calcula la serie temporal NDVI de los últimos 6 meses
    para cada lote, llenando el caché antes de que el usuario lo solicite.
    """
    end_date   = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=180)
    features   = geojson_dict.get("features", [])

    print(f"[PreCompute] Iniciando pre-cómputo para {len(features)} lotes...")
    for i, feature in enumerate(features):
        try:
            geom = feature.get("geometry", {})
            if geom.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            name = feature.get("properties", {}).get("Lote_Name") or f"Lote_{i+1}"
            print(f"[PreCompute] [{i+1}/{len(features)}] Calculando NDVI para '{name}'...")
            get_timeseries(geom, start_date, end_date, "NDVI", use_cache=True)
        except Exception as e:
            print(f"[PreCompute] Error en lote {i}: {e}")
    print("[PreCompute] Pre-cómputo completado. Caché listo.")


@router.post("/upload-lotes")
async def upload_lotes(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Recibe un archivo KML/GeoJSON, extrae geometrias y calcula estadisticas base."""
    if not (file.filename.endswith('.kml') or file.filename.endswith('.geojson') or file.filename.endswith('.json')):
        raise HTTPException(status_code=400, detail="Formato no soportado. Use .kml o .geojson")
        
    try:
        content = await file.read()
        gdf = load_spatial_data_from_bytes(content, file.filename)
        
        if gdf is None or gdf.empty:
            raise HTTPException(status_code=400, detail="Archivo vacío o sin geometrías válidas.")
            
        area_ha, lat, lon, gdf_processed = calculate_metrics(gdf)
        
        # Convertir a GeoJSON puro para que el Frontend lo pueda mapear (Mapbox/Leaflet)
        geojson_str = gdf_processed.to_json()
        geojson_dict = json.loads(geojson_str)

        # Invalidar caché anterior (nuevo conjunto de lotes)
        invalidate_cache()
        
        # Lanzar pre-cómputo en segundo plano (no bloquea la respuesta al usuario)
        background_tasks.add_task(_precompute_timeseries_for_lotes, geojson_dict)
        background_tasks.add_task(_precompute_ranking, geojson_dict)
        
        return {
            "status": "success",
            "metadata": {
                "total_area_ha": round(area_ha, 2),
                "center_lat": lat,
                "center_lon": lon,
                "feature_count": len(gdf_processed),
                "cache_warming": True  # Indica al frontend que el caché se está calentando
            },
            "geojson": geojson_dict
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

