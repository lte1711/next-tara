'use client'

import { EngineState } from '@/lib/api'

interface EngineStatusCardProps {
  engine: EngineState | null
  loading: boolean
}

export function EngineStatusCard({ engine, loading }: EngineStatusCardProps) {
  if (loading) {
    return (
      <div className="bg-panel rounded-lg p-6 border border-border-subtle">
        <h2 className="text-xl font-bold mb-4 text-text-strong">Engine Status</h2>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-panel-2 rounded w-1/2"></div>
          <div className="h-4 bg-panel-2 rounded w-1/3"></div>
        </div>
      </div>
    )
  }

  if (!engine) {
    return (
      <div className="bg-panel rounded-lg p-6 border border-border-subtle">
        <h2 className="text-xl font-bold mb-4 text-text-strong">Engine Status</h2>
        <p className="text-muted">No data available</p>
      </div>
    )
  }

  const killSwitchColor = engine.kill_switch_on ? 'text-danger' : 'text-ok'
  const killSwitchBg = engine.kill_switch_on ? 'bg-danger/10' : 'bg-ok/10'

  return (
    <div className="bg-panel rounded-lg p-6 border border-border-subtle">
      <h2 className="text-xl font-bold mb-4 text-text-strong">Engine Status</h2>
      
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
          <span className="text-muted">Risk Type:</span>
          <span className="font-mono">{engine.risk_type || '—'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Reason:</span>
          <span className="font-mono">{engine.reason || '—'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Uptime:</span>
          <span className="font-mono">{engine.uptime_sec.toFixed(1)}s</span>
        </div>
        <div className="flex justify-between pt-2 border-t border-border-subtle mt-2">
          <span className="text-muted">Published:</span>
          <span className="font-mono">{engine.published}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Consumed:</span>
          <span className="font-mono">{engine.consumed}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Pending:</span>
          <span className="font-mono">{engine.pending_total}</span>
        </div>
      </div>
    </div>
  )
}
