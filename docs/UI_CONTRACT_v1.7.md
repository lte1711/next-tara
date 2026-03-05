# NEXT-TRADE UI Contract v1.7

Document ID: NEXT-TRADE-CC-OPS-UI-CONTRACT-042  
Status: Frozen (Operational Baseline)  
Effective Date: 2026-03-03

## 1) Scope

This contract defines non-functional UI operating rules for:

- Visual token governance
- Route role separation
- WebSocket visibility semantics
- Restart/recovery runbook linkage
- Chart sizing policy

This document is additive-only and does not change backend API contracts.

## 2) Theme Token Contract

Single source of truth:

- `src/app/globals.css` for `--nt-*` tokens
- `tailwind.config.*` for `colors.nt.*` mapping

Rules:

- Do not hardcode one-off color values in feature components if a token exists.
- UI state colors must map to `nt.up`, `nt.down`, `nt.warn`, `nt.info`.
- Numeric/status heavy UI should use `tabular-nums`.

## 3) Route Role Contract

- `/command-center`: decision screen (summary-first)
- `/command-center/events`: deep log analysis screen

Rules:

- Large event tables are prohibited in `/command-center`.
- `/command-center` may show only compact event summary + navigation to full view.

## 4) WS Visibility Contract

To avoid operator misinterpretation:

- `WS Heartbeat`: frame arrival freshness (transport-level alive)
- `Data Changed`: last meaningful payload state change (domain-level change)

Rules:

- Heartbeat and Data Change must be shown as separate fields.
- If payload is unchanged, heartbeat can update while data change remains stale.

## 5) Runtime Restart Contract

Operational issues must follow standardized recovery tickets:

- 038: UI change not reflected (old instance / wrong route target)
- 041: `/_next/static/*` returns 400 (asset hash/runtime mismatch)
- 035: Recharts `width(-1)/height(-1)` warning (layout sizing fault)

Do not run ad-hoc restart sequences outside these runbooks.

## 6) Chart Contract (v1.7 Baseline)

Current accepted stable policy:

- Fixed chart size (`720x260`) + `overflow-x-auto` wrapper
- `min-h-0` on card/content containers where flex/grid shrink can occur

Alternative allowed policy:

- `ResponsiveContainer` only if direct parent has explicit non-zero height and `min-w-0`

## 7) Verification Gates

Minimum acceptance before operational approval:

1. `npm run build` succeeds
2. `/command-center` and `/command-center/events` are both reachable
3. No `/_next/static/*` 400 responses
4. Recharts `-1` warning is absent in build/runtime logs

## 8) Change Control

- Any deviation from this contract requires a new document ID and explicit approval.
- Existing frozen tickets remain valid baseline references:
  - 031, 032, 034, 035, 038, 039, 041

