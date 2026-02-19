import { RiskSnapshot, RiskMode, TradeLevel } from '../types/risk'

/**
 * Return a deterministic RiskSnapshot for a given tick.
 * Behavior (non-runtime description):
 *  - tick % 4 === 0 => NORMAL
 *  - tick % 4 === 1 => WARN
 *  - tick % 4 === 2 => DOWNGRADE
 *  - tick % 4 === 3 => KILL
 * pnl, drawdown, exposure are simple functions of tick to vary numbers.
 */
export function getMockRiskSnapshot(tick: number = 0): RiskSnapshot {
  const modes: RiskMode[] = ['NORMAL', 'WARN', 'DOWNGRADE', 'KILL']
  const mode = modes[Math.abs(Math.floor(tick)) % modes.length]

  const level: TradeLevel = tick % 3 === 0 ? 'L2_FULL' : tick % 3 === 1 ? 'L1_LIMITED' : 'L0_VIEW'

  const base = (tick % 10) - 5
  const pnl = Number((base * 12.34).toFixed(2))
  const drawdown = Math.min(Math.abs(base) / 10, 0.5)
  const exposure = Math.min(Math.abs(base) / 20, 1)

  const snapshot: RiskSnapshot = {
    mode,
    level,
    pnl,
    drawdown,
    exposure,
    lastUpdate: new Date().toLocaleTimeString('ko-KR'),
    riskEngineActive: true,
    killSwitchArmed: mode === 'KILL',
    reason: mode === 'KILL' ? 'Maintenance window: trading disabled' : mode === 'DOWNGRADE' ? 'Reduced capacity — downgrade active' : undefined,
  }

  return snapshot
}

export default getMockRiskSnapshot
