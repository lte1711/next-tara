"use client";

import { V1FillItem, V1OrderItem, V1PnlResponse } from "@/lib/api";

type ProgressCardProps = {
  loading: boolean;
  error: string | null;
  uptimeSec: number;
  sessionState: string;
  processedEvents: number;
  restartCount: number;
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
  const { loading, error, pnl, onRetry } = props;

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
            <span className="text-muted">Realized</span>
            <span>{(pnl?.realized_pnl ?? 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Unrealized</span>
            <span>{(pnl?.unrealized_pnl ?? 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Equity</span>
            <span>{(pnl?.equity ?? 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Worst DD</span>
            <span>{(pnl?.worst_dd ?? 0).toFixed(2)}</span>
          </div>
          <Sparkline points={pnl?.equity_curve ?? []} />
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
