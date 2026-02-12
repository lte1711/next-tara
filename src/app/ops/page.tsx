
"use client";

import React, { useEffect, useState, useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, XCircle, AlertCircle, Clock, TrendingUp } from "lucide-react";

const OPS_TOKEN = process.env.NEXT_PUBLIC_OPS_TOKEN || "dev-ops-token-change-me";
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/ops";

// 다양한 로그 응답 포맷 흡수
const pickLines = (j: any): string[] => {
  if (!j) return [];
  if (Array.isArray(j.lines)) return j.lines.map(String);
  if (Array.isArray(j.items)) return j.items.map(String);
  if (Array.isArray(j.stdout)) return j.stdout.map(String);
  if (Array.isArray(j.stderr)) return j.stderr.map(String);
  if (typeof j.text === "string") return j.text.split("\n").filter(Boolean);
  if (typeof j.content === "string") return j.content.split("\n").filter(Boolean);
  return [];
};

export default function OpsPage() {
  // 안전 숫자 변환 헬퍼 (SSOT)
  const asNum = (v: any, fallback = 0) => typeof v === "number" && Number.isFinite(v) ? v : fallback;
  const [isClient, setIsClient] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [status, setStatus] = useState<EvergreenStatus | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [stdoutLines, setStdoutLines] = useState<string[]>([]);
  const [stderrLines, setStderrLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);

  useEffect(() => {
    setIsClient(true);
  }, []);


  // fetchData: 모든 데이터 fetch (프록시 경로 사용, 10초마다 자동 갱신)
  const fetchData = async () => {
    try {
      setLoading(true);
      const headers = { "X-OPS-TOKEN": OPS_TOKEN };
      const [healthRes, statusRes, historyRes, alertsRes, stdoutRes, stderrRes] = await Promise.all([
        fetch(`/api/ops/health`, { headers }),
        fetch(`/api/ops/evergreen/status`, { headers }),
        fetch(`/api/ops/history?hours=24`, { headers }),
        fetch(`/api/ops/alerts?limit=50`, { headers }),
        fetch(`/api/ops/logs/stdout?limit=200`, { headers }).catch(() => null as any),
        fetch(`/api/ops/logs/stderr?limit=200`, { headers }).catch(() => null as any),
      ]);

      const rawHealth = healthRes?.ok ? await healthRes.json() : null;
      const rawStatus = statusRes?.ok ? await statusRes.json() : null;
      const statusText = (rawHealth?.service_status ?? rawStatus?.status ?? rawHealth?.status ?? "down");
      const service_status = typeof statusText === "string" ? statusText.toLowerCase() : "down";
      const last_heartbeat_age_sec =
        asNum(rawHealth?.last_heartbeat_age_sec ?? rawStatus?.heartbeat_sec_ago ?? rawStatus?.last_heartbeat_age_sec);
      setHealth({
        service_status,
        last_heartbeat_age_sec,
        last_heartbeat_ts: asNum(rawHealth?.last_heartbeat_ts ?? rawStatus?.last_heartbeat_ts),
        grade: rawStatus?.grade ?? rawHealth?.grade,
        mission: rawStatus?.mission ?? rawHealth?.mission,
        next_milestone: rawHealth?.next_milestone,
        next_milestone_eta: rawHealth?.next_milestone_eta ?? null,
        last_update_ts: rawStatus?.last_update_ts ?? rawHealth?.last_update_ts,
      } as any);
      if (rawStatus) setStatus(rawStatus);

      // history fetch 방어 및 필드 매핑
      let hist: any[] = [];
      try {
        if (historyRes?.ok) {
          const data = await historyRes.json();
          hist = (data.points || data.history || []).map((p: any) => ({
            ...p,
            ts: Number(p.ts),
            cumulative_runtime_sec:
              p.cumulative_runtime_sec ?? (p.runtime_h ? Number(p.runtime_h) * 3600 : undefined),
            progress_168h_pct: Number(p.progress_168h_pct ?? p.progress ?? 0),
            restart_count: Number(p.restart_count ?? 0),
          }));
        }
      } catch {
        hist = [];
      }
      // 정렬/중복 제거(그래프 튐 방지)
      hist.sort((a, b) => a.ts - b.ts);
      setHistory(hist);

      // alerts fetch 방어
      let alertsList: any[] = [];
      try {
        if (alertsRes?.ok) {
          const data = await alertsRes.json();
          alertsList = data.items || data.alerts || [];
        }
      } catch {
        alertsList = [];
      }
      setAlerts(alertsList);

      // stdout/stderr 채우기
      try {
        if (stdoutRes && stdoutRes.ok) setStdoutLines(pickLines(await stdoutRes.json()));
        else setStdoutLines([]);
      } catch {
        setStdoutLines([]);
      }

      try {
        if (stderrRes && stderrRes.ok) setStderrLines(pickLines(await stderrRes.json()));
        else setStderrLines([]);
      } catch {
        setStderrLines([]);
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  // Recent Events: WS(events) 실시간 수신
  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws/events");
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        setEvents(prev => [msg, ...prev].slice(0, 200));
      } catch {}
    };
    ws.onerror = () => {};
    return () => ws.close();
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // 10초마다 자동 갱신
    return () => clearInterval(interval);
  }, []);

  // 차트 다운샘플링: 2000개 이상이면 1/stride만 표시
  const getDownsampledHistory = () => {
    if (history.length <= 2000) return history;
    const stride = Math.ceil(history.length / 500); // 최대 500포인트
    return history.filter((_, i) => i % stride === 0);
  };

  // 운영 등급 배지 및 미션/마일스톤
  const getGradeBadge = () => {
    const grade = health?.grade || "BRONZE";
    const gradeColor: Record<string, string> = {
      "EVERGREEN": "bg-emerald-700 border-emerald-900",
      "GOLD": "bg-yellow-400 text-yellow-900 border-yellow-600",
      "SILVER": "bg-slate-400 text-slate-900 border-slate-500",
      "BRONZE": "bg-orange-400 text-orange-900 border-orange-600"
    };
    const color = gradeColor[grade] || "bg-gray-300 border-gray-400";
    return (
      <span className={`inline-flex items-center gap-1 ${color} text-xs font-bold px-3 py-1 rounded-full shadow-sm border ml-2`}>
        <span className="text-lg">🏆</span> {grade} GRADE
      </span>
    );
  };

  // 168H MISSION + next milestone/ETA
  const getMissionInfo = () => {
    if (!health) return null;
    const eta = health.next_milestone_eta;
    let etaStr = "";
    if (typeof eta === "number" && Number.isFinite(eta)) {
      const h = Math.floor(eta / 3600);
      const m = Math.floor((eta % 3600) / 60);
      etaStr = ` (ETA: ${h}h ${m}m)`;
    }
    return (
      <span className="ml-4 text-xs font-bold text-blue-700 bg-blue-100 px-2 py-1 rounded">
        168H MISSION
        {health.next_milestone ? (
          <> | Next: <span className="text-blue-900">{health.next_milestone}</span>{etaStr}</>
        ) : null}
      </span>
    );
  };


  useEffect(() => {
    const fetchData = async () => {
      try {
        const headers = { "X-OPS-TOKEN": OPS_TOKEN };
        const [healthRes, statusRes, historyRes, alertsRes] = await Promise.all([
          fetch(`${API_BASE}/health`, { headers }),
          fetch(`${API_BASE}/evergreen/status`, { headers }),
          fetch(`${API_BASE}/history?hours=24`, { headers }),
          fetch(`${API_BASE}/alerts?limit=50`, { headers }),
        ]);

        const rawHealth = healthRes.ok ? await healthRes.json() : null;
        const rawStatus = statusRes.ok ? await statusRes.json() : null;
        const statusText = (rawHealth?.service_status ?? rawStatus?.status ?? rawHealth?.status ?? "down");
        const service_status = typeof statusText === "string" ? statusText.toLowerCase() : "down";
        const last_heartbeat_age_sec =
          asNum(rawHealth?.last_heartbeat_age_sec ?? rawStatus?.last_heartbeat_age_sec);
        setHealth({
          service_status,
          last_heartbeat_age_sec,
          last_heartbeat_ts: asNum(rawHealth?.last_heartbeat_ts ?? rawStatus?.last_heartbeat_ts),
          grade: rawStatus?.grade ?? rawHealth?.grade,
          mission: rawStatus?.mission ?? rawHealth?.mission,
          next_milestone: rawHealth?.next_milestone,
          next_milestone_eta: rawHealth?.next_milestone_eta ?? null,
          last_update_ts: rawStatus?.last_update_ts ?? rawHealth?.last_update_ts,
        } as any);
        if (rawStatus) setStatus(rawStatus);

        // history fetch 방어 및 필드 매핑
        let hist = [];
        try {
          if (historyRes.ok) {
            const data = await historyRes.json();
            hist = (data.points || data.history || []).map((p: any) => ({
              ...p,
              cumulative_runtime_sec: p.cumulative_runtime_sec ?? (p.runtime_h ? p.runtime_h * 3600 : undefined),
            }));
          }
        } catch (e) {
          hist = [];
        }
        setHistory(hist);

        // alerts fetch 방어
        let alertsList = [];
        try {
          if (alertsRes.ok) {
            const data = await alertsRes.json();
            alertsList = data.items || data.alerts || [];
          }
        } catch (e) {
          alertsList = [];
        }
        setAlerts(alertsList);

        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const getDataMode = (): DataMode => {
    if (!health) return "DOWN";
    const age = health.last_heartbeat_age_sec;
    if (age === null) return "DOWN";
    if (age < 30 && health.service_status === "running") return "LIVE";
    if (age < 120) return "STALE";
    return "DOWN";
  };

  const getDataModeBadge = () => {
    const mode = getDataMode();
    const colors: Record<DataMode, string> = {
      LIVE: "bg-green-500 text-white",
      STALE: "bg-yellow-500 text-black",
      DOWN: "bg-red-500 text-white",
      DEMO: "bg-purple-500 text-white",
    };
    const icons: Record<DataMode, string> = {
      LIVE: "🟢",
      STALE: "🟡",
      DOWN: "🔴",
      DEMO: "🟣",
    };
    return (
      <Badge className={`${colors[mode]} font-bold text-sm px-3 py-1`}>
        {icons[mode]} {mode}
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      running: "default",
      stale: "secondary",
      down: "destructive",
      error: "destructive",
    };
    const key = typeof status === "string" && status.length > 0 ? status.toLowerCase() : "unknown";
    const label = key.toUpperCase();
    return (
      <Badge variant={variants[key] || "outline"} className="text-sm">
        {label}
      </Badge>
    );
  };

  // Severity 색상/아이콘
  const getSeverityColor = (sev: string) => {
    switch (sev) {
      case "critical": return "bg-pink-600 text-white border-pink-800";
      case "error": return "bg-red-600 text-white border-red-800";
      case "warn": return "bg-amber-200 text-amber-900 border-amber-400";
      case "success": return "bg-emerald-100 text-emerald-900 border-emerald-400";
      case "info": return "bg-slate-100 text-slate-800 border-slate-300";
      default: return "bg-gray-200 text-gray-700 border-gray-300";
    }
  };
  const getSeverityIcon = (sev: string) => {
    switch (sev) {
      case "critical": return <XCircle className="inline w-4 h-4 mr-1 text-pink-100 align-middle" />;
      case "error": return <XCircle className="inline w-4 h-4 mr-1 text-red-100 align-middle" />;
      case "warn": return <AlertCircle className="inline w-4 h-4 mr-1 text-amber-500 align-middle" />;
      case "success": return <CheckCircle2 className="inline w-4 h-4 mr-1 text-emerald-600 align-middle" />;
      case "info": return <Clock className="inline w-4 h-4 mr-1 text-slate-400 align-middle" />;
      default: return null;
    }
  };


  // 상태 변화 리스트 (status_change만)
  const statusChanges = alerts.filter(a => a.event === "status_change");

  // === 반드시 컴포넌트 스코프 내에 존재해야 함 ===
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <CheckCircle2 className="h-6 w-6 text-green-500" />;
      case "stale":
        return <AlertCircle className="h-6 w-6 text-yellow-500" />;
      case "down":
      case "error":
        return <XCircle className="h-6 w-6 text-red-500" />;
      default:
        return null;
    }
  };


  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold text-slate-900">Evergreen Ops Dashboard</h1>
            {getGradeBadge()}
            {getMissionInfo()}
          </div>
          <div className="flex items-center gap-4">
            {getDataModeBadge()}
            <div className="text-sm text-slate-500">
              Auto-refresh: 10s | Last update: {isClient ? (
                <span>{new Date().toLocaleTimeString("ko-KR")}</span>
              ) : (
                <span>--:--:--</span>
              )}
            </div>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Service Status */}
          <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-medium text-slate-600">Service Status</CardTitle>
              {status && getStatusIcon(String(status.status).toLowerCase())}
            </CardHeader>
            <CardContent>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{status && getStatusBadge(String(status.status).toLowerCase())}</div>
              <p className="mt-1 text-xs text-slate-500">
                Heartbeat: {typeof status?.heartbeat_sec_ago === "number"
                  ? `${status.heartbeat_sec_ago.toFixed(1)}s ago`
                  : "N/A"}
              </p>
            </CardContent>
          </Card>

          {/* Cumulative Runtime */}
          <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-medium text-slate-600">Cumulative Runtime</CardTitle>
              <TrendingUp className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              {(() => {
                const asNum = (v: any, fallback = 0) => (typeof v === "number" && Number.isFinite(v) ? v : fallback);
                const cumulativeRuntimeSec =
                  typeof (status as any)?.cumulative_runtime_sec === "number"
                    ? asNum((status as any).cumulative_runtime_sec, 0)
                    : asNum((status as any)?.cumulative_runtime_h, 0) * 3600;
                const cumulativeRuntimeH =
                  typeof (status as any)?.cumulative_runtime_h === "number"
                    ? asNum((status as any).cumulative_runtime_h, 0)
                    : cumulativeRuntimeSec / 3600;
                const targetH = asNum((status as any)?.target_h, 168);
                return <>
                  <div className="mt-1 text-2xl font-semibold text-slate-900">{cumulativeRuntimeH.toFixed(2)}h</div>
                  <p className="mt-1 text-xs text-slate-500">
                    {Math.floor(cumulativeRuntimeSec)}s | Target: {targetH}h
                  </p>
                </>;
              })()}
            </CardContent>
          </Card>

          {/* Progress */}
          <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-medium text-slate-600">Progress</CardTitle>
              {(() => {
                const progressPct =
                  typeof (status as any)?.progress_percent === "number"
                    ? asNum((status as any).progress_percent, 0)
                    : asNum((status as any)?.progress_pct, 0);
                return (
                  <div className="text-sm font-semibold text-blue-600">{progressPct.toFixed(2)}%</div>
                );
              })()}
            </CardHeader>
            <CardContent>
              {(() => {
                const progressPct =
                  typeof (status as any)?.progress_percent === "number"
                    ? asNum((status as any).progress_percent, 0)
                    : asNum((status as any)?.progress_pct, 0);
                const remainingH =
                  typeof (status as any)?.remaining_h === "number"
                    ? asNum((status as any).remaining_h, 0)
                    : asNum((status as any)?.remaining_hours, 0);
                return <>
                  <Progress value={progressPct} className="mt-2" />
                  <p className="mt-1 text-xs text-slate-500">
                    Remaining: {remainingH.toFixed(2)}h
                  </p>
                </>;
              })()}
            </CardContent>
          </Card>

          {/* Restart Count */}
          <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-medium text-slate-600">Restart Count</CardTitle>
              <AlertCircle className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{status?.restart_count || 0}</div>
              <p className="mt-1 text-xs text-slate-500">
                Ticks: {asNum((status as any)?.total_ticks, 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Milestones */}
        <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-xs font-medium text-slate-600">Milestones</CardTitle>
          </CardHeader>
          <CardContent>
            {(() => {
              const milestones = (status as any)?.milestones ?? {};
              const m24 = !!milestones["24h"];
              const m72 = !!milestones["72h"];
              const m168 = !!milestones["168h"];
              return (
                <div className="flex gap-4">
                  <div className={`flex-1 p-4 rounded-lg ${m24 ? "bg-green-100" : "bg-gray-100"}`}>
                    <div className="flex items-center gap-2">
                      {m24 ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <Clock className="h-5 w-5 text-gray-400" />
                      )}
                      <span className="font-semibold">24 Hours</span>
                    </div>
                  </div>
                  <div className={`flex-1 p-4 rounded-lg ${m72 ? "bg-green-100" : "bg-gray-100"}`}>
                    <div className="flex items-center gap-2">
                      {m72 ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <Clock className="h-5 w-5 text-gray-400" />
                      )}
                      <span className="font-semibold">72 Hours</span>
                    </div>
                  </div>
                  <div className={`flex-1 p-4 rounded-lg ${m168 ? "bg-green-100" : "bg-gray-100"}`}>
                    <div className="flex items-center gap-2">
                      {m168 ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <Clock className="h-5 w-5 text-gray-400" />
                      )}
                      <span className="font-semibold">168 Hours 🎯</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </CardContent>
        </Card>

        {/* Events & Logs Tabs */}
        <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-xs font-medium text-slate-600">Events & Logs</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="events" className="w-full">
              <TabsList>
                <TabsTrigger value="events">Recent Events ({events.length})</TabsTrigger>
                <TabsTrigger value="stdout">Stdout ({stdoutLines.length})</TabsTrigger>
                <TabsTrigger value="stderr">Stderr ({stderrLines.length})</TabsTrigger>
              </TabsList>

              <TabsContent value="events" className="mt-4">
                <div className="border rounded-lg overflow-hidden">
                  <div className="max-h-96 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-100 sticky top-0">
                        <tr className="text-xs font-semibold text-slate-700">
                          <th className="px-4 py-2 text-left">Timestamp</th>
                          <th className="px-4 py-2 text-left">Event</th>
                          <th className="px-4 py-2 text-left">Severity</th>
                          <th className="px-4 py-2 text-left">Runtime (h)</th>
                          <th className="px-4 py-2 text-left">Restarts</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 bg-white">
                        {events.map((event, idx) => (
                          <tr key={idx} className="text-xs text-slate-700 hover:bg-slate-50">
                            <td className="px-4 py-2">
                              {new Date(event.ts * 1000).toLocaleString()}
                            </td>
                            <td className="px-4 py-2 font-mono text-xs">{event.event || "-"}</td>
                            <td className="px-4 py-2">
                              <span className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold ${getSeverityColor(event.severity ?? "info")}`}>{event.severity || "info"}</span>
                            </td>
                            <td className="px-4 py-2">
                              {event.cumulative_runtime_sec ? (event.cumulative_runtime_sec / 3600).toFixed(2) : "-"}
                            </td>
                            <td className="px-4 py-2">{event.restart_count || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="stdout" className="mt-4">
                <div className="bg-black text-green-400 p-4 rounded-lg font-mono text-xs h-96 overflow-y-auto">
                  {stdoutLines.map((line, idx) => (
                    <div key={idx}>{line}</div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="stderr" className="mt-4">
                <div className="bg-black text-red-400 p-4 rounded-lg font-mono text-xs h-96 overflow-y-auto">
                  {stderrLines.map((line, idx) => (
                    <div key={idx}>{line}</div>
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {/* PHASE 24-5: History & Alerts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* History(24h) 라인차트 */}
        <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-xs font-medium text-slate-600">History (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ width: "100%", height: 260, minHeight: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={getDownsampledHistory()} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <XAxis dataKey="ts" tickFormatter={ts => new Date(ts * 1000).getHours() + ":" + String(new Date(ts * 1000).getMinutes()).padStart(2, "0")}/>
                  <YAxis dataKey="runtime_h" tickFormatter={v => v.toFixed(1)} width={60} />
                  <Tooltip labelFormatter={ts => new Date(ts * 1000).toLocaleString()} formatter={(v: any, n: any) => n === "runtime_h" && typeof v === "number" ? v.toFixed(2) + "h" : v} />
                  <Line type="monotone" dataKey="runtime_h" stroke="#2563eb" dot={false} name="Runtime (h)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* 상태 변화 리스트 */}
            <div className="mt-4">
              <div className="font-semibold mb-2">Status Changes (24h)</div>
              <ul className="space-y-1 text-sm">
                {statusChanges.length === 0 && <li className="text-gray-400">No status changes in 24h</li>}
                {statusChanges.map((ev, idx) => (
                  <li key={idx} className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded border ${getSeverityColor(ev.severity)}`}>{getSeverityIcon(ev.severity)}{ev.severity}</span>
                    <span>{ev.msg}</span>
                    <span className="text-gray-400">{new Date(ev.ts * 1000).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>

        {/* Alerts 패널 */}
        <Card className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-xs font-medium text-slate-600">Alerts (최근 20개)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-72 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="bg-slate-100 sticky top-0">
                  <tr className="text-xs font-semibold text-slate-700">
                    <th className="px-2 py-1 text-left">ts</th>
                    <th className="px-2 py-1 text-left">event</th>
                    <th className="px-2 py-1 text-left">severity</th>
                    <th className="px-2 py-1 text-left">msg</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {alerts.slice(0, 20).map((a, idx) => (
                    <tr key={idx} className="text-xs text-slate-700 hover:bg-slate-50">
                      <td className="px-2 py-1">{new Date(a.ts * 1000).toLocaleString()}</td>
                      <td className="px-2 py-1 font-mono text-xs">{a.event}</td>
                      <td className="px-2 py-1"><span className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold border ${getSeverityColor(a.severity)}`}>{getSeverityIcon(a.severity)}{a.severity}</span></td>
                      <td className="px-2 py-1 break-all">{a.msg}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
