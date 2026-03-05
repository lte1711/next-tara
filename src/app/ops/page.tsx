
"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, XCircle, AlertCircle, Clock, TrendingUp } from "lucide-react";

const OPS_TOKEN = process.env.NEXT_PUBLIC_OPS_TOKEN || "dev-ops-token-change-me";
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/ops";

// 타입 정의
interface HealthStatus {
  service_status: string;
  last_heartbeat_age_sec: number | null;
  last_heartbeat_ts?: number;
  grade?: string;
  mission?: string;
  next_milestone?: string;
  next_milestone_eta?: number | null;
  last_update_ts?: number;
}

interface EvergreenStatus {
  status: string;
  heartbeat_sec_ago?: number;
  last_heartbeat_age_sec?: number;
  last_heartbeat_ts?: number;
  grade?: string;
  mission?: string;
  cumulative_runtime_sec?: number;
  cumulative_runtime_h?: number;
  progress_percent?: number;
  progress_pct?: number;
  remaining_h?: number;
  remaining_hours?: number;
  restart_count?: number;
  target_h?: number;
  total_ticks?: number;
  last_update_ts?: number;
  milestones?: Record<string, boolean>;
}

interface Event {
  ts: number;
  event?: string;
  severity?: string;
  cumulative_runtime_sec?: number;
  restart_count?: number;
}

interface HistoryPoint {
  ts: number;
  runtime_h: number;
  cumulative_runtime_sec?: number;
  progress_168h_pct?: number;
  progress?: number;
  restart_count?: number;
}

interface AlertEvent {
  ts: number;
  event: string;
  severity: string;
  msg: string;
}

type DataMode = "LIVE" | "STALE" | "DOWN" | "DEMO";

// 이벤트 보관 최대 개수
const MAX_EVENTS = 500;

// Reconnect policy
const MAX_RECONNECT_ATTEMPTS = 10; // after this, backoff will pause until online/visibility

// (StrictMode protection removed) Rely on `wsRef` single-instance guard

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

// ===== LOG HELPERS (dedupe + maxN) =====
const normalizeLine = (s: any) => String(s ?? "").replace(/\r\n/g, "\n").trimEnd();

