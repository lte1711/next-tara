"use client";

import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";

type RuntimeHealth = {
  engine_pid: number | null;
  engine_alive: boolean;
  engine_cmdline_hint?: string | null;
  checkpoint_age_sec: number | null;
  checkpoint_status: "FRESH" | "STALE" | "EXPIRED" | "UNKNOWN";
  health_status: "OK" | "WARN" | "CRITICAL" | "UNKNOWN";
  last_health_ok: string | null;
  restart_count: number;
  flap_detected: boolean;
  task_state: string;
  timestamp: string;
};

type RuntimeEvent = {
  timestamp: number;
  event_id: string;
  event_type: string;
  severity: string;
  reason: string;
  trace_id?: string;
  data?: Record<string, unknown>;
};

export default function OpsRuntimePage() {
  const [health, setHealth] = useState<RuntimeHealth | null>(null);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastWsMessage, setLastWsMessage] = useState<string>("");
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";
  const wsBase = process.env.NEXT_PUBLIC_API_WS || "ws://127.0.0.1:8100";

  const wsUrl = useMemo(
    () => `${wsBase.replace(/\/+$/, "")}/ws/events`,
    [wsBase],
  );

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await apiClient.getHealth();
        if (!data?.data) return;
        setHealth({
          ...data.data,
          last_health_ok: data.data.last_health_ok ?? null,
          timestamp: data.ts,
        });
      } catch {
        // fail silent for skeleton stability
      }
    };

    const fetchEvents = async () => {
      try {
        const data = await apiClient.getRisks(20);
        setEvents(Array.isArray(data?.items) ? data.items : []);
      } catch {
        // fail silent for skeleton stability
      }
    };

    fetchHealth();
    fetchEvents();
    const timer = window.setInterval(() => {
      fetchHealth();
      fetchEvents();
    }, 5000);

    return () => window.clearInterval(timer);
  }, [apiBase]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);
    ws.onmessage = (event) => {
      setLastWsMessage(
        typeof event.data === "string" ? event.data.slice(0, 240) : "",
      );
    };

    return () => ws.close();
  }, [wsUrl]);

  const statusTone =
    health?.health_status === "CRITICAL"
      ? "var(--alert-critical)"
      : health?.health_status === "WARN"
        ? "var(--health-warn)"
        : "var(--health-ok)";

  return (
    <main
      className="min-h-screen bg-bg text-text"
      style={{ padding: "calc(var(--space-base) * 3)" }}
    >
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-text-strong">Ops Runtime</h1>
        <p className="text-sm text-muted">
          Contract-bound runtime monitoring ({apiBase})
        </p>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{
            padding: "calc(var(--space-base) * 2)",
            borderTop: `3px solid ${statusTone}`,
          }}
        >
          <h2 className="text-lg font-semibold text-text-strong mb-2">
            Runtime Health
          </h2>
          <pre className="text-xs text-muted overflow-auto">
            {JSON.stringify(health ?? { status: "unavailable" }, null, 2)}
          </pre>
        </article>

        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{ padding: "calc(var(--space-base) * 2)" }}
        >
          <h2 className="text-lg font-semibold text-text-strong mb-2">
            Runtime Events
          </h2>
          <pre className="text-xs text-muted overflow-auto">
            {JSON.stringify(events.slice(0, 10), null, 2)}
          </pre>
        </article>

        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{
            padding: "calc(var(--space-base) * 2)",
            borderTop: `3px solid ${wsConnected ? "var(--health-ok)" : "var(--alert-critical)"}`,
          }}
        >
          <h2 className="text-lg font-semibold text-text-strong mb-2">
            WS Stream
          </h2>
          <p
            className="text-sm mb-2"
            style={{
              color: wsConnected ? "var(--health-ok)" : "var(--alert-critical)",
            }}
          >
            {wsConnected ? "Connected" : "Disconnected"} · {wsUrl}
          </p>
          <pre className="text-xs text-muted overflow-auto">
            {lastWsMessage || "No message yet"}
          </pre>
        </article>
      </section>
    </main>
  );
}
