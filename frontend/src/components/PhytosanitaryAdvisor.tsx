import React from 'react';
import { Wind, Droplets, Thermometer, CloudRain, AlertTriangle, CheckCircle, XCircle, Info, FlaskConical } from 'lucide-react';

// ─── Fórmula psicrométrica para Temperatura de Bulbo Húmedo ──────────────────
// Fórmula de Stull (2011) - Ampliamente usada en agronomía
function wetBulbTemp(T: number, RH: number): number {
    return T * Math.atan(0.151977 * Math.pow(RH + 8.313659, 0.5))
        + Math.atan(T + RH)
        - Math.atan(RH - 1.676331)
        + 0.00391838 * Math.pow(RH, 1.5) * Math.atan(0.023101 * RH)
        - 4.686035;
}

// ─── Calcular ΔT ───────────────────────────────────────────────────────────
function calcDeltaT(T: number, RH: number): number {
    const Tw = wetBulbTemp(T, RH);
    return parseFloat((T - Tw).toFixed(1));
}

// ─── Tipos ────────────────────────────────────────────────────────────────
type Status = 'ok' | 'warning' | 'danger';

interface Evaluation {
    status: Status;
    label: string;
    detail: string;
}

interface OverallVerdict {
    status: Status;
    title: string;
    message: string;
    adjuvant?: string;
}

// ─── Evaluaciones ────────────────────────────────────────────────────────────
function evaluateWind(speed: number): Evaluation {
    if (speed < 4) {
        return {
            status: 'danger',
            label: `${speed.toFixed(1)} km/h`,
            detail: 'Calma chicha — Alto riesgo de inversión térmica. NO APLICAR.'
        };
    }
    if (speed <= 15) {
        return {
            status: 'ok',
            label: `${speed.toFixed(1)} km/h`,
            detail: 'Viento óptimo para pulverización (5–15 km/h).'
        };
    }
    if (speed <= 18) {
        return {
            status: 'warning',
            label: `${speed.toFixed(1)} km/h`,
            detail: 'Viento elevado. Aumento del riesgo de deriva. Aplicar con precaución.'
        };
    }
    return {
        status: 'danger',
        label: `${speed.toFixed(1)} km/h`,
        detail: `Viento excesivo (>${speed.toFixed(1)} km/h). Riesgo de deriva severo. NO APLICAR.`
    };
}

function evaluateDeltaT(dT: number): Evaluation {
    if (dT < 2) {
        return {
            status: 'warning',
            label: `ΔT = ${dT}`,
            detail: 'Humedad muy alta. Gotas en suspensión. Riesgo de endoderiva y escurrimiento.'
        };
    }
    if (dT <= 6) {
        return {
            status: 'ok',
            label: `ΔT = ${dT}`,
            detail: 'Condiciones ideales. Se puede aplicar solo con agua.'
        };
    }
    if (dT <= 8) {
        return {
            status: 'warning',
            label: `ΔT = ${dT}`,
            detail: 'Evaporación moderada. Agregar coadyuvante anti-evaporante (aceite): 0.5 L/ha.'
        };
    }
    if (dT <= 10) {
        return {
            status: 'warning',
            label: `ΔT = ${dT}`,
            detail: 'Evaporación alta. Usar dosis máxima de aceite (1 L/ha). Evaluar postergar.'
        };
    }
    return {
        status: 'danger',
        label: `ΔT = ${dT}`,
        detail: 'Ambiente extremadamente seco. Las gotas se evaporan antes de llegar al blanco. NO APLICAR.'
    };
}

function evaluateHumidity(rh: number): Evaluation {
    if (rh > 85) {
        return {
            status: 'warning',
            label: `${rh}%`,
            detail: 'Humedad muy alta. Posible exceso de rocío y escurrimiento del producto (endo-deriva).'
        };
    }
    if (rh >= 50) {
        return { status: 'ok', label: `${rh}%`, detail: 'Humedad relativa en rango óptimo.' };
    }
    return { status: 'warning', label: `${rh}%`, detail: 'Humedad baja. Complementar con revisión del ΔT.' };
}

function evaluateTemperature(T: number): Evaluation {
    if (T > 30) {
        return { status: 'warning', label: `${T}°C`, detail: 'Temperatura alta. Riesgo de evaporación. Verificar ΔT.' };
    }
    if (T >= 15) {
        return { status: 'ok', label: `${T}°C`, detail: 'Temperatura en rango óptimo (15–30°C).' };
    }
    if (T >= 10) {
        return { status: 'warning', label: `${T}°C`, detail: 'Temperatura baja. Actividad biológica reducida. Revisar ΔT por riesgo de gotas en suspensión.' };
    }
    return { status: 'danger', label: `${T}°C`, detail: 'Temperatura muy baja. Condiciones marginales para la aplicación.' };
}

