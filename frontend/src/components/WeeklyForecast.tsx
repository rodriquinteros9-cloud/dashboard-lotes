import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Wind, Droplets, Thermometer, CloudRain, CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react';

// ─── Tipos ──────────────────────────────────────────────────────────────────
interface HourData {
    time: string;
    hour: string;
    temp: number;
    humidity: number;
    wind: number;
    precipitation: number;
    precip_prob: number;
    weather_code: number;
    delta_t: number;
    verdict: 'ok' | 'caution' | 'no';
}

interface DayForecast {
    date: string;
    temp_max: number;
    temp_min: number;
    wind_max: number;
    wind_avg: number;
    precip_total: number;
    ok_hours: number;
    caution_hours: number;
    verdict: 'ok' | 'caution' | 'no';
    hours: HourData[];
}

interface Props {
    forecast: DayForecast[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────
const DAYS_ES = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
const MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

function formatDate(dateStr: string): { day: string; dayNum: number; month: string; isToday: boolean } {
    const d = new Date(dateStr + 'T12:00:00');
    const today = new Date();
    const isToday = d.toDateString() === today.toDateString();
    return {
        day: DAYS_ES[d.getDay()],
        dayNum: d.getDate(),
        month: MONTHS_ES[d.getMonth()],
        isToday,
    };
}

// Weather code → emoji icon
function weatherIcon(code: number): string {
    if (code === 0) return '☀️';
    if (code <= 2) return '🌤️';
    if (code <= 3) return '☁️';
    if (code <= 49) return '🌫️';
    if (code <= 59) return '🌦️';
    if (code <= 69) return '🌧️';
    if (code <= 79) return '🌨️';
    if (code <= 82) return '🌧️';
    if (code <= 99) return '⛈️';
    return '🌡️';
}

// Verdict config
const VERDICT_CONFIG = {
    ok: {
        label: 'Apto',
        bg: 'rgba(45,106,79,0.08)',
        border: 'rgba(45,106,79,0.25)',
        text: '#1B4332',
        badgeBg: '#2D6A4F',
        bar: '#52B788',
        Icon: CheckCircle,
        iconColor: '#2D6A4F',
    },
    caution: {
        label: 'Precaución',
        bg: 'rgba(212,168,67,0.08)',
        border: 'rgba(212,168,67,0.3)',
        text: '#7A5A00',
        badgeBg: '#D4A843',
        bar: '#F0C96A',
        Icon: AlertTriangle,
        iconColor: '#D4A843',
    },
    no: {
        label: 'No Aplicar',
        bg: 'rgba(192,57,43,0.06)',
        border: 'rgba(192,57,43,0.2)',
        text: '#7B1A10',
        badgeBg: '#C0392B',
        bar: '#E57373',
        Icon: XCircle,
        iconColor: '#C0392B',
    },
};

// ─── Sub-component: Hourly timeline bar ────────────────────────────────────
function HourlyTimeline({ hours }: { hours: HourData[] }) {
    const grouped: HourData[][] = [];
    let cur: HourData[] = [];
    hours.forEach((h, i) => {
        cur.push(h);
        if ((i + 1) % 6 === 0 || i === hours.length - 1) {
            grouped.push(cur);
            cur = [];
        }
    });

    return (
        <div className="mt-4 space-y-3">
            {/* Hour ticks row */}
            <div className="grid gap-0.5" style={{ gridTemplateColumns: `repeat(${hours.length}, 1fr)` }}>
                {hours.map((h) => {
                    const cfg = VERDICT_CONFIG[h.verdict];
                    return (
                        <div key={h.time} title={`${h.hour}  T:${h.temp}°  HR:${h.humidity}%  Viento:${h.wind}km/h  ΔT:${h.delta_t}`}>
                            <div
                                className="h-6 rounded-sm transition-opacity hover:opacity-80 cursor-default"
                                style={{ background: cfg.bar }}
                            />
                        </div>
                    );
                })}
            </div>

            {/* Hour labels every 3h */}
            <div className="grid gap-0" style={{ gridTemplateColumns: `repeat(${hours.length}, 1fr)` }}>
                {hours.map((h, i) => (
                    <span key={h.time} className="text-center" style={{ fontSize: '9px', color: 'var(--color-muted)' }}>
                        {i % 3 === 0 ? h.hour.replace(':00', 'h') : ''}
                    </span>
                ))}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 pt-1">
                {(['ok', 'caution', 'no'] as const).map(v => {
                    const cfg = VERDICT_CONFIG[v];
                    return (
                        <div key={v} className="flex items-center gap-1.5">
                            <div className="w-3 h-3 rounded-sm" style={{ background: cfg.bar }} />
                            <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>{cfg.label}</span>
                        </div>
                    );
                })}
            </div>

            {/* Hourly detail table */}
            <div className="overflow-x-auto rounded-xl border" style={{ borderColor: 'var(--color-border)' }}>
                <table className="w-full text-xs" style={{ minWidth: 520 }}>
                    <thead>
                        <tr style={{ background: 'var(--color-background)' }}>
                            <th className="px-3 py-2 text-left font-semibold" style={{ color: 'var(--color-muted)' }}>Hora</th>
                            <th className="px-3 py-2 text-center font-semibold" style={{ color: 'var(--color-muted)' }}>Temp</th>
                            <th className="px-3 py-2 text-center font-semibold" style={{ color: 'var(--color-muted)' }}>HR</th>
                            <th className="px-3 py-2 text-center font-semibold" style={{ color: 'var(--color-muted)' }}>Viento</th>
                            <th className="px-3 py-2 text-center font-semibold" style={{ color: 'var(--color-muted)' }}>ΔT</th>
                            <th className="px-3 py-2 text-center font-semibold" style={{ color: 'var(--color-muted)' }}>Lluvia</th>
                            <th className="px-3 py-2 text-center font-semibold" style={{ color: 'var(--color-muted)' }}>Aptitud</th>
                        </tr>
                    </thead>
                    <tbody>
                        {hours.map((h, i) => {
                            const cfg = VERDICT_CONFIG[h.verdict];
                            return (
                                <tr
                                    key={h.time}
                                    style={{
                                        background: i % 2 === 0 ? 'white' : 'var(--color-background)',
                                        borderTop: '1px solid var(--color-border)',
                                    }}
                                >
                                    <td className="px-3 py-2 font-semibold" style={{ color: 'var(--color-text)' }}>{h.hour}</td>
                                    <td className="px-3 py-2 text-center" style={{ color: '#D4A843' }}>{h.temp}°C</td>
                                    <td className="px-3 py-2 text-center" style={{ color: '#4A90B8' }}>{h.humidity}%</td>
                                    <td className="px-3 py-2 text-center" style={{ color: 'var(--color-primary)' }}>{h.wind} km/h</td>
                                    <td className="px-3 py-2 text-center font-semibold" style={{ color: h.delta_t > 8 ? '#C0392B' : h.delta_t > 6 ? '#D4A843' : 'var(--color-primary)' }}>
                                        {h.delta_t}
                                    </td>
                                    <td className="px-3 py-2 text-center" style={{ color: h.precipitation > 0 ? '#C0392B' : 'var(--color-muted)' }}>
                                        {h.precipitation > 0 ? `${h.precipitation}mm` : '—'}
                                    </td>
                                    <td className="px-3 py-2 text-center">
                                        <span
                                            className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-bold text-white"
                                            style={{ background: cfg.badgeBg }}
                                        >
                                            {cfg.label}
                                        </span>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// ─── Componente Principal ────────────────────────────────────────────────────
export default function WeeklyForecast({ forecast }: Props) {
    const [expandedDay, setExpandedDay] = useState<number | null>(null);

    const toggle = (i: number) => setExpandedDay(prev => prev === i ? null : i);

    return (
        <div className="agro-card p-6 flex flex-col gap-5">
            {/* Header */}
            <div>
                <h3 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--color-text)' }}>
                    <Clock size={17} style={{ color: 'var(--color-primary)' }} />
                    Pronóstico de 7 Días — Ventanas de Aplicación
                </h3>
                <p className="text-xs mt-0.5" style={{ color: 'var(--color-muted)' }}>
                    Basado en viento, ΔT, temperatura y lluvia. Hacé click en un día para ver el detalle por hora.
                </p>
            </div>

            {/* Day cards */}
            <div className="space-y-2">
                {forecast.map((day, i) => {
                    const { day: dayName, dayNum, month, isToday } = formatDate(day.date);
                    const cfg = VERDICT_CONFIG[day.verdict];
                    const isExpanded = expandedDay === i;
                    const VerdictIcon = cfg.Icon;
                    const totalSpray = day.ok_hours + day.caution_hours;

                    return (
                        <div
                            key={day.date}
                            className="rounded-xl overflow-hidden transition-all"
                            style={{
                                border: `1px solid ${isExpanded ? 'var(--color-primary-light)' : cfg.border}`,
                                background: isExpanded ? 'white' : 'transparent',
                                boxShadow: isExpanded ? '0 2px 12px rgba(45,106,79,0.08)' : 'none',
                            }}
                        >
                            {/* Day summary row */}
                            <button
                                onClick={() => toggle(i)}
                                className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white"
                            >
                                {/* Date */}
                                <div className="w-14 shrink-0 text-center">
                                    <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--color-muted)' }}>
                                        {isToday ? 'HOY' : dayName}
                                    </p>
                                    <p className="text-lg font-bold leading-tight" style={{ color: 'var(--color-text)' }}>{dayNum}</p>
                                    <p className="text-[10px]" style={{ color: 'var(--color-muted)' }}>{month}</p>
                                </div>

                                {/* Weather icon */}
                                <span className="text-2xl shrink-0">{weatherIcon(day.hours[12]?.weather_code ?? 0)}</span>

                                {/* Temp range */}
                                <div className="shrink-0 text-center w-16">
                                    <span className="font-bold text-sm" style={{ color: '#C0392B' }}>{day.temp_max}°</span>
                                    <span className="text-sm mx-1" style={{ color: 'var(--color-muted)' }}>/</span>
                                    <span className="text-sm" style={{ color: '#4A90B8' }}>{day.temp_min}°</span>
                                </div>

                                {/* Wind + Precip mini stats */}
                                <div className="hidden sm:flex items-center gap-4 text-xs shrink-0" style={{ color: 'var(--color-text-secondary)' }}>
                                    <span className="flex items-center gap-1">
                                        <Wind size={11} /> {day.wind_avg} km/h
                                    </span>
                                    <span className="flex items-center gap-1">
                                        <Droplets size={11} /> {day.precip_total > 0 ? `${day.precip_total}mm` : 'sin lluvia'}
                                    </span>
                                </div>

                                {/* Application windows bar */}
                                <div className="flex-1 hidden md:block px-2">
                                    <div className="flex h-4 rounded-full overflow-hidden gap-px" style={{ background: 'var(--color-border)' }}>
                                        {day.ok_hours > 0 && (
                                            <div style={{ width: `${(day.ok_hours / 24) * 100}%`, background: VERDICT_CONFIG.ok.bar }} title={`${day.ok_hours}h aptas`} />
                                        )}
                                        {day.caution_hours > 0 && (
                                            <div style={{ width: `${(day.caution_hours / 24) * 100}%`, background: VERDICT_CONFIG.caution.bar }} title={`${day.caution_hours}h con precaución`} />
                                        )}
                                    </div>
                                    <p className="text-[10px] mt-1" style={{ color: 'var(--color-muted)' }}>
                                        {totalSpray > 0
                                            ? `${totalSpray}h disponibles para aplicar`
                                            : 'Sin ventanas de aplicación'}
                                    </p>
                                </div>

                                {/* Verdict badge */}
                                <div className="ml-auto shrink-0 flex items-center gap-2">
                                    <VerdictIcon size={16} style={{ color: cfg.iconColor }} />
                                    <span className="text-xs font-bold" style={{ color: cfg.text }}>{cfg.label}</span>
                                    <span style={{ color: 'var(--color-muted)' }}>
                                        {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                                    </span>
                                </div>
                            </button>

                            {/* Expanded hourly detail */}
                            {isExpanded && (
                                <div className="px-4 pb-4" style={{ borderTop: '1px solid var(--color-border)' }}>
                                    <HourlyTimeline hours={day.hours} />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-4 pt-2 border-t" style={{ borderColor: 'var(--color-border)' }}>
                <p className="text-xs font-semibold w-full" style={{ color: 'var(--color-muted)' }}>Criterios de aptitud:</p>
                {[
                    { color: VERDICT_CONFIG.ok.bar, label: 'Apto — Viento 4–15 km/h, ΔT 2–6, T 15–30°C, sin lluvia' },
                    { color: VERDICT_CONFIG.caution.bar, label: 'Precaución — Parámetro en zona marginal' },
                    { color: VERDICT_CONFIG.no.bar, label: 'No Aplicar — Condición crítica' },
                ].map(l => (
                    <div key={l.label} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                        <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: l.color }} />
                        {l.label}
                    </div>
                ))}
            </div>
        </div>
    );
}
