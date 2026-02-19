'use client'

import { RiskEvent } from '@/lib/api'

interface RecentRisksTableProps {
  events: RiskEvent[] | null
  loading: boolean
}

export function RecentRisksTable({ events, loading }: RecentRisksTableProps) {
  if (loading) {
    return (
      <div className="bg-panel rounded-lg p-6 border border-border-subtle">
        <h2 className="text-xl font-bold mb-4 text-text-strong">Recent Risks (Last 20)</h2>
        <div className="animate-pulse space-y-2">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-4 bg-panel-2 rounded w-full"></div>
          ))}
        </div>
      </div>
    )
  }

  if (!events || events.length === 0) {
    return (
      <div className="bg-panel rounded-lg p-6 border border-border-subtle">
        <h2 className="text-xl font-bold mb-4 text-text-strong">Recent Risks (Last 20)</h2>
        <p className="text-muted">No risk events</p>
      </div>
    )
  }

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'text-danger'
      case 'WARNING':
        return 'text-warn'
      case 'INFO':
        return 'text-info'
      default:
        return 'text-muted'
    }
  }

  const formatTime = (ts: number) => {
    return new Date(ts * 1000).toLocaleTimeString()
  }

  return (
    <div className="bg-panel rounded-lg p-6 border border-border-subtle col-span-2">
      <h2 className="text-xl font-bold mb-4 text-text-strong">Recent Risks (Last 20)</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="border-b border-border-subtle">
              <th className="text-left py-2 px-2 text-muted">Time</th>
              <th className="text-left py-2 px-2 text-muted">Level</th>
              <th className="text-left py-2 px-2 text-muted">Event Type</th>
              <th className="text-left py-2 px-2 text-muted">Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.slice(0, 20).map((event, idx) => (
              <tr key={idx} className="border-b border-border-subtle hover:bg-panel-2">
                <td className="py-2 px-2 text-muted">{formatTime(event.timestamp)}</td>
                <td className={`py-2 px-2 font-bold ${getLevelColor(event.level)}`}>
                  {event.level}
                </td>
                <td className="py-2 px-2">{event.event_type}</td>
                <td className="py-2 px-2">{event.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {events.length > 20 && (
        <p className="text-xs text-muted mt-2">
          Showing 20 of {events.length} events
        </p>
      )}
    </div>
  )
}
