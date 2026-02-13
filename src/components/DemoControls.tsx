"use client"

import React from 'react'
import { useRisk } from '../context/RiskContext'

const buttonBase: React.CSSProperties = {
  padding: '6px 8px',
  borderRadius: 6,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'var(--text)',
  fontSize: 12,
}

export const DemoControls: React.FC = () => {
  const { demoMode, setDemoMode, paused, setPaused, manualMode, setManualMode, intervalMs, setIntervalMs } = useRisk()

  // optional stability features
  const { pauseOnKill, setPauseOnKill, reset } = useRisk()

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: 'var(--panel)', padding: 8, borderRadius: 8, border: '1px solid var(--border)', boxShadow: 'none', flexWrap: 'nowrap', whiteSpace: 'nowrap', overflowX: 'auto', minHeight: 40 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{ ...buttonBase, fontWeight: demoMode === 'AUTO' ? 700 : 400, flexShrink: 0, whiteSpace: 'nowrap' }}
            onClick={() => setDemoMode('AUTO')}
            aria-pressed={demoMode === 'AUTO'}
          >
            Auto
          </button>
          <button
            style={{ ...buttonBase, fontWeight: demoMode === 'MANUAL' ? 700 : 400, flexShrink: 0, whiteSpace: 'nowrap' }}
            onClick={() => setDemoMode('MANUAL')}
            aria-pressed={demoMode === 'MANUAL'}
          >
            Manual
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            style={{ ...buttonBase }}
            onClick={() => setPaused(p => !p)}
            disabled={demoMode !== 'AUTO'}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)' }}>
            <input type="checkbox" checked={pauseOnKill} onChange={(e) => setPauseOnKill(e.target.checked)} />
            <span>Pause on KILL</span>
          </label>
          <button style={{ ...buttonBase, flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => reset()}>Reset</button>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{ ...buttonBase, ...(manualMode === 'NORMAL' ? { fontWeight: 700 } : {}) }}
            onClick={() => setManualMode('NORMAL')}
            disabled={demoMode !== 'MANUAL'}
          >
            NORMAL
          </button>
          <button
            style={{ ...buttonBase, ...(manualMode === 'WARN' ? { fontWeight: 700 } : {}) }}
            onClick={() => setManualMode('WARN')}
            disabled={demoMode !== 'MANUAL'}
          >
            WARN
          </button>
          <button
            style={{ ...buttonBase, ...(manualMode === 'DOWNGRADE' ? { fontWeight: 700 } : {}) }}
            onClick={() => setManualMode('DOWNGRADE')}
            disabled={demoMode !== 'MANUAL'}
          >
            DOWNGRADE
          </button>
          <button
            style={{ ...buttonBase, ...(manualMode === 'KILL' ? { fontWeight: 700 } : {}) }}
            onClick={() => setManualMode('KILL')}
            disabled={demoMode !== 'MANUAL'}
          >
            KILL
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{ ...buttonBase, fontSize: 11, flexShrink: 0, whiteSpace: 'nowrap' }}
            onClick={() => setIntervalMs(5000)}
            aria-pressed={intervalMs === 5000}
          >
            5s
          </button>
          <button
            style={{ ...buttonBase, fontSize: 11, flexShrink: 0, whiteSpace: 'nowrap' }}
            onClick={() => setIntervalMs(8000)}
            aria-pressed={intervalMs === 8000}
          >
            8s
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', marginLeft: 8 }}>
          <div style={{ padding: '4px 8px', borderRadius: 999, border: '1px solid var(--border)', fontSize: 12, color: 'var(--muted)' }}>
            {demoMode} {paused ? '· PAUSED' : ''}
          </div>
        </div>
      </div>
    </div>
  )
}

export default DemoControls
