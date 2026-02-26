"use client"

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'

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
  rawEvents: unknown[]
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

let singletonWs: WebSocket | null = null
let singletonUrl = ''
let subscriberCount = 0
let reconnectTimer: number | null = null
let closeTimer: number | null = null
let backoffMs = 1000
let closingIntent = false
const messageSubscribers = new Set<(data: unknown) => void>()
const statusSubscribers = new Set<(connected: boolean) => void>()

const notifyConnected = (connected: boolean) => {
  statusSubscribers.forEach((fn) => fn(connected))
}

const getDefaultWsUrl = () => {
  if (typeof window === 'undefined') return ''
  const base = process.env.NEXT_PUBLIC_API_WS || 'ws://127.0.0.1:8100'
  return `${base.replace(/\/+$/, '')}/ws/events`
}

const connectSingleton = (url: string) => {
  if (!url) return
  if (singletonWs && (singletonWs.readyState === WebSocket.OPEN || singletonWs.readyState === WebSocket.CONNECTING)) {
    return
  }

  closingIntent = false
  console.log('[WS_CONNECT]', typeof window !== 'undefined' ? window.location.pathname : 'server', Date.now())

  const ws = new WebSocket(url)
  singletonWs = ws
  console.log('[WS_STATE]', ws.readyState)

  ws.onopen = () => {
    backoffMs = 1000
    notifyConnected(true)
  }

  ws.onmessage = (ev) => {
    let parsed: unknown = ev.data
    try {
      parsed = JSON.parse(ev.data)
    } catch {
      parsed = ev.data
    }
    messageSubscribers.forEach((fn) => fn(parsed))
  }

  ws.onclose = () => {
    if (singletonWs === ws) singletonWs = null
    notifyConnected(false)
    if (closingIntent || subscriberCount === 0) return
    if (reconnectTimer) window.clearTimeout(reconnectTimer)
    reconnectTimer = window.setTimeout(() => connectSingleton(url), backoffMs)
    backoffMs = Math.min(backoffMs * 2, 15000)
  }

  ws.onerror = () => {
    // ignore: onclose handles reconnect
  }
}

export const subscribeLiveRisk = (
  onMessage: (data: unknown) => void,
  onStatus?: (connected: boolean) => void
) => {
  subscriberCount += 1
  messageSubscribers.add(onMessage)
  if (onStatus) statusSubscribers.add(onStatus)

  if (closeTimer) {
    window.clearTimeout(closeTimer)
    closeTimer = null
  }

  const url = getDefaultWsUrl()
  if (url && singletonUrl !== url) singletonUrl = url
  connectSingleton(singletonUrl)

  return () => {
    messageSubscribers.delete(onMessage)
    if (onStatus) statusSubscribers.delete(onStatus)
    subscriberCount = Math.max(0, subscriberCount - 1)
    if (subscriberCount === 0) {
      closingIntent = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      closeTimer = window.setTimeout(() => {
        if (subscriberCount === 0 && singletonWs) {
          singletonWs.close(1000)
          singletonWs = null
        }
      }, 500)
    }
  }
}

export const LiveRiskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<RiskState>({ mode: 'UNKNOWN' })
  const [events, setEvents] = useState<RiskEvent[]>([])
  const [rawEvents, setRawEvents] = useState<unknown[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const unsubscribe = subscribeLiveRisk((raw) => {
      setRawEvents((e) => [raw, ...e].slice(0, 200))
      const parsed = parseEvent(raw)
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
    }, setConnected)

    return () => {
      unsubscribe()
    }
  }, [])

  const value = useMemo(() => ({ state, events, rawEvents, connected }), [state, events, rawEvents, connected])

  return <LiveRiskContext.Provider value={value}>{children}</LiveRiskContext.Provider>
}

export default LiveRiskProvider
