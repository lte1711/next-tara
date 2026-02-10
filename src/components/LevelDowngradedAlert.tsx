'use client'

import { useState, useEffect } from 'react'

export interface LevelDowngradedEvent {
  previous_level: number
  new_level: number
  reason: string
  affected_symbols?: string[]
  trace_id: string
  ts: number
}

interface LevelDowngradedAlertProps {
  event: LevelDowngradedEvent | null
  onAcknowledge: () => void
}

export function LevelDowngradedAlert({ event, onAcknowledge }: LevelDowngradedAlertProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (event) {
      setIsVisible(true)
    }
  }, [event])

  if (!event || !isVisible) {
    return null
  }

  const handleAcknowledge = () => {
    setIsVisible(false)
    onAcknowledge()
  }

  const levelColor = {
    0: 'bg-red-900',
    1: 'bg-red-800',
    2: 'bg-orange-700',
    3: 'bg-yellow-700',
    4: 'bg-green-700',
  }

  const levelName = {
    0: 'CRITICAL',
    1: 'SEVERE',
    2: 'HIGH',
    3: 'MEDIUM',
    4: 'LOW',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
      <div className="bg-gray-800 border-4 border-red-600 rounded-lg p-8 max-w-md animate-pulse">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-red-400 mb-2">⚠️ RISK LEVEL DOWNGRADED</h2>
          <p className="text-gray-400 text-sm">Operational Response Required</p>
        </div>

        {/* Level Change */}
        <div className="bg-gray-900 rounded p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-gray-500 text-sm">Previous Level</p>
              <div className={`${levelColor[event.previous_level as keyof typeof levelColor]} text-white font-bold py-2 px-4 rounded inline-block`}>
                Level {event.previous_level} ({levelName[event.previous_level as keyof typeof levelName]})
              </div>
            </div>
            <span className="text-2xl">→</span>
            <div>
              <p className="text-gray-500 text-sm">New Level</p>
              <div className={`${levelColor[event.new_level as keyof typeof levelColor]} text-white font-bold py-2 px-4 rounded inline-block`}>
                Level {event.new_level} ({levelName[event.new_level as keyof typeof levelName]})
              </div>
            </div>
          </div>
        </div>

        {/* Reason */}
        <div className="bg-gray-900 rounded p-4 mb-6">
          <p className="text-gray-500 text-sm mb-2">Reason</p>
          <p className="text-white font-mono text-sm break-words">{event.reason}</p>
        </div>

        {/* Affected Symbols */}
        {event.affected_symbols && event.affected_symbols.length > 0 && (
          <div className="bg-gray-900 rounded p-4 mb-6">
            <p className="text-gray-500 text-sm mb-2">Affected Symbols</p>
            <div className="flex flex-wrap gap-2">
              {event.affected_symbols.map(symbol => (
                <span key={symbol} className="bg-red-900 text-red-200 px-3 py-1 rounded text-sm">
                  {symbol}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Audit Info */}
        <div className="bg-gray-900 rounded p-4 mb-6">
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <p className="text-gray-500 mb-1">Trace ID</p>
              <p className="text-gray-300 font-mono break-all">{event.trace_id.substring(0, 16)}...</p>
            </div>
            <div>
              <p className="text-gray-500 mb-1">Timestamp</p>
              <p className="text-gray-300 font-mono">{new Date(event.ts).toLocaleTimeString()}</p>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <button
          onClick={handleAcknowledge}
          className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded transition-colors"
        >
          ✓ Acknowledged
        </button>
      </div>
    </div>
  )
}
