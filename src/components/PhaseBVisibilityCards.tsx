"use client";

import Link from "next/link";
import { useWebSocket, WSEvent } from "@/hooks/useWebSocket";
import {
  apiClient,
  ContractHealth,
  ContractState,
  V1FillItem,
  V1OrderItem,
  V1PnlResponse,
} from "@/lib/api";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PH7CObservabilityCard from "@/components/PH7CObservabilityCard";

type ProgressCardProps = {
  loading: boolean;
  error: string | null;
  uptimeSec: number;
  sessionState: string;
  processedEvents: number;
  restartCount: number;
  wsConnected: boolean;
  wsFrameCount: number;
  wsHeartbeatAgeSec: number | null;
  dataChangeAgeSec: number | null;
  lastChangedFields: string | null;
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
      className="h-16 min-w-0 w-full rounded-xl bg-nt-surface-2 p-1"
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
    wsFrameCount,
    wsHeartbeatAgeSec,
    dataChangeAgeSec,
    lastChangedFields,
    onRetry,
  } = props;

  return (
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
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
            <span className="text-muted">WS Frames</span>
            <span>{wsFrameCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">WS Heartbeat</span>
            <span>
              {wsHeartbeatAgeSec === null
                ? "-"
                : `${wsHeartbeatAgeSec.toFixed(0)}s ago`}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Data Changed</span>
            <span>
              {dataChangeAgeSec === null
                ? "-"
                : `${dataChangeAgeSec.toFixed(0)}s ago`}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Changed Fields</span>
            <span className="max-w-[150px] truncate text-right">
              {lastChangedFields ?? "-"}
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
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
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
  const sessionRealized = pmxRealized ?? null;
  const ledgerRealized =
    typeof pnl?.realized_pnl === "number" ? pnl.realized_pnl : null;
  const sessionColor =
    sessionRealized === null
      ? ""
      : sessionRealized >= 0
        ? "text-emerald-600"
        : "text-red-500";
  const ledgerColor =
    ledgerRealized === null
      ? ""
      : ledgerRealized >= 0
        ? "text-emerald-600"
        : "text-red-500";

  return (
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
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
              Session Realized (Profitmax)
              <span className="ml-1 rounded bg-blue-100 px-1 py-0.5 text-[10px] text-blue-800">
                SESSION
              </span>
            </span>
            <span className={`font-bold ${sessionColor}`}>
              {sessionRealized === null
                ? "-"
                : (sessionRealized >= 0 ? "+" : "") +
                  sessionRealized.toFixed(4) +
                  " USDT"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted font-semibold">
              Ledger Realized (Account, cumulative)
              <span className="ml-1 rounded bg-slate-200 px-1 py-0.5 text-[10px] text-slate-800">
                CUMULATIVE
              </span>
            </span>
            <span className={`font-bold ${ledgerColor}`}>
              {ledgerRealized === null
                ? "-"
                : (ledgerRealized >= 0 ? "+" : "") +
                  ledgerRealized.toFixed(4) +
                  " USDT"}
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
              Equity curve (aux Binance rp)
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

const MAX_GUARDRAIL_EVENTS = 200;

type HaStatusPayload = {
  source?: string;
  active_stamp?: string | null;
  stamp?: string | null;
  age_sec?: number | null;
  data_ts?: string | null;
  ha_eval?: number | null;
  ha_pass?: number | null;
  ha_skip?: number | null;
  delta_eval?: number | null;
  delta_pass?: number | null;
  delta_skip?: number | null;
  engine_alive?: boolean;
  last_order_ts?: number;
  last_fill_ts?: number;
  open_orders_count?: number;
  canceled_count?: number;
  rejected_count?: number;
  blocked_count?: number;
  kill_switch?: boolean;
  risk_level?: string;
  downgrade_level?: number;
};

function getPmxStopReason(events: Record<string, unknown>[]): string | null {
  for (const ev of events) {
    const eventType = String(ev.event_type ?? "");
    const payload = (ev.payload as Record<string, unknown>) ?? {};
    if (eventType === "STOPPED_EARLY") {
      const reason = String(payload.reason ?? "guardrail");
      if (reason === "max_consecutive_sl") {
        return "Stopped early: cooldown armed (max consecutive SL)";
      }
      return `Stopped early: ${reason}`;
    }
    if (eventType === "SL_COOLDOWN_ARMED") {
      return "Stopped early: cooldown armed (max consecutive SL)";
    }
    if (eventType === "KILL_SWITCH") {
      return "Stopped: kill switch";
    }
  }
  return null;
}

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
  const stopReason = getPmxStopReason(events);
  return (
    <article className="col-span-full rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
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
          {killed
            ? "STOPPED (Guardrail)"
            : posOpen
              ? "IN POSITION"
              : "WATCHING"}
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
      {killed && stopReason ? (
        <div className="mb-2 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-800">
          {stopReason}
        </div>
      ) : null}
      <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="text-muted">Event Feed Summary</span>
          <span className="text-text-strong">Recent: {events.length}</span>
        </div>
        <div className="mb-3 max-h-20 overflow-y-auto text-xs text-muted">
          {events.slice(0, 5).map((ev, idx) => (
            <div key={idx} className="flex justify-between py-0.5">
              <span className="font-mono">{toKST(String(ev.ts ?? ""))}</span>
              <span className="ml-2 truncate">{String(ev.event_type ?? "-")}</span>
            </div>
          ))}
          {events.length === 0 ? <div>No recent events</div> : null}
        </div>
        <Link
          href="/command-center/events"
          className="inline-flex items-center rounded-lg border border-nt-border px-3 py-1.5 text-xs font-semibold text-nt-fg hover:bg-nt-surface"
        >
          View Events -&gt;
        </Link>
      </div>
    </article>
  );
}

type GuardrailAnalysisCardProps = {
  events: Record<string, unknown>[];
};

function GuardrailAnalysisCard({ events }: GuardrailAnalysisCardProps) {
  const analysis = useMemo(() => {
    const recent = events.slice(0, MAX_GUARDRAIL_EVENTS);
    const reasonCounts = new Map<string, number>();
    const stopped: Array<{ ts: unknown; reason: string }> = [];
    const riskTransitions: string[] = [];
    let lastRisk = "";

    const getReason = (ev: Record<string, unknown>): string => {
      const payload = (ev.payload as Record<string, unknown>) ?? {};
      const candidates = [
        payload.reason,
        payload.code,
        payload.gate,
        payload.rule,
        ev.reason,
        ev.code,
        ev.gate,
        ev.rule,
      ];
      for (const candidate of candidates) {
        if (typeof candidate === "string" && candidate.trim()) {
          return candidate.trim();
        }
      }
      const type = ev.event_type;
      return typeof type === "string" && type.trim() ? type : "unknown";
    };

    const isBlockedLike = (evType: string) => {
      const upper = evType.toUpperCase();
      return (
        upper.includes("BLOCK") ||
        upper.includes("GUARDRAIL") ||
        upper.includes("STOPPED") ||
        upper.includes("KILL")
      );
    };

    const isStoppedLike = (evType: string) => {
      const upper = evType.toUpperCase();
      return (
        upper.includes("STOPPED") ||
        upper.includes("SL_COOLDOWN_ARMED") ||
        upper.includes("KILL")
      );
    };

    for (const ev of recent) {
      const eventType = String(ev.event_type ?? ev.type ?? "");
      const payload = (ev.payload as Record<string, unknown>) ?? {};

      if (isBlockedLike(eventType) || typeof payload.reason === "string") {
        const reason = getReason(ev);
        reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
      }

      if (isStoppedLike(eventType) && stopped.length < 5) {
        stopped.push({ ts: ev.ts, reason: getReason(ev) });
      }

      const riskValue =
        typeof payload.risk_level === "string"
          ? payload.risk_level.toUpperCase()
          : typeof ev.risk_level === "string"
            ? String(ev.risk_level).toUpperCase()
            : "";

      if (riskValue && riskValue !== lastRisk) {
        if (lastRisk) {
          riskTransitions.push(`${lastRisk} -> ${riskValue}`);
        } else {
          riskTransitions.push(riskValue);
        }
        lastRisk = riskValue;
      }
      if (riskTransitions.length >= 10) break;
    }

    const totalReasonCount = Array.from(reasonCounts.values()).reduce(
      (acc, n) => acc + n,
      0,
    );
    const topReasons = Array.from(reasonCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    return { topReasons, totalReasonCount, stopped, riskTransitions };
  }, [events]);

  return (
    <article className="col-span-full rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Guardrail Analysis</h3>
        <Link
          href="/command-center/events"
          className="rounded-lg border border-nt-border px-3 py-1.5 text-xs font-semibold text-nt-fg hover:bg-nt-surface-2"
        >
          Open Events -&gt;
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
          <div className="mb-2 text-xs font-semibold text-muted">Top Reasons (N=5)</div>
          <div className="space-y-1 text-xs">
            {analysis.topReasons.length === 0 ? (
              <div className="text-muted">No guardrail reasons</div>
            ) : (
              analysis.topReasons.map(([reason, count]) => (
                <div key={reason} className="flex justify-between">
                  <span className="max-w-[180px] truncate">{reason}</span>
                  <span className="font-semibold">
                    {count}
                    {analysis.totalReasonCount > 0
                      ? ` (${Math.round((count / analysis.totalReasonCount) * 100)}%)`
                      : ""}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
          <div className="mb-2 text-xs font-semibold text-muted">Recent STOPPED (N=5)</div>
          <div className="space-y-1 text-xs">
            {analysis.stopped.length === 0 ? (
              <div className="text-muted">No recent STOPPED</div>
            ) : (
              analysis.stopped.map((item, idx) => (
                <div key={`${String(item.ts)}-${idx}`} className="flex justify-between gap-2">
                  <span className="w-16 shrink-0 text-muted">{toAgo(item.ts)}</span>
                  <span className="max-w-[180px] truncate" title={item.reason}>
                    {item.reason}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
          <div className="mb-2 text-xs font-semibold text-muted">Risk Transitions (N=10)</div>
          <div className="space-y-1 text-xs">
            {analysis.riskTransitions.length === 0 ? (
              <div className="text-muted">No risk transitions</div>
            ) : (
              analysis.riskTransitions.slice(0, 5).map((line, idx) => (
                <div key={`${line}-${idx}`} className="truncate">
                  {line}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

type SessionFlowTimelineCardProps = {
  events: Record<string, unknown>[];
  activeStamp: string | null;
};

function SessionFlowTimelineCard({
  events,
  activeStamp,
}: SessionFlowTimelineCardProps) {
  const flow = useMemo(() => {
    const source = events.slice(0, MAX_GUARDRAIL_EVENTS);
    const scoped =
      activeStamp && activeStamp.trim()
        ? source.filter((ev) => String(ev.trace_id ?? "").includes(activeStamp))
        : source;
    const recent = scoped.length > 0 ? scoped : source;

    type StepKey =
      | "START"
      | "ORDER"
      | "FILL"
      | "BLOCK"
      | "COOLDOWN"
      | "RESUME"
      | "END";

    const stepOrder: StepKey[] = [
      "START",
      "ORDER",
      "FILL",
      "BLOCK",
      "COOLDOWN",
      "RESUME",
      "END",
    ];

    const stepTs: Record<StepKey, number | null> = {
      START: null,
      ORDER: null,
      FILL: null,
      BLOCK: null,
      COOLDOWN: null,
      RESUME: null,
      END: null,
    };

    const hit = (u: string, keys: string[]) => keys.some((k) => u.includes(k));

    for (const ev of recent) {
      const eventType = String(ev.event_type ?? ev.type ?? "").toUpperCase();
      const payload = (ev.payload as Record<string, unknown>) ?? {};
      const reason = String(payload.reason ?? "").toUpperCase();
      const msg = String(payload.msg ?? ev.msg ?? "").toUpperCase();
      const merged = `${eventType} ${reason} ${msg}`;
      const ts = toEpochMs(ev.ts) ?? Date.now();

      if (hit(merged, ["RUN_START", "SESSION_START", "ENGINE_START"])) {
        stepTs.START = Math.max(stepTs.START ?? 0, ts);
      }
      if (hit(merged, ["ORDER_", "OPEN_ORDER", "ORDER_NEW", "ORDER_SUBMIT"])) {
        stepTs.ORDER = Math.max(stepTs.ORDER ?? 0, ts);
      }
      if (hit(merged, ["FILL", "FILLED", "TRADE"])) {
        stepTs.FILL = Math.max(stepTs.FILL ?? 0, ts);
      }
      if (
        hit(merged, ["BLOCK", "STRATEGY_BLOCKED", "RISK_BLOCKED", "GUARDRAIL"])
      ) {
        stepTs.BLOCK = Math.max(stepTs.BLOCK ?? 0, ts);
      }
      if (hit(merged, ["COOLDOWN", "SL_COOLDOWN_ARMED"])) {
        stepTs.COOLDOWN = Math.max(stepTs.COOLDOWN ?? 0, ts);
        stepTs.BLOCK = Math.max(stepTs.BLOCK ?? 0, ts);
      }
      if (hit(merged, ["RESUME", "COOLDOWN_RELEASED", "RUNNING"])) {
        stepTs.RESUME = Math.max(stepTs.RESUME ?? 0, ts);
      }
      if (
        hit(merged, ["RUN_END", "SESSION_END", "STOPPED_EARLY", "STOPPED", "KILL"])
      ) {
        stepTs.END = Math.max(stepTs.END ?? 0, ts);
      }
    }

    const last = stepOrder
      .map((step) => ({ step, ts: stepTs[step] }))
      .filter((item) => item.ts !== null)
      .sort((a, b) => (b.ts ?? 0) - (a.ts ?? 0))[0] ?? { step: null, ts: null };

    return {
      recentCount: recent.length,
      stepOrder,
      stepTs,
      lastStep: last.step as StepKey | null,
      lastTs: last.ts as number | null,
    };
  }, [events, activeStamp]);

  const styleForStep = (step: string, ts: number | null) => {
    if (!ts) return "border-nt-border text-muted";
    if (step === "END") return "border-nt-down/40 bg-nt-down/10 text-nt-down";
    if (step === "BLOCK" || step === "COOLDOWN") {
      return "border-nt-warn/40 bg-nt-warn/10 text-nt-warn";
    }
    return "border-nt-up/40 bg-nt-up/10 text-nt-up";
  };

  return (
    <article className="col-span-full rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Session Flow Timeline</h3>
        <span className="text-xs text-muted">
          Derived from recent events (N={MAX_GUARDRAIL_EVENTS})
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {flow.stepOrder.map((step) => (
          <div
            key={step}
            className={`rounded-lg border px-2 py-2 text-xs font-semibold ${styleForStep(
              step,
              flow.stepTs[step],
            )}`}
          >
            <div className="flex items-center gap-1">
              <span>●</span>
              <span>{step}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 text-xs text-muted">
        {flow.lastStep && flow.lastTs
          ? `Last step: ${flow.lastStep} (${toAgo(flow.lastTs)})`
          : "No recent events to derive flow"}
      </div>
      <div className="mt-1 text-[10px] text-muted">Recent events considered: {flow.recentCount}</div>
    </article>
  );
}

function toEpochMs(ts: unknown): number | null {
  if (typeof ts === "number") {
    return ts > 1_000_000_000_000 ? ts : ts * 1000;
  }
  if (typeof ts !== "string") return null;
  const parsed = Date.parse(ts);
  return Number.isNaN(parsed) ? null : parsed;
}

function toAgo(ts: unknown): string {
  const ms = toEpochMs(ts);
  if (!ms) return "-";
  const sec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}h ago`;
  const day = Math.floor(hour / 24);
  return `${day}d ago`;
}

type HaStatusCardProps = {
  summary: Record<string, unknown>;
  haStatus: HaStatusPayload | null;
};

function HaStatusCard({ summary, haStatus }: HaStatusCardProps) {
  const summaryEval =
    typeof summary.ha_filter_eval_count === "number"
      ? summary.ha_filter_eval_count
      : null;
  const summaryPass =
    typeof summary.ha_filter_pass_count === "number"
      ? summary.ha_filter_pass_count
      : null;
  const summarySkip =
    typeof summary.ha_filter_skip_count === "number"
      ? summary.ha_filter_skip_count
      : null;
  const evalCount = typeof haStatus?.ha_eval === "number" ? haStatus.ha_eval : summaryEval;
  const passCount = typeof haStatus?.ha_pass === "number" ? haStatus.ha_pass : summaryPass;
  const skipCount = typeof haStatus?.ha_skip === "number" ? haStatus.ha_skip : summarySkip;
  const deltaEval =
    typeof haStatus?.delta_eval === "number" ? haStatus.delta_eval : null;
  const deltaPass =
    typeof haStatus?.delta_pass === "number" ? haStatus.delta_pass : null;
  const deltaSkip =
    typeof haStatus?.delta_skip === "number" ? haStatus.delta_skip : null;
  const source = haStatus?.source || "none";
  const activeStamp = haStatus?.active_stamp || haStatus?.stamp || null;
  const ageSec = typeof haStatus?.age_sec === "number" ? haStatus.age_sec : null;

  const renderValue = (v: number | null) => (v === null ? "N/A" : String(v));
  const renderAge = (sec: number | null) => {
    if (sec === null) return "N/A";
    if (sec < 60) return `${Math.round(sec)}s`;
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return `${m}m ${s}s`;
  };
  const ageBadgeClass =
    ageSec === null
      ? "bg-slate-100 text-slate-700"
      : ageSec <= 15
        ? "bg-emerald-100 text-emerald-700"
        : ageSec <= 60
          ? "bg-amber-100 text-amber-700"
          : "bg-red-100 text-red-700";

  return (
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">HA Filter</h3>
        <div className="flex items-center gap-1">
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-700">
            Session
          </span>
          <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] text-blue-700">
            {source}
          </span>
          <span className={`rounded px-2 py-0.5 text-[10px] ${ageBadgeClass}`}>
            Age {renderAge(ageSec)}
          </span>
        </div>
      </div>
      <div className="mb-2 text-[10px] text-muted">
        STAMP: {activeStamp ?? "N/A"}
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted">HA Eval (session)</span>
          <span>{renderValue(evalCount)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">HA Pass (session)</span>
          <span>{renderValue(passCount)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">HA Skip (session)</span>
          <span>{renderValue(skipCount)}</span>
        </div>
        <div className="mt-2 border-t border-border-subtle pt-2 text-xs">
          <div className="flex justify-between">
            <span className="text-muted">HA Eval Delta</span>
            <span>{renderValue(deltaEval)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">HA Pass Delta</span>
            <span>{renderValue(deltaPass)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">HA Skip Delta</span>
            <span>{renderValue(deltaSkip)}</span>
          </div>
        </div>
      </div>
      {evalCount === null &&
      passCount === null &&
      skipCount === null &&
      source === "none" ? (
        <div className="mt-2 text-[10px] text-muted">
          Source unavailable in current status payload. Check PMX summary for
          ha_filter_eval/pass/skip.
        </div>
      ) : null}
    </article>
  );
}

type StrategyHealthSummaryCardProps = {
  contractHealth: ContractHealth | null;
  pmxSummary: Record<string, unknown>;
  haStatus: HaStatusPayload | null;
  wsFrames: number;
  lastWsAgeSec: number | null;
  dataChangeAgeSec: number | null;
  lastStateChange: string | null;
  deltaOrders5s: number;
  deltaFills5s: number;
};

function EngineStatusCard({
  contractHealth,
  pmxSummary,
  haStatus,
  wsFrames,
  lastWsAgeSec,
  dataChangeAgeSec,
  lastStateChange,
  deltaOrders5s,
  deltaFills5s,
}: StrategyHealthSummaryCardProps) {
  const engineAlive = !!contractHealth?.data?.engine_alive;
  const enginePid = contractHealth?.data?.engine_pid;
  const killed = !!pmxSummary.kill;
  const profitmaxStatusRaw = String(
    pmxSummary.status ?? pmxSummary.profitmax_status ?? "",
  ).toUpperCase();
  const profitmaxStopped = killed || profitmaxStatusRaw.includes("STOPPED");
  const reason = killed ? "Guardrail STOPPED (no new orders/fills expected)" : "Running";
  const riskLevelRaw = String(haStatus?.risk_level ?? "LOW").toUpperCase();
  const riskLevel = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].includes(riskLevelRaw)
    ? riskLevelRaw
    : "LOW";
  const riskClass =
    riskLevel === "CRITICAL"
      ? "text-nt-down"
      : riskLevel === "HIGH"
        ? "text-nt-info"
        : riskLevel === "MEDIUM"
          ? "text-nt-warn"
          : "text-nt-up";
  const lastFillTs = typeof haStatus?.last_fill_ts === "number" ? haStatus.last_fill_ts : 0;
  const lastFillAgeSec =
    lastFillTs > 0 ? Math.max(0, Math.floor((Date.now() - lastFillTs) / 1000)) : null;
  const lastFillClass =
    lastFillAgeSec === null
      ? "text-muted"
      : lastFillAgeSec > 180
        ? "text-nt-down"
        : lastFillAgeSec > 60
          ? "text-nt-warn"
          : "text-nt-up";
  const blockedCount = haStatus?.blocked_count ?? 0;
  const reasonLine = haStatus?.kill_switch
    ? "Reason: Kill Switch ON"
    : killed
      ? "Reason: Guardrail STOPPED (no new orders/fills expected)"
      : blockedCount > 0 && deltaFills5s === 0
        ? "Reason: Blocked gate active (fills not increasing)"
        : "Reason: normal monitoring";

  const statusLabel = haStatus?.kill_switch
    ? "KILL_SWITCH"
    : killed
      ? reason.toLowerCase().includes("cooldown")
        ? "COOLING DOWN"
        : "STOPPED (Guardrail)"
      : "RUNNING";
  const statusClass =
    statusLabel === "RUNNING"
      ? "bg-nt-up/20 text-nt-up"
      : statusLabel === "COOLING DOWN"
        ? "bg-nt-warn/20 text-nt-warn"
        : "bg-nt-down/20 text-nt-down";
  const freezeLevel =
    engineAlive &&
    !profitmaxStopped &&
    !haStatus?.kill_switch &&
    wsFrames > 0 &&
    typeof dataChangeAgeSec === "number" &&
    dataChangeAgeSec > 60 &&
    deltaOrders5s === 0 &&
    deltaFills5s === 0
      ? dataChangeAgeSec > 120
        ? "down"
        : "warn"
      : null;
  const freezeClass =
    freezeLevel === "down"
      ? "bg-nt-down/15 text-nt-down border-nt-down/30"
      : "bg-nt-warn/15 text-nt-warn border-nt-warn/30";

  return (
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Engine Status</h3>
      </div>
      {freezeLevel ? (
        <div className={`mb-3 rounded-xl border px-3 py-2 text-sm font-semibold ${freezeClass}`}>
          ⚠ ENGINE FREEZE DETECTED
          <span className="ml-2 text-xs font-normal opacity-80">
            No state change for {Math.floor(dataChangeAgeSec ?? 0)}s (WS alive) ·
            {" "}ordersΔ=0 fillsΔ=0
          </span>
        </div>
      ) : null}
      <div className={`mb-3 rounded-xl px-2 py-2 text-xs font-semibold ${statusClass}`}>
        PROFITMAX: {statusLabel}
      </div>
      <div className="mb-3 space-y-1 rounded-xl border border-nt-border bg-nt-surface-2 p-2 text-xs">
        <div className="flex justify-between">
          <span className="text-muted">Last WS Update</span>
          <span>{lastWsAgeSec === null ? "-" : `${Math.round(lastWsAgeSec)}s ago`}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">WS Frame Count</span>
          <span>{wsFrames}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">State Change</span>
          <span className="max-w-[160px] truncate text-right">{lastStateChange ?? "-"}</span>
        </div>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted">Engine</span>
          <span>{engineAlive ? "ALIVE" : "DEAD"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Engine PID</span>
          <span>{enginePid ?? "-"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Risk Level</span>
          <span className={riskClass}>{riskLevel}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Kill Switch</span>
          <span>{haStatus?.kill_switch ? "ON" : "OFF"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Open Orders</span>
          <span>{haStatus?.open_orders_count ?? 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Rejected</span>
          <span>{haStatus?.rejected_count ?? 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Blocked</span>
          <span className={blockedCount > 0 ? "font-semibold text-nt-warn" : ""}>
            {blockedCount > 0 ? `${blockedCount} ⚠` : blockedCount}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Last Fill</span>
          <span className={lastFillClass}>
            {lastFillAgeSec === null ? "-" : `${lastFillAgeSec}s ago`}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Profitmax</span>
          <span>{killed ? "STOPPED (Guardrail)" : "RUNNING/WATCHING"}</span>
        </div>
      </div>
      <div className="mt-2 text-[10px] text-muted">{reasonLine}</div>
    </article>
  );
}

type SessionReportCardProps = {
  orders: V1OrderItem[];
  fills: V1FillItem[];
  haStatus: HaStatusPayload | null;
  deltaOrders5s: number;
  deltaFills5s: number;
  deltaBlocks5s: number;
};

function deltaClass(delta: number) {
  return delta > 0
    ? "text-nt-up transition-all duration-1000 animate-pulse"
    : "text-text";
}

function SessionReportCard({
  orders,
  fills,
  haStatus,
  deltaOrders5s,
  deltaFills5s,
  deltaBlocks5s,
}: SessionReportCardProps) {
  const lastOrderTs = orders.length ? orders[0]?.ts : null;
  const lastFillTs = fills.length ? fills[0]?.ts : null;
  return (
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Session Report</h3>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted">Active Stamp</span>
          <span>{haStatus?.active_stamp ?? haStatus?.stamp ?? "N/A"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Order TS (latest)</span>
          <span>{lastOrderTs ?? "-"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Fill TS (latest)</span>
          <span>{lastFillTs ?? "-"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">HA Δ (eval/pass/skip)</span>
          <span>
            {(haStatus?.delta_eval ?? "N/A")}/{(haStatus?.delta_pass ?? "N/A")}/
            {(haStatus?.delta_skip ?? "N/A")}
          </span>
        </div>
        <div className="mt-2 border-t border-border-subtle pt-2 text-xs">
          <div className="flex justify-between">
            <span className="text-muted">5s Orders Delta</span>
            <span className={deltaClass(deltaOrders5s)}>
              {deltaOrders5s > 0 ? `↑ ${deltaOrders5s}` : deltaOrders5s}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">5s Fills Delta</span>
            <span className={deltaClass(deltaFills5s)}>
              {deltaFills5s > 0 ? `↑ ${deltaFills5s}` : deltaFills5s}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">5s Blocks Delta</span>
            <span className={deltaClass(deltaBlocks5s)}>
              {deltaBlocks5s > 0 ? `↑ ${deltaBlocks5s}` : deltaBlocks5s}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}

type PerfSnapshot = {
  ws_fps: number;
  data_cps: number;
  render_fps: number;
  reconnects: number;
  sampled_at: number;
};

type OpsPerformancePanelProps = {
  perf: PerfSnapshot;
  open: boolean;
  onToggle: () => void;
};

function metricClass(value: number, warn: number, down: number) {
  if (value <= down) return "text-nt-down";
  if (value < warn) return "text-nt-warn";
  return "text-nt-up";
}

function OpsPerformancePanel({ perf, open, onToggle }: OpsPerformancePanelProps) {
  const wsClass = metricClass(perf.ws_fps, 0.5, 0);
  const dataClass = metricClass(perf.data_cps, 0.2, 0);
  const renderClass = perf.render_fps > 20 ? "text-nt-warn" : "text-nt-up";
  const reconnClass = perf.reconnects > 0 ? "text-nt-warn" : "text-nt-up";

  return (
    <article className="col-span-full rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">Ops Performance</h3>
        <button
          onClick={onToggle}
          className="rounded-lg border border-nt-border px-3 py-1.5 text-xs font-semibold text-nt-fg hover:bg-nt-surface-2"
        >
          {open ? "Collapse" : "Expand"}
        </button>
      </div>
      {open ? (
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
            <div className="text-xs text-muted">WS frames/sec (5s avg)</div>
            <div className={`text-lg font-semibold ${wsClass}`}>{perf.ws_fps.toFixed(2)}</div>
          </div>
          <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
            <div className="text-xs text-muted">Data changes/sec (5s avg)</div>
            <div className={`text-lg font-semibold ${dataClass}`}>{perf.data_cps.toFixed(2)}</div>
          </div>
          <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
            <div className="text-xs text-muted">Render/sec (5s avg)</div>
            <div className={`text-lg font-semibold ${renderClass}`}>{perf.render_fps.toFixed(2)}</div>
          </div>
          <div className="rounded-xl border border-nt-border bg-nt-surface-2 p-3">
            <div className="text-xs text-muted">WS reconnect count</div>
            <div className={`text-lg font-semibold ${reconnClass}`}>{perf.reconnects}</div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export default function PhaseBVisibilityCards() {
  const renderCountRef = useRef(0);
  renderCountRef.current += 1;

  const [loadingProgress, setLoadingProgress] = useState(true);
  const [loadingTrades, setLoadingTrades] = useState(true);
  const [loadingPnl, setLoadingPnl] = useState(true);
  const isInitialLoadRef = useRef(true);
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
  const [displayUptimeSec, setDisplayUptimeSec] = useState(0);
  const sessionStartMsRef = useRef<number | null>(null);
  const lastRestartCountRef = useRef<number | null>(null);
  const [wsUrl, setWsUrl] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const [liveEventCount, setLiveEventCount] = useState(0);
  const [lastEventAtMs, setLastEventAtMs] = useState<number | null>(null);
  const [lastEventAgeSec, setLastEventAgeSec] = useState<number | null>(null);
  const [dataChangeAtMs, setDataChangeAtMs] = useState<number | null>(null);
  const [dataChangeAgeSec, setDataChangeAgeSec] = useState<number | null>(null);
  const [lastChangedFields, setLastChangedFields] = useState<string | null>(null);
  const [lastStateChange, setLastStateChange] = useState<string | null>(null);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [perfOpen, setPerfOpen] = useState(false);
  const [perfSnapshot, setPerfSnapshot] = useState<PerfSnapshot>({
    ws_fps: 0,
    data_cps: 0,
    render_fps: 0,
    reconnects: 0,
    sampled_at: Date.now(),
  });
  const dataChangeCountRef = useRef(0);
  const hasConnectedOnceRef = useRef(false);
  const prevWsConnectedRef = useRef(false);
  const perfPrevRef = useRef({
    wsFrames: 0,
    dataChanges: 0,
    renders: 0,
    sampledAt: Date.now(),
  });

  const [pmxSummary, setPmxSummary] = useState<Record<string, unknown>>({});
  const [pmxEvents, setPmxEvents] = useState<Record<string, unknown>[]>([]);
  const [haStatus, setHaStatus] = useState<HaStatusPayload | null>(null);
  const [deltaOrders5s, setDeltaOrders5s] = useState(0);
  const [deltaFills5s, setDeltaFills5s] = useState(0);
  const [deltaBlocks5s, setDeltaBlocks5s] = useState(0);
  const prevHaSnapshotRef = useRef<{
    last_order_ts: number;
    last_fill_ts: number;
    blocked_count: number;
  } | null>(null);
  const lastHaSigRef = useRef<string>("");

  const applyHaStatusUpdate = useCallback((next: HaStatusPayload) => {
    const changed: string[] = [];
    if (haStatus) {
      const watched: (keyof HaStatusPayload)[] = [
        "ha_eval",
        "ha_pass",
        "ha_skip",
        "delta_eval",
        "delta_pass",
        "delta_skip",
        "engine_alive",
        "last_order_ts",
        "last_fill_ts",
        "open_orders_count",
        "blocked_count",
        "kill_switch",
        "risk_level",
      ];
      for (const key of watched) {
        if (haStatus[key] !== next[key]) changed.push(String(key));
      }
    } else {
      changed.push("initial");
    }
    const sig = JSON.stringify({
      source: next.source ?? "",
      active_stamp: next.active_stamp ?? next.stamp ?? "",
      ha_eval: next.ha_eval ?? null,
      ha_pass: next.ha_pass ?? null,
      ha_skip: next.ha_skip ?? null,
      delta_eval: next.delta_eval ?? null,
      delta_pass: next.delta_pass ?? null,
      delta_skip: next.delta_skip ?? null,
      engine_alive: next.engine_alive ?? null,
      last_order_ts: next.last_order_ts ?? 0,
      last_fill_ts: next.last_fill_ts ?? 0,
      blocked_count: next.blocked_count ?? 0,
      kill_switch: next.kill_switch ?? false,
      risk_level: next.risk_level ?? "",
    });
    if (sig === lastHaSigRef.current) {
      return;
    }
    lastHaSigRef.current = sig;
    dataChangeCountRef.current += 1;
    setDataChangeAtMs(Date.now());
    setLastChangedFields(changed.slice(0, 3).join(", ") || "state");

    const nextOrderTs = typeof next.last_order_ts === "number" ? next.last_order_ts : 0;
    const nextFillTs = typeof next.last_fill_ts === "number" ? next.last_fill_ts : 0;
    const nextBlockedCount =
      typeof next.blocked_count === "number" ? next.blocked_count : 0;
    const prev = prevHaSnapshotRef.current;
    const prevRiskLevel = (haStatus?.risk_level ?? "").toUpperCase();
    const nextRiskLevel = String(next.risk_level ?? "").toUpperCase();
    const prevKill = !!haStatus?.kill_switch;
    const nextKill = !!next.kill_switch;
    if (prev) {
      setDeltaOrders5s(nextOrderTs > prev.last_order_ts ? 1 : 0);
      setDeltaFills5s(nextFillTs > prev.last_fill_ts ? 1 : 0);
      setDeltaBlocks5s(Math.max(0, nextBlockedCount - prev.blocked_count));
      if (nextKill !== prevKill) {
        setLastStateChange(nextKill ? "Kill switch ON" : "Kill switch OFF");
      } else if (nextRiskLevel && nextRiskLevel !== prevRiskLevel) {
        setLastStateChange(`Risk ${prevRiskLevel || "-"} -> ${nextRiskLevel}`);
      } else if (nextBlockedCount > prev.blocked_count) {
        setLastStateChange(`Blocked +${nextBlockedCount - prev.blocked_count}`);
      } else if (nextFillTs > prev.last_fill_ts) {
        setLastStateChange("New fill");
      } else if (nextOrderTs > prev.last_order_ts) {
        setLastStateChange("New order");
      }
    } else {
      setDeltaOrders5s(0);
      setDeltaFills5s(0);
      setDeltaBlocks5s(0);
      setLastStateChange("Initial snapshot");
    }
    prevHaSnapshotRef.current = {
      last_order_ts: nextOrderTs,
      last_fill_ts: nextFillTs,
      blocked_count: nextBlockedCount,
    };
    setHaStatus(next);
  }, [haStatus]);

  const load = useCallback(async () => {
    const isFirst = isInitialLoadRef.current;

    try {
      if (isFirst) setLoadingProgress(true);
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
      const fetchedUptime = stateData?.freshness?.checkpoint_age_sec ?? 0;
      const restartCount = stateData?.counters.restart_count ?? 0;
      if (
        sessionStartMsRef.current === null ||
        lastRestartCountRef.current === null ||
        restartCount > lastRestartCountRef.current
      ) {
        lastRestartCountRef.current = restartCount;
        sessionStartMsRef.current = Date.now() - fetchedUptime * 1000;
      }
    } catch {
      setProgressError("v1_progress_error");
    } finally {
      if (isFirst) setLoadingProgress(false);
    }

    try {
      if (isFirst) setLoadingTrades(true);
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
      if (isFirst) setLoadingTrades(false);
    }

    try {
      if (isFirst) setLoadingPnl(true);
      setPnlError(null);
      const pnlData = await apiClient.getPnl();
      if (!pnlData) {
        setPnlError("v1_pnl_unavailable");
      }
      setPnl(pnlData);
    } catch {
      setPnlError("v1_pnl_error");
    } finally {
      if (isFirst) setLoadingPnl(false);
      isInitialLoadRef.current = false;
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
    const intervalId = window.setInterval(() => {
      const start = sessionStartMsRef.current;
      if (start !== null) {
        setDisplayUptimeSec((Date.now() - start) / 1000);
      }
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, []);

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
    if (dataChangeAtMs === null) {
      setDataChangeAgeSec(null);
      return;
    }
    const tick = () => {
      setDataChangeAgeSec((Date.now() - dataChangeAtMs) / 1000);
    };
    tick();
    const intervalId = window.setInterval(tick, 1000);
    return () => window.clearInterval(intervalId);
  }, [dataChangeAtMs]);

  useEffect(() => {
    const prev = prevWsConnectedRef.current;
    if (!prev && wsConnected) {
      if (hasConnectedOnceRef.current) {
        setReconnectCount((v) => v + 1);
      } else {
        hasConnectedOnceRef.current = true;
      }
    }
    prevWsConnectedRef.current = wsConnected;
  }, [wsConnected]);

  useEffect(() => {
    const iv = window.setInterval(() => {
      const now = Date.now();
      const prev = perfPrevRef.current;
      const dtSec = Math.max(1, (now - prev.sampledAt) / 1000);
      const nextWs = liveEventCount;
      const nextData = dataChangeCountRef.current;
      const nextRenders = renderCountRef.current;
      const wsFps = (nextWs - prev.wsFrames) / dtSec;
      const dataCps = (nextData - prev.dataChanges) / dtSec;
      const renderFps = (nextRenders - prev.renders) / dtSec;

      setPerfSnapshot({
        ws_fps: Math.max(0, wsFps),
        data_cps: Math.max(0, dataCps),
        render_fps: Math.max(0, renderFps),
        reconnects: reconnectCount,
        sampled_at: now,
      });

      perfPrevRef.current = {
        wsFrames: nextWs,
        dataChanges: nextData,
        renders: nextRenders,
        sampledAt: now,
      };
    }, 5000);
    return () => window.clearInterval(iv);
  }, [liveEventCount, reconnectCount]);

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
    const wsType = String(event.event_type || event.type || "");
    if (wsType === "OPS_HA_STATUS" && event.data) {
      const payload = event.data as Record<string, unknown>;
      const prev = haStatus ?? {};
      applyHaStatusUpdate({
        ...(prev ?? {}),
        source: typeof payload.source === "string" ? payload.source : prev?.source,
        active_stamp:
          typeof payload.active_stamp === "string"
            ? payload.active_stamp
            : prev?.active_stamp,
        stamp: typeof payload.stamp === "string" ? payload.stamp : prev?.stamp,
        age_sec:
          typeof payload.age_sec === "number" ? payload.age_sec : prev?.age_sec,
        data_ts:
          typeof payload.data_ts === "string" ? payload.data_ts : prev?.data_ts,
        ha_eval:
          typeof payload.ha_eval === "number" ? payload.ha_eval : prev?.ha_eval,
        ha_pass:
          typeof payload.ha_pass === "number" ? payload.ha_pass : prev?.ha_pass,
        ha_skip:
          typeof payload.ha_skip === "number" ? payload.ha_skip : prev?.ha_skip,
        delta_eval:
          typeof payload.delta_eval === "number"
            ? payload.delta_eval
            : prev?.delta_eval,
        delta_pass:
          typeof payload.delta_pass === "number"
            ? payload.delta_pass
            : prev?.delta_pass,
        delta_skip:
          typeof payload.delta_skip === "number"
            ? payload.delta_skip
            : prev?.delta_skip,
        engine_alive:
          typeof payload.engine_alive === "boolean"
            ? payload.engine_alive
            : prev?.engine_alive,
        last_order_ts:
          typeof payload.last_order_ts === "number"
            ? payload.last_order_ts
            : prev?.last_order_ts,
        last_fill_ts:
          typeof payload.last_fill_ts === "number"
            ? payload.last_fill_ts
            : prev?.last_fill_ts,
        open_orders_count:
          typeof payload.open_orders_count === "number"
            ? payload.open_orders_count
            : prev?.open_orders_count,
        canceled_count:
          typeof payload.canceled_count === "number"
            ? payload.canceled_count
            : prev?.canceled_count,
        rejected_count:
          typeof payload.rejected_count === "number"
            ? payload.rejected_count
            : prev?.rejected_count,
        blocked_count:
          typeof payload.blocked_count === "number"
            ? payload.blocked_count
            : prev?.blocked_count,
        kill_switch:
          typeof payload.kill_switch === "boolean"
            ? payload.kill_switch
            : prev?.kill_switch,
        risk_level:
          typeof payload.risk_level === "string"
            ? payload.risk_level
            : prev?.risk_level,
        downgrade_level:
          typeof payload.downgrade_level === "number"
            ? payload.downgrade_level
            : prev?.downgrade_level,
      });
    }
  }, [applyHaStatusUpdate, haStatus]);

  useWebSocket({
    url: wsUrl,
    onMessage: handleWSMessage,
    onConnect: () => setWsConnected(true),
    onDisconnect: () => setWsConnected(false),
    onError: () => setWsConnected(false),
  });

  // Fallback for routes where WS frames are visible but strict event parsing/counting is sparse.
  const liveEventDisplayCount =
    liveEventCount > 0 ? liveEventCount : wsConnected ? processedEvents : 0;

  useEffect(() => {
    const fetchPmx = async () => {
      try {
        const r = await fetch(`/api/profitmax/status?limit=${MAX_GUARDRAIL_EVENTS}`);
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

  useEffect(() => {
    const fetchHaStatus = async () => {
      try {
        const response = await fetch("/api/ops/ha-status", { cache: "no-store" });
        if (!response.ok) return;
        const payload = (await response.json()) as HaStatusPayload;
        applyHaStatusUpdate(payload);
      } catch {
        // Keep UI stable with existing summary/N/A fallback.
      }
    };
    fetchHaStatus();
    const iv = window.setInterval(fetchHaStatus, 5000);
    return () => window.clearInterval(iv);
  }, [applyHaStatusUpdate]);

  return (
    <div className="grid auto-rows-min grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
      <ProgressCard
        loading={loadingProgress}
        error={progressError}
        uptimeSec={displayUptimeSec}
        sessionState={contractHealth?.status ?? "UNKNOWN"}
        processedEvents={processedEvents}
        restartCount={contractState?.counters.restart_count ?? 0}
        wsConnected={wsConnected}
        wsFrameCount={liveEventDisplayCount}
        wsHeartbeatAgeSec={lastEventAgeSec}
        dataChangeAgeSec={dataChangeAgeSec}
        lastChangedFields={lastChangedFields}
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
      <PH7CObservabilityCard />
      <EngineStatusCard
        contractHealth={contractHealth}
        pmxSummary={pmxSummary}
        haStatus={haStatus}
        wsFrames={liveEventCount}
        lastWsAgeSec={lastEventAgeSec}
        dataChangeAgeSec={dataChangeAgeSec}
        lastStateChange={lastStateChange}
        deltaOrders5s={deltaOrders5s}
        deltaFills5s={deltaFills5s}
      />
      <HaStatusCard summary={pmxSummary} haStatus={haStatus} />
      <SessionReportCard
        orders={orders}
        fills={fills}
        haStatus={haStatus}
        deltaOrders5s={deltaOrders5s}
        deltaFills5s={deltaFills5s}
        deltaBlocks5s={deltaBlocks5s}
      />
      <SessionFlowTimelineCard
        events={pmxEvents}
        activeStamp={haStatus?.active_stamp ?? haStatus?.stamp ?? null}
      />
      <GuardrailAnalysisCard events={pmxEvents} />
      <PmxCard summary={pmxSummary} events={pmxEvents} />
      <OpsPerformancePanel
        perf={perfSnapshot}
        open={perfOpen}
        onToggle={() => setPerfOpen((v) => !v)}
      />
    </div>
  );
}

