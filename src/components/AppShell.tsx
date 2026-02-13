"use client";

import React, { ReactNode } from 'react';
import GlobalRiskBar, { RiskMode } from './GlobalRiskBar';

interface AppShellProps {
    children: ReactNode;
    riskMode?: RiskMode;
    riskMessage?: string;
}

export default function AppShell({
    children,
    riskMode = 'NORMAL',
    riskMessage
}: AppShellProps) {
    return (
        <div
            style={{
                width: '100vw',
                height: '100vh',
                display: 'flex',
                flexDirection: 'column',
                background: 'var(--bg)',
            }}
        >
            <GlobalRiskBar mode={riskMode} message={riskMessage} />
            <div
                style={{
                    flex: 1,
                    overflow: 'hidden',
                }}
            >
                {children}
            </div>
        </div>
    );
}
