"use client"

import React, { useMemo, useState } from 'react'
import { RiskMode, TradeLevel } from '../types/risk'

export interface OrderPanelProps {
  mode: RiskMode
  level: TradeLevel
  reason?: string
  initialSymbol?: string
  initialQty?: string
  initialPrice?: string
}

export const OrderPanel: React.FC<OrderPanelProps> = ({ mode, level, reason, initialSymbol = 'BTCUSDT', initialQty = '1', initialPrice = '50000' }) => {
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
  // Local input state (client-rendered) with sensible defaults. For SSR evidence capture
  // the `initial*` props may be provided by the page temporarily.
  const [symbol, setSymbol] = useState<string>(initialSymbol)
  const [qty, setQty] = useState<string>(initialQty)
  const [price, setPrice] = useState<string>(initialPrice)

  // Validation rules
  const errors = useMemo(() => {
    const e: { symbol?: string; qty?: string; price?: string; form?: string } = {}
    const s = (symbol ?? '').trim()
    if (!s) e.symbol = 'Symbol is required'
    else if (s.length < 1 || s.length > 20) e.symbol = 'Symbol length 1–20'

    const q = parseFloat((qty ?? '').toString())
    if (qty === undefined || qty === null || (qty ?? '') === '') e.qty = 'Qty is required'
    else if (!Number.isFinite(q) || q <= 0) e.qty = 'Qty must be a number > 0'

    // Price validation only applies when price is enabled (not DOWNGRADE)
    if (!isDowngrade) {
      const p = parseFloat((price ?? '').toString())
      if (price === undefined || price === null || (price ?? '') === '') e.price = 'Price is required'
      else if (!Number.isFinite(p) || p <= 0) e.price = 'Price must be a number > 0'
    }

    return e
  }, [symbol, qty, price, isDowngrade])

  const hasErrors = Object.keys(errors).length > 0
  const canSubmit = !isKill && !hasErrors

  // Input styles with error state preserved space for inline error lines
  const inputBase: React.CSSProperties = { padding: 8, borderRadius: 6, border: '1px solid var(--border)', background: isKill ? '#111' : 'transparent', color: 'var(--text)', fontFamily: 'ui-monospace, monospace' }
  const errorBorder = { border: '1px solid rgba(185,28,28,0.7)', background: 'rgba(185,28,28,0.03)' }

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
        <div>
          <input
            placeholder="Symbol (e.g. BTCUSDT)"
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            style={{ ...inputBase, ...(errors.symbol ? errorBorder : {}) }}
            disabled={isKill}
          />
          <div style={{ minHeight: 18, fontSize: 12, color: 'rgba(185,28,28,0.9)', marginTop: 4 }}>{errors.symbol ?? ' '}</div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1 }}>
            <input
              placeholder="Qty"
              value={qty}
              onChange={e => setQty(e.target.value)}
              style={{ ...inputBase, ...(errors.qty ? errorBorder : {}) }}
              disabled={isKill}
            />
            <div style={{ minHeight: 18, fontSize: 12, color: 'rgba(185,28,28,0.9)', marginTop: 4 }}>{errors.qty ?? ' '}</div>
          </div>

          <div style={{ width: 120 }}>
            <input
              placeholder="Price"
              value={price}
              onChange={e => setPrice(e.target.value)}
              style={{ ...inputBase, ...(errors.price ? errorBorder : {}) }}
              disabled={isKill || isDowngrade}
            />
            <div style={{ minHeight: 18, fontSize: 12, color: 'rgba(185,28,28,0.9)', marginTop: 4 }}>{errors.price ?? ' '}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
          <button style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text)' }} disabled={!canSubmit}>Preview</button>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button style={{ ...sendBtnStyle, opacity: canSubmit ? 1 : 0.5 }} disabled={!canSubmit}>Send Order</button>
            {isDowngrade && <div style={{ fontSize: 11, color: 'var(--muted)', border: '1px solid rgba(255,255,255,0.04)', padding: '2px 6px', borderRadius: 4 }}>Limited</div>}
          </div>
        </div>

        {/* reason shown at top-right; keep bottom area free */}
      </div>
    </div>
  )
}

export default OrderPanel
