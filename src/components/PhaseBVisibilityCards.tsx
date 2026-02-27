"use client";

import { useWebSocket, WSEvent } from "@/hooks/useWebSocket";
import {
  apiClient,
  ContractHealth,
  ContractState,
  V1FillItem,
  V1OrderItem,
  V1PnlResponse,
} from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

type ProgressCardProps = {
  loading: boolean;
  error: string | null;
  uptimeSec: number;
  sessionState: string;
  processedEvents: number;
  restartCount: number;
  wsConnected: boolean;
  liveEventCount: number;
  lastEventAgeSec: number | null;
  onRetry: () => void;
};

type TradesCardProps = {
  loading: boolean;
  error: string | null;
  orders: V1OrderItem[];
  fills: V1FillItem[];
  onRetry: () => void;
};

type PnlCardProps = {
  loading: boolean;
  error: string | null;
  pnl: V1PnlResponse | null;
  pmxRealized: number | null;
  onRetry: () => void;
};

function ErrorBadge({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <span className="inline-flex items-center rounded border border-danger px-2 py-0.5 text-[11px] text-danger">
      Contract error
    </span>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-2">
      <div className="h-3 rounded bg-panel-2" />
      <div className="h-3 rounded bg-panel-2" />
      <div className="h-3 rounded bg-panel-2" />
    </div>
  );
}

function Sparkline({
  points,
}: {
  points: Array<{ ts: number; equity: number }>;
}) {
  if (!points.length) {
    return <div className="text-xs text-muted">No equity points</div>;
  }

  const values = points.map((point) => point.equity);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;

  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 100;
      const y = 100 - ((point.equity - minValue) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      viewBox="0 0 100 100"
      className="h-16 w-full rounded bg-panel-2 p-1"
      preserveAspectRatio="none"
    >
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        points={path}
        className="text-accent"
      />
    </svg>
  );
}

