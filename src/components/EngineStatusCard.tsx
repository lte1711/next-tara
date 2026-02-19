'use client'

import { EngineState } from '@/lib/api'

interface EngineStatusCardProps {
  engine: EngineState | null
  loading: boolean
}

export function EngineStatusCard({ engine, loading }: EngineStatusCardProps) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Engine Status</h2>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-700 rounded w-1/2"></div>
          <div className="h-4 bg-gray-700 rounded w-1/3"></div>
        </div>
      </div>
    )
  }

  if (!engine) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Engine Status</h2>
        <p className="text-gray-400">No data available</p>
      </div>
    )
  }

  const killSwitchColor = engine.kill_switch_on ? 'text-red-500' : 'text-green-500'
  const killSwitchBg = engine.kill_switch_on ? 'bg-red-900' : 'bg-green-900'

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4">Engine Status</h2>
      
      <div className={`mb-4 p-3 rounded ${killSwitchBg}`}>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${killSwitchColor}`}></div>
          <span className={`font-mono text-sm ${killSwitchColor}`}>
            {engine.kill_switch_on ? 'KILL-SWITCH: ON' : 'KILL-SWITCH: OFF'}
          </span>
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-400">Risk Type:</span>
          <span className="font-mono">{engine.risk_type || '—'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Reason:</span>
          <span className="font-mono">{engine.reason || '—'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Uptime:</span>
          <span className="font-mono">{engine.uptime_sec.toFixed(1)}s</span>
        </div>
        <div className="flex justify-between pt-2 border-t border-gray-700 mt-2">
          <span className="text-gray-400">Published:</span>
          <span className="font-mono">{engine.published}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Consumed:</span>
          <span className="font-mono">{engine.consumed}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Pending:</span>
          <span className="font-mono">{engine.pending_total}</span>
        </div>
      </div>
    </div>
  )
}
