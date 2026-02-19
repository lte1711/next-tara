'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api'

interface KillSwitchControlPanelProps {
  isOn: boolean
  onToggle: (success: boolean) => void
}

export function KillSwitchControlPanel({ isOn, onToggle }: KillSwitchControlPanelProps) {
  const [loading, setLoading] = useState(false)
  const [reason, setReason] = useState('')
  const [auditId, setAuditId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleToggle = async () => {
    if (!reason.trim()) {
      setError('Reason is required')
      return
    }

    setLoading(true)
    setError(null)
    setAuditId(null)

    try {
      const result = await apiClient.toggleKillSwitch(!isOn, reason)
      setAuditId(result.audit_id)
      onToggle(true)
      setReason('')
      console.log('[Kill-Switch] Toggled | audit_id:', result.audit_id)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      console.error('[Kill-Switch] Error:', errorMsg)
      onToggle(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-panel rounded-lg p-6 border border-border-subtle">
      <h2 className="text-xl font-bold mb-4 text-text-strong">Kill-Switch Control</h2>

      <div className="space-y-4">
        {/* Current Status */}
        <div className={`p-3 rounded ${isOn ? 'bg-danger/10 border border-danger' : 'bg-ok/10 border border-ok'}`}>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isOn ? 'bg-danger' : 'bg-ok'}`}></div>
            <span className={`font-mono text-sm ${isOn ? 'text-danger' : 'text-ok'}`}>
              Current: {isOn ? 'ON' : 'OFF'}
            </span>
          </div>
        </div>

        {/* Reason Input */}
        <div>
          <label className="block text-sm text-muted mb-2">
            Reason (required)
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Manual intervention, high volatility detected"
            className="w-full bg-panel-2 border border-border rounded px-3 py-2 text-text placeholder-muted-dark text-sm"
            disabled={loading}
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 rounded bg-danger/10 border border-danger">
            <p className="text-danger text-sm">{error}</p>
          </div>
        )}

        {/* Audit ID */}
        {auditId && (
          <div className="p-3 rounded bg-ok/10 border border-ok">
            <p className="text-ok text-sm">
              <strong>Success!</strong> Audit ID: {auditId}
            </p>
          </div>
        )}

        {/* Toggle Button */}
        <button
          onClick={handleToggle}
          disabled={loading}
          className={`w-full py-2 px-4 rounded font-bold transition-colors text-white ${
            loading
              ? 'bg-muted-dark cursor-not-allowed'
              : isOn
              ? 'bg-warn hover:bg-warn/80'
              : 'bg-danger hover:bg-danger/80'
          }`}
        >
          {loading ? 'Processing...' : isOn ? 'Turn OFF' : 'Turn ON'}
        </button>
      </div>
    </div>
  )
}
