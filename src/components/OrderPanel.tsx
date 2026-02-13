import React from 'react'
import { RiskMode, TradeLevel } from '../types/risk'

export interface OrderPanelProps {
  mode: RiskMode
  level: TradeLevel
  reason?: string
}

export const OrderPanel: React.FC<OrderPanelProps> = ({ mode, level, reason }) => {
  const isKill = mode === 'KILL'
  const isDowngrade = mode === 'DOWNGRADE'

  const topStyle: React.CSSProperties = {}
  if (mode === 'WARN') topStyle.borderTop = '2px solid var(--warn)'
  if (mode === 'KILL') topStyle.borderTop = '4px solid var(--kill)'

  return (
    <div style={{ background: 'var(--panel2)', padding: 12, borderRadius: 'var(--radius)', border: '1px solid var(--border)', minWidth: 280, ...topStyle }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Order Entry</div>
          <div style={{ fontSize: 14, color: 'var(--text)', fontWeight: 700 }}>Limit / Market</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {isKill ? (
            <div style={{ color: 'var(--kill)', fontWeight: 700 }}>KILL-SWITCH: Orders disabled</div>
          ) : isDowngrade ? (
            <div style={{ color: 'var(--downgrade)', fontWeight: 700 }}>Downgrade: Advanced features limited</div>
          ) : (
            <div style={{ color: 'var(--muted)' }}>Trade Level: {level}</div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <input placeholder="Symbol (e.g. BTCUSDT)" style={{ padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }} disabled={isKill} />
        <div style={{ display: 'flex', gap: 8 }}>
          <input placeholder="Qty" style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }} disabled={isKill} />
          <input placeholder="Price" style={{ width: 120, padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }} disabled={isKill || isDowngrade} />
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text)' }} disabled={isKill}>Preview</button>
          <button style={{ padding: '8px 12px', borderRadius: 6, border: isKill ? '2px solid var(--kill)' : '1px solid var(--border)', background: isKill ? 'rgba(185,28,28,0.06)' : 'var(--panel)', color: isKill ? 'var(--kill)' : 'var(--text)', fontWeight: 700 }} disabled={isKill}>Send Order</button>
        </div>

        { (isKill || isDowngrade) && (
          <div style={{ marginTop: 8, color: 'var(--muted)', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={reason || ''}>
            {reason || (isKill ? 'Orders temporarily disabled by kill switch' : 'Certain order features are limited in downgrade mode')}
          </div>
        )}
      </div>
    </div>
  )
}

export default OrderPanel
