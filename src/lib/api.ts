const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

// Fail Silent helper for optional endpoints
async function safeGet<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url)
    if (response.status === 404) return null
    if (!response.ok) return null
    return response.json()
  } catch {
    return null
  }
}

export interface EngineState {
  kill_switch_on: boolean
  risk_type?: string
  reason?: string
  uptime_sec: number
  published: number
  consumed: number
  pending_total: number
}

export interface Position {
  symbol: string
  qty: number
  avg_entry_price: number
  mark_price: number
  pnl: number
}

export interface PositionsResponse {
  positions: Position[]
  timestamp: number
}

export interface RiskEvent {
  timestamp: number
  event_id: string
  event_type: string
  level: string
  reason: string
  risk_type?: string
  metadata?: Record<string, unknown>
}

export interface TraceSummary {
  trace_id: string
  first_ts: number
  last_ts: number
  last_event_type: string
  symbol?: string | null
  status?: string | null
}

export interface TraceListResponse {
  items: TraceSummary[]
}

export interface TraceTimelineEvent {
  ts: number
  event_type: string
  detail: Record<string, unknown>
  missing?: boolean
}

export interface TraceTimelineResponse {
  trace_id: string
  status: string
  started_at: string
  events: TraceTimelineEvent[]
}

export interface DashboardSummary {
  total_traces: number
  by_last_event_type: Record<string, number>
  reject_hard_count: number
  reject_soft_count: number
  exec_report_count: number
  avg_latency_ms: number | null
  window_sec: number
}

export const apiClient = {
  async getEngineState(): Promise<EngineState | null> {
    return safeGet<EngineState>(`${API_BASE}/state/engine`)
  },

  async getPositions(): Promise<PositionsResponse | null> {
    return safeGet<PositionsResponse>(`${API_BASE}/state/positions`)
  },

  async getRiskHistory(limit: number = 20): Promise<RiskEvent[]> {
    const result = await safeGet<{ events: RiskEvent[] }>(`${API_BASE}/history/risks?limit=${limit}`)
    return result?.events || []
  },

  async toggleKillSwitch(isOn: boolean, reason: string): Promise<{ audit_id: string }> {
    const response = await fetch(`${API_BASE}/control/kill-switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_on: isOn, reason }),
    })
    if (!response.ok) throw new Error('Failed to toggle kill-switch')
    return response.json()
  },

  async getTraceList(params?: {
    limit?: number
    event_type?: string
    since_ms?: number
  }): Promise<TraceSummary[]> {
    const query = new URLSearchParams()
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.event_type) query.set('event_type', params.event_type)
    if (params?.since_ms) query.set('since_ms', String(params.since_ms))

    const result = await safeGet<TraceListResponse>(
      `${API_BASE}/dashboard/traces?${query.toString()}`
    )
    return result?.items || []
  },

  async getTraceTimeline(traceId: string): Promise<TraceTimelineResponse | null> {
    return safeGet<TraceTimelineResponse>(`${API_BASE}/dashboard/orders/${traceId}`)
  },

  async getDashboardSummary(windowSec: number = 300): Promise<DashboardSummary | null> {
    return safeGet<DashboardSummary>(`${API_BASE}/dashboard/summary?window_sec=${windowSec}`)
  },
}
