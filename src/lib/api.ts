const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";
const API_BASE = `${API_ORIGIN.replace(/\/+$/, "")}/api`;
const API_V1_BASE = `${API_BASE}/v1`;

async function safeGet<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

async function safePost<T>(url: string, body: unknown): Promise<T | null> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export interface EngineState {
  kill_switch_on: boolean;
  risk_type?: string;
  reason?: string;
  uptime_sec: number;
  published: number;
  consumed: number;
  pending_total: number;
}

export interface ContractHealth {
  contract_version: string;
  ts: string;
  status: "OK" | "WARN" | "CRITICAL" | "UNKNOWN";
  data: {
    engine_pid: number | null;
    engine_alive: boolean;
    engine_cmdline_hint?: string | null;
    checkpoint_age_sec: number | null;
    checkpoint_status: "FRESH" | "STALE" | "EXPIRED" | "UNKNOWN";
    health_status: "OK" | "WARN" | "CRITICAL" | "UNKNOWN";
    last_health_ok?: string | null;
    restart_count: number;
    flap_detected: boolean;
    task_state: string;
  };
}

export interface ContractState {
  contract_version: string;
  ts: string;
  engine: {
    pid: number | null;
    alive: boolean;
    cmdline_hint?: string | null;
    task_state: string;
    health_status: string;
  };
  kill: {
    is_on: boolean;
    reason?: string;
  };
  counters: {
    published: number;
    consumed: number;
    pending_total: number;
    restart_count: number;
  };
  freshness: {
    checkpoint_age_sec: number;
    checkpoint_status: string;
    is_stale: boolean;
    last_health_ok?: string | null;
    flap_detected: boolean;
  };
}

export interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  mark_price: number;
  pnl: number;
}

export interface PositionsResponse {
  positions: Position[];
  timestamp: number;
}

export interface RiskEvent {
  timestamp: number;
  event_id: string;
  event_type: string;
  level: string;
  reason: string;
  risk_type?: string;
  metadata?: Record<string, unknown>;
}

export interface ContractRiskItem {
  timestamp: number;
  event_id: string;
  event_type: string;
  severity: string;
  reason: string;
  trace_id?: string;
  data?: Record<string, unknown>;
}

export interface ContractRisksResponse {
  contract_version: string;
  count: number;
  items: ContractRiskItem[];
}

export interface TraceSummary {
  trace_id: string;
  first_ts: number;
  last_ts: number;
  last_event_type: string;
  symbol?: string | null;
  status?: string | null;
}

export interface TraceListResponse {
  items: TraceSummary[];
}

export interface TraceTimelineEvent {
  ts: number;
  event_type: string;
  detail: Record<string, unknown>;
  missing?: boolean;
}

export interface TraceTimelineResponse {
  trace_id: string;
  status: string;
  started_at: string;
  events: TraceTimelineEvent[];
}

export interface DashboardSummary {
  total_traces: number;
  by_last_event_type: Record<string, number>;
  reject_hard_count: number;
  reject_soft_count: number;
  exec_report_count: number;
  avg_latency_ms: number | null;
  window_sec: number;
}

export const apiClient = {
  async getHealth(): Promise<ContractHealth | null> {
    return safeGet<ContractHealth>(`${API_V1_BASE}/ops/health`);
  },

  async getState(): Promise<ContractState | null> {
    return safeGet<ContractState>(`${API_V1_BASE}/ops/state`);
  },

  async getEngineState(): Promise<EngineState | null> {
    const state = await apiClient.getState();
    if (!state) return null;

    return {
      kill_switch_on: state.kill.is_on,
      risk_type: state.freshness.checkpoint_status,
      reason: state.kill.reason,
      uptime_sec: state.freshness.checkpoint_age_sec,
      published: state.counters.published,
      consumed: state.counters.consumed,
      pending_total: state.counters.pending_total,
    };
  },

  async getPositions(): Promise<PositionsResponse | null> {
    return safeGet<PositionsResponse>(`${API_V1_BASE}/ops/positions`);
  },

  async getRisks(limit: number = 20): Promise<ContractRisksResponse | null> {
    return safeGet<ContractRisksResponse>(
      `${API_V1_BASE}/ops/risks?limit=${limit}`,
    );
  },

  async getRiskHistory(limit: number = 20): Promise<RiskEvent[]> {
    const risks = await apiClient.getRisks(limit);
    if (!risks?.items?.length) return [];
    return risks.items.map((event) => ({
      timestamp: event.timestamp,
      event_id: event.event_id,
      event_type: event.event_type,
      level: event.severity,
      reason: event.reason,
      metadata: {
        trace_id: event.trace_id,
        ...(event.data || {}),
      },
    }));
  },

  async postEmitEvent(payload: {
    event_type: string;
    trace_id?: string;
    severity?: string;
    index?: number;
    total?: number;
    metadata?: Record<string, unknown>;
  }): Promise<{
    ok: boolean;
    emitted: string;
    trace_id: string;
    ts: number;
  } | null> {
    return safePost<{
      ok: boolean;
      emitted: string;
      trace_id: string;
      ts: number;
    }>(`${API_V1_BASE}/dev/emit-event`, payload);
  },

  async toggleKillSwitch(
    isOn: boolean,
    reason: string,
  ): Promise<{ audit_id: string }> {
    const response = await fetch(`${API_BASE}/control/kill-switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_on: isOn, reason }),
    });
    if (!response.ok) throw new Error("Failed to toggle kill-switch");
    return response.json();
  },

  async getTraceList(params?: {
    limit?: number;
    event_type?: string;
    since_ms?: number;
  }): Promise<TraceSummary[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.event_type) query.set("event_type", params.event_type);
    if (params?.since_ms) query.set("since_ms", String(params.since_ms));

    const result = await safeGet<TraceListResponse>(
      `${API_BASE}/dashboard/traces?${query.toString()}`,
    );
    return result?.items || [];
  },

  async getTraceTimeline(
    traceId: string,
  ): Promise<TraceTimelineResponse | null> {
    return safeGet<TraceTimelineResponse>(
      `${API_BASE}/dashboard/orders/${traceId}`,
    );
  },

  async getDashboardSummary(
    windowSec: number = 300,
  ): Promise<DashboardSummary | null> {
    return safeGet<DashboardSummary>(
      `${API_BASE}/dashboard/summary?window_sec=${windowSec}`,
    );
  },
};
