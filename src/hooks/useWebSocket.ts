'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

export type WSEventType = 
  | 'risk_event' 
  | 'order_update' 
  | 'position_snapshot' 
  | 'engine_state' 
  | 'heartbeat'
  | 'RISK_TRIGGERED'
  | 'ORDER_REJECTED'
  | 'LEVEL_DOWNGRADED'
  | 'LEVEL_RESTORED'
  | 'SYSTEM_GUARD'
  | 'AUDIT_LOG'
  | 'ROUTE_DECIDED'
  | 'ROUTE_SPLIT'
  | 'ROUTE_REJECTED_SOFT'
  | 'ROUTE_REJECTED_HARD'

export interface WSEvent {
  event_type: WSEventType
  type?: string  // fallback for alternative message format
  ts: number
  trace_id?: string
  data: Record<string, unknown>
}

export interface UseWebSocketOptions {
  url: string
  onMessage?: (event: WSEvent) => void
  onError?: (error: Error) => void
  onConnect?: () => void
  onDisconnect?: () => void
  backoffMultiplier?: number
  maxBackoffMs?: number
}

export function useWebSocket(options: UseWebSocketOptions) {
  const { 
    url, 
    onMessage, 
    onError, 
    onConnect, 
    onDisconnect,
    backoffMultiplier = 2,
    maxBackoffMs = 30000,
  } = options
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSEvent | null>(null)
  const [backoffMs, setBackoffMs] = useState(1000)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(false)

  const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null

  const isWSEventType = (value: string): value is WSEventType =>
    [
      'risk_event',
      'order_update',
      'position_snapshot',
      'engine_state',
      'heartbeat',
      'RISK_TRIGGERED',
      'ORDER_REJECTED',
      'LEVEL_DOWNGRADED',
      'LEVEL_RESTORED',
      'SYSTEM_GUARD',
      'AUDIT_LOG',
      'ROUTE_DECIDED',
      'ROUTE_SPLIT',
      'ROUTE_REJECTED_SOFT',
      'ROUTE_REJECTED_HARD',
    ].includes(value)

  // Mount/unmount tracking - separate from connection logic
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      try { wsRef.current?.close() } catch {}
      wsRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!url) return // url 없을 때만 막음
    if (!mountedRef.current) return // unmount 이후에만 막음

    // 중복 연결 방지
    if (wsRef.current && 
        (wsRef.current.readyState === WebSocket.OPEN || 
         wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WS] Connected:', url)
        setIsConnected(true)
        setBackoffMs(1000)
        onConnect?.()
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const raw: unknown = JSON.parse(event.data)
          if (!isRecord(raw)) return
          const rawEventType = typeof raw.event_type === 'string' ? raw.event_type : undefined
          const rawType = typeof raw.type === 'string' ? raw.type : undefined
          const event_type: WSEventType = rawEventType && isWSEventType(rawEventType)
            ? rawEventType
            : rawType && isWSEventType(rawType)
            ? rawType
            : 'heartbeat'
          const data: WSEvent = {
            event_type,
            type: rawType,
            ts: typeof raw.ts === 'number' ? raw.ts : Math.floor(Date.now() / 1000),
            trace_id: typeof raw.trace_id === 'string' ? raw.trace_id : undefined,
            data: isRecord(raw.data) ? raw.data : {},
          }
          console.log('[WS] Received:', data.event_type || data.type, data)
          setLastMessage(data)
          onMessage?.(data)
        } catch (_e) {
          console.error('[WS] Parse error:', _e)
        }
      }

      ws.onerror = () => {
        const error = new Error('WebSocket error')
        console.error('[WS] Error:', error)
        onError?.(error)
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected, will reconnect in', backoffMs, 'ms')
        setIsConnected(false)
        onDisconnect?.()

        // Schedule reconnection with exponential backoff
        if (mountedRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              const nextBackoff = Math.min(backoffMs * backoffMultiplier, maxBackoffMs)
              setBackoffMs(nextBackoff)
              connect()
            }
          }, backoffMs)
        }
      }

      wsRef.current = ws
    } catch (_e) {
      console.error('[WS] Connection error:', _e)
      onError?.(_e instanceof Error ? _e : new Error(String(_e)))
    }
  }, [url, onMessage, onError, onConnect, onDisconnect, backoffMs, backoffMultiplier, maxBackoffMs])

  // Initial connection on url change
  useEffect(() => {
    if (!url) return
    connect()
    // Cleanup: Do NOT close on effect re-run, only on unmount (handled by mountedRef useEffect)
  }, [url, connect])

  return { isConnected, lastMessage }
}
