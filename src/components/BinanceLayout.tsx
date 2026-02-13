
"use client"

import React from 'react'
import GlobalRiskBar from './GlobalRiskBar'
import OrderPanel from './OrderPanel'
import { useRisk } from '../context/RiskContext'
import type { RiskSnapshot } from '../types/risk'

interface Props {
  children?: React.ReactNode
}

export const BinanceLayout: React.FC<Props> = ({ children }) => {
  // snapshot and control state come from RiskContext (Provider)
  const { snapshot } = useRisk()

  // Note: purely presentational scaffold for Binance-like layout
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <aside style={{ width: 260, padding: 16, borderRight: '1px solid var(--border)', background: 'var(--panel)' }}>
        <h2 style={{ marginBottom: 12 }}>Evergreen · Ops</h2>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button style={{ padding: 8, borderRadius: 6, background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)' }}>Dashboard</button>
          <button style={{ padding: 8, borderRadius: 6, background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)' }}>Strategies</button>
          <button style={{ padding: 8, borderRadius: 6, background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)' }}>Execution</button>
        </nav>
      </aside>

      <main style={{ flex: 1, padding: 16 }}>
        <header style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
          {/* Top row: match the grid used in the main section so right edge lines up with the right column */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', alignItems: 'center', gap: 4 }}>
            <div style={{ minWidth: 0 }}>
              <h1 style={{ margin: 0 }}>Binance View (Scaffold)</h1>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>Institutional theme — High contrast</div>
            </div>
          </div>

          {/* Second row: full-width GlobalRiskBar (metrics + indicators) */}
          <div style={{ width: '100%' }}>
            <GlobalRiskBar
              mode={snapshot.mode}
              pnl={snapshot.pnl}
              drawdown={snapshot.drawdown}
              exposure={snapshot.exposure}
              lastUpdate={snapshot.lastUpdate}
              riskEngineActive={snapshot.riskEngineActive}
              killArmed={snapshot.killSwitchArmed}
            />
          </div>

          {/* DemoControls are rendered inside GlobalRiskBar (compact single-line) */}
        </header>

        <section style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
          <article style={{ background: 'var(--panel2)', padding: 12, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
            {children ?? <div style={{ color: 'var(--muted)' }}>Main market stream / chart placeholder</div>}
          </article>

          <aside style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ background: 'var(--panel2)', padding: 12, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              Orderbook / depth placeholder
            </div>
            <div style={{ background: 'var(--panel2)', padding: 12, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              Positions / PnL placeholder
            </div>
            <div>
              {/* OrderPanel receives snapshot from RiskContext */}
              <OrderPanel mode={snapshot.mode} level={snapshot.level} reason={snapshot.reason} />
            </div>
          </aside>
        </section>
      </main>
    </div>
  )
}

export default BinanceLayout
