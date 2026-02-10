const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

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
  metadata?: Record<string, any>
}

export const apiClient = {
  async getEngineState(): Promise<EngineState> {
    const response = await fetch(`${API_BASE}/state/engine`)
    if (!response.ok) throw new Error('Failed to fetch engine state')
    return response.json()
  },

  async getPositions(): Promise<PositionsResponse> {
    const response = await fetch(`${API_BASE}/state/positions`)
    if (!response.ok) throw new Error('Failed to fetch positions')
    return response.json()
  },

  async getRiskHistory(limit: number = 20): Promise<RiskEvent[]> {
    const response = await fetch(`${API_BASE}/history/risks?limit=${limit}`)
    if (!response.ok) throw new Error('Failed to fetch risk history')
    const data = await response.json()
    return data.events || []
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
}
