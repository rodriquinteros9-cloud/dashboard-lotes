import requests
import geopandas as gpd
import hashlib
import datetime
from typing import Optional

# ─── Caché en memoria para datos de suelo WFS ────────────────────────────────
# Los datos de suelo IDECOR se actualizan muy raramente → TTL 7 días
_wfs_cache: dict = {}
_WFS_TTL_SECONDS = 7 * 24 * 3600   # 7 días

def _wfs_cache_key(minx, miny, maxx, maxy) -> str:
    """Clave basada en bbox redondeado a 4 decimales."""
    raw = f"{round(minx,4)},{round(miny,4)},{round(maxx,4)},{round(maxy,4)}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_wfs_cache(key: str) -> Optional[gpd.GeoDataFrame]:
    entry = _wfs_cache.get(key)
    if entry and datetime.datetime.utcnow() < entry["expires"]:
        return entry["data"]
    return None

def _save_wfs_cache(key: str, gdf: gpd.GeoDataFrame):
    _wfs_cache[key] = {
        "data": gdf,
        "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=_WFS_TTL_SECONDS)
    }

def invalidate_wfs_cache():
    _wfs_cache.clear()
# ─────────────────────────────────────────────────────────────────────────────

def fetch_soil_data_from_wfs(gdf_lotes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Obtiene datos de suelo desde IDECOR (Mapas Córdoba) usando WFS basado en el BBOX.
    Los resultados se cachean 7 días para evitar llamadas repetidas al WFS externo.
    """
    try:
        if gdf_lotes is None or gdf_lotes.empty:
            return None
            
        if gdf_lotes.crs is None or gdf_lotes.crs.to_epsg() != 4326:
            gdf_bounds = gdf_lotes.to_crs(epsg=4326)
        else:
            gdf_bounds = gdf_lotes
            
        bounds = gdf_bounds.total_bounds
        
        buffer_deg = 0.01
        minx, miny, maxx, maxy = (bounds[0]-buffer_deg, bounds[1]-buffer_deg,
                                   bounds[2]+buffer_deg, bounds[3]+buffer_deg)

        # ── Verificar caché ──────────────────────────────────────────────────
        key = _wfs_cache_key(minx, miny, maxx, maxy)
        cached = _get_wfs_cache(key)
        if cached is not None:
            print(f"[WFS Cache] HIT — bbox key={key[:8]}")
            return cached
        print(f"[WFS Cache] MISS — consultando IDECOR WFS (key={key[:8]})")
        # ────────────────────────────────────────────────────────────────────

        url = 'https://idecor-ws.mapascordoba.gob.ar/geoserver/idecor/wfs'
        params = {
            'service': 'WFS',
            'version': '2.0.0',
            'request': 'GetFeature',
            'typeName': 'idecor:cartas_suelo_unidas_2025_ip',
            'outputFormat': 'application/json',
            'bbox': f'{minx},{miny},{maxx},{maxy},EPSG:4326',
        }
        
        response = requests.get(url, params=params, timeout=45)
        response.raise_for_status()
        
        data = response.json()
        if not data.get('features'):
            return None
            
        gdf_suelos = gpd.GeoDataFrame.from_features(data["features"])
        gdf_suelos.set_crs(epsg=4326, inplace=True)

        # ── Guardar en caché ────────────────────────────────────────────────
        _save_wfs_cache(key, gdf_suelos)
        print(f"[WFS Cache] GUARDADO key={key[:8]} ({len(gdf_suelos)} features)")
        # ────────────────────────────────────────────────────────────────────
        
        return gdf_suelos
    except Exception as e:
        print(f"Error consultando API de Suelos IDECOR: {e}")
        return None


def calculate_ip_ponderado(gdf_lotes: gpd.GeoDataFrame, gdf_suelos: gpd.GeoDataFrame, ip_col: str, clase_col: str):
    """Calcula el IP Ponderado y la Clase Productiva predominante para cada lote."""
    if gdf_suelos is None or gdf_suelos.empty:
      return gdf_lotes, False

    try:
        crs_objetivo = 3857
        original_crs = gdf_lotes.crs
        
        gdf_lotes_proj = gdf_lotes.to_crs(epsg=crs_objetivo)
        if gdf_suelos.crs is None:
            gdf_suelos.set_crs(epsg=4326, inplace=True)
        gdf_suelos_proj = gdf_suelos.to_crs(epsg=crs_objetivo)
        
        gdf_lotes_proj['geometry'] = gdf_lotes_proj.geometry.buffer(0)
        gdf_suelos_proj['geometry'] = gdf_suelos_proj.geometry.buffer(0).simplify(10)
        
        interseccion = gpd.overlay(gdf_lotes_proj, gdf_suelos_proj, how='intersection')
        if interseccion.empty:
          return gdf_lotes, False

        interseccion['Area_suelo'] = interseccion.geometry.area
        
        if ip_col and ip_col != "Auto-Detectar":
            interseccion[ip_col] = interseccion[ip_col].fillna(0).astype(float)
            interseccion['IP_Area'] = interseccion[ip_col] * interseccion['Area_suelo']
            
            resumen_lote = interseccion.groupby('temp_id').agg({
                'Area_suelo': 'sum',
                'IP_Area': 'sum'
            }).reset_index()
            
            resumen_lote['Index_Ponderado'] = resumen_lote['IP_Area'] / resumen_lote['Area_suelo']
            resumen_lote['Index_Ponderado'] = resumen_lote['Index_Ponderado'].round(2)
            
            gdf_lotes_proj = gdf_lotes_proj.merge(
                resumen_lote[['temp_id', 'Index_Ponderado']], on='temp_id', how='left'
            )
        
        gdf_final = gdf_lotes_proj.to_crs(original_crs)
        return gdf_final, True
    except Exception as e:
        print(f"Error procesando el corte espacial con suelo: {str(e)}") 
        import traceback
        traceback.print_exc()
        return gdf_lotes, False
