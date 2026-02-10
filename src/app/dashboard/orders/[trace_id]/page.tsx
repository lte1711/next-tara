'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { apiClient, TraceTimelineResponse } from '@/lib/api'
import { TraceTimeline } from '@/components/TraceTimeline'

export default function TraceDetailPage({ params }: { params: { trace_id: string } }) {
  const traceId = params.trace_id
  const [data, setData] = useState<TraceTimelineResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    apiClient.getTraceTimeline(traceId).then((res) => {
      if (!mounted) return
      setData(res)
      setLoading(false)
    })
    return () => {
      mounted = false
    }
  }, [traceId])

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-400">Trace Timeline</p>
          <h1 className="text-2xl font-semibold text-slate-100">{traceId}</h1>
        </div>
        <Link href="/dashboard/orders" className="text-sm text-cyan-300 hover:text-cyan-200">
          Back to list
        </Link>
      </div>

      {loading && (
        <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-6 text-slate-400">
          Loading timeline...
        </div>
      )}

      {!loading && !data && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-6 text-rose-200">
          Trace not found.
        </div>
      )}

      {!loading && data && (
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <div className="flex flex-wrap gap-6 text-sm text-slate-300">
              <div>
                <span className="text-slate-400">Status</span>
                <div className="font-semibold text-slate-100">{data.status}</div>
              </div>
              <div>
                <span className="text-slate-400">Started at</span>
                <div className="font-semibold text-slate-100">{data.started_at}</div>
              </div>
              <div>
                <span className="text-slate-400">Events</span>
                <div className="font-semibold text-slate-100">{data.events.length}</div>
              </div>
            </div>
          </div>

          <TraceTimeline events={data.events} />
        </div>
      )}
    </div>
  )
}
