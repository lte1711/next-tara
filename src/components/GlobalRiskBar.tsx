import React from 'react'

type Mode = 'NORMAL' | 'WARN' | 'KILL' | 'DOWNGRADE'

interface Props {
  mode?: Mode
  onChange?: (mode: Mode) => void
}

const modes: { key: Mode; label: string; colorVar: string }[] = [
  { key: 'NORMAL', label: 'Normal', colorVar: '--text' },
  { key: 'WARN', label: 'Warn', colorVar: '--warn' },
  { key: 'KILL', label: 'Kill', colorVar: '--kill' },
  { key: 'DOWNGRADE', label: 'Downgrade', colorVar: '--downgrade' },
]

export const GlobalRiskBar: React.FC<Props> = ({ mode = 'NORMAL', onChange }) => {
  return (
    <div style={{ padding: '8px', background: 'var(--panel2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <strong style={{ color: 'var(--text)' }}>Risk Mode:</strong>
        <div style={{ display: 'flex', gap: 8 }}>
          {modes.map(m => (
            <button
              key={m.key}
              onClick={() => onChange && onChange(m.key)}
              aria-pressed={mode === m.key}
              style={{
                padding: '6px 10px',
                borderRadius: 6,
                border: mode === m.key ? `2px solid var(${m.colorVar})` : '1px solid var(--border)',
                background: mode === m.key ? `rgba(255,255,255,0.02)` : 'transparent',
                color: 'var(--text)',
                cursor: 'pointer',
              }}
            >
              {m.label}
            </button>
          ))}
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
