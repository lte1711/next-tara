'use client'

import Link from 'next/link'
import { TraceSummary } from '@/lib/api'

const statusColor: Record<string, string> = {
  FILLED: 'bg-ok/10 text-ok border-ok/20',
  PARTIAL: 'bg-warn/10 text-warn border-warn/20',
  REJECTED: 'bg-danger/10 text-danger border-danger/20',
  CANCELED: 'bg-muted/10 text-muted border-muted/20',
  UNKNOWN: 'bg-muted/10 text-muted border-muted/20',
}

function formatTs(ms?: number) {
  if (!ms) return '-'
  return new Date(ms).toLocaleString()
}

export function TraceListTable({ items }: { items: TraceSummary[] }) {
  if (!items.length) {
    return (
      <div className="rounded-lg border border-border-subtle bg-panel p-6 text-muted">
        No traces found.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border-subtle">
      <table className="w-full text-sm">
        <thead className="bg-panel-2 text-left text-text">
          <tr>
            <th className="px-4 py-3">Trace ID</th>
            <th className="px-4 py-3">Symbol</th>
            <th className="px-4 py-3">Last Event</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Started</th>
            <th className="px-4 py-3">Last Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {items.map((item) => {
            const status = (item.status || 'UNKNOWN').toUpperCase()
            return (
              <tr key={item.trace_id} className="hover:bg-panel">
                <td className="px-4 py-3">
                  <Link
                    href={`/dashboard/orders/${item.trace_id}`}
                    className="text-info hover:text-info/80"
                  >
                    {item.trace_id}
                  </Link>
                </td>
                <td className="px-4 py-3 text-text">{item.symbol || '-'}</td>
                <td className="px-4 py-3 text-text">{item.last_event_type}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-1 text-xs ${
                      statusColor[status] || statusColor.UNKNOWN
                    }`}
                  >
                    {status}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted">{formatTs(item.first_ts)}</td>
                <td className="px-4 py-3 text-muted">{formatTs(item.last_ts)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
