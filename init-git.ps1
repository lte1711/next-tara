# NEXT-TRADE-UI git initialization (PowerShell)
# Run from: c:\projects\NEXT-TRADE-UI

Set-Location c:\projects\NEXT-TRADE-UI

# Initialize git repo
git init

# Add all files
git add -A

# Commit with message
git commit -m "feat(ui): PHASE 9-1 Dashboard MVP - Command Center

- 4 Dashboard Cards: Engine Status, Positions, Recent Risks, Kill-Switch Control
- WebSocket integration (/ws/events): real-time risk_event, position_snapshot, engine_state
- REST API client: /state/engine, /state/positions, /history/risks, /control/killswitch
- Next.js 14 + React 18 + TypeScript + Tailwind CSS
- Kill-switch toggle with 1-second UI update validation
- Audit ID display on successful toggle
- Console logging for test verification"
