'use client'

import { DashboardSummary } from '@/lib/api'

function formatLatency(value: number | null) {
  if (value === null || Number.isNaN(value)) return '-'
  return `${value.toFixed(1)} ms`
}

export function SummaryCards({ summary }: { summary: DashboardSummary | null }) {
  const cards = [
    {
      label: 'Total traces (window)',
      value: summary ? summary.total_traces : '-',
    },
    {
      label: 'Exec reports',
      value: summary ? summary.exec_report_count : '-',
    },
    {
      label: 'Hard rejects',
      value: summary ? summary.reject_hard_count : '-',
    },
    {
      label: 'Soft rejects',
      value: summary ? summary.reject_soft_count : '-',
    },
    {
      label: 'Avg latency',
      value: summary ? formatLatency(summary.avg_latency_ms) : '-',
    },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-5">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
          <p className="text-xs text-slate-400">{card.label}</p>
          <p className="mt-2 text-lg font-semibold text-slate-100">{card.value}</p>
        </div>
      ))}
    </div>
  )
}
