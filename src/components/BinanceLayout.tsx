import React from 'react'
import GlobalRiskBar from './GlobalRiskBar'
import OrderPanel from './OrderPanel'
import { getMockRiskSnapshot } from '../mocks/riskMock'
import type { RiskSnapshot } from '../types/risk'

interface Props {
  children?: React.ReactNode
}

export const BinanceLayout: React.FC<Props> = ({ children }) => {
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
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <h1 style={{ margin: 0 }}>Binance View (Scaffold)</h1>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>Institutional theme — High contrast</div>
          </div>
          <div style={{ minWidth: 320 }}>
            {/* Dummy mode shared between RiskBar and OrderPanel (scaffold only) */}
            {
              // Use static mock snapshot (no timers/intervals in scaffold)
              (() => {
                const snapshot: RiskSnapshot = getMockRiskSnapshot(0)
                return (
                  <GlobalRiskBar
                    mode={snapshot.mode}
                    pnl={snapshot.pnl}
                    drawdown={snapshot.drawdown}
                    exposure={snapshot.exposure}
                    lastUpdate={snapshot.lastUpdate}
                    riskEngineActive={snapshot.riskEngineActive}
                    killArmed={snapshot.killSwitchArmed}
                  />
                )
              })()
            }
          </div>
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
              {/* OrderPanel receives same dummy mode and trade level */}
              {/* Inject snapshot-derived props (static call) */}
              {(() => {
                const s = getMockRiskSnapshot(0)
                return <OrderPanel mode={s.mode} level={s.level} reason={s.reason} />
              })()}
            </div>
          </aside>
        </section>
      </main>
    </div>
  )
}

export default BinanceLayout