export function ProgressCard(props: ProgressCardProps) {
  const {
    loading,
    error,
    uptimeSec,
    sessionState,
    processedEvents,
    restartCount,
    wsConnected,
    liveEventCount,
    lastEventAgeSec,
    onRetry,
  } = props;

  return (
    <article className="rounded-lg border border-border-subtle bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Progress</h3>
        <ErrorBadge error={error} />
      </div>
      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Session</span>
            <span>{sessionState}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Uptime(s)</span>
            <span>{uptimeSec.toFixed(1)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Events</span>
            <span>{processedEvents}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Live WS</span>
            <span className="inline-flex items-center gap-1">
              <span
                className={`h-2 w-2 rounded-full ${wsConnected ? "animate-pulse bg-ok" : "bg-danger"}`}
              />
              {wsConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Live Events</span>
            <span>{liveEventCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Last Event</span>
            <span>
              {lastEventAgeSec === null
                ? "-"
                : `${lastEventAgeSec.toFixed(0)}s ago`}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Restarts</span>
            <span>{restartCount}</span>
          </div>
        </div>
      )}
      {error ? (
        <button
          className="mt-3 rounded border border-border-subtle px-2 py-1 text-xs text-muted hover:text-text"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </article>
  );
}

export function TradesCard(props: TradesCardProps) {
  const { loading, error, orders, fills, onRetry } = props;

  return (
    <article className="rounded-lg border border-border-subtle bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Trades</h3>
        <ErrorBadge error={error} />
      </div>
      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-3 text-sm">
          <div>
            <div className="mb-1 text-xs text-muted">
              Recent Orders ({orders.length})
            </div>
            <div className="max-h-24 space-y-1 overflow-auto">
              {orders.slice(0, 5).map((order) => (
                <div
                  key={order.order_id}
                  className="flex justify-between text-xs"
                >
                  <span>{order.symbol}</span>
                  <span>
                    {order.side} {order.status}
                  </span>
                </div>
              ))}
              {orders.length === 0 ? (
                <div className="text-xs text-muted">No orders</div>
              ) : null}
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-muted">
              Recent Fills ({fills.length})
            </div>
            <div className="max-h-24 space-y-1 overflow-auto">
              {fills.slice(0, 5).map((fill) => (
                <div
                  key={fill.trade_id}
                  className="flex justify-between text-xs"
                >
                  <span>{fill.symbol}</span>
                  <span>
                    {fill.qty}@{fill.price}
                  </span>
                </div>
              ))}
              {fills.length === 0 ? (
                <div className="text-xs text-muted">No fills</div>
              ) : null}
            </div>
          </div>
        </div>
      )}
      {error ? (
        <button
          className="mt-3 rounded border border-border-subtle px-2 py-1 text-xs text-muted hover:text-text"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </article>
  );
}

export function PnlCard(props: PnlCardProps) {
  const { loading, error, pnl, pmxRealized, onRetry } = props;
  const ssot = pmxRealized ?? null;
  const ssotColor =
    ssot === null ? "" : ssot >= 0 ? "text-emerald-600" : "text-red-500";

  return (
    <article className="rounded-lg border border-border-subtle bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">PnL</h3>
        <ErrorBadge error={error} />
      </div>
      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted font-semibold">
              Ledger Realized (SSOT)
            </span>
            <span className={`font-bold ${ssotColor}`}>
              {(() => {
                const v =
                  typeof pnl?.realized_pnl === "number"
                    ? pnl.realized_pnl
                    : null;
                return v === null
                  ? "-"
                  : (v >= 0 ? "+" : "") + v.toFixed(4) + " USDT";
              })()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted text-xs">Unrealized</span>
            <span className="text-xs">
              {(pnl?.unrealized_pnl ?? 0).toFixed(4)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted text-xs">Worst DD</span>
            <span className="text-xs">{(pnl?.worst_dd ?? 0).toFixed(4)}</span>
          </div>
          <div className="border-t border-border-subtle pt-1">
            <div className="mb-1 text-[10px] text-muted">
              Equity curve (aux 쨌 Binance rp)
            </div>
            <Sparkline points={pnl?.equity_curve ?? []} />
          </div>
        </div>
      )}
      {error ? (
        <button
          className="mt-3 rounded border border-border-subtle px-2 py-1 text-xs text-muted hover:text-text"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </article>
  );
}

type PmxCardProps = {
  summary: Record<string, unknown>;
  events: Record<string, unknown>[];
};

function toKST(ts: string): string {
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts.slice(11, 19);
    return d.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "Asia/Seoul",
    });
  } catch {
    return ts.slice(11, 19);
  }
}

function PmxCard({ summary, events }: PmxCardProps) {
  const pnl =
    typeof summary.session_realized_pnl === "number"
      ? summary.session_realized_pnl
      : 0;
  const posOpen = !!summary.position_open;
  const killed = !!summary.kill;
  return (
    <article className="rounded-lg border border-border-subtle bg-panel p-4 col-span-full">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold text-text-strong">PROFITMAX v1</h3>
        <span
          className={
            "inline-flex items-center rounded px-2 py-0.5 text-[11px] font-bold " +
            (killed
              ? "bg-red-200 text-red-800"
              : posOpen
                ? "bg-green-200 text-green-800"
                : "bg-blue-100 text-blue-800")
          }
        >
          {killed ? "KILL" : posOpen ? "IN POSITION" : "WATCHING"}
        </span>
        <span
          className={
            "inline-flex items-center rounded px-2 py-0.5 text-[11px] font-bold " +
            (pnl >= 0
              ? "bg-emerald-100 text-emerald-800"
              : "bg-red-100 text-red-800")
          }
        >
          {"PnL: " + (pnl >= 0 ? "+" : "") + pnl.toFixed(4) + " USDT"}
        </span>
      </div>
      <div className="max-h-48 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-panel-2">
            <tr className="text-xs font-semibold text-text-strong">
              <th className="px-2 py-1 text-left">Time</th>
              <th className="px-2 py-1 text-left">Event</th>
              <th className="px-2 py-1 text-left">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {events.map((ev, idx) => {
              const t = String(ev.event_type ?? "");
              const p = (ev.payload as Record<string, unknown>) ?? {};
              const d =
                t === "ENTRY"
                  ? String(p.side) +
                    " " +
                    String(p.qty) +
                    " BTC @ " +
                    String(p.entry_price) +
                    " | " +
                    String(p.strategy_id) +
                    " (" +
                    String(p.regime) +
                    ")"
                  : t === "EXIT"
                    ? "pnl=" +
                      (typeof p.pnl === "number"
                        ? (p.pnl as number).toFixed(4)
                        : "-") +
                      " reason=" +
                      String(p.reason)
                    : t === "HEARTBEAT"
                      ? "price=" +
                        String(p.price) +
                        " regime=" +
                        String(p.regime) +
                        " pnl=" +
                        String(p.session_realized_pnl)
                      : t === "QTY_ADJUSTED"
                        ? String(p.qty_before) +
                          " -> " +
                          String(p.qty_after) +
                          " BTC"
                        : JSON.stringify(p).slice(0, 70);
              const bg =
                t === "ENTRY"
                  ? "bg-green-50"
                  : t === "EXIT"
                    ? "bg-blue-50"
                    : t === "KILL_SWITCH"
                      ? "bg-red-50"
                      : "";
              return (
                <tr
                  key={idx}
                  className={"text-xs text-text hover:bg-panel-2 " + bg}
                >
                  <td className="px-2 py-1 font-mono">
                    {String(ev.ts ?? "").slice(11, 19)}
                  </td>
                  <td className="px-2 py-1 font-bold">{t}</td>
                  <td className="px-2 py-1 text-muted">{d}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </article>
  );
}

export default function PhaseBVisibilityCards() {
  const [loadingProgress, setLoadingProgress] = useState(true);
  const [loadingTrades, setLoadingTrades] = useState(true);
  const [loadingPnl, setLoadingPnl] = useState(true);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [pnlError, setPnlError] = useState<string | null>(null);

  const [contractHealth, setContractHealth] = useState<ContractHealth | null>(
    null,
  );
  const [contractState, setContractState] = useState<ContractState | null>(
    null,
  );
  const [orders, setOrders] = useState<V1OrderItem[]>([]);
  const [fills, setFills] = useState<V1FillItem[]>([]);
  const [pnl, setPnl] = useState<V1PnlResponse | null>(null);
  const [processedEvents, setProcessedEvents] = useState(0);
  const [uptimeBaseSec, setUptimeBaseSec] = useState(0);
  const [uptimeSyncedAtMs, setUptimeSyncedAtMs] = useState<number | null>(null);
  const [displayUptimeSec, setDisplayUptimeSec] = useState(0);
  const [wsUrl, setWsUrl] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const [liveEventCount, setLiveEventCount] = useState(0);
  const [lastEventAtMs, setLastEventAtMs] = useState<number | null>(null);
  const [lastEventAgeSec, setLastEventAgeSec] = useState<number | null>(null);

  const [pmxSummary, setPmxSummary] = useState<Record<string, unknown>>({});
  const [pmxEvents, setPmxEvents] = useState<Record<string, unknown>[]>([]);

  const load = useCallback(async () => {
    try {
      setLoadingProgress(true);
      setProgressError(null);
      const [healthData, stateData, risksData] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getState(),
        apiClient.getRisks(20),
      ]);
      if (!healthData || !stateData) {
        setProgressError("v1_progress_unavailable");
      }
      setContractHealth(healthData);
      setContractState(stateData);
      setProcessedEvents(risksData?.count ?? 0);
      const fetchedUptime = stateData?.freshness.checkpoint_age_sec ?? 0;
      setUptimeBaseSec(fetchedUptime);
      setUptimeSyncedAtMs(Date.now());
      setDisplayUptimeSec(fetchedUptime);
    } catch {
      setProgressError("v1_progress_error");
    } finally {
      setLoadingProgress(false);
    }

    try {
      setLoadingTrades(true);
      setTradesError(null);
      const [ordersData, fillsData] = await Promise.all([
        apiClient.getOrders(10),
        apiClient.getFills(10),
      ]);
      if (!ordersData || !fillsData) {
        setTradesError("v1_trades_unavailable");
      }
      setOrders(ordersData?.items ?? []);
      setFills(fillsData?.items ?? []);
    } catch {
      setTradesError("v1_trades_error");
    } finally {
      setLoadingTrades(false);
    }

    try {
      setLoadingPnl(true);
      setPnlError(null);
      const pnlData = await apiClient.getPnl();
      if (!pnlData) {
        setPnlError("v1_pnl_unavailable");
      }
      setPnl(pnlData);
    } catch {
      setPnlError("v1_pnl_error");
    } finally {
      setLoadingPnl(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      load();
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [load]);

  useEffect(() => {
    if (uptimeSyncedAtMs === null) {
      setDisplayUptimeSec(uptimeBaseSec);
      return;
    }
    const intervalId = window.setInterval(() => {
      const elapsedSec = (Date.now() - uptimeSyncedAtMs) / 1000;
      setDisplayUptimeSec(uptimeBaseSec + elapsedSec);
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [uptimeBaseSec, uptimeSyncedAtMs]);

  useEffect(() => {
    if (lastEventAtMs === null) {
      setLastEventAgeSec(null);
      return;
    }
    const tick = () => {
      setLastEventAgeSec((Date.now() - lastEventAtMs) / 1000);
    };
    tick();
    const intervalId = window.setInterval(tick, 1000);
    return () => window.clearInterval(intervalId);
  }, [lastEventAtMs]);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsEnv =
      process.env.NEXT_PUBLIC_WS_URL || process.env.NEXT_PUBLIC_API_WS;
    const finalUrl = wsEnv
      ? wsEnv.includes("/ws/events")
        ? wsEnv
        : `${wsEnv.replace(/\/+$/, "")}/ws/events`
      : `${protocol}//${window.location.hostname}:8100/ws/events`;
    setWsUrl(finalUrl);
  }, []);

  const handleWSMessage = useCallback((event: WSEvent) => {
    setLiveEventCount((previous) => previous + 1);
    const eventTimeMs = Date.now();
    setLastEventAtMs(eventTimeMs);
    (window as Window & { __lastEvent?: WSEvent }).__lastEvent = event;
  }, []);

  useWebSocket({
    url: wsUrl,
    onMessage: handleWSMessage,
    onConnect: () => setWsConnected(true),
    onDisconnect: () => setWsConnected(false),
    onError: () => setWsConnected(false),
  });

  useEffect(() => {
    const fetchPmx = async () => {
      try {
        const r = await fetch("/api/profitmax/status?limit=20");
        if (r.ok) {
          const data = await r.json();
          setPmxSummary((data.summary as Record<string, unknown>) ?? {});
          setPmxEvents((data.events as Record<string, unknown>[]) ?? []);
        }
      } catch {
        /* ignore */
      }
    };
    fetchPmx();
    const iv = window.setInterval(fetchPmx, 5000);
    return () => window.clearInterval(iv);
  }, []);

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
      <ProgressCard
        loading={loadingProgress}
        error={progressError}
        uptimeSec={displayUptimeSec}
        sessionState={contractHealth?.status ?? "UNKNOWN"}
        processedEvents={processedEvents}
        restartCount={contractState?.counters.restart_count ?? 0}
        wsConnected={wsConnected}
        liveEventCount={liveEventCount}
        lastEventAgeSec={lastEventAgeSec}
        onRetry={load}
      />
      <TradesCard
        loading={loadingTrades}
        error={tradesError}
        orders={orders}
        fills={fills}
        onRetry={load}
      />
      <PnlCard
        loading={loadingPnl}
        error={pnlError}
        pnl={pnl}
        pmxRealized={
          typeof pmxSummary.session_realized_pnl === "number"
            ? pmxSummary.session_realized_pnl
            : null
        }
        onRetry={load}
      />
      <PmxCard summary={pmxSummary} events={pmxEvents} />
    </div>
  );
}

