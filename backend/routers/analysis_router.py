from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Any
import datetime
import json
import geopandas as gpd
import pandas as pd

from services.idecor_service import fetch_soil_data_from_wfs, calculate_ip_ponderado
from services.ee_service import get_timeseries, get_benchmark_timeseries, get_cache_stats, invalidate_cache
from services.weather_service import get_weather_data

router = APIRouter()

# Modelos Pydantic para recibir peticiones JSON estructuradas
class GeometriaLote(BaseModel):
    id: str
    name: str
    coordinates: List[Any]
    area_ha: float
    center_lat: float
    center_lon: float

class RequerimientoAnalisis(BaseModel):
    lotes: List[GeometriaLote]
    fecha_inicio: datetime.date
    fecha_fin: datetime.date
    indice: str = "NDVI"
    force_refresh: bool = False   # Si True, ignora el caché y recalcula en EE


@router.post("/ranking")
async def generar_ranking(lotes: List[GeometriaLote]):
    """Cruza los lotes directamente con IDECOR para generar el Índice Productivo."""
    try:
        # Reconstruir un GeoDataFrame a partir de los datos recibidos
        features = []
        for lote in lotes:
            polygon = {"type": "Polygon", "coordinates": lote.coordinates}
            features.append({
                "type": "Feature",
                "geometry": polygon,
                "properties": {
                    "temp_id": lote.id,
                    "Lote_Name": lote.name,
                    "Area_ha": lote.area_ha,
                    "centroide_lat": lote.center_lat,
                    "centroide_lon": lote.center_lon
                }
            })
            
        gdf_lotes = gpd.GeoDataFrame.from_features(features)
        gdf_lotes.set_crs(epsg=4326, inplace=True)
        
        # Consultar Suelos WFS
        gdf_suelos = fetch_soil_data_from_wfs(gdf_lotes)
        if gdf_suelos is None or gdf_suelos.empty:
            return {"status": "warning", "msg": "No hay datos de suelo en esta ubicación", "ranking": []}
            
        # Cruzar para obtener el IP
        gdf_procesado, procesado = calculate_ip_ponderado(gdf_lotes, gdf_suelos, ip_col='ip', clase_col='cap')
        
        # Preparar respuesta base JSON
        ranking_data = []
        for idx, row in gdf_procesado.iterrows():
            ip_val = row.get('Index_Ponderado', 0)
            clase = "Desconocida"
            if ip_val > 80: clase = "Muy Alta"
            elif ip_val > 60: clase = "Alta"
            elif ip_val > 40: clase = "Media"
            elif ip_val > 0: clase = "Baja"
            else: clase = "Sin Dato"
            
            ranking_data.append({
                "id": row.get('temp_id'),
                "name": row.get('Lote_Name', f"Lote {idx}"),
                "area_ha": row.get('Area_ha', 0),
                "ip_ponderado": ip_val if not pd.isna(ip_val) else 0,
                "clase_productiva": clase
            })
            
        ranking_data = sorted(ranking_data, key=lambda i: i['ip_ponderado'], reverse=True)
        
        return {"status": "success", "ranking": ranking_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/timeseries/individual")
async def calcular_serie_individual(req: RequerimientoAnalisis):
    """Calcula NDVI/EVI en serie temporal por Earth Engine para un lote especifico"""
    try:
        if not req.lotes:
             return {"status": "error", "message": "No enviaron geometria."}
             
        lote = req.lotes[0]
        # Crear dic tipo geojson
        geojson_poly = {"type": "Polygon", "coordinates": lote.coordinates}
        
        # Extraer a DataFrame
        df = get_timeseries(geojson_poly, req.fecha_inicio, req.fecha_fin, req.indice,
                            use_cache=not req.force_refresh)
        if df.empty:
            return {"status": "success", "data": []}
            
        # Convertir timestamps a string
        df['Fecha'] = df['Fecha'].dt.strftime('%Y-%m-%d')
        
        return {"status": "success", "data": df.to_dict(orient="records")}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@router.post("/timeseries/benchmark")
async def calcular_serie_benchmark(req: RequerimientoAnalisis):
    """Calcula NDVI en masa para comparar Lotes cruzados y un Promedio General"""
    try:
        if not req.lotes: return {"data": []}
        
        features = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": l.coordinates}, "properties": {"temp_id": l.id, "Lote_Name": l.name}} for l in req.lotes]
        gdf_lotes = gpd.GeoDataFrame.from_features(features)
        gdf_lotes.set_crs(epsg=4326, inplace=True)
        
        # Se bloquea sincrónicamente hasta que Earth Engine devuelva
        df_bench = get_benchmark_timeseries(gdf_lotes, req.fecha_inicio, req.fecha_fin, req.indice)
        
        if df_bench is None or df_bench.empty:
            return {"status": "success", "data": []}
            
        df_bench = df_bench.reset_index()
        if 'Fecha' in df_bench.columns:
            df_bench['Fecha'] = pd.to_datetime(df_bench['Fecha']).dt.strftime('%Y-%m-%d')
            
        df_bench = df_bench.fillna(0) # EE puede tener nulls en nubes severas
        
        return {"status": "success", "data": df_bench.to_dict(orient="records")}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/weather")
async def obtener_clima(lat: float, lon: float):
    weather = get_weather_data(lat, lon)
    if not weather:
        raise HTTPException(status_code=503, detail="Fallo petición a Open-Meteo")
    return weather

# ─── Endpoints de gestión de caché ─────────────────────────────────────────
@router.get("/timeseries/cache")
def cache_status():
    """Devuelve el estado actual del caché en memoria."""
    return {"status": "ok", **get_cache_stats()}

@router.delete("/timeseries/cache")
def clear_cache():
    """Invalida todo el caché de series temporales."""
    invalidate_cache()
    return {"status": "ok", "message": "Caché vaciado correctamente."}
