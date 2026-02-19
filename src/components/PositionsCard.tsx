'use client'

import { Position } from '@/lib/api'

interface PositionsCardProps {
  positions: Position[] | null
  loading: boolean
}

export function PositionsCard({ positions, loading }: PositionsCardProps) {
  if (loading) {
    return (
      <div className="bg-panel rounded-lg p-6 border border-border-subtle">
        <h2 className="text-xl font-bold mb-4 text-text-strong">Positions</h2>
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-4 bg-panel-2 rounded w-full"></div>
          ))}
        </div>
      </div>
    )
  }

  if (!positions || positions.length === 0) {
    return (
      <div className="bg-panel rounded-lg p-6 border border-border-subtle">
        <h2 className="text-xl font-bold mb-4 text-text-strong">Positions</h2>
        <p className="text-muted">No positions</p>
      </div>
    )
  }

  const latestPosition = positions[0]
  const pnlColor = latestPosition.pnl >= 0 ? 'text-ok' : 'text-danger'

  return (
    <div className="bg-panel rounded-lg p-6 border border-border-subtle">
      <h2 className="text-xl font-bold mb-4 text-text-strong">Positions</h2>

      <div className="space-y-1 text-sm font-mono">
        <div className="flex justify-between">
          <span className="text-muted">Symbol:</span>
          <span className="font-bold">{latestPosition.symbol}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Qty:</span>
          <span>{latestPosition.qty.toFixed(8)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Avg Entry:</span>
          <span>${latestPosition.avg_entry_price.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Mark Price:</span>
          <span>${latestPosition.mark_price.toFixed(2)}</span>
        </div>
        <div className={`flex justify-between pt-2 border-t border-border-subtle mt-2 ${pnlColor}`}>
          <span className="text-muted">PnL:</span>
          <span className="font-bold">
            {latestPosition.pnl >= 0 ? '+' : ''}{latestPosition.pnl.toFixed(2)} USDT
          </span>
        </div>
      </div>

      {positions.length > 1 && (
        <div className="mt-4 pt-4 border-t border-border-subtle">
          <p className="text-xs text-muted">
            +{positions.length - 1} more position{positions.length > 2 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
