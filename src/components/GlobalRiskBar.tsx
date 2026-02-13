import React from 'react'
import DemoControls from './DemoControls'
import { RiskMode } from '../types/risk'

export interface GlobalRiskBarProps {
  mode?: RiskMode
  pnl?: number
  drawdown?: number
  exposure?: number
  lastUpdate?: string // ISO timestamp or human string
  riskEngineActive?: boolean
  killArmed?: boolean
}

const formatCurrency = (v: number) => {
  if (Number.isNaN(v) || v === undefined || v === null) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2)
}

const formatPct = (v: number) => {
  if (Number.isNaN(v) || v === undefined || v === null) return '--'
  return (v * 100).toFixed(2) + '%'
}

export const GlobalRiskBar: React.FC<GlobalRiskBarProps> = ({
  mode = 'NORMAL',
  pnl = 0,
  drawdown = 0,
  exposure = 0,
  lastUpdate = new Date().toLocaleTimeString('ko-KR'),
  riskEngineActive = true,
  killArmed = false,
}) => {
  const topBorderStyle: React.CSSProperties = {}
  if (mode === 'WARN') topBorderStyle.borderTop = `2px solid var(--warn)`
  if (mode === 'KILL') topBorderStyle.borderTop = `4px solid var(--kill)`

  const modeBadgeStyle: React.CSSProperties = {
    padding: '4px 8px',
    borderRadius: 6,
    fontWeight: 700,
    color: 'var(--text)',
    background: 'transparent',
    border: '1px solid var(--border)',
  }

  if (mode === 'WARN') modeBadgeStyle.border = `1px solid var(--warn)`
  if (mode === 'KILL') modeBadgeStyle.border = `2px solid var(--kill)`
  if (mode === 'DOWNGRADE') modeBadgeStyle.border = `1px solid var(--downgrade)`

  return (
    <div
      style={{
        height: 52,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '0 12px',
        background: 'var(--panel)',
        borderBottom: '1px solid var(--border)',
        fontFamily: "Inter, 'Segoe UI', Roboto, 'Helvetica Neue', Arial",
        position: 'relative',
        zIndex: 90,
        ...topBorderStyle,
      }}
      role="region"
      aria-label="Global Risk Bar"
    >
      {/* Left block: status + metrics (badge moved next to STATUS) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 24, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 200 }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase' }}>SYSTEM STATUS</div>
              <div style={modeBadgeStyle} aria-hidden>
                {mode}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>GLOBAL PnL</div>
            <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Courier New", monospace', fontSize: 18, color: pnl >= 0 ? 'var(--profit)' : 'var(--loss)' }}>{formatCurrency(pnl)}</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>MAX DRAWDOWN</div>
            <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 18, color: 'var(--muted)' }}>{formatPct(drawdown)}</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>EXPOSURE</div>
            <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 18, color: 'var(--muted)' }}>{formatPct(exposure)}</div>
          </div>
        </div>

      </div>

      {/* Right: indicators + compact controls (thin divider + left padding) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 360, borderLeft: '1px solid rgba(255,255,255,0.08)', paddingLeft: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: 'var(--muted)', textAlign: 'right' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 12 }}>Last update</div>
            <div suppressHydrationWarning style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>{lastUpdate}</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Risk Engine</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ width: 10, height: 10, borderRadius: 20, background: riskEngineActive ? 'var(--profit)' : 'var(--muted)' }} aria-hidden />
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>{riskEngineActive ? 'Active' : 'Idle'}</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Kill Switch</div>
            <div style={{ fontSize: 12 }}>
              <span style={{ marginRight: 8, color: killArmed ? 'var(--kill)' : 'var(--muted)' }}>{killArmed ? 'ARMED' : 'DISARMED'}</span>
            </div>
          </div>
        </div>

        <div style={{ marginLeft: 8 }}>
          <DemoControls compact />
        </div>
      </div>
    </div>
  )
}

export default GlobalRiskBar

