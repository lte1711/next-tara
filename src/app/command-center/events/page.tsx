"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type PmxEvent = {
  ts?: string;
  event_type?: string;
  payload?: Record<string, unknown>;
};

function toKST(ts: string): string {
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    return d.toLocaleString("ko-KR", {
      hour12: false,
      timeZone: "Asia/Seoul",
    });
  } catch {
    return ts;
  }
}

function eventDetail(ev: PmxEvent): string {
  const t = String(ev.event_type ?? "");
  const p = ev.payload ?? {};
  if (t === "ENTRY") {
    return `${String(p.side)} ${String(p.qty)} BTC @ ${String(p.entry_price)} | ${String(p.strategy_id)} (${String(p.regime)})`;
  }
  if (t === "EXIT") {
    const pnl =
      typeof p.pnl === "number" ? (p.pnl as number).toFixed(4) : String(p.pnl ?? "-");
    return `pnl=${pnl} reason=${String(p.reason ?? "-")}`;
  }
  if (t === "HEARTBEAT") {
    return `price=${String(p.price)} regime=${String(p.regime)} pnl=${String(p.session_realized_pnl)}`;
  }
  return JSON.stringify(p).slice(0, 160);
}

export default function CommandCenterEventsPage() {
  const [events, setEvents] = useState<PmxEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch("/api/profitmax/status?limit=200", {
          cache: "no-store",
        });
        if (!response.ok) {
          setError(`status_${response.status}`);
          return;
        }
        const data = (await response.json()) as { events?: PmxEvent[] };
        setEvents(data.events ?? []);
        setError(null);
      } catch {
        setError("fetch_failed");
      }
    };
    load();
    const iv = window.setInterval(load, 5000);
    return () => window.clearInterval(iv);
  }, []);

  return (
    <main className="min-h-screen bg-nt-bg text-nt-fg">
      <div className="mx-auto max-w-7xl px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold">Command Center Events</h1>
          <Link
            href="/command-center"
            className="rounded-lg border border-nt-border px-3 py-1.5 text-xs font-semibold hover:bg-nt-surface"
          >
            Back to Command Center
          </Link>
        </div>
        <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between text-sm">
            <span className="text-muted">Recent Events</span>
            <span>{events.length}</span>
          </div>
          {error ? (
            <div className="mb-3 rounded-lg border border-nt-down/40 bg-nt-down/10 px-3 py-2 text-xs text-nt-down">
              Event feed error: {error}
            </div>
          ) : null}
          <div className="max-h-[72vh] overflow-y-auto rounded-lg border border-nt-border">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-nt-surface-2">
                <tr>
                  <th className="px-2 py-1 text-left">Time (KST)</th>
                  <th className="px-2 py-1 text-left">Event</th>
                  <th className="px-2 py-1 text-left">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nt-border">
                {events.map((ev, idx) => (
                  <tr key={`${ev.ts ?? "na"}-${idx}`} className="hover:bg-nt-surface-2/60">
                    <td className="px-2 py-1 font-mono">{toKST(String(ev.ts ?? "-"))}</td>
                    <td className="px-2 py-1 font-semibold">{String(ev.event_type ?? "-")}</td>
                    <td className="px-2 py-1 text-muted">{eventDetail(ev)}</td>
                  </tr>
                ))}
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-2 py-6 text-center text-muted">
                      No events
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </main>
  );
}

