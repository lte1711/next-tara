"use client"

import React, { createContext, useContext, useEffect, useState } from 'react'
import { getMockRiskSnapshot } from '../mocks/riskMock'
import type { RiskSnapshot, RiskMode } from '../types/risk'

type DemoMode = 'AUTO' | 'MANUAL'

interface RiskContextValue {
  snapshot: RiskSnapshot
  tick: number
  demoMode: DemoMode
  setDemoMode: (m: DemoMode) => void
  paused: boolean
  setPaused: (p: boolean) => void
  manualMode: RiskMode
  setManualMode: (m: RiskMode) => void
  intervalMs: number
  setIntervalMs: (ms: number) => void
  pauseOnKill: boolean
  setPauseOnKill: (v: boolean) => void
  reset: () => void
}

const defaultSnapshot: RiskSnapshot = getMockRiskSnapshot(0)

const RiskContext = createContext<RiskContextValue | null>(null)

export const MockProvider: React.FC<React.PropsWithChildren<{}>> = ({ children }) => {
  const [tick, setTick] = useState<number>(0)
  const [demoMode, setDemoMode] = useState<DemoMode>('AUTO')
  const [paused, setPaused] = useState<boolean>(false)
  const [manualMode, setManualMode] = useState<RiskMode>('NORMAL')
  const [intervalMs, setIntervalMs] = useState<number>(5000)
  const [pauseOnKill, setPauseOnKill] = useState<boolean>(false)

  useEffect(() => {
    if (demoMode !== 'AUTO' || paused) return undefined
    const id = setInterval(() => setTick(t => t + 1), intervalMs)
    return () => clearInterval(id)
  }, [demoMode, paused, intervalMs])

  // If pause-on-kill enabled, pause when snapshot transitions to KILL
  useEffect(() => {
    const s = getMockRiskSnapshot(tick)
    if (pauseOnKill && s.mode === 'KILL') {
      setPaused(true)
    }
  }, [tick, pauseOnKill])

  let snapshot = getMockRiskSnapshot(tick)
  if (demoMode === 'MANUAL') snapshot = { ...snapshot, mode: manualMode }

  const reset = () => {
    setTick(0)
    setManualMode('NORMAL')
    setDemoMode('AUTO')
    setPaused(false)
  }

  const value: RiskContextValue = {
    snapshot,
    tick,
    demoMode,
    setDemoMode,
    paused,
    setPaused,
    manualMode,
    setManualMode,
    intervalMs,
    setIntervalMs,
    pauseOnKill,
    setPauseOnKill,
    reset,
  }

  return <RiskContext.Provider value={value}>{children}</RiskContext.Provider>
}

export function useRisk(): RiskContextValue {
  const ctx = useContext(RiskContext)
  if (!ctx) throw new Error('useRisk must be used within a MockProvider')
  return ctx
}

export default MockProvider
