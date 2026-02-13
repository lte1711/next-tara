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
  // Utils: step/tick checks + display formatter
  const isMultipleOfStep = (value: number, step: number) => {
    if (!isFinite(value) || !isFinite(step) || step === 0) return false
    const ratio = value / step
    const rounded = Math.round(ratio)
    return Math.abs(ratio - rounded) < 1e-9
  }

  const formatNumber = (value: number, decimals: number) => {
    if (!Number.isFinite(value)) return ''
    return value.toFixed(decimals)
  }

  const errors = useMemo(() => {
    const e: { symbol?: string; qty?: string; price?: string; form?: string } = {}

    // Symbol normalization for validation
    const sNorm = (symbol ?? '').trim().toUpperCase()
    const symbolRegex = /^[A-Z0-9_-]+$/
    if (!sNorm || sNorm.length < 2 || sNorm.length > 20 || !symbolRegex.test(sNorm)) {
      e.symbol = 'Symbol must be 2–20 chars (A–Z, 0–9, _ or -).'
    }

    // Qty rules
    const minQty = 0.001
    const qtyStep = 0.001
    const qParsed = parseFloat((qty ?? '').toString())
    if (qty === undefined || qty === null || (qty ?? '') === '') {
      e.qty = 'Qty must be ≥ 0.001 and in steps of 0.001.'
    } else if (!Number.isFinite(qParsed) || qParsed < minQty || !isMultipleOfStep(qParsed, qtyStep)) {
      e.qty = 'Qty must be ≥ 0.001 and in steps of 0.001.'
    }

    // Price rules (skip validation when DOWNGRADE)
    if (!isDowngrade) {
      const minPrice = 0.01
      const tickSize = 0.01
      const pParsed = parseFloat((price ?? '').toString())
      if (price === undefined || price === null || (price ?? '') === '') {
        e.price = 'Price must be ≥ 0.01 and in ticks of 0.01.'
      } else if (!Number.isFinite(pParsed) || pParsed < minPrice || !isMultipleOfStep(pParsed, tickSize)) {
        e.price = 'Price must be ≥ 0.01 and in ticks of 0.01.'
      }
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
