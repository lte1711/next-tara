'use client'

import { useState, useEffect, useCallback } from 'react'
import { EngineStatusCard } from '@/components/EngineStatusCard'
import { PositionsCard } from '@/components/PositionsCard'
import { RecentRisksTable } from '@/components/RecentRisksTable'
import { KillSwitchControlPanel } from '@/components/KillSwitchControlPanel'
import { useWebSocket, WSEvent } from '@/hooks/useWebSocket'
import { apiClient, EngineState, Position, RiskEvent } from '@/lib/api'

export default function Dashboard() {
  const [engine, setEngine] = useState<EngineState | null>(null)
  const [positions, setPositions] = useState<Position[] | null>(null)
  const [risks, setRisks] = useState<RiskEvent[]>([])
  const [loadingEngine, setLoadingEngine] = useState(true)
  const [loadingPositions, setLoadingPositions] = useState(true)
  const [loadingRisks, setLoadingRisks] = useState(true)
  const [wsConnected, setWsConnected] = useState(false)

  // Load initial data
  const loadData = useCallback(async () => {
    try {
      setLoadingEngine(true)
      const engineData = await apiClient.getEngineState()
      setEngine(engineData)
      console.log('[Dashboard] Engine state loaded:', engineData)
    } catch (err) {
      console.error('[Dashboard] Failed to load engine state:', err)
    } finally {
      setLoadingEngine(false)
    }

    try {
      setLoadingPositions(true)
      const positionsData = await apiClient.getPositions()
      setPositions(positionsData.positions)
      console.log('[Dashboard] Positions loaded:', positionsData)
    } catch (err) {
      console.error('[Dashboard] Failed to load positions:', err)
    } finally {
      setLoadingPositions(false)
    }

    try {
      setLoadingRisks(true)
      const risksData = await apiClient.getRiskHistory(20)
      setRisks(risksData)
      console.log('[Dashboard] Risk history loaded:', risksData)
    } catch (err) {
      console.error('[Dashboard] Failed to load risk history:', err)
    } finally {
      setLoadingRisks(false)
    }
  }, [])

  // Load data on mount
  useEffect(() => {
    loadData()
  }, [loadData])

  // WebSocket message handler
  const handleWSMessage = useCallback((event: WSEvent) => {
    console.log('[Dashboard] WS Event:', event.event_type, event)

    switch (event.event_type) {
      case 'engine_state':
        // Update engine status
        if (event.data) {
          const newEngine: EngineState = {
            kill_switch_on: event.data.kill_switch_on,
            risk_type: event.data.risk_type,
            reason: event.data.reason,
            uptime_sec: event.data.uptime_sec || 0,
            published: event.data.published || 0,
            consumed: event.data.consumed || 0,
            pending_total: event.data.pending_total || 0,
          }
          setEngine(newEngine)
        }
        break

      case 'position_snapshot':
        // Update positions
        if (event.data) {
          const newPosition: Position = {
            symbol: event.data.symbol,
            qty: event.data.qty,
            avg_entry_price: event.data.avg_entry_price,
            mark_price: event.data.current_price,
            pnl: event.data.position_pnl,
          }
          setPositions(prev => {
            if (!prev) return [newPosition]
            const filtered = prev.filter(p => p.symbol !== newPosition.symbol)
            return [newPosition, ...filtered]
          })
        }
        break

      case 'risk_event':
        // Add to risk events (prepend to list)
        if (event.data) {
          const newRisk: RiskEvent = {
            timestamp: event.ts,
            event_id: event.data.metadata?.audit_id || `risk_${Date.now()}`,
            event_type: event.data.risk_type,
            level: event.data.metadata?.level || 'INFO',
            reason: event.data.reason,
            risk_type: event.data.risk_type,
            metadata: event.data.metadata,
          }
          setRisks(prev => [newRisk, ...prev.slice(0, 19)])
        }
        break

      case 'heartbeat':
        // Ignore heartbeats
        break
    }
  }, [])

  const wsUrl = (() => {
    if (typeof window === 'undefined') return ''
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = process.env.NEXT_PUBLIC_WS_URL || `${window.location.hostname}:8000`
    return `${protocol}//${host}/api/ws/events`
  })()

  useWebSocket({
    url: wsUrl,
    onMessage: handleWSMessage,
    onConnect: () => {
      setWsConnected(true)
      console.log('[Dashboard] WebSocket connected')
    },
    onDisconnect: () => {
      setWsConnected(false)
      console.log('[Dashboard] WebSocket disconnected')
    },
    onError: (error) => {
      console.error('[Dashboard] WebSocket error:', error)
    },
  })

  const handleKillSwitchToggle = async (success: boolean) => {
    if (success) {
      // Reload data after successful toggle
      await loadData()
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Command Center</h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-sm text-gray-400">
              {wsConnected ? 'WebSocket Connected' : 'WebSocket Disconnected'}
            </span>
          </div>
          <span className="text-sm text-gray-500">PHASE 9-1 Dashboard MVP</span>
        </div>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* A. Engine Status Card */}
        <EngineStatusCard engine={engine} loading={loadingEngine} />

        {/* B. Positions Card */}
        <PositionsCard positions={positions} loading={loadingPositions} />
      </div>

      {/* D. Kill-Switch Control Panel */}
      <div className="mb-6">
        <KillSwitchControlPanel
          isOn={engine?.kill_switch_on || false}
          onToggle={handleKillSwitchToggle}
        />
      </div>

      {/* C. Recent Risks Table */}
      <RecentRisksTable events={risks} loading={loadingRisks} />

      {/* Footer Debug Info */}
      <div className="mt-8 p-4 bg-gray-800 rounded border border-gray-700">
        <p className="text-xs text-gray-500 font-mono">
          API: {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'} | WS: {wsUrl}
        </p>
      </div>
    </div>
  )
}
