'use client'

import { RiskEvent } from '@/lib/api'

interface RecentRisksTableProps {
  events: RiskEvent[] | null
  loading: boolean
}

export function RecentRisksTable({ events, loading }: RecentRisksTableProps) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Recent Risks (Last 20)</h2>
        <div className="animate-pulse space-y-2">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-4 bg-gray-700 rounded w-full"></div>
          ))}
        </div>
      </div>
    )
  }

  if (!events || events.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Recent Risks (Last 20)</h2>
        <p className="text-gray-400">No risk events</p>
      </div>
    )
  }

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'text-red-400'
      case 'WARNING':
        return 'text-yellow-400'
      case 'INFO':
        return 'text-blue-400'
      default:
        return 'text-gray-400'
    }
  }

  const formatTime = (ts: number) => {
    return new Date(ts * 1000).toLocaleTimeString()
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 col-span-2">
      <h2 className="text-xl font-bold mb-4">Recent Risks (Last 20)</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-2 px-2 text-gray-400">Time</th>
              <th className="text-left py-2 px-2 text-gray-400">Level</th>
              <th className="text-left py-2 px-2 text-gray-400">Event Type</th>
              <th className="text-left py-2 px-2 text-gray-400">Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.slice(0, 20).map((event, idx) => (
              <tr key={idx} className="border-b border-gray-700 hover:bg-gray-700/50">
                <td className="py-2 px-2 text-gray-400">{formatTime(event.timestamp)}</td>
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
        <p className="text-xs text-gray-400 mt-2">
          Showing 20 of {events.length} events
        </p>
      )}
    </div>
  )
}
