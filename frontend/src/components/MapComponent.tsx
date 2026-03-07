import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface MapComponentProps {
    geojsonData: any;
    centerLat: number;
    centerLon: number;
}

export default function MapComponent({ geojsonData, centerLat, centerLon }: MapComponentProps) {
    // Configuración de estilo de lotes
    const styleFunction = (feature: any) => {
        const gColor = feature?.properties?.Clase_Productiva === 'Muy Alta' ? '#006d2c' :
            feature?.properties?.Clase_Productiva === 'Alta' ? '#31a354' :
                feature?.properties?.Clase_Productiva === 'Media' ? '#74c476' :
                    feature?.properties?.Clase_Productiva === 'Baja' ? '#c7e9c0' : '#2E8B57';
        return {
            fillColor: gColor,
            color: '#ffffff',
            weight: 2,
            fillOpacity: 0.7
        };
    };

    const onEachFeature = (feature: any, layer: any) => {
        if (feature.properties) {
            const name = feature.properties.Lote_Name || 'Lote Desconocido';
            const area = feature.properties.Area_ha ? feature.properties.Area_ha.toFixed(2) + ' ha' : '';
            layer.bindTooltip(`<strong>${name}</strong><br/>${area}`, { sticky: true });
        }
    };

    return (
        <div style={{ height: '100%', width: '100%', borderRadius: '0.5rem', overflow: 'hidden' }}>
            <MapContainer
                center={[centerLat, centerLon]}
                zoom={13}
                style={{ height: "100%", width: "100%" }}
                scrollWheelZoom={true}
            >
                <TileLayer
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    attribution="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
                />
                {geojsonData && (
                    <GeoJSON
                        data={geojsonData}
                        style={styleFunction}
                        onEachFeature={onEachFeature}
                    />
                )}
            </MapContainer>
        </div>
    );
}
