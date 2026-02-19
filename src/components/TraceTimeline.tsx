'use client'

import { TraceTimelineEvent } from '@/lib/api'

const typeColor: Record<string, string> = {
  ROUTE_DECIDED: 'border-info/40 text-info',
  ORDER_CREATED: 'border-info/40 text-info',
  ORDER_ACK: 'border-ok/40 text-ok',
  ORDER_EXEC_REPORT: 'border-ok/40 text-ok',
  ORDER_REJECTED: 'border-danger/40 text-danger',
  ORDER_EXECUTION_SKIPPED: 'border-warn/40 text-warn',
}

function formatTs(ms: number) {
  return `${ms} ms`
}

export function TraceTimeline({ events }: { events: TraceTimelineEvent[] }) {
  if (!events.length) {
    return (
      <div className="rounded-lg border border-border-subtle bg-panel p-6 text-muted">
        No events recorded.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {events.map((event, index) => {
        const color = typeColor[event.event_type] || 'border-muted text-muted'
        return (
          <div key={`${event.event_type}-${event.ts}-${index}`} className="rounded-lg border border-border-subtle bg-panel p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`rounded-full border px-2 py-1 text-xs ${color}`}>
                {event.event_type}
              </span>
              <span className="text-xs text-muted">{formatTs(event.ts)}</span>
              {event.missing && (
                <span className="rounded-full border border-danger/40 px-2 py-1 text-xs text-danger">
                  missing
                </span>
              )}
            </div>
            <pre className="mt-3 max-h-60 overflow-auto rounded-md bg-panel-2 p-3 text-xs text-text">
              {JSON.stringify(event.detail, null, 2)}
            </pre>
          </div>
        )
      })}
    </div>
  )
}
