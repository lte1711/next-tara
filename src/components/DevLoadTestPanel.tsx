'use client'

import { useState } from 'react'

type DevLoadTestPanelProps = {
  onEmit10kEvents?: () => void
}

export function DevLoadTestPanel({ onEmit10kEvents }: DevLoadTestPanelProps): JSX.Element {
  const [isRunning, setIsRunning] = useState(false)
  const [eventsSent, setEventsSent] = useState(0)
  const [droppedCount, setDroppedCount] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const handleEmit10k = async () => {
    onEmit10kEvents?.()
    setIsRunning(true)
    setEventsSent(0)
    setDroppedCount(0)
    setError(null)

    try {
      // Simulate 10,000 event emissions
      const eventTypes = [
        'RISK_TRIGGERED',
        'ORDER_REJECTED',
        'LEVEL_DOWNGRADED',
        'LEVEL_RESTORED',
        'SYSTEM_GUARD',
        'AUDIT_LOG',
      ]

      for (let i = 0; i < 10000; i++) {
        try {
          const eventType = eventTypes[i % eventTypes.length]
          
          // Emit to backend (assuming POST /api/dev/emit-event)
          const response = await fetch('/api/dev/emit-event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              event_type: eventType,
              index: i,
              total: 10000,
            }),
          })

          if (!response.ok) {
            setDroppedCount(prev => prev + 1)
          }
          setEventsSent(i + 1)

          // Throttle to avoid overwhelming the connection
          if (i % 100 === 0) {
            await new Promise(resolve => setTimeout(resolve, 10))
          }
        } catch {
          setDroppedCount(prev => prev + 1)
          setEventsSent(i + 1)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="bg-gray-900 border-2 border-yellow-600 rounded p-4 mb-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-yellow-600 text-lg">⚙️</span>
        <h3 className="text-yellow-600 font-bold">DEV-ONLY: Load Test (10,000 Events)</h3>
      </div>

      {/* Status */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-gray-800 rounded p-3">
          <p className="text-gray-500 text-xs mb-1">Events Sent</p>
          <p className="text-white font-mono text-lg">{eventsSent.toLocaleString()}</p>
        </div>
        <div className="bg-gray-800 rounded p-3">
          <p className="text-gray-500 text-xs mb-1">Dropped</p>
          <p className={`font-mono text-lg ${droppedCount > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {droppedCount.toLocaleString()}
          </p>
        </div>
        <div className="bg-gray-800 rounded p-3">
          <p className="text-gray-500 text-xs mb-1">Success Rate</p>
          <p className="text-white font-mono text-lg">
            {eventsSent > 0 ? (((eventsSent - droppedCount) / eventsSent) * 100).toFixed(1) : 0}%
          </p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-900 border border-red-700 text-red-200 p-2 rounded mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Button */}
      <button
        onClick={handleEmit10k}
        disabled={isRunning}
        className={`w-full py-3 px-4 rounded font-bold transition-colors ${
          isRunning
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-yellow-600 hover:bg-yellow-700 text-white'
        }`}
      >
        {isRunning ? `Emitting... (${eventsSent}/10,000)` : 'Emit 10,000 Events (Stress Test)'}
      </button>

      {/* Info */}
      <p className="text-xs text-gray-500 mt-3">
        💡 Monitors: WS backpressure, UI responsiveness, reconnection behavior, WS_DROPPED audit logs
      </p>
    </div>
  )
}