function evaluatePrecipitation(precip: number): Evaluation {
    if (precip > 0) {
        return { status: 'danger', label: `${precip} mm`, detail: 'Hay lluvia activa. El producto será lavado antes de actuar. NO APLICAR.' };
    }
    return { status: 'ok', label: '0 mm', detail: 'Sin lluvia actual.' };
}

function evaluateThermalInversion(windSpeed: number): Evaluation {
    if (windSpeed < 4) {
        return {
            status: 'danger',
            label: 'RIESGO ALTO',
            detail: 'Viento < 4 km/h indica probable inversión térmica. Las gotas pueden viajar hasta 3.5 km lateralmente.'
        };
    }
    return {
        status: 'ok',
        label: 'SIN RIESGO',
        detail: 'Viento suficiente para descartar inversión térmica.'
    };
}

// ─── Veredicto global ────────────────────────────────────────────────────────
function getOverallVerdict(
    wind: Evaluation,
    dT: number,
    tempEval: Evaluation,
    humEval: Evaluation,
    precip: Evaluation
): OverallVerdict {
    const isDanger = [wind, tempEval, precip].some(e => e.status === 'danger') || dT > 10;

    if (isDanger) {
        const reasons: string[] = [];
        if (wind.status === 'danger') reasons.push('viento fuera de rango');
        if (dT > 10) reasons.push('ΔT > 10 (evaporación extrema)');
        if (precip.status === 'danger') reasons.push('lluvia activa');
        if (tempEval.status === 'danger') reasons.push('temperatura extrema');
        return {
            status: 'danger',
            title: 'NO APLICAR',
            message: `Condición crítica: ${reasons.join(', ')}.`,
        };
    }

    const isWarning = [wind, tempEval, humEval].some(e => e.status === 'warning') || (dT > 6 && dT <= 10);

    if (isWarning) {
        let adjuvant = '';
        if (dT > 8 && dT <= 10) adjuvant = 'Usar aceite anti-evaporante: 1 L/ha.';
        else if (dT > 6 && dT <= 8) adjuvant = 'Agregar aceite anti-evaporante: 0.5 L/ha.';

        return {
            status: 'warning',
            title: 'APLICAR CON PRECAUCIÓN',
            message: 'Las condiciones son aceptables, pero hay variables en zona marginal.',
            adjuvant,
        };
    }

    return {
        status: 'ok',
        title: 'CONDICIONES APTAS',
        message: 'Todos los parámetros están en zona verde. Se puede aplicar solo con agua.',
    };
}

// ─── Sub-componentes UI ───────────────────────────────────────────────────────
const statusColors: Record<Status, { bg: string; border: string; text: string; badge: string }> = {
    ok: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-800', badge: 'bg-green-100 text-green-700' },
    warning: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', badge: 'bg-amber-100 text-amber-700' },
    danger: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', badge: 'bg-red-100 text-red-700' },
};

const StatusIcon = ({ status, size = 18 }: { status: Status; size?: number }) => {
    if (status === 'ok') return <CheckCircle size={size} className="text-green-500 shrink-0" />;
    if (status === 'warning') return <AlertTriangle size={size} className="text-amber-500 shrink-0" />;
    return <XCircle size={size} className="text-red-500 shrink-0" />;
};

interface EvalCardProps {
    icon: React.ReactNode;
    title: string;
    evaluation: Evaluation;
}

