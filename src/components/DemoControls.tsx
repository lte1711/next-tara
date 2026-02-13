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

  return (
    <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 60 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: 'var(--panel)', padding: 8, borderRadius: 8, border: '1px solid var(--border)', boxShadow: 'none' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{ ...buttonBase, fontWeight: demoMode === 'AUTO' ? 700 : 400 }}
            onClick={() => setDemoMode('AUTO')}
            aria-pressed={demoMode === 'AUTO'}
          >
            Auto
          </button>
          <button
            style={{ ...buttonBase, fontWeight: demoMode === 'MANUAL' ? 700 : 400 }}
            onClick={() => setDemoMode('MANUAL')}
            aria-pressed={demoMode === 'MANUAL'}
          >
            Manual
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{ ...buttonBase }}
            onClick={() => setPaused(p => !p)}
            disabled={demoMode !== 'AUTO'}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
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
            style={{ ...buttonBase, fontSize: 11 }}
            onClick={() => setIntervalMs(5000)}
            aria-pressed={intervalMs === 5000}
          >
            5s
          </button>
          <button
            style={{ ...buttonBase, fontSize: 11 }}
            onClick={() => setIntervalMs(8000)}
            aria-pressed={intervalMs === 8000}
          >
            8s
          </button>
        </div>
      </div>
    </div>
  )
}

export default DemoControls
