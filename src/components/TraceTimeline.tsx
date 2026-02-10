'use client'

import { TraceTimelineEvent } from '@/lib/api'

const typeColor: Record<string, string> = {
  ROUTE_DECIDED: 'border-cyan-500/40 text-cyan-300',
  ORDER_CREATED: 'border-indigo-500/40 text-indigo-300',
  ORDER_ACK: 'border-emerald-500/40 text-emerald-300',
  ORDER_EXEC_REPORT: 'border-emerald-500/40 text-emerald-200',
  ORDER_REJECTED: 'border-rose-500/40 text-rose-300',
  ORDER_EXECUTION_SKIPPED: 'border-amber-500/40 text-amber-300',
}

function formatTs(ms: number) {
  return `${ms} ms`
}

export function TraceTimeline({ events }: { events: TraceTimelineEvent[] }) {
  if (!events.length) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-6 text-slate-400">
        No events recorded.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {events.map((event, index) => {
        const color = typeColor[event.event_type] || 'border-slate-600 text-slate-200'
        return (
          <div key={`${event.event_type}-${event.ts}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`rounded-full border px-2 py-1 text-xs ${color}`}>
                {event.event_type}
              </span>
              <span className="text-xs text-slate-400">{formatTs(event.ts)}</span>
              {event.missing && (
                <span className="rounded-full border border-rose-500/40 px-2 py-1 text-xs text-rose-300">
                  missing
                </span>
              )}
            </div>
            <pre className="mt-3 max-h-60 overflow-auto rounded-md bg-slate-900/70 p-3 text-xs text-slate-200">
              {JSON.stringify(event.detail, null, 2)}
            </pre>
          </div>
        )
      })}
    </div>
  )
}
