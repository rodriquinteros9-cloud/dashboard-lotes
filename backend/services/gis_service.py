import geopandas as gpd
from shapely.geometry import shape

def load_spatial_data_from_bytes(file_bytes: bytes, filename: str) -> gpd.GeoDataFrame:
    """Lee y procesa archivos espaciales (KML/GeoJSON) desde bytes y retorna un GeoDataFrame unificado."""
    import tempfile
    import os
    import pyogrio
    
    # pyogrio/osgeo suelen requerir archivos físicos o VSI, usaremos tempfile por simplicidad de la API
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
        
    try:
        # Configurar variable de entorno requerida por el driver KML libkml
        os.environ['OGR_SKIP'] = 'KML'
        
        gdf = pyogrio.read_dataframe(tmp_path)
        
        # Eliminar las dimensiones Z si existen (3D a 2D)
        if gdf.has_z.any():
            from shapely import force_2d
            gdf.geometry = force_2d(gdf.geometry)
            
        return gdf
    except Exception as e:
        raise ValueError(f"Error procesando {filename}: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def calculate_metrics(gdf: gpd.GeoDataFrame):
    """Calcula area (ha) y obtiene el centroide general y por lote."""
    if gdf is None or gdf.empty:
        raise ValueError("GeoDataFrame vacío")

    # Reproyectar a web mercator (metros) para calcular área
    gdf_proj = gdf.to_crs(epsg=3857)
    
    # Calcular área en hectáreas y sumarla
    gdf_proj['Area_ha'] = gdf_proj.geometry.area / 10000
    total_area = gdf_proj['Area_ha'].sum()
    
    # Devolver al CRS original (WGS84 EPSG:4326)
    gdf_final = gdf_proj.to_crs(epsg=4326)
    
    # Calcular centroides individuales (en WGS84 para visualización)
    centroides = gdf_final.geometry.centroid
    gdf_final['centroide_lat'] = centroides.y
    gdf_final['centroide_lon'] = centroides.x
    
    # Si hay columna 'Name', la unificamos a 'Lote_Name'
    if 'Name' in gdf_final.columns:
        gdf_final['Lote_Name'] = gdf_final['Name']
        
    # Calcular centroide global de todo el bloque
    punto_central = gdf_final.geometry.unary_union.centroid
    
    return total_area, punto_central.y, punto_central.x, gdf_final
