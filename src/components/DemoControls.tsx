"use client"

import React from 'react'
import { useRisk } from '../context/RiskContext'

const buttonBase: React.CSSProperties = {
  padding: '0 10px',
  borderRadius: 6,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'var(--text)',
  fontSize: 11,
  height: 32,
  minWidth: 0,
}

const DemoControls: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { demoMode, setDemoMode, paused, setPaused, manualMode, setManualMode, intervalMs, setIntervalMs } = useRisk()
  const { pauseOnKill, setPauseOnKill, reset } = useRisk()

  if (compact) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button style={{ ...buttonBase, fontWeight: demoMode === 'AUTO' ? 700 : 400, flexShrink: 0 }} onClick={() => setDemoMode('AUTO')}>Auto</button>
        <button style={{ ...buttonBase, fontWeight: demoMode === 'MANUAL' ? 700 : 400, flexShrink: 0 }} onClick={() => setDemoMode('MANUAL')}>Manual</button>
        <button style={{ ...buttonBase, flexShrink: 0 }} onClick={() => setPaused(p => !p)} disabled={demoMode !== 'AUTO'}>{paused ? 'Resume' : 'Pause'}</button>
        <button style={{ ...buttonBase, flexShrink: 0 }} onClick={() => reset()}>Reset</button>

        <div style={{ width: 8 }} />

        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <button style={{ ...buttonBase, ...(manualMode === 'NORMAL' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('NORMAL')} disabled={demoMode !== 'MANUAL'}>NORMAL</button>
          <button style={{ ...buttonBase, ...(manualMode === 'WARN' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('WARN')} disabled={demoMode !== 'MANUAL'}>WARN</button>
          <button style={{ ...buttonBase, ...(manualMode === 'DOWNGRADE' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('DOWNGRADE')} disabled={demoMode !== 'MANUAL'}>DOWNGRADE</button>
          <button style={{ ...buttonBase, ...(manualMode === 'KILL' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('KILL')} disabled={demoMode !== 'MANUAL'}>KILL</button>
        </div>

        <select value={intervalMs} onChange={(e) => setIntervalMs(Number(e.target.value))} style={{ background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 6, padding: '0 8px', fontSize: 11, height: 32 }}>
          <option value={5000}>5s</option>
          <option value={8000}>8s</option>
        </select>

        <div style={{ padding: '4px 10px', borderRadius: 999, border: '1px solid var(--border)', fontSize: 12, color: 'var(--muted)', background: 'transparent', flexShrink: 0, height: 32, display: 'flex', alignItems: 'center' }}>{demoMode}{paused ? ' · PAUSED' : ''}</div>
      </div>
    )
  }

  return (
    <div className="max-w-full scrollbar-hide" style={{ overflow: 'visible' }}>
      <div style={{ background: 'var(--panel2)', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', boxShadow: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflowX: 'auto', whiteSpace: 'nowrap' }}>
          <button style={{ ...buttonBase, fontWeight: demoMode === 'AUTO' ? 700 : 400, flexShrink: 0 }} onClick={() => setDemoMode('AUTO')}>Auto</button>
          <button style={{ ...buttonBase, fontWeight: demoMode === 'MANUAL' ? 700 : 400, flexShrink: 0 }} onClick={() => setDemoMode('MANUAL')}>Manual</button>
          <button style={{ ...buttonBase, flexShrink: 0 }} onClick={() => setPaused(p => !p)} disabled={demoMode !== 'AUTO'}>{paused ? 'Resume' : 'Pause'}</button>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)', flexShrink: 0 }}>
            <input type="checkbox" checked={pauseOnKill} onChange={(e) => setPauseOnKill(e.target.checked)} />
            <span>Pause on KILL</span>
          </label>
          <button style={{ ...buttonBase, flexShrink: 0 }} onClick={() => reset()}>Reset</button>
        </div>

        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8, overflowX: 'auto', whiteSpace: 'nowrap' }}>
          <button style={{ ...buttonBase, ...(manualMode === 'NORMAL' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('NORMAL')} disabled={demoMode !== 'MANUAL'}>NORMAL</button>
          <button style={{ ...buttonBase, ...(manualMode === 'WARN' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('WARN')} disabled={demoMode !== 'MANUAL'}>WARN</button>
          <button style={{ ...buttonBase, ...(manualMode === 'DOWNGRADE' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('DOWNGRADE')} disabled={demoMode !== 'MANUAL'}>DOWNGRADE</button>
          <button style={{ ...buttonBase, ...(manualMode === 'KILL' ? { fontWeight: 700 } : {}), flexShrink: 0 }} onClick={() => setManualMode('KILL')} disabled={demoMode !== 'MANUAL'}>KILL</button>
          <button style={{ ...buttonBase, fontSize: 11, flexShrink: 0 }} onClick={() => setIntervalMs(5000)} aria-pressed={intervalMs === 5000}>5s</button>
          <button style={{ ...buttonBase, fontSize: 11, flexShrink: 0 }} onClick={() => setIntervalMs(8000)} aria-pressed={intervalMs === 8000}>8s</button>
          <div style={{ marginLeft: 'auto', padding: '4px 8px', borderRadius: 999, border: '1px solid var(--border)', fontSize: 12, color: 'var(--muted)', background: 'transparent', flexShrink: 0 }}>{demoMode} {paused ? '· PAUSED' : ''}</div>
        </div>
      </div>
    </div>
  )
}

export default DemoControls
