'use client'

import { useState, useEffect, useRef } from 'react'

export interface AuditLogEntry {
  event_type: string
  ts: number
  trace_id: string
  data: Record<string, unknown>
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

  const getDataString = (data: Record<string, unknown>, key: string): string => {
    const value = data[key]
    return typeof value === 'string' ? value : ''
  }

  const getLogColor = (eventType: string): string => {
    switch (eventType) {
      case 'RISK_TRIGGERED':
        return 'text-danger'
      case 'ORDER_REJECTED':
        return 'text-warn'
      case 'LEVEL_DOWNGRADED':
        return 'text-danger'
      case 'LEVEL_RESTORED':
        return 'text-ok'
      case 'SYSTEM_GUARD':
        return 'text-warn'
      case 'AUDIT_LOG':
        return 'text-info'
      default:
        return 'text-muted'
    }
  }

  const getBgColor = (eventType: string): string => {
    switch (eventType) {
      case 'LEVEL_DOWNGRADED':
        return 'bg-danger/10'
      case 'LEVEL_RESTORED':
        return 'bg-ok/10'
      case 'RISK_TRIGGERED':
        return 'bg-danger/5'
      default:
        return 'bg-panel-2'
    }
  }

  return (
    <div className="flex flex-col h-full bg-panel border border-border-subtle rounded">
      {/* Header */}
      <div className="bg-panel-2 border-b border-border-subtle p-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className="text-ok text-lg">▶</span>
          <span className="text-muted font-mono text-sm">AUDIT STREAM</span>
          <span className="text-muted-dark text-xs ml-2">({filteredLogs.length})</span>
        </div>
        <div className="flex gap-2">
          {filterTraceId && (
            <button
              onClick={() => {
                setFilterTraceId(null)
                onTraceFilterChange?.(null)
              }}
              className="text-xs bg-panel-2 hover:bg-panel px-2 py-1 rounded text-text"
            >
              Clear Filter
            </button>
          )}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`text-xs px-2 py-1 rounded ${
              autoScroll 
                ? 'bg-ok/10 text-ok' 
                : 'bg-panel-2 hover:bg-panel text-text'
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
          <div className="text-muted-dark">
            {filterTraceId ? '(no logs matching filter)' : '(waiting for events...)'}
          </div>
        ) : (
          filteredLogs.map((log, idx) => {
            const reason =
              getDataString(log.data, 'reason') ||
              getDataString(log.data, 'rejection_reason')

            return (
            <div
              key={idx}
              className={`${getBgColor(log.event_type)} p-2 rounded hover:bg-opacity-70 transition-colors cursor-pointer border-l-4 border-border-subtle`}
              onClick={() => handleTraceClick(log.trace_id)}
            >
              <div className="flex items-start gap-2">
                {/* Timestamp */}
                <span className="text-muted-dark shrink-0 whitespace-nowrap">
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
                  <span className="text-danger font-semibold shrink-0 whitespace-nowrap">
                    reason={reason}
                  </span>
                )}

                {/* Trace ID (clickable) */}
                <span
                  className={`text-info hover:text-info/80 underline cursor-pointer whitespace-nowrap`}
                  title="Click to filter by trace_id"
                >
                  #{log.trace_id.substring(0, 8)}
                </span>

                {/* Data Preview */}
                <span className="text-text break-all">
                  {JSON.stringify(log.data).substring(0, 100)}
                  {JSON.stringify(log.data).length > 100 ? '...' : ''}
                </span>
              </div>
            </div>
          )})
        )}
      </div>

      {/* Footer */}
      <div className="bg-panel-2 border-t border-border-subtle p-2 text-xs text-muted-dark">
        {filterTraceId && (
          <span>
            🔍 Filtered by trace_id: <span className="text-muted font-mono">{filterTraceId.substring(0, 12)}...</span>
          </span>
        )}
      </div>
    </div>
  )
}
