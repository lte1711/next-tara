'use client'

import { useState, useEffect, useCallback } from 'react'

export type WSEventType = 'risk_event' | 'order_update' | 'position_snapshot' | 'engine_state' | 'heartbeat'

export interface WSEvent {
  event_type: WSEventType
  ts: number
  data: Record<string, any>
}

export interface UseWebSocketOptions {
  url: string
  onMessage?: (event: WSEvent) => void
  onError?: (error: Error) => void
  onConnect?: () => void
  onDisconnect?: () => void
}

export function useWebSocket(options: UseWebSocketOptions) {
  const { url, onMessage, onError, onConnect, onDisconnect } = options
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSEvent | null>(null)

  useEffect(() => {
    const ws = new WebSocket(url)

    ws.onopen = () => {
      console.log('[WS] Connected:', url)
      setIsConnected(true)
      onConnect?.()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
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
      console.log('[WS] Disconnected')
      setIsConnected(false)
      onDisconnect?.()
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [url, onMessage, onError, onConnect, onDisconnect])

  return { isConnected, lastMessage }
}
