'use client'

import { useState, useCallback, useEffect, useRef } from 'react'

export interface AuditLogEntry {
  event_type: string
  ts: number
  trace_id: string
  data: Record<string, any>
}

interface AuditTerminalProps {
  logs: AuditLogEntry[]
  onTraceFilterChange?: (traceId: string | null) => void
}

export function AuditTerminal({ logs, onTraceFilterChange }: AuditTerminalProps) {
  const [filterTraceId, setFilterTraceId] = useState<string | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const terminalRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const filteredLogs = filterTraceId 
    ? logs.filter(log => log.trace_id === filterTraceId)
    : logs

  const handleTraceClick = (traceId: string) => {
    const newFilter = filterTraceId === traceId ? null : traceId
    setFilterTraceId(newFilter)
    onTraceFilterChange?.(newFilter)
  }

  const getLogColor = (eventType: string): string => {
    switch (eventType) {
      case 'RISK_TRIGGERED':
        return 'text-red-400'
      case 'ORDER_REJECTED':
        return 'text-yellow-400'
      case 'LEVEL_DOWNGRADED':
        return 'text-red-600'
      case 'LEVEL_RESTORED':
        return 'text-green-400'
      case 'SYSTEM_GUARD':
        return 'text-orange-400'
      case 'AUDIT_LOG':
        return 'text-blue-400'
      default:
        return 'text-gray-400'
    }
  }

  const getBgColor = (eventType: string): string => {
    switch (eventType) {
      case 'LEVEL_DOWNGRADED':
        return 'bg-red-950'
      case 'LEVEL_RESTORED':
        return 'bg-green-950'
      case 'RISK_TRIGGERED':
        return 'bg-red-900'
      default:
        return 'bg-gray-900'
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-950 border border-gray-700 rounded">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 p-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className="text-green-400 text-lg">▶</span>
          <span className="text-gray-400 font-mono text-sm">AUDIT STREAM</span>
          <span className="text-gray-600 text-xs ml-2">({filteredLogs.length})</span>
        </div>
        <div className="flex gap-2">
          {filterTraceId && (
            <button
              onClick={() => {
                setFilterTraceId(null)
                onTraceFilterChange?.(null)
              }}
              className="text-xs bg-gray-800 hover:bg-gray-700 px-2 py-1 rounded text-gray-300"
            >
              Clear Filter
            </button>
          )}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`text-xs px-2 py-1 rounded ${
              autoScroll 
                ? 'bg-green-900 text-green-300' 
                : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
            }`}
          >
            {autoScroll ? '🔒 Auto' : '🔓 Manual'}
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div
        ref={terminalRef}
        className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1"
      >
        {filteredLogs.length === 0 ? (
          <div className="text-gray-600">
            {filterTraceId ? '(no logs matching filter)' : '(waiting for events...)'}
          </div>
        ) : (
          filteredLogs.map((log, idx) => {
            const reason =
              (log.data?.reason as string | undefined) ||
              (log.data?.rejection_reason as string | undefined) ||
              ''

            return (
            <div
              key={idx}
              className={`${getBgColor(log.event_type)} p-2 rounded hover:bg-opacity-70 transition-colors cursor-pointer border-l-4 border-gray-700`}
              onClick={() => handleTraceClick(log.trace_id)}
            >
              <div className="flex items-start gap-2">
                {/* Timestamp */}
                <span className="text-gray-600 shrink-0 whitespace-nowrap">
                  {new Date(log.ts).toLocaleTimeString('en-US', { 
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                </span>

                {/* Event Type */}
                <span className={`${getLogColor(log.event_type)} font-bold shrink-0 whitespace-nowrap`}>
                  [{log.event_type}]
                </span>

                {reason && (
                  <span className="text-red-300 font-semibold shrink-0 whitespace-nowrap">
                    reason={reason}
                  </span>
                )}

                {/* Trace ID (clickable) */}
                <span
                  className={`text-blue-300 hover:text-blue-100 underline cursor-pointer whitespace-nowrap`}
                  title="Click to filter by trace_id"
                >
                  #{log.trace_id.substring(0, 8)}
                </span>

                {/* Data Preview */}
                <span className="text-gray-300 break-all">
                  {JSON.stringify(log.data).substring(0, 100)}
                  {JSON.stringify(log.data).length > 100 ? '...' : ''}
                </span>
              </div>
            </div>
          )})
        )}
      </div>

      {/* Footer */}
      <div className="bg-gray-900 border-t border-gray-700 p-2 text-xs text-gray-600">
        {filterTraceId && (
          <span>
            🔍 Filtered by trace_id: <span className="text-gray-400 font-mono">{filterTraceId.substring(0, 12)}...</span>
          </span>
        )}
      </div>
    </div>
  )
}