const EvalCard = ({ icon, title, evaluation }: EvalCardProps) => {
    const c = statusColors[evaluation.status];
    return (
        <div className={`rounded-xl border p-4 ${c.bg} ${c.border} flex flex-col gap-2`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-gray-700 text-sm">
                    {icon}
                    {title}
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${c.badge}`}>
                    {evaluation.label}
                </span>
            </div>
            <div className="flex items-start gap-2">
                <StatusIcon status={evaluation.status} size={14} />
                <p className={`text-xs ${c.text} leading-relaxed`}>{evaluation.detail}</p>
            </div>
        </div>
    );
};

// ─── Componente Principal ────────────────────────────────────────────────────
interface Props {
    weatherData: {
        temperature: number;
        humidity: number;
        wind_speed: number;
        dew_point?: number;
        precipitation?: number;
    };
}

export default function PhytosanitaryAdvisor({ weatherData }: Props) {
    const T = weatherData.temperature;
    const RH = weatherData.humidity;
    const wind = weatherData.wind_speed;
    const precip = weatherData.precipitation ?? 0;

    const dT = calcDeltaT(T, RH);

    const windEval = evaluateWind(wind);
    const dtEval = evaluateDeltaT(dT);
    const humEval = evaluateHumidity(RH);
    const tempEval = evaluateTemperature(T);
    const precipEval = evaluatePrecipitation(precip);
    const invEval = evaluateThermalInversion(wind);

    const verdict = getOverallVerdict(windEval, dT, tempEval, humEval, precipEval);

    const verdictColors = {
        ok: { bg: 'bg-green-600', border: 'border-green-700', icon: <CheckCircle size={28} className="text-white" /> },
        warning: { bg: 'bg-amber-500', border: 'border-amber-600', icon: <AlertTriangle size={28} className="text-white" /> },
        danger: { bg: 'bg-red-600', border: 'border-red-700', icon: <XCircle size={28} className="text-white" /> },
    };
    const vc = verdictColors[verdict.status];

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col gap-5">
            {/* Header */}
            <div>
                <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                    <FlaskConical className="text-primary" size={22} />
                    Aptitud para Aplicación de Fitosanitarios
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                    Evaluación en tiempo real de las condiciones climáticas del lote para pulverización.
                </p>
            </div>

            {/* Veredicto Global */}
            <div className={`rounded-2xl ${vc.bg} p-5 flex items-start gap-4`}>
                <div className="shrink-0 mt-0.5">{vc.icon}</div>
                <div>
                    <p className="text-white font-extrabold text-xl tracking-wide">{verdict.title}</p>
                    <p className="text-white/90 text-sm mt-1">{verdict.message}</p>
                    {verdict.adjuvant && (
                        <div className="mt-2 flex items-center gap-2 bg-white/20 rounded-lg px-3 py-2">
                            <FlaskConical size={14} className="text-white shrink-0" />
                            <span className="text-white font-semibold text-sm">{verdict.adjuvant}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Grid de evaluaciones */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <EvalCard
                    icon={<Wind size={15} className="text-gray-500" />}
                    title="Velocidad del Viento"
                    evaluation={windEval}
                />
                <EvalCard
                    icon={<Thermometer size={15} className="text-gray-500" />}
                    title="ΔT (Evaporación)"
                    evaluation={dtEval}
                />
                <EvalCard
                    icon={<AlertTriangle size={15} className="text-gray-500" />}
                    title="Inversión Térmica"
                    evaluation={invEval}
                />
                <EvalCard
                    icon={<Thermometer size={15} className="text-gray-500" />}
                    title="Temperatura"
                    evaluation={tempEval}
                />
                <EvalCard
                    icon={<Droplets size={15} className="text-gray-500" />}
                    title="Humedad Relativa"
                    evaluation={humEval}
                />
                <EvalCard
                    icon={<CloudRain size={15} className="text-gray-500" />}
                    title="Lluvia Actual"
                    evaluation={precipEval}
                />
            </div>

            {/* Tabla ΔT de referencia */}
            <details className="group">
                <summary className="cursor-pointer text-xs text-gray-500 flex items-center gap-1 select-none hover:text-gray-700 transition-colors">
                    <Info size={13} />
                    Ver tabla de referencia ΔT completa
                    <span className="ml-auto group-open:rotate-180 transition-transform">▾</span>
                </summary>
                <div className="mt-3 overflow-x-auto rounded-xl border border-gray-100">
                    <table className="w-full text-xs text-left">
                        <thead>
                            <tr className="bg-gray-50">
                                <th className="px-3 py-2 font-semibold text-gray-600">ΔT</th>
                                <th className="px-3 py-2 font-semibold text-gray-600">Condición</th>
                                <th className="px-3 py-2 font-semibold text-gray-600">Recomendación</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            <tr className="bg-amber-50"><td className="px-3 py-2 font-bold text-amber-700">&lt; 2</td><td className="px-3 py-2 text-amber-700">Marginal / Prohibida</td><td className="px-3 py-2 text-gray-700">Gotas en suspensión. Riesgo de deriva y escurrimiento.</td></tr>
                            <tr className="bg-green-50"><td className="px-3 py-2 font-bold text-green-700">2 – 6</td><td className="px-3 py-2 text-green-700">Óptima</td><td className="px-3 py-2 text-gray-700">Aplicar con agua. Condiciones ideales.</td></tr>
                            <tr className="bg-amber-50"><td className="px-3 py-2 font-bold text-amber-700">6 – 8</td><td className="px-3 py-2 text-amber-700">Aceptable con precaución</td><td className="px-3 py-2 text-gray-700">Agregar aceite anti-evaporante: <strong>0.5 L/ha</strong>.</td></tr>
                            <tr className="bg-orange-50"><td className="px-3 py-2 font-bold text-orange-700">8 – 10</td><td className="px-3 py-2 text-orange-700">Marginal</td><td className="px-3 py-2 text-gray-700">Dosis máxima de aceite: <strong>1 L/ha</strong>. Considerar postergar.</td></tr>
                            <tr className="bg-red-50"><td className="px-3 py-2 font-bold text-red-700">&gt; 10</td><td className="px-3 py-2 text-red-700">Prohibida</td><td className="px-3 py-2 text-gray-700">Evaporación extrema. Gota no llega al blanco. NO APLICAR.</td></tr>
                        </tbody>
                    </table>
                </div>
            </details>
        </div>
    );
}
