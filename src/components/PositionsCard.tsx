'use client'

import { Position } from '@/lib/api'

interface PositionsCardProps {
  positions: Position[] | null
  loading: boolean
}

export function PositionsCard({ positions, loading }: PositionsCardProps) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Positions</h2>
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-4 bg-gray-700 rounded w-full"></div>
          ))}
        </div>
      </div>
    )
  }

  if (!positions || positions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Positions</h2>
        <p className="text-gray-400">No positions</p>
      </div>
    )
  }

  const latestPosition = positions[0]
  const pnlColor = latestPosition.pnl >= 0 ? 'text-green-400' : 'text-red-400'

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4">Positions</h2>

      <div className="space-y-1 text-sm font-mono">
        <div className="flex justify-between">
          <span className="text-gray-400">Symbol:</span>
          <span className="font-bold">{latestPosition.symbol}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Qty:</span>
          <span>{latestPosition.qty.toFixed(8)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Avg Entry:</span>
          <span>${latestPosition.avg_entry_price.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Mark Price:</span>
          <span>${latestPosition.mark_price.toFixed(2)}</span>
        </div>
        <div className={`flex justify-between pt-2 border-t border-gray-700 mt-2 ${pnlColor}`}>
          <span className="text-gray-400">PnL:</span>
          <span className="font-bold">
            {latestPosition.pnl >= 0 ? '+' : ''}{latestPosition.pnl.toFixed(2)} USDT
          </span>
        </div>
      </div>

      {positions.length > 1 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-400">
            +{positions.length - 1} more position{positions.length > 2 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
