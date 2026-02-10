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

export interface WSEvent {
  event_type: WSEventType
  ts: number
  trace_id?: string
  data: Record<string, any>
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
  const isMountedRef = useRef(true)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])

  const connect = useCallback(() => {
    if (!isMountedRef.current) return

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WS] Connected:', url)
        setIsConnected(true)
        setBackoffMs(1000) // Reset backoff on successful connect
        onConnect?.()
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as WSEvent
          console.log('[WS] Received:', data.event_type || data.type, data)
          setLastMessage(data)
          onMessage?.(data)
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      ws.onerror = (event: Event) => {
        const error = new Error('WebSocket error')
        console.error('[WS] Error:', error)
        onError?.(error)
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected, will reconnect in', backoffMs, 'ms')
        setIsConnected(false)
        onDisconnect?.()

        // Schedule reconnection with exponential backoff
        if (isMountedRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              const nextBackoff = Math.min(backoffMs * backoffMultiplier, maxBackoffMs)
              setBackoffMs(nextBackoff)
              connect()
            }
          }, backoffMs)
        }
      }

      wsRef.current = ws
    } catch (e) {
      console.error('[WS] Connection error:', e)
      onError?.(e instanceof Error ? e : new Error(String(e)))
    }
  }, [url, onMessage, onError, onConnect, onDisconnect, backoffMs, backoffMultiplier, maxBackoffMs])

  // Initial connection
  useEffect(() => {
    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  return { isConnected, lastMessage }
      }
    }
  }, [url, onMessage, onError, onConnect, onDisconnect])

  return { isConnected, lastMessage }
}
