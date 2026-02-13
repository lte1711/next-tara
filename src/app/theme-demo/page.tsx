"use client";

import React, { useState } from 'react';
import AppShell from '@/components/AppShell';
import Panel from '@/components/Panel';
import { RiskMode } from '@/components/GlobalRiskBar';

export default function InstitutionalThemeDemo() {
    const [riskMode, setRiskMode] = useState<RiskMode>('NORMAL');

    return (
        <AppShell
            riskMode={riskMode}
            riskMessage={riskMode !== 'NORMAL' ? 'System status changed' : undefined}
        >
            <div style={{
                display: 'grid',
                gridTemplateColumns: '250px 1fr 300px',
                gridTemplateRows: '400px 1fr',
                gap: '8px',
                padding: '8px',
                height: '100%',
            }}>
                {/* Market List */}
                <Panel title="Markets" style={{ gridRow: 'span 2' }}>
                    <div style={{ padding: '14px' }}>
                        {['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT'].map((pair) => (
                            <div
                                key={pair}
                                style={{
                                    padding: '8px',
                                    marginBottom: '4px',
                                    cursor: 'pointer',
                                    borderRadius: '4px',
                                    fontSize: '13px',
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--panel2)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                            >
                                <div style={{ fontWeight: 600 }}>{pair}</div>
                                <div style={{ color: 'var(--profit)', fontSize: '11px' }}>+2.45%</div>
                            </div>
                        ))}
                    </div>
                </Panel>

                {/* Chart */}
                <Panel title="Chart" style={{ gridColumn: '2' }}>
                    <div style={{
                        padding: '14px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                        color: 'var(--muted)',
                        fontSize: '13px',
                    }}>
                        Chart placeholder (TradingView integration)
                    </div>
                </Panel>

                {/* Orderbook */}
                <Panel title="Orderbook" style={{ gridColumn: '3' }}>
                    <div style={{ padding: '14px', fontSize: '11px', fontFamily: 'monospace' }}>
                        {[...Array(8)].map((_, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                                <span style={{ color: i % 2 === 0 ? 'var(--profit)' : 'var(--loss)' }}>
                                    {(42000 + i * 10).toFixed(2)}
                                </span>
                                <span style={{ color: 'var(--muted)' }}>
                                    {(Math.random() * 2).toFixed(4)}
                                </span>
                            </div>
                        ))}
                    </div>
                </Panel>

                {/* Trades */}
                <Panel title="Recent Trades" style={{ gridColumn: '2' }}>
                    <div style={{ padding: '14px', fontSize: '11px', fontFamily: 'monospace' }}>
                        {[...Array(6)].map((_, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{ color: i % 3 === 0 ? 'var(--profit)' : 'var(--loss)' }}>
                                    {(42000 + Math.random() * 100).toFixed(2)}
                                </span>
                                <span style={{ color: 'var(--muted)' }}>
                                    {(Math.random() * 0.5).toFixed(4)}
                                </span>
                                <span style={{ color: 'var(--muted)', fontSize: '10px' }}>
                                    {new Date().toLocaleTimeString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </Panel>

                {/* Order Panel */}
                <Panel title="Order Entry" style={{ gridColumn: '3' }}>
                    <div style={{ padding: '14px' }}>
                        <div style={{ marginBottom: '12px' }}>
                            <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
                                Price
                            </label>
                            <input
                                type="text"
                                placeholder="42000.00"
                                disabled={riskMode === 'KILL'}
                                style={{
                                    width: '100%',
                                    padding: '8px',
                                    background: 'var(--panel2)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '4px',
                                    color: 'var(--text)',
                                    fontSize: '13px',
                                }}
                            />
                        </div>
                        <div style={{ marginBottom: '12px' }}>
                            <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
                                Amount
                            </label>
                            <input
                                type="text"
                                placeholder="0.001"
                                disabled={riskMode === 'KILL'}
                                style={{
                                    width: '100%',
                                    padding: '8px',
                                    background: 'var(--panel2)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '4px',
                                    color: 'var(--text)',
                                    fontSize: '13px',
                                }}
                            />
                        </div>
                        <button
                            disabled={riskMode === 'KILL'}
                            style={{
                                width: '100%',
                                padding: '10px',
                                background: riskMode === 'KILL' ? 'var(--muted)' : 'var(--profit)',
                                border: 'none',
                                borderRadius: '4px',
                                color: '#fff',
                                fontWeight: 600,
                                fontSize: '13px',
                                cursor: riskMode === 'KILL' ? 'not-allowed' : 'pointer',
                                opacity: riskMode === 'KILL' ? 0.5 : 1,
                            }}
                        >
                            {riskMode === 'KILL' ? 'TRADING DISABLED' : 'BUY'}
                        </button>
                    </div>
                </Panel>
            </div>

            {/* Risk Mode Switcher (Demo Only) */}
            <div style={{
                position: 'fixed',
                bottom: '20px',
                right: '20px',
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '12px',
                display: 'flex',
                gap: '8px',
            }}>
                {(['NORMAL', 'WARN', 'KILL', 'DOWNGRADE'] as RiskMode[]).map((mode) => (
                    <button
                        key={mode}
                        onClick={() => setRiskMode(mode)}
                        style={{
                            padding: '6px 12px',
                            background: riskMode === mode ? 'var(--panel2)' : 'transparent',
                            border: '1px solid var(--border)',
                            borderRadius: '4px',
                            color: 'var(--text)',
                            fontSize: '11px',
                            cursor: 'pointer',
                        }}
                    >
                        {mode}
                    </button>
                ))}
            </div>
        </AppShell>
    );
}
