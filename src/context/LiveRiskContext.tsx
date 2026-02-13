import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

type Mode = 'NORMAL' | 'DOWNGRADE' | 'KILL' | 'UNKNOWN'

export type RiskEvent = {
  type: string
  time?: string
  trace_id?: string
  severity?: string
  message?: string
  payload?: any
}

export type RiskState = {
  mode: Mode
  risk_score?: number
  limits?: Record<string, number>
  reason?: string
}

type LiveRiskContextValue = {
  state: RiskState
  events: RiskEvent[]
  connected: boolean
}

const LiveRiskContext = createContext<LiveRiskContextValue | undefined>(undefined)

export const useLiveRisk = () => {
  const v = useContext(LiveRiskContext)
  if (!v) throw new Error('useLiveRisk must be used within LiveRiskProvider')
  return v
}

function parseEvent(raw: any): RiskEvent {
  try {
    if (typeof raw === 'string') return JSON.parse(raw)
    return raw
  } catch (e) {
    return { type: 'unknown', message: String(raw), payload: raw }
  }
}

export const LiveRiskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<RiskState>({ mode: 'UNKNOWN' })
  const [events, setEvents] = useState<RiskEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<number | null>(null)

  const WS = typeof window !== 'undefined' ? process.env.NEXT_PUBLIC_API_WS || 'ws://127.0.0.1:8000' : ''

  useEffect(() => {
    if (!WS) return

    let closed = false
    function connect() {
      const ws = new WebSocket(`${WS.replace(/\/+$/,'')}/ws/events`)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        // optional: fetch snapshot via HTTP here if desired
      }

      ws.onmessage = (ev) => {
        const parsed = parseEvent(ev.data)
        // keep latest state derived from event types
        if (parsed.type === 'risk_state' || parsed.type === 'risk_update') {
          const p = parsed.payload || parsed
          setState((s) => ({ ...s, mode: (p.mode || p.status || s.mode) as any, risk_score: p.risk_score ?? s.risk_score, limits: p.limits ?? s.limits, reason: p.reason ?? s.reason }))
        } else if (parsed.type === 'risk_downgrade') {
          const p = parsed.payload || parsed
          setState((s) => ({ ...s, mode: 'DOWNGRADE', limits: p.limits ?? s.limits, reason: p.reason ?? s.reason }))
        } else if (parsed.type === 'kill_switch') {
          const p = parsed.payload || parsed
          setState((s) => ({ ...s, mode: 'KILL', reason: p.reason ?? s.reason }))
        }

        setEvents((e) => [{ ...parsed, time: new Date().toISOString() }, ...e].slice(0, 200))
      }

      ws.onclose = () => {
        setConnected(false)
        if (!closed) {
          // simple reconnect backoff
          reconnectRef.current = window.setTimeout(() => connect(), 2000)
        }
      }

      ws.onerror = () => {
        // errors will cause close and reconnect
      }
    }

    connect()

    return () => {
      closed = true
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [WS])

  const value = useMemo(() => ({ state, events, connected }), [state, events, connected])

  return <LiveRiskContext.Provider value={value}>{children}</LiveRiskContext.Provider>
}

export default LiveRiskProvider
