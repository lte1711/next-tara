"use client"

import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

type Mode = 'NORMAL' | 'DOWNGRADE' | 'KILL' | 'UNKNOWN'

export type RiskEvent = {
  type: string
  time?: string
  trace_id?: string
  severity?: string
  message?: string
  payload?: Record<string, unknown>
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

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const toMode = (value: unknown, fallback: Mode): Mode =>
  value === 'NORMAL' || value === 'DOWNGRADE' || value === 'KILL' || value === 'UNKNOWN'
    ? value
    : fallback

const toNumberRecord = (value: unknown): Record<string, number> | undefined => {
  if (!isRecord(value)) return undefined
  const entries = Object.entries(value).filter(([, v]) => typeof v === 'number')
  if (entries.length === 0) return undefined
  return Object.fromEntries(entries) as Record<string, number>
}

function parseEvent(raw: unknown): RiskEvent {
  try {
    if (typeof raw === 'string') {
      const parsed: unknown = JSON.parse(raw)
      if (isRecord(parsed)) {
        return {
          type: typeof parsed.type === 'string' ? parsed.type : 'unknown',
          time: typeof parsed.time === 'string' ? parsed.time : undefined,
          trace_id: typeof parsed.trace_id === 'string' ? parsed.trace_id : undefined,
          severity: typeof parsed.severity === 'string' ? parsed.severity : undefined,
          message: typeof parsed.message === 'string' ? parsed.message : undefined,
          payload: isRecord(parsed.payload) ? parsed.payload : undefined,
        }
      }
    }
    if (isRecord(raw)) {
      return {
        type: typeof raw.type === 'string' ? raw.type : 'unknown',
        time: typeof raw.time === 'string' ? raw.time : undefined,
        trace_id: typeof raw.trace_id === 'string' ? raw.trace_id : undefined,
        severity: typeof raw.severity === 'string' ? raw.severity : undefined,
        message: typeof raw.message === 'string' ? raw.message : undefined,
        payload: isRecord(raw.payload) ? raw.payload : undefined,
      }
    }
    return { type: 'unknown', message: String(raw) }
  } catch {
    return { type: 'unknown', message: String(raw) }
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
          const p = parsed.payload ?? (isRecord(parsed) ? parsed : {})
          setState((s) => ({
            ...s,
            mode: toMode((p as Record<string, unknown>).mode ?? (p as Record<string, unknown>).status, s.mode),
            risk_score: typeof (p as Record<string, unknown>).risk_score === 'number' ? (p as Record<string, unknown>).risk_score as number : s.risk_score,
            limits: toNumberRecord((p as Record<string, unknown>).limits) ?? s.limits,
            reason: typeof (p as Record<string, unknown>).reason === 'string' ? (p as Record<string, unknown>).reason as string : s.reason,
          }))
        } else if (parsed.type === 'risk_downgrade') {
          const p = parsed.payload ?? (isRecord(parsed) ? parsed : {})
          setState((s) => ({
            ...s,
            mode: 'DOWNGRADE',
            limits: toNumberRecord((p as Record<string, unknown>).limits) ?? s.limits,
            reason: typeof (p as Record<string, unknown>).reason === 'string' ? (p as Record<string, unknown>).reason as string : s.reason,
          }))
        } else if (parsed.type === 'kill_switch') {
          const p = parsed.payload ?? (isRecord(parsed) ? parsed : {})
          setState((s) => ({
            ...s,
            mode: 'KILL',
            reason: typeof (p as Record<string, unknown>).reason === 'string' ? (p as Record<string, unknown>).reason as string : s.reason,
          }))
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
