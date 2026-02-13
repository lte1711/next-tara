import React from 'react'

type RiskMode = 'NORMAL' | 'WARN' | 'KILL' | 'DOWNGRADE'

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
    padding: '6px 10px',
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
        height: 64,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '0 16px',
        background: 'var(--panel)',
        borderBottom: '1px solid var(--border)',
        fontFamily: "Inter, 'Segoe UI', Roboto, 'Helvetica Neue', Arial",
        ...topBorderStyle,
      }}
      role="region"
      aria-label="Global Risk Bar"
    >
      {/* System Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 200 }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>SYSTEM STATUS</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{mode}</div>
        </div>
      </div>

      {/* Metrics */}
      <div style={{ display: 'flex', gap: 24, alignItems: 'center', flex: 1 }}>
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

      {/* Right side: indicators and mode */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'right' }}>
          <div style={{ fontSize: 12 }}>Last update</div>
          <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>{lastUpdate}</div>
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

        <div>
          <div style={modeBadgeStyle} aria-hidden>
            {mode}
          </div>
        </div>
      </div>
    </div>
  )
}

export default GlobalRiskBar
"use client";

import React from 'react';

export type RiskMode = 'NORMAL' | 'WARN' | 'KILL' | 'DOWNGRADE';

interface GlobalRiskBarProps {
  mode: RiskMode;
  message?: string;
}

export default function GlobalRiskBar({ mode, message }: GlobalRiskBarProps) {
  const getBorderColor = () => {
    switch (mode) {
      case 'WARN':
        return 'var(--warn)';
      case 'KILL':
        return 'var(--kill)';
      case 'DOWNGRADE':
        return 'var(--downgrade)';
      default:
        return 'var(--border)';
    }
  };

  const getBackgroundColor = () => {
    switch (mode) {
      case 'WARN':
        return 'rgba(245, 158, 11, 0.1)';
      case 'KILL':
        return 'rgba(185, 28, 28, 0.1)';
      case 'DOWNGRADE':
        return 'rgba(124, 58, 237, 0.1)';
      default:
        return 'transparent';
    }
  };

  const getLabel = () => {
    switch (mode) {
      case 'WARN':
        return 'WARNING';
      case 'KILL':
        return 'KILL SWITCH ACTIVE';
      case 'DOWNGRADE':
        return 'SYSTEM DOWNGRADE';
      default:
        return 'OPERATIONAL';
    }
  };

  return (
    <div
      style={{
        borderTop: `2px solid ${getBorderColor()}`,
        borderBottom: `2px solid ${getBorderColor()}`,
        backgroundColor: getBackgroundColor(),
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '13px',
        fontWeight: 600,
        letterSpacing: '0.5px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span
          style={{
            color: getBorderColor(),
            textTransform: 'uppercase',
          }}
        >
          {getLabel()}
        </span>
        {message && (
          <span style={{ color: 'var(--muted)', fontWeight: 400 }}>
            {message}
          </span>
        )}
      </div>
      <div style={{ color: 'var(--muted)', fontSize: '11px' }}>
        {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}
