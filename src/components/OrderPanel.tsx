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

  const levelStyleMap: Record<string, React.CSSProperties> = {
    L0_VIEW: { opacity: 0.6 },
    L1_LIMITED: { opacity: 0.8 },
    L2_FULL: { fontWeight: 700, border: '1px solid rgba(255,255,255,0.04)', padding: '2px 6px', borderRadius: 4 },
  }

  const reasonText = isKill
    ? 'KILL-SWITCH: Orders disabled'
    : isDowngrade
    ? 'Downgrade: Advanced features limited'
    : mode === 'WARN'
    ? 'Warning: trading under constraints'
    : undefined

  const sendBtnDisabled = isKill
  const sendBtnBase: React.CSSProperties = { padding: '8px 12px', borderRadius: 6, background: 'var(--panel)', fontWeight: 700 }
  let sendBtnStyle: React.CSSProperties = { ...sendBtnBase, border: '1px solid var(--border)', color: 'var(--text)' }

  if (mode === 'WARN') {
    sendBtnStyle = { ...sendBtnBase, border: '2px solid var(--warn)', color: 'var(--warn)' }
  }

  if (isDowngrade) {
    sendBtnStyle = { ...sendBtnBase, border: '1px solid var(--downgrade)', color: 'var(--muted)' }
  }

  if (isKill) {
    sendBtnStyle = { ...sendBtnBase, border: '2px solid var(--kill)', color: 'var(--kill)', background: 'rgba(185,28,28,0.04)' }
  }

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
          {reasonText && <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>{reasonText}</div>}

          <div style={levelStyleMap[level] || { opacity: 0.85, fontWeight: 600 }}>Trade Level: {level}</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <input placeholder="Symbol (e.g. BTCUSDT)" style={{ padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }} disabled={isKill} />
        <div style={{ display: 'flex', gap: 8 }}>
          <input placeholder="Qty" style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }} disabled={isKill} />
          <input placeholder="Price" style={{ width: 120, padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }} disabled={isKill || isDowngrade} />
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
          <button style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text)' }} disabled={isKill}>Preview</button>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button style={sendBtnStyle} disabled={sendBtnDisabled}>Send Order</button>
            {isDowngrade && <div style={{ fontSize: 11, color: 'var(--muted)', border: '1px solid rgba(255,255,255,0.04)', padding: '2px 6px', borderRadius: 4 }}>Limited</div>}
          </div>
        </div>

        {/* reason shown at top-right; keep bottom area free */}
      </div>
    </div>
  )
}

export default OrderPanel
