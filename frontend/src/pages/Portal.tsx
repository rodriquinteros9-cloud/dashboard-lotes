import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, Activity, BarChart3, Loader2, CheckCircle2, FileBox, X } from 'lucide-react';

export default function Portal({ setAppState }: { setAppState: any }) {
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState("");
    const [isUploaded, setIsUploaded] = useState(false);
    const [isDragOver, setIsDragOver] = useState(false);
    const [fileName, setFileName] = useState("");
    const [metadata, setMetadata] = useState<any>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const navigate = useNavigate();

    const processFile = async (file: File) => {
        if (!file) return;
        setLoading(true);
        setErrorMsg("");
        setFileName(file.name);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const resp = await fetch("http://127.0.0.1:8000/api/upload-lotes", {
                method: "POST",
                body: formData,
            });

            const data = await resp.json();

            if (!resp.ok) throw new Error(data.detail || "Error subiendo archivo");

            // Resetear el caché del módulo cuando se sube un archivo nuevo
            setAppState({ spatialData: data.geojson, globalMetadata: data.metadata, moduleCache: {} });
            setMetadata(data.metadata);
            setIsUploaded(true);
        } catch (error: any) {
            setErrorMsg(error.message);
            setFileName("");
        } finally {
            setLoading(false);
        }
    };

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) processFile(file);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) processFile(file);
    };

    const handleReset = () => {
        setIsUploaded(false);
        setFileName("");
        setMetadata(null);
        setErrorMsg("");
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-green-950 to-slate-900 flex flex-col items-center justify-center p-6 relative overflow-hidden">

            {/* Decorative background blobs */}
            <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-primary/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

            {/* Logo / Brand */}
            <div className="text-center mb-10 relative z-10">
                <img
                    src="/logo.png"
                    alt="AgroPulse — Plataforma Satelital de Monitoreo de Cultivos"
                    className="h-40 mx-auto object-contain drop-shadow-xl"
                />
            </div>

            {/* ── FASE 1: Uploader ─────────────────────────────────────────── */}
            {!isUploaded ? (
                <div className="relative z-10 w-full max-w-lg">
                    <div
                        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                        onDragLeave={() => setIsDragOver(false)}
                        onDrop={handleDrop}
                        onClick={() => !loading && fileInputRef.current?.click()}
                        className={`
                            group cursor-pointer rounded-3xl border-2 border-dashed p-10 flex flex-col items-center text-center transition-all duration-300
                            ${isDragOver
                                ? 'border-primary bg-primary/10 scale-[1.02]'
                                : 'border-slate-600 bg-white/5 hover:border-primary/60 hover:bg-white/10'
                            }
                        `}
                    >
                        <div className={`w-20 h-20 rounded-2xl flex items-center justify-center mb-5 transition-all duration-300 ${isDragOver ? 'bg-primary scale-110' : 'bg-slate-800 group-hover:bg-primary/20'}`}>
                            {loading
                                ? <Loader2 size={36} className="text-primary animate-spin" />
                                : <UploadCloud size={36} className={`transition-colors ${isDragOver ? 'text-white' : 'text-slate-400 group-hover:text-primary'}`} />
                            }
                        </div>

                        {loading ? (
                            <>
                                <p className="text-white font-bold text-xl mb-1">Procesando lotes...</p>
                                <p className="text-slate-400 text-sm">Validando geometrías y calculando métricas</p>
                            </>
                        ) : (
                            <>
                                <p className="text-white font-bold text-xl mb-2">
                                    {isDragOver ? 'Soltar archivo aquí' : 'Cargar archivo de lotes'}
                                </p>
                                <p className="text-slate-400 text-sm mb-4">
                                    Arrastrá o hacé clic para seleccionar
                                </p>
                                <span className="inline-flex items-center gap-2 text-xs text-slate-500 bg-slate-800 px-3 py-1.5 rounded-full">
                                    <FileBox size={12} /> .KML · .GeoJSON · .JSON
                                </span>
                            </>
                        )}

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".kml,.geojson,.json"
                            onChange={handleFileInput}
                            className="hidden"
                        />
                    </div>

                    {errorMsg && (
                        <div className="mt-4 flex items-start gap-2 bg-red-950/60 border border-red-800 text-red-300 text-sm p-4 rounded-2xl">
                            <X size={16} className="shrink-0 mt-0.5" />
                            <span>{errorMsg}</span>
                        </div>
                    )}

                    <p className="text-center text-slate-600 text-xs mt-6">
                        Los datos son procesados localmente. Nada se almacena en la nube.
                    </p>
                </div>

            ) : (
                /* ── FASE 2: Módulos revelados ───────────────────────────────── */
                <div className="relative z-10 w-full max-w-3xl animate-in fade-in slide-in-from-bottom-6 duration-700">

                    {/* Confirmación de carga */}
                    <div className="flex items-center justify-between bg-green-950/60 border border-green-800 rounded-2xl px-5 py-3 mb-8">
                        <div className="flex items-center gap-3">
                            <CheckCircle2 size={20} className="text-primary shrink-0" />
                            <div>
                                <p className="text-white font-semibold text-sm">{fileName}</p>
                                <p className="text-green-400 text-xs">
                                    {metadata?.feature_count} lote{metadata?.feature_count !== 1 ? 's' : ''} cargado{metadata?.feature_count !== 1 ? 's' : ''} — {metadata?.total_area_ha?.toFixed(1)} ha totales
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={handleReset}
                            title="Cargar otro archivo"
                            className="text-slate-500 hover:text-slate-300 transition-colors p-1"
                        >
                            <X size={16} />
                        </button>
                    </div>

                    {/* Título */}
                    <p className="text-center text-slate-400 text-sm mb-6 font-medium">
                        ¿Qué módulo deseas explorar?
                    </p>

                    {/* Cards de módulos */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                        {/* Ranking */}
                        <button
                            onClick={() => navigate("/dashboard/ranking")}
                            className="group relative bg-white/5 hover:bg-blue-500/10 border border-slate-700 hover:border-blue-500/50 rounded-3xl p-8 flex flex-col items-center text-center gap-4 transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl hover:shadow-blue-500/10"
                        >
                            <div className="w-16 h-16 rounded-2xl bg-blue-500/20 group-hover:bg-blue-500/30 flex items-center justify-center transition-colors">
                                <BarChart3 size={32} className="text-blue-400" />
                            </div>
                            <div>
                                <h3 className="text-white font-bold text-xl mb-1">Ranking de Lotes</h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    Comparativa de índices productivos y suelos en todos tus lotes simultáneamente.
                                </p>
                            </div>
                            <span className="text-xs text-blue-400/70 font-medium mt-auto">
                                Índice Productivo · Benchmark NDVI →
                            </span>
                        </button>

                        {/* Análisis Individual */}
                        <button
                            onClick={() => navigate("/dashboard/analysis")}
                            className="group relative bg-white/5 hover:bg-primary/10 border border-slate-700 hover:border-primary/50 rounded-3xl p-8 flex flex-col items-center text-center gap-4 transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl hover:shadow-primary/10"
                        >
                            <div className="w-16 h-16 rounded-2xl bg-primary/20 group-hover:bg-primary/30 flex items-center justify-center transition-colors">
                                <Activity size={32} className="text-primary" />
                            </div>
                            <div>
                                <h3 className="text-white font-bold text-xl mb-1">Análisis Individual</h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    Monitoreo profundo de vigor NDVI, clima, y aptitud para pulverización por lote.
                                </p>
                            </div>
                            <span className="text-xs text-primary/70 font-medium mt-auto">
                                NDVI · ΔT · Fitosanitarios →
                            </span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