const mergeLines = (prev: string[], incoming: string[], maxN = 200) => {
  const p = Array.isArray(prev) ? prev.map(normalizeLine).filter(Boolean) : [];
  const inc = Array.isArray(incoming) ? incoming.map(normalizeLine).filter(Boolean) : [];

  // 빠른 dedupe: 최근 1000개만 set으로 관리
  const recent = p.slice(Math.max(0, p.length - 1000));
  const seen = new Set(recent);

  const out = [...p];
  for (const line of inc) {
    if (!line) continue;
    if (seen.has(line)) continue;
    out.push(line);
    seen.add(line);
  }

  // 최대 N 유지 (마지막 N줄)
  if (out.length > maxN) return out.slice(out.length - maxN);
  return out;
};

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
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
  const [, setLoading] = useState(true);
  const [, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [copied, setCopied] = useState<null | "stdout" | "stderr">(null);
  const [account, setAccount] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);

  // WS refs to avoid duplicate connections (StrictMode / HMR safe)
  const wsRef = useRef<WebSocket | null>(null);
  const wsConnectSeqRef = useRef(0);
  const connectingRef = useRef(false);
  const closingIntentRef = useRef(false);
  // (removed unused StrictMode ref)
  // WS single-connection lock
  const wsLockRef = useRef<'idle' | 'connecting' | 'open'>('idle');
  const reconnectTimerRef = useRef<number | null>(null);
  const lastEventRef = useRef<any>(null);
  const initialConnectTimerRef = useRef<number | null>(null);

  // --- WS backoff & close info ---
  const [closeCode, setCloseCode] = useState<number | null>(null);
  const [closeReason, setCloseReason] = useState<string>("");
  const [retryInMs, setRetryInMs] = useState<number | null>(null);

  const retryTimerRef = useRef<number | null>(null);
  const attemptRef = useRef<number>(0); // backoff attempt
  const aliveRef = useRef<boolean>(true); // unmount guard
  const [wsStatus, setWsStatus] = useState<"CONNECTING" | "OPEN" | "CLOSED">("CONNECTING");
  const prevSeqRef = useRef<number | null>(null);
  const [seqGap, setSeqGap] = useState<boolean>(false);
  const [seqGapMsg, setSeqGapMsg] = useState<string>("");

  const [killSwitch, setKillSwitch] = useState<boolean>(false);
  const [killMsg, setKillMsg] = useState<string>("");

  // 안정적인 WS URL 결정 (env 우선)
  // Expect NEXT_PUBLIC_WS_URL to be a base like ws://127.0.0.1:8100
  // and always append /ws/events exactly once. If env already includes
  // /ws/events, use it as-is.
  const WS_URL = useMemo(() => {
    const envBase = (process.env.NEXT_PUBLIC_WS_URL || '').trim();
    const defaultBase = 'ws://127.0.0.1:8100';
    const base = envBase.length > 0 ? envBase.replace(/\/$/, '') : defaultBase;
    return base.endsWith('/ws/events') ? base : `${base}/ws/events`;
  }, []);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    const loadInvestor = async () => {
      try {
        const acc = await fetch("http://127.0.0.1:8100/api/investor/account").then((r) => r.json());
        const tr = await fetch("http://127.0.0.1:8100/api/investor/trades/BTCUSDT").then((r) => r.json());
        setAccount(acc);
        setTrades(Array.isArray(tr) ? tr.slice(0, 10) : []);
      } catch {
        // ignore fetch errors
      }
    };

    loadInvestor();
    const interval = setInterval(loadInvestor, 3000);
    return () => clearInterval(interval);
  }, []);


  // fetchData: 모든 데이터 fetch (프록시 경로 사용, 10초마다 자동 갱신)
  const fetchData = async () => {
    try {
      setLoading(true);

      const headers = { "X-OPS-TOKEN": OPS_TOKEN };

      const [
        healthRes,
        statusRes,
        historyRes,
        alertsRes,
        stdoutRes,
        stderrRes,
      ] = await Promise.all([
        fetch(`${API_BASE}/health`, { headers }),
        fetch(`${API_BASE}/evergreen/status`, { headers }),
        fetch(`${API_BASE}/history?hours=24`, { headers }),
        fetch(`${API_BASE}/alerts?limit=50`, { headers }),
        fetch(`${API_BASE}/logs/stdout?limit=200`, { headers }),
        fetch(`${API_BASE}/logs/stderr?limit=200`, { headers }),
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

      // history
      let hist: any[] = [];
      try {
        if (historyRes?.ok) {
          const data = await historyRes.json();
          hist = (data.points || data.history || []).map((p: any) => ({
            ...p,
            ts: Number(p.ts),
            cumulative_runtime_sec: p.cumulative_runtime_sec ?? (p.runtime_h ? Number(p.runtime_h) * 3600 : undefined),
            progress_168h_pct: Number(p.progress_168h_pct ?? p.progress ?? 0),
            restart_count: Number(p.restart_count ?? 0),
          }));
        }
      } catch {
        hist = [];
      }
      hist.sort((a, b) => a.ts - b.ts);
      setHistory(hist);

      // alerts
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

      // logs
      const MAX_LOG_LINES = 300;
      try {
        if (stdoutRes && stdoutRes.ok) {
          const incoming = pickLines(await stdoutRes.json());
          setStdoutLines(prev => mergeLines(prev, incoming, MAX_LOG_LINES));
        } else {
          setStdoutLines([]);
        }
      } catch {
        setStdoutLines([]);
      }

      try {
        if (stderrRes && stderrRes.ok) {
          const incoming = pickLines(await stderrRes.json());
          setStderrLines(prev => mergeLines(prev, incoming, MAX_LOG_LINES));
        } else {
          setStderrLines([]);
        }
      } catch {
        setStderrLines([]);
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }

  }

  const eventKey = (e: any) => {
    const ts = Number(e?.ts) || 0;
    const ev = String(e?.event ?? "");
    const msg = String(e?.msg ?? "");
    const sev = String(e?.severity ?? "");
    const rt = Number(e?.cumulative_runtime_sec ?? e?.runtime_sec ?? 0) || 0;
    const rc = Number(e?.restart_count ?? 0) || 0;
    return `${ts}|${ev}|${sev}|${rc}|${rt}|${msg}`;
  };

  const pushEvent = (incoming: any) => {
    setEvents(prev => {
      const next = Array.isArray(prev) ? [...prev] : [];

      const k = eventKey(incoming);

      if (!incoming) return prev;
      // 중복 방지: 같은 key가 이미 존재하면 무시
      if (next.findIndex((e: any) => eventKey(e) === k) !== -1) return prev;

      const normalizedIncoming = {
        ts: Number(incoming?.ts) || Math.floor(Date.now() / 1000),
        event: incoming?.event ?? incoming?.type ?? "event",
        severity: incoming?.severity ?? "info",
        msg: incoming?.msg ?? "",
        cumulative_runtime_sec: incoming?.cumulative_runtime_sec ?? incoming?.runtime_sec,
        restart_count: incoming?.restart_count ?? 0,
        ...incoming,
      };

      // Seq gap detection (prefer explicit seq, fallback to ts)
      try {
        const hasSeq = incoming && (incoming?.seq !== undefined && incoming?.seq !== null);
        if (hasSeq) {
          const curSeq = Number(incoming.seq);
          if (Number.isFinite(curSeq) && prevSeqRef.current !== null) {
            if (curSeq - (prevSeqRef.current || 0) > 1) {
              setSeqGap(true);
              setSeqGapMsg(`gap ${prevSeqRef.current} -> ${curSeq}`);
            } else {
              setSeqGap(false);
              setSeqGapMsg("");
            }
          }
          prevSeqRef.current = curSeq;
        } else {
          // fallback: detect time gap > 120s
          const curTs = Number(normalizedIncoming.ts || 0);
          if (prevSeqRef.current !== null) {
            const prevTs = prevSeqRef.current;
            if (curTs - prevTs > 120) {
              setSeqGap(true);
              setSeqGapMsg(`time gap ${prevTs} -> ${curTs}`);
            } else {
              setSeqGap(false);
              setSeqGapMsg("");
            }
          }
          prevSeqRef.current = curTs;
        }
      } catch (e) {
        // ignore seq detect failures
      }

      // Kill-switch detection
      try {
        const evstr = String(normalizedIncoming.event ?? "").toLowerCase();
        const sev = String(normalizedIncoming.severity ?? "").toLowerCase();
        const hasKillFlag = normalizedIncoming?.kill_switch === true || normalizedIncoming?.payload?.kill_switch === true;
        const nestedEvent = String(normalizedIncoming?.payload?.event ?? "").toLowerCase();
        if (
          evstr.includes("kill") ||
          evstr.includes("kill_switch") ||
          nestedEvent.includes("kill") ||
          nestedEvent.includes("kill_switch") ||
          sev === "critical" ||
          hasKillFlag
        ) {
          setKillSwitch(true);
          // 메시지가 없다면 payload.msg 또는 kill_switch 플래그 기반 메시지 사용
          const msgCandidate = String(normalizedIncoming.msg ?? normalizedIncoming?.payload?.msg ?? (hasKillFlag ? "kill_switch" : "detected"));
          setKillMsg(msgCandidate);
        }
      } catch (e) {}

      next.push(normalizedIncoming);
      // ts 기준 정렬(혹시 out-of-order 들어오는 경우 대비)
      next.sort((a: any, b: any) => (Number(a?.ts) || 0) - (Number(b?.ts) || 0));

      // 최대 N 유지 (오래된 것부터 제거)
      if (next.length > MAX_EVENTS) {
        return next.slice(next.length - MAX_EVENTS);
      }
      return next;
    });
  };

  

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // 10초마다 자동 갱신
    return () => clearInterval(interval);
  }, []);

  // WS 연결 + 재시도(backoff) + close 정보 표시 (안전한 단일화)
  useEffect(() => {
    // 이미 소켓이 존재하면 절대 다시 연결 시도하지 않음
    if (wsRef.current) return;

    let cancelled = false;
    aliveRef.current = true;

    const clearRetryTimer = () => {
      if (retryTimerRef.current) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      setRetryInMs(null);
    };

    const safeClose = (ws: WebSocket | null) => {
      if (!ws) return;
      try {
        ws.onopen = null as any;
        ws.onmessage = null as any;
        ws.onerror = null as any;
        ws.onclose = null as any;
        ws.close();
        // 닫을 때 락 해제
        try { wsLockRef.current = 'idle'; } catch {}
      } catch {}
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      // Prevent endless fast retries: cap attempts
      if (attemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        console.warn("[WS] Max reconnect attempts reached; waiting for online/visibility");
        setRetryInMs(null);
        return;
      }

      const base = 1000;
      const max = 30000; // larger cap for production
      const exp = Math.min(max, base * Math.pow(2, attemptRef.current));
      const jitter = Math.floor(Math.random() * Math.min(1000, exp / 2));
      const wait = Math.max(500, exp + jitter);

      setRetryInMs(wait);
      attemptRef.current += 1;

      clearRetryTimer();
      retryTimerRef.current = window.setTimeout(() => {
        if (cancelled) return;
        // ensure only one reconnect timer active
        if (retryTimerRef.current) {
          window.clearTimeout(retryTimerRef.current);
          retryTimerRef.current = null;
        }
        connect();
      }, wait) as unknown as number;
    };

    // Network/visibility helpers: try immediate reconnect when user gets online or tab visible
    const onOnline = () => {
      try {
        if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
          attemptRef.current = 0; // reset attempts on network restore
          connect();
        }
      } catch (e) {}
    };

    const onVisibility = () => {
      try {
        if (document.visibilityState === 'visible') {
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            connect();
          }
        }
      } catch (e) {}
    };

    window.addEventListener && window.addEventListener('online', onOnline);
    document.addEventListener && document.addEventListener('visibilitychange', onVisibility);

    const connect = () => {
      if (cancelled) return;
      // prevent duplicate connections (StrictMode / rerender / retry storms)
      if (wsLockRef.current === 'connecting' || wsLockRef.current === 'open') return;
      wsLockRef.current = 'connecting';

      // 중복 connect 차단
      if (connectingRef.current) return;
      const cur = wsRef.current;
      if (cur && (cur.readyState === WebSocket.OPEN || cur.readyState === WebSocket.CONNECTING)) return;

      connectingRef.current = true;
      // reset closing intent for a fresh connect
      closingIntentRef.current = false;
      // increment visible connect counter
      wsConnectSeqRef.current += 1;
      const seq = wsConnectSeqRef.current;

      setWsStatus("CONNECTING");
      setCloseCode(null);
      setCloseReason("");
      clearRetryTimer();

      // 기존 소켓 강제 정리
      safeClose(wsRef.current);
      wsRef.current = null;

      console.log(`[WS] Connecting seq=${seq} to ${WS_URL} (attempt ${attemptRef.current + 1})`);

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        connectingRef.current = false;
        attemptRef.current = 0;
        setWsStatus("OPEN");
        setRetryInMs(null);
        // 락을 OPEN으로 표시
        wsLockRef.current = 'open';
        pushEvent({ ts: Math.floor(Date.now()/1000), event: "ws_connected", severity: "info", msg: "WebSocket connected" });
      };

      ws.onmessage = (ev) => {
        if (cancelled) return;
        try {
          const obj = JSON.parse(ev.data);
          // 디버그용 마지막 이벤트 보관
          lastEventRef.current = obj;
          try { (window as any).__lastEvent = obj; } catch {}
          try { (window as any)._lastEvent = obj; } catch {}
          // 즉시 KILL-SW 반영: 다양한 페이로드 형태를 포괄하여 즉시 UI 반영
          try {
            const evstr = String(obj?.event ?? obj?.type ?? "").toLowerCase();
            const sev = String(obj?.severity ?? "").toLowerCase();
            const nestedEvent = String(obj?.payload?.event ?? "").toLowerCase();
            const hasKillFlag = obj?.kill_switch === true || obj?.payload?.kill_switch === true;

            const killDetected = hasKillFlag || evstr.includes("kill") || nestedEvent.includes("kill") || sev === "critical";
            if (killDetected) {
              setKillSwitch(true);
              const m = String(obj?.msg ?? obj?.payload?.msg ?? "kill_switch");
              setKillMsg(m);
              console.warn("[OPS] KILL SWITCH ACTIVATED", m);
            }
          } catch (e) {}
          const normalized = {
            ts: Number(obj?.ts) || Math.floor(Date.now() / 1000),
            event: obj?.event ?? obj?.type ?? "event",
            severity: obj?.severity ?? "info",
            msg: obj?.msg ?? "",
            cumulative_runtime_sec: obj?.cumulative_runtime_sec ?? obj?.runtime_sec,
            restart_count: obj?.restart_count,
            ...obj,
          };
          pushEvent(normalized);
        } catch (e) {
          console.warn("[WS] Failed to parse message:", e);
          pushEvent({ ts: Math.floor(Date.now() / 1000), event: "ws_parse_error", severity: "warn", msg: String(ev.data ?? "") });
        }
      };

      ws.onerror = (e) => { if (!cancelled && !closingIntentRef.current) console.error("[WS] Error:", e); };

      ws.onclose = (ev) => {
        if (cancelled) return;
        connectingRef.current = false;
        // 닫힘 시 락 초기화
        wsLockRef.current = 'idle';
        setWsStatus("CLOSED");
        setCloseCode(ev.code ?? null);
        setCloseReason(ev.reason ?? "");
        pushEvent({ ts: Math.floor(Date.now() / 1000), event: "ws_disconnected", severity: "warn", msg: `WebSocket closed (code=${ev.code})` });

        // dev/StrictMode에서 발생하는 의도된 cleanup close면 재연결하지 않음
        if (closingIntentRef.current) return;

        // 정상 종료(1000)에서 재연결을 막고 싶으면 아래에서 체크
        // if (ev?.code === 1000) return;

        // 재연결 타이머 중복 방지
        if (reconnectTimerRef.current) {
          window.clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }

        // scheduleReconnect 사용 (기존 backoff 로직)
        scheduleReconnect();
      };
    };

    // Defer actual connect to next macrotask so StrictMode's mount->cleanup
    // cycle can cancel it before a real socket is created.
    initialConnectTimerRef.current = window.setTimeout(() => {
      initialConnectTimerRef.current = null;
      connect();
    }, 0) as unknown as number;

    return () => {
      cancelled = true;
      aliveRef.current = false;
      if (initialConnectTimerRef.current) {
        window.clearTimeout(initialConnectTimerRef.current);
        initialConnectTimerRef.current = null;
      }
      clearRetryTimer();
      connectingRef.current = false;
      // mark intent to close so onclose handler won't trigger reconnect
      closingIntentRef.current = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsLockRef.current = 'idle';
      safeClose(wsRef.current);
      wsRef.current = null;
      try { window.removeEventListener && window.removeEventListener('online', onOnline); } catch {}
      try { document.removeEventListener && document.removeEventListener('visibilitychange', onVisibility); } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [WS_URL]);

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

        <div className="rounded-md bg-slate-900 text-slate-100 p-4 shadow-sm">
          <h3 className="text-sm font-semibold mb-2">Investor Account (Binance Testnet)</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
            <div>Total Wallet: {account?.totalWalletBalance ?? "-"} USDT</div>
            <div>Available: {account?.availableBalance ?? "-"} USDT</div>
            <div>Unrealized PnL: {account?.totalUnrealizedProfit ?? "-"} USDT</div>
          </div>
          {trades.length > 0 ? (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-300">
                    <th className="py-1">Side</th>
                    <th className="py-1">Qty</th>
                    <th className="py-1">Price</th>
                    <th className="py-1">Realized PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t, i) => (
                    <tr key={i} className="border-t border-slate-800">
                      <td className="py-1">{t.side}</td>
                      <td className="py-1">{t.qty}</td>
                      <td className="py-1">{t.price}</td>
                      <td className="py-1">{t.realizedPnl}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-3 text-xs text-slate-400">No recent trades.</div>
          )}
        </div>

        {/* WS Monitor Panel (lightweight observability) */}
        <div className="flex items-center justify-start">
          <div className="rounded-md bg-white p-3 shadow-sm border flex items-center gap-6">
            <div className="text-sm font-mono">
              <div><span className="font-semibold">WS STATUS :</span> {wsStatus}</div>
              <div><span className="font-semibold">LAST SEQ  :</span> {events.length ? (events[events.length - 1].ts ?? "—") : "—"}</div>
              <div><span className="font-semibold">LAST EVT  :</span> {events.length ? (events[events.length - 1].event ?? "—") : "—"}</div>
              <div><span className="font-semibold">CONNECT #:</span> {wsConnectSeqRef.current}</div>
                <div>
                  <span className="font-semibold">SEQ GAP :</span>
                  {seqGap ? (
                    <span className="text-red-600 ml-2 font-semibold">YES ({seqGapMsg})</span>
                  ) : (
                    <span className="text-slate-500 ml-2">no</span>
                  )}
                </div>
                <div>
                  <span className="font-semibold">KILL-SW :</span>
                  {killSwitch ? (
                    <span className="ml-2 inline-flex items-center gap-2 text-red-600 font-semibold">
                      <span className="h-2 w-2 rounded-full bg-red-600 animate-pulse" />
                      {killMsg || "detected"}
                    </span>
                  ) : (
                    <span className="text-slate-500 ml-2">no</span>
                  )}
                </div>
              <div><span className="font-semibold">CLOSE CODE :</span> {closeCode ?? "-"}</div>
              <div><span className="font-semibold">CLOSE REASON :</span> {closeReason ? closeReason : "-"}</div>
              <div><span className="font-semibold">RETRY IN :</span> {retryInMs ?? "-"}</div>
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
                      <thead className="bg-slate-100 sticky top-0 z-10">
                        <tr className="text-xs font-semibold text-slate-700">
                          <th className="px-4 py-2 text-left w-[170px]">Timestamp</th>
                          <th className="px-4 py-2 text-left w-[160px]">Event</th>
                          <th className="px-4 py-2 text-left w-[120px]">Severity</th>
                          <th className="px-4 py-2 text-left w-[120px]">Runtime (h)</th>
                          <th className="px-4 py-2 text-left w-[90px]">Restarts</th>
                        </tr>
                      </thead>

                      <tbody className="divide-y divide-slate-200 bg-white">
                        {(events ?? []).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                              No events yet (waiting for WS stream)
                            </td>
                          </tr>
                        ) : (
                          (events ?? [])
                            .slice() // 원본 불변
                            .sort((a: any, b: any) => (Number(b?.ts) || 0) - (Number(a?.ts) || 0)) // 최신 우선
                            .map((event: any, idx: number) => {
                              const tsNum = Number(event?.ts);
                              const tsText = Number.isFinite(tsNum)
                                ? new Date(tsNum * 1000).toLocaleString()
                                : "-";
                              const ev = String(event?.event ?? "");
                              const sev = String(event?.severity ?? "info");
                              const rtSec =
                                Number(event?.cumulative_runtime_sec ?? event?.runtime_sec ?? 0) || 0;
                              const rtH = rtSec > 0 ? (rtSec / 3600).toFixed(2) : "-";
                              const rc = event?.restart_count ?? "-";
                              const msg = String(event?.msg ?? "");

                              return (
                                <tr key={`${tsNum || "na"}-${idx}`} className="text-slate-700 hover:bg-slate-50">
                                  <td className="px-4 py-2 whitespace-nowrap">{tsText}</td>

                                  <td className="px-4 py-2">
                                    <div className="font-mono text-[11px]">{ev || "-"}</div>
                                    {msg ? (
                                      <div className="text-[11px] text-slate-500 break-words whitespace-pre-wrap">
                                        {msg}
                                      </div>
                                    ) : null}
                                  </td>

                                  <td className="px-4 py-2">
                                    <span
                                      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold border ${getSeverityColor(
                                        sev
                                      )}`}
                                    >
                                      {getSeverityIcon(sev)}
                                      {sev}
                                    </span>
                                  </td>

                                  <td className="px-4 py-2">{rtH}</td>
                                  <td className="px-4 py-2">{String(rc)}</td>
                                </tr>
                              );
                            })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="stdout" className="mt-4">
                <div className="border rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between gap-2 bg-slate-50 px-4 py-2 border-b">
                    <div className="text-xs font-medium text-slate-600">Stdout (최근 {stdoutLines.length} lines)</div>

                    <div className="flex items-center gap-2">
                      {copied === "stdout" ? (
                        <span className="text-[11px] text-emerald-600 font-semibold">COPIED</span>
                      ) : null}

                      <button
                        type="button"
                        className="text-[11px] px-2 py-1 border rounded-md hover:bg-slate-50 bg-white"
                        onClick={async () => {
                          const ok = await copyToClipboard((stdoutLines ?? []).join("\n"));
                          if (ok) {
                            setCopied("stdout");
                            setTimeout(() => setCopied(null), 1200);
                          }
                        }}
                        disabled={(stdoutLines ?? []).length === 0}
                        title="Copy stdout"
                      >
                        Copy
                      </button>

                      <button
                        type="button"
                        className="text-[11px] px-2 py-1 border rounded-md hover:bg-slate-50 bg-white"
                        onClick={() => setStdoutLines([])}
                        disabled={(stdoutLines ?? []).length === 0}
                        title="Clear stdout"
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  <div className="bg-black text-green-400 p-4 font-mono text-xs h-96 overflow-y-auto">
                    {(stdoutLines ?? []).length === 0 ? (
                      <div className="text-slate-500 p-4">No stdout yet.</div>
                    ) : (
                      <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words">
                        {(stdoutLines ?? []).join("\n")}
                      </pre>
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="stderr" className="mt-4">
                <div className="border rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between gap-2 bg-slate-50 px-4 py-2 border-b">
                    <div className="text-xs font-medium text-slate-600">Stderr (최근 {stderrLines.length} lines)</div>

                    <div className="flex items-center gap-2">
                      {copied === "stderr" ? (
                        <span className="text-[11px] text-emerald-600 font-semibold">COPIED</span>
                      ) : null}

                      <button
                        type="button"
                        className="text-[11px] px-2 py-1 border rounded-md hover:bg-slate-50 bg-white"
                        onClick={async () => {
                          const ok = await copyToClipboard((stderrLines ?? []).join("\n"));
                          if (ok) {
                            setCopied("stderr");
                            setTimeout(() => setCopied(null), 1200);
                          }
                        }}
                        disabled={(stderrLines ?? []).length === 0}
                        title="Copy stderr"
                      >
                        Copy
                      </button>

                      <button
                        type="button"
                        className="text-[11px] px-2 py-1 border rounded-md hover:bg-slate-50 bg-white"
                        onClick={() => setStderrLines([])}
                        disabled={(stderrLines ?? []).length === 0}
                        title="Clear stderr"
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  <div className="bg-black text-red-400 p-4 font-mono text-xs h-96 overflow-y-auto">
                    {(stderrLines ?? []).length === 0 ? (
                      <div className="text-slate-500 p-4">No stderr yet.</div>
                    ) : (
                      <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words">
                        {(stderrLines ?? []).join("\n")}
                      </pre>
                    )}
                  </div>
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
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={getDownsampledHistory()}
                  margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
                >
                  {/* X: ts(sec) → HH:MM */}
                  <XAxis
                    dataKey="ts"
                    tickFormatter={(ts: any) => {
                      const v = Number(ts);
                      if (!Number.isFinite(v)) return "";
                      const d = new Date(v * 1000);
                      const hh = String(d.getHours()).padStart(2, "0");
                      const mm = String(d.getMinutes()).padStart(2, "0");
                      return `${hh}:${mm}`;
                    }}
                    minTickGap={24}
                  />

                  {/* Y: runtime_h */}
                  <YAxis
                    tickFormatter={(v: any) => {
                      const n = Number(v);
                      return Number.isFinite(n) ? n.toFixed(1) : "";
                    }}
                    width={56}
                    domain={["auto", "auto"]}
                  />

                  <Tooltip
                    labelFormatter={(ts: any) => {
                      const v = Number(ts);
                      if (!Number.isFinite(v)) return "";
                      return new Date(v * 1000).toLocaleString();
                    }}
                    formatter={(value: any, name: any) => {
                      const n = Number(value);
                      if (name === "Runtime (h)" && Number.isFinite(n)) return [`${n.toFixed(2)}h`, name];
                      if (name === "Progress (%)" && Number.isFinite(n)) return [`${n.toFixed(2)}%`, name];
                      return [String(value), String(name)];
                    }}
                  />

                  {/* Runtime 라인 */}
                  <Line
                    type="monotone"
                    dataKey="runtime_h"
                    dot={false}
                    name="Runtime (h)"
                    stroke="#2563eb"
                    isAnimationActive={false}
                  />

                  {/* (옵션) Progress 라인도 같이 보고 싶으면 주석 해제:
                  <Line
                    type="monotone"
                    dataKey="progress"
                    dot={false}
                    name="Progress (%)"
                    stroke="#16a34a"
                    isAnimationActive={false}
                  />
                  */}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* 상태 변화 리스트 */}
            <div className="mt-4">
              <div className="font-semibold mb-2">Status Changes (24h)</div>
              <ul className="space-y-1 text-sm">
                {statusChanges.length === 0 && (
                  <li className="text-gray-400">No status changes in 24h</li>
                )}

                {statusChanges.map((ev, idx) => (
                  <li key={idx} className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded border ${getSeverityColor(ev.severity)}`}>
                      {getSeverityIcon(ev.severity)}
                      {ev.severity}
                    </span>
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
            <div className="max-h-72 overflow-y-auto rounded-md border border-slate-200">
              <table className="w-full text-xs">
                <thead className="bg-slate-100 sticky top-0 z-10">
                  <tr className="text-xs font-semibold text-slate-700">
                    <th className="px-2 py-2 text-left w-[160px]">ts</th>
                    <th className="px-2 py-2 text-left w-[140px]">event</th>
                    <th className="px-2 py-2 text-left w-[120px]">severity</th>
                    <th className="px-2 py-2 text-left">msg</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-200 bg-white">
                  {(alerts ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-6 text-center text-slate-400">
                        No alerts
                      </td>
                    </tr>
                  ) : (
                    (alerts ?? [])
                      .slice(0, 20)
                      // ts 내림차순(최신 우선) 안전 정렬
                      .sort((a: any, b: any) => (Number(b?.ts) || 0) - (Number(a?.ts) || 0))
                      .map((a: any, idx: number) => {
                        const tsNum = Number(a?.ts);
                        const tsText = Number.isFinite(tsNum)
                          ? new Date(tsNum * 1000).toLocaleString()
                          : "-";
                        const ev = String(a?.event ?? "");
                        const sev = String(a?.severity ?? "info");
                        const msg = String(a?.msg ?? "");

                        return (
                          <tr key={`${tsNum || "na"}-${idx}`} className="text-slate-700 hover:bg-slate-50">
                            <td className="px-2 py-2 whitespace-nowrap">{tsText}</td>

                            <td className="px-2 py-2">
                              <span className="font-mono text-[11px] text-slate-700">
                                {ev || "-"}
                              </span>
                            </td>

                            <td className="px-2 py-2">
                              <span
                                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold border ${getSeverityColor(
                                  sev
                                )}`}
                                title={sev}
                              >
                                {getSeverityIcon(sev)}
                                {sev}
                              </span>
                            </td>

                            <td className="px-2 py-2">
                              <div className="break-words whitespace-pre-wrap leading-5">
                                {msg || "-"}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
