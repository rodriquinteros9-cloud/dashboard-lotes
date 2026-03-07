import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import type { AppState } from '../App';
import { FileUp, BarChart3, LineChart, Loader2, ArrowLeft, Layers } from 'lucide-react';
import { useState } from 'react';

export default function DashboardLayout({ appState, setAppState }: { appState: AppState, setAppState: any }) {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);

    if (!appState.spatialData) {
        navigate("/");
        return null;
    }

    const handleSidebarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setLoading(true);
        const formData = new FormData();
        formData.append("file", file);

        try {
            const resp = await fetch("http://127.0.0.1:8000/api/upload-lotes", { method: "POST", body: formData });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail);

            setAppState({
                spatialData: data.geojson,
                globalMetadata: data.metadata,
                moduleCache: {},
            });
        } catch (error) {
            alert("Error en la carga: " + error);
        } finally {
            setLoading(false);
        }
    };

    const area = appState.globalMetadata?.total_area_ha?.toFixed(0) || 0;
    const count = appState.globalMetadata?.feature_count || 0;

    return (
        <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-background)' }}>

            {/* ── Sidebar ── */}
            <aside className="sidebar w-64 flex flex-col shrink-0 shadow-lg">

                {/* Logo */}
                <div className="px-5 pt-6 pb-4 border-b border-white/10 flex justify-center">
                    <img src="/logo.png" alt="AgroPulse" className="h-14 object-contain" />
                </div>

                {/* Nav */}
                <nav className="flex-1 px-3 py-5 space-y-1">
                    <p className="px-3 text-[10px] font-semibold tracking-widest uppercase text-white/30 mb-3">
                        Módulos
                    </p>

                    <NavLink
                        to="/dashboard/ranking"
                        className={({ isActive }) => `sidebar-nav-item ${isActive ? 'active' : ''}`}
                    >
                        <BarChart3 size={18} />
                        Ranking de Lotes
                    </NavLink>

                    <NavLink
                        to="/dashboard/analysis"
                        className={({ isActive }) => `sidebar-nav-item ${isActive ? 'active' : ''}`}
                    >
                        <LineChart size={18} />
                        Análisis Individual
                    </NavLink>
                </nav>

                {/* Footer: stats + upload */}
                <div className="px-4 pb-5 space-y-3">
                    {/* Lot stats */}
                    <div className="rounded-xl p-3.5" style={{ background: 'rgba(255,255,255,0.07)' }}>
                        <p className="text-[10px] font-semibold tracking-widest uppercase text-white/30 mb-2.5">
                            Datos Activos
                        </p>
                        <div className="flex items-center gap-2 mb-1.5">
                            <Layers size={13} className="text-green-300 shrink-0" />
                            <span className="text-sm text-white/80">
                                <span className="font-bold text-white">{count}</span> lotes cargados
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-sm shrink-0" style={{ background: 'var(--color-primary-light)' }} />
                            <span className="text-sm text-white/80">
                                <span className="font-bold text-white">{area}</span> ha totales
                            </span>
                        </div>
                    </div>

                    {/* Upload new KML */}
                    <div className="relative rounded-xl border border-white/15 hover:border-green-400/40 transition-colors cursor-pointer group"
                        style={{ background: 'rgba(255,255,255,0.05)' }}>
                        <button className="flex items-center justify-center gap-2 w-full py-2.5 px-3 text-sm font-medium text-white/60 group-hover:text-white/90 transition-colors">
                            {loading ? <Loader2 className="animate-spin" size={15} /> : <FileUp size={15} />}
                            {loading ? "Procesando..." : "Subir nuevo KML"}
                        </button>
                        <input
                            type="file" accept=".kml,.geojson,.json"
                            onChange={handleSidebarUpload}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                            disabled={loading}
                        />
                    </div>

                    {/* Back to portal */}
                    <button
                        onClick={() => navigate('/')}
                        className="w-full flex items-center justify-center gap-2 py-2 text-xs font-medium text-white/35 hover:text-white/60 transition-colors"
                    >
                        <ArrowLeft size={12} /> Volver al Portal
                    </button>
                </div>
            </aside>

            {/* ── Main Content ── */}
            <main className="flex-1 min-w-0 overflow-y-auto">
                <div className="p-8 max-w-7xl mx-auto">
                    <Outlet />
                </div>
            </main>
        </div>
    );
}
