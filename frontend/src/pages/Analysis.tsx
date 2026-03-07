import React, { useState, useEffect } from 'react';
import type { AppState } from '../App';
import { Map, Wind, Droplets, Thermometer, Loader2, Info, Calendar, Activity, TrendingUp, Zap, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import PhytosanitaryAdvisor from '../components/PhytosanitaryAdvisor';
import WeeklyForecast from '../components/WeeklyForecast';

export default function Analysis({ appState, setAppState }: { appState: AppState, setAppState: any }) {
    const features = appState.spatialData?.features || [];

    const lotes = React.useMemo(() => {
        return features.map((f: any, i: number) => ({
            id: f.properties.temp_id || `lote_${i}`,
            name: f.properties.Lote_Name || `Lote ${i + 1}`,
            area_ha: f.properties.Area_ha || 0,
            center_lat: f.properties.centroide_lat || 0,
            center_lon: f.properties.centroide_lon || 0,
            coordinates: f.geometry.coordinates
        }));
    }, [features]);

    const [selectedLotId, setSelectedLotId] = useState<string>("");

    // Loading / error — always local (reset naturally on lot change)
    const [loadingWeather, setLoadingWeather] = useState(false);
    const [weatherError, setWeatherError] = useState("");
    const [loadingTimeSeries, setLoadingTimeSeries] = useState(false);
    const [timeSeriesError, setTimeSeriesError] = useState("");
    const [fromCache, setFromCache] = useState<boolean | null>(null);

    const [startDate, setStartDate] = useState<string>(() => {
        const d = new Date();
        d.setMonth(d.getMonth() - 6);
        return d.toISOString().split('T')[0];
    });
    const [endDate, setEndDate] = useState<string>(() => new Date().toISOString().split('T')[0]);

    // Derived values — computed every render (no stale closure risk)
    const activeLotId = selectedLotId || (lotes.length > 0 ? lotes[0].id : "");
    const selectedLot = lotes.find((l: any) => l.id === activeLotId);
    const tsCacheKey = `${activeLotId}|${startDate}|${endDate}`;

    // ── Simple local state for data ──────────────────────────────────────────
    const [weatherData, setWeatherDataLocal] = useState<any>(null);
    const [timeSeriesData, setTimeSeriesDataLocal] = useState<any[]>([]);

    // ── Write-through helpers: update local + global cache atomically ─────────
    const setWeatherData = (data: any) => {
        setWeatherDataLocal(data);
        setAppState((prev: AppState) => ({
            ...prev,
            moduleCache: {
                ...prev.moduleCache,
                weatherData: { ...(prev.moduleCache?.weatherData || {}), [activeLotId]: data }
            }
        }));
    };

    const setTimeSeriesData = (data: any[]) => {
        setTimeSeriesDataLocal(data);
        setAppState((prev: AppState) => ({
            ...prev,
            moduleCache: {
                ...prev.moduleCache,
                analysisTimeSeries: { ...(prev.moduleCache?.analysisTimeSeries || {}), [tsCacheKey]: data }
            }
        }));
    };

    // ── Sync weather: restore from cache or fetch fresh ──────────────────────
    useEffect(() => {
        if (!activeLotId) return;

        const cached = appState.moduleCache?.weatherData?.[activeLotId];
        if (cached) {
            setWeatherDataLocal(cached);
            return;
        }

        setWeatherDataLocal(null);
        if (!selectedLot) return;

        const fetchWeather = async () => {
            setLoadingWeather(true);
            setWeatherError("");
            try {
                const resp = await fetch(
                    `http://127.0.0.1:8000/api/weather?lat=${selectedLot.center_lat}&lon=${selectedLot.center_lon}`
                );
                if (!resp.ok) throw new Error("Error al obtener clima");
                const data = await resp.json();
                setWeatherData(data);
            } catch (err: any) {
                setWeatherError(err.message);
            } finally {
                setLoadingWeather(false);
            }
        };
        fetchWeather();
    }, [activeLotId]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Sync timeseries: restore from cache when lot/dates change ─────────────
    useEffect(() => {
        const cached = appState.moduleCache?.analysisTimeSeries?.[tsCacheKey];
        if (cached && cached.length > 0) {
            setTimeSeriesDataLocal(cached);
            setFromCache(true);
        } else {
            setTimeSeriesDataLocal([]);
            setFromCache(null);
        }
    }, [tsCacheKey]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Fetch Time Series — forceRefresh bypasses the backend cache ───────────
    const fetchTimeSeries = async (forceRefresh = false) => {
        if (!selectedLot) return;
        setLoadingTimeSeries(true);
        setTimeSeriesError("");
        setTimeSeriesDataLocal([]);
        setFromCache(null);

        const t0 = performance.now();
        try {
            const payload = {
                lotes: [{
                    id: selectedLot.id,
                    name: selectedLot.name,
                    coordinates: selectedLot.coordinates,
                    area_ha: selectedLot.area_ha,
                    center_lat: selectedLot.center_lat,
                    center_lon: selectedLot.center_lon
                }],
                fecha_inicio: startDate,
                fecha_fin: endDate,
                indice: "NDVI",
                force_refresh: forceRefresh
            };

            const resp = await fetch(`http://127.0.0.1:8000/api/timeseries/individual`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!resp.ok) throw new Error("Error al calcular serie temporal");
            const result = await resp.json();
            if (result.status === 'success') {
                setTimeSeriesData(result.data); // writes to moduleCache too
                const elapsed = performance.now() - t0;
                setFromCache(elapsed < 500);
            } else {
                throw new Error(result.message || "Error desconocido");
            }
        } catch (err: any) {
            setTimeSeriesError(err.message);
        } finally {
            setLoadingTimeSeries(false);
        }
    };

    // Custom tooltip for recharts
    const CustomTooltip = ({ active, payload, label }: any) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-white p-3 border border-gray-200 shadow-md rounded-lg text-sm">
                    <p className="font-bold text-gray-700 mb-2">{label}</p>
                    {payload.map((entry: any, index: number) => (
                        <p key={index} style={{ color: entry.color }} className="flex justify-between gap-4">
                            <span>{entry.name}:</span>
                            <span className="font-semibold">{entry.value.toFixed(2)}</span>
                        </p>
                    ))}
                </div>
            );
        }
        return null;
    };

    return (
        <div className="flex flex-col gap-6 h-full overflow-y-auto pb-8">
            <div>
                <h1 className="text-2xl font-bold" style={{ color: 'var(--color-text)' }}>Análisis Individual</h1>
                <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>Evolución temporal de vigor y parámetros del lote seleccionado.</p>
            </div>

            {/* Selector de Lote */}
            <div className="agro-card p-5">
                <label className="block text-xs font-semibold mb-2 flex items-center gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                    <Map size={13} /> Seleccioná un Lote
                </label>
                <select
                    value={activeLotId}
                    onChange={(e) => setSelectedLotId(e.target.value)}
                    className="w-full text-sm rounded-lg px-3 py-2.5 outline-none transition font-medium"
                    style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                >
                    {lotes.map((lote: any) => (
                        <option key={lote.id} value={lote.id}>{lote.name}</option>
                    ))}
                </select>
                {lotes.length === 0 && (
                    <p className="text-xs mt-2 flex items-center gap-1" style={{ color: '#B08000' }}>
                        <Info size={12} /> No hay lotes cargados. Subí un KML en el inicio.
                    </p>
                )}
            </div>

            {selectedLot && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Superficie */}
                        <div className="agro-card p-6 flex flex-col items-center justify-center text-center">
                            <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--color-muted)' }}>Superficie del Lote</p>
                            <div className="text-5xl font-extrabold mb-1" style={{ color: 'var(--color-primary)' }}>
                                {selectedLot.area_ha.toFixed(2)}
                                <span className="text-2xl font-medium ml-1" style={{ color: 'var(--color-muted)' }}>ha</span>
                            </div>
                            <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>Área total del polígono</p>
                        </div>

                        {/* Clima */}
                        <div className="agro-card p-6 flex flex-col justify-center">
                            <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: 'var(--color-muted)' }}>Condiciones Climáticas Actuales</p>

                            {loadingWeather ? (
                                <div className="flex flex-col items-center justify-center py-4">
                                    <Loader2 className="animate-spin mb-2" size={24} style={{ color: 'var(--color-primary)' }} />
                                    <span className="text-xs" style={{ color: 'var(--color-muted)' }}>Cargando clima…</span>
                                </div>
                            ) : weatherError ? (
                                <div className="text-sm p-3 rounded-lg" style={{ background: '#FFF0F0', color: '#B71C1C' }}>{weatherError}</div>
                            ) : weatherData ? (
                                <div className="grid grid-cols-3 gap-3">
                                    <div className="flex flex-col items-center p-3 rounded-xl" style={{ background: 'rgba(212,168,67,0.08)', border: '1px solid rgba(212,168,67,0.2)' }}>
                                        <Thermometer size={20} className="mb-1.5" style={{ color: '#D4A843' }} />
                                        <span className="text-lg font-bold" style={{ color: 'var(--color-text)' }}>{weatherData.temperature}°C</span>
                                        <span className="text-[10px] font-semibold uppercase" style={{ color: '#B08000' }}>Temp</span>
                                    </div>
                                    <div className="flex flex-col items-center p-3 rounded-xl" style={{ background: 'rgba(74,144,184,0.08)', border: '1px solid rgba(74,144,184,0.2)' }}>
                                        <Droplets size={20} className="mb-1.5" style={{ color: '#4A90B8' }} />
                                        <span className="text-lg font-bold" style={{ color: 'var(--color-text)' }}>{weatherData.humidity}%</span>
                                        <span className="text-[10px] font-semibold uppercase" style={{ color: '#2A6B8A' }}>Humedad</span>
                                    </div>
                                    <div className="flex flex-col items-center p-3 rounded-xl" style={{ background: 'rgba(45,106,79,0.07)', border: '1px solid rgba(45,106,79,0.15)' }}>
                                        <Wind size={20} className="mb-1.5" style={{ color: 'var(--color-primary)' }} />
                                        <span className="text-lg font-bold" style={{ color: 'var(--color-text)' }}>{weatherData.wind_speed}</span>
                                        <span className="text-[10px] font-semibold uppercase" style={{ color: 'var(--color-primary)' }}>{weatherData.wind_unit || 'km/h'}</span>
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    </div>

                    {/* Panel de aptitud ACTUAL para fitosanitarios */}
                    {weatherData && (
                        <PhytosanitaryAdvisor weatherData={weatherData} />
                    )}

                    {/* Pronóstico 7 días con ventanas de aplicación */}
                    {weatherData?.forecast && weatherData.forecast.length > 0 && (
                        <WeeklyForecast forecast={weatherData.forecast} />
                    )}

                    {/* Serie Temporal NDVI */}
                    <div className="agro-card p-6 flex flex-col">
                        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-5">
                            <div>
                                <h3 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
                                    <Activity style={{ color: 'var(--color-primary)' }} size={18} />
                                    Evolución de Vigor (NDVI) y Uniformidad (CV%)
                                </h3>
                                <p className="text-xs mt-0.5" style={{ color: 'var(--color-muted)' }}>Biomasa satelital — Sentinel-2 / Earth Engine.</p>
                            </div>

                            {/* Controles de Fecha */}
                            <div className="flex items-center gap-2">
                                <div className="flex items-center gap-1.5 rounded-lg px-3 py-2" style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)' }}>
                                    <Calendar size={13} style={{ color: 'var(--color-muted)' }} />
                                    <input
                                        type="date" value={startDate}
                                        onChange={e => setStartDate(e.target.value)}
                                        className="bg-transparent text-xs outline-none" style={{ color: 'var(--color-text)' }}
                                    />
                                    <span style={{ color: 'var(--color-muted)' }}>–</span>
                                    <input
                                        type="date" value={endDate}
                                        onChange={e => setEndDate(e.target.value)}
                                        className="bg-transparent text-xs outline-none" style={{ color: 'var(--color-text)' }}
                                    />
                                </div>
                                <button
                                    onClick={() => fetchTimeSeries(false)}
                                    disabled={loadingTimeSeries}
                                    className="btn-primary text-xs px-3 py-2"
                                >
                                    {loadingTimeSeries ? <Loader2 size={13} className="animate-spin" /> : <TrendingUp size={13} />}
                                    Analizar
                                </button>
                                {timeSeriesData.length > 0 && !loadingTimeSeries && (
                                    <button
                                        onClick={() => fetchTimeSeries(true)}
                                        title="Forzar recalculo"
                                        className="btn-ghost text-xs px-2.5 py-2"
                                    >
                                        <RefreshCw size={12} />
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Chart Area */}
                        <div className="w-full h-[400px] flex items-center justify-center bg-gray-50 rounded-xl border border-gray-100 p-4 relative">
                            {fromCache === true && !loadingTimeSeries && (
                                <div className="absolute top-3 right-3 flex items-center gap-1 bg-green-50 text-green-700 border border-green-200 text-xs font-semibold px-2 py-1 rounded-full">
                                    <Zap size={11} className="fill-green-500 text-green-500" /> Caché instantáneo
                                </div>
                            )}
                            {loadingTimeSeries ? (
                                <div className="flex flex-col items-center justify-center text-primary">
                                    <Loader2 size={40} className="animate-spin mb-4" />
                                    <span className="font-medium">Calculando en Google Earth Engine...</span>
                                    <span className="text-sm text-gray-500 mt-2">Solo la primera vez tarda. Las siguientes serán instantáneas.</span>
                                </div>
                            ) : timeSeriesError ? (
                                <div className="text-center max-w-sm">
                                    <Info className="mx-auto mb-2" size={26} style={{ color: 'var(--color-danger)' }} />
                                    <p className="font-bold text-sm" style={{ color: 'var(--color-danger)' }}>Error al procesar</p>
                                    <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>{timeSeriesError}</p>
                                </div>
                            ) : timeSeriesData && timeSeriesData.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={timeSeriesData} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="0" vertical={false} stroke="var(--color-border)" />
                                        <XAxis
                                            dataKey="Fecha"
                                            tickFormatter={(val) => {
                                                const d = new Date(val);
                                                return `${d.getDate()}/${d.getMonth() + 1}/${String(d.getFullYear()).slice(2)}`;
                                            }}
                                            tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }}
                                            tickMargin={10}
                                            axisLine={{ stroke: 'var(--color-border)' }}
                                            tickLine={false}
                                        />
                                        <YAxis yAxisId="left" tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} />
                                        <YAxis yAxisId="right" orientation="right" tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                                        <Tooltip content={<CustomTooltip />} />
                                        <Legend wrapperStyle={{ paddingTop: '16px', fontSize: 12 }} />
                                        <Line
                                            yAxisId="left" name="Vigor (NDVI)" type="monotone" dataKey="NDVI_Mean"
                                            stroke="var(--color-primary)" strokeWidth={3}
                                            dot={{ r: 2.5, fill: 'var(--color-primary)', strokeWidth: 0 }}
                                            activeDot={{ r: 5 }}
                                        />
                                        <Line
                                            yAxisId="right" name="Heterogeneidad (CV %)" type="monotone" dataKey="CV_%"
                                            stroke="var(--color-accent)" strokeWidth={2}
                                            strokeDasharray="5 4"
                                            dot={{ r: 2, fill: 'var(--color-accent)', strokeWidth: 0 }}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="flex flex-col items-center gap-2">
                                    <Info className="opacity-25" size={28} style={{ color: 'var(--color-muted)' }} />
                                    <p className="text-sm" style={{ color: 'var(--color-muted)' }}>Presá <strong>Analizar</strong> para calcular la evolución de vigor.</p>
                                </div>
                            )}
                        </div>

                        {/* Summary Cards */}
                        {timeSeriesData && timeSeriesData.length > 0 && !loadingTimeSeries && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
                                {[{
                                    label: 'NDVI Reciente', value: timeSeriesData[timeSeriesData.length - 1]?.NDVI_Mean?.toFixed(2) || 'N/A',
                                    bg: 'rgba(45,106,79,0.07)', border: 'rgba(45,106,79,0.18)', color: 'var(--color-primary)'
                                }, {
                                    label: 'CV% Reciente', value: `${timeSeriesData[timeSeriesData.length - 1]?.['CV_%']?.toFixed(1) || 'N/A'}%`,
                                    sub: 'Mayor % = lote desparejo',
                                    bg: 'rgba(212,168,67,0.07)', border: 'rgba(212,168,67,0.2)', color: 'var(--color-accent)'
                                }, {
                                    label: 'NDVI Máximo', value: Math.max(...timeSeriesData.map((d: any) => d.NDVI_Mean || 0)).toFixed(2),
                                    bg: 'var(--color-background)', border: 'var(--color-border)', color: 'var(--color-text)'
                                }, {
                                    label: 'Imágenes válidas', value: timeSeriesData.length,
                                    sub: 'Sin cobertura nubosa',
                                    bg: 'var(--color-background)', border: 'var(--color-border)', color: 'var(--color-text)'
                                }].map((s, i) => (
                                    <div key={i} className="rounded-xl p-4 flex flex-col justify-center" style={{ background: s.bg, border: `1px solid ${s.border}` }}>
                                        <span className="text-[10px] font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--color-muted)' }}>{s.label}</span>
                                        <span className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</span>
                                        {s.sub && <span className="text-[10px] mt-0.5" style={{ color: 'var(--color-muted)' }}>{s.sub}</span>}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
