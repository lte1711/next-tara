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
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4">Kill-Switch Control</h2>

      <div className="space-y-4">
        {/* Current Status */}
        <div className={`p-3 rounded ${isOn ? 'bg-red-900' : 'bg-green-900'}`}>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isOn ? 'text-red-500' : 'text-green-500'}`}></div>
            <span className={`font-mono text-sm ${isOn ? 'text-red-400' : 'text-green-400'}`}>
              Current: {isOn ? 'ON' : 'OFF'}
            </span>
          </div>
        </div>

        {/* Reason Input */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">
            Reason (required)
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Manual intervention, high volatility detected"
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-500 text-sm"
            disabled={loading}
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 rounded bg-red-900 border border-red-700">
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* Audit ID */}
        {auditId && (
          <div className="p-3 rounded bg-green-900 border border-green-700">
            <p className="text-green-300 text-sm">
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
              ? 'bg-gray-700 cursor-not-allowed'
              : isOn
              ? 'bg-yellow-600 hover:bg-yellow-700'
              : 'bg-red-600 hover:bg-red-700'
          }`}
        >
          {loading ? 'Processing...' : isOn ? 'Turn OFF' : 'Turn ON'}
        </button>
      </div>
    </div>
  )
}
