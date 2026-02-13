"use client";

import React, { ReactNode } from 'react';

interface PanelProps {
    title?: string;
    children: ReactNode;
    className?: string;
}

export default function Panel({ title, children, className = '' }: PanelProps) {
    return (
        <div
            style={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                overflow: 'hidden',
            }}
            className={className}
        >
            {title && (
                <div
                    style={{
                        padding: '10px 14px',
                        borderBottom: '1px solid var(--border)',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: 'var(--text)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        background: 'var(--panel2)',
                    }}
                >
                    {title}
                </div>
            )}
            <div style={{ padding: title ? '0' : '14px' }}>
                {children}
            </div>
        </div>
    );
}
