'use client'

import Link from 'next/link'
import { TraceSummary } from '@/lib/api'

const statusColor: Record<string, string> = {
  FILLED: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
  PARTIAL: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  REJECTED: 'bg-rose-500/10 text-rose-300 border-rose-500/20',
  CANCELED: 'bg-slate-500/10 text-slate-300 border-slate-500/20',
  UNKNOWN: 'bg-slate-500/10 text-slate-300 border-slate-500/20',
}

function formatTs(ms?: number) {
  if (!ms) return '-'
  return new Date(ms).toLocaleString()
}

export function TraceListTable({ items }: { items: TraceSummary[] }) {
  if (!items.length) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-6 text-slate-400">
        No traces found.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/70 text-left text-slate-300">
          <tr>
            <th className="px-4 py-3">Trace ID</th>
            <th className="px-4 py-3">Symbol</th>
            <th className="px-4 py-3">Last Event</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Started</th>
            <th className="px-4 py-3">Last Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/70">
          {items.map((item) => {
            const status = (item.status || 'UNKNOWN').toUpperCase()
            return (
              <tr key={item.trace_id} className="hover:bg-slate-900/40">
                <td className="px-4 py-3">
                  <Link
                    href={`/dashboard/orders/${item.trace_id}`}
                    className="text-cyan-300 hover:text-cyan-200"
                  >
                    {item.trace_id}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-200">{item.symbol || '-'}</td>
                <td className="px-4 py-3 text-slate-200">{item.last_event_type}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-1 text-xs ${
                      statusColor[status] || statusColor.UNKNOWN
                    }`}
                  >
                    {status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">{formatTs(item.first_ts)}</td>
                <td className="px-4 py-3 text-slate-400">{formatTs(item.last_ts)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
