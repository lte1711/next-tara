export type RiskMode = 'NORMAL' | 'WARN' | 'KILL' | 'DOWNGRADE'

export type TradeLevel = 'L0_VIEW' | 'L1_LIMITED' | 'L2_FULL'

export default RiskMode

export interface RiskSnapshot {
	mode: RiskMode
	level: TradeLevel
	pnl: number
	drawdown: number
	exposure: number
	lastUpdate: string
	riskEngineActive: boolean
	killSwitchArmed: boolean
	reason?: string
}
