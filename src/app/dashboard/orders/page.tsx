'use client'

import { useCallback, useEffect, useState } from 'react'
import { apiClient, DashboardSummary, TraceSummary } from '@/lib/api'
import { TraceListTable } from '@/components/TraceListTable'
import { SummaryCards } from '@/components/SummaryCards'

export default function OrdersDashboardPage() {
  const [items, setItems] = useState<TraceSummary[]>([])
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [limit, setLimit] = useState(50)
  const [eventType, setEventType] = useState('')
  const [sinceMinutes, setSinceMinutes] = useState(60)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    const since_ms = sinceMinutes > 0 ? Date.now() - sinceMinutes * 60_000 : undefined

    const [list, summaryData] = await Promise.all([
      apiClient.getTraceList({
        limit,
        event_type: eventType || undefined,
        since_ms,
      }),
      apiClient.getDashboardSummary(300),
    ])

    setItems(list)
    setSummary(summaryData)
    setLoading(false)
  }, [limit, eventType, sinceMinutes])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">Trace Dashboard</h1>
        <p className="mt-2 text-sm text-slate-400">
          Trace ID 기준으로 주문 타임라인을 확인하고, 운영 지표를 요약합니다.
        </p>
      </div>

      <SummaryCards summary={summary} />

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Limit</label>
          <input
            type="number"
            value={limit}
            onChange={(e) => setLimit(Math.min(200, Math.max(1, Number(e.target.value))))}
            className="w-24 rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Event Type</label>
          <input
            type="text"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            placeholder="ORDER_ACK"
            className="w-48 rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Since (minutes)</label>
          <input
            type="number"
            value={sinceMinutes}
            onChange={(e) => setSinceMinutes(Math.max(0, Number(e.target.value)))}
            className="w-32 rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100"
          />
        </div>
        <button
          onClick={loadData}
          className="rounded-md bg-cyan-500/20 px-4 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-500/30"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <TraceListTable items={items} />
    </div>
  )
}
