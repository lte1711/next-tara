<<<<<<< HEAD

## 🚀 Investor Demo Ready (OVL-003/004)

This repository includes a complete investor demo package:

- OPS Dashboard (OVL-001, OVL-002)
- Investor Demo Script (OVL-003)
- Investor Demo Runbook + Auto Verification (OVL-004)
- Reproducible demo verification script (`tools/honey_reports/verify_investor_demo.ps1`)

Bundle:
docs/NEXT-TRADE_OVL-003-004_Investor-Demo-Bundle_v1.1.zip


---

> For details and evidence files see `docs/` and `evidence/phase-ops/`.

=======
# NEXT-TRADE Command Center UI - PHASE 9-1

Dashboard MVP for real-time trading engine monitoring.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- FastAPI backend running on `localhost:8000`

### Installation & Run (Windows PowerShell)

**Terminal 1: Start FastAPI backend**
```powershell
cd c:\projects\NEXT-TRADE
python -m uvicorn src.next_trade.api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2: Install and start Next.js dev server**
```powershell
cd c:\projects\NEXT-TRADE-UI
npm install
npm run dev
```

Or in one line (PowerShell):
```powershell
cd c:\projects\NEXT-TRADE-UI ; npm install ; npm run dev
```

Dashboard will be available at: **http://localhost:3000**

## 📋 Features

### 4 Dashboard Cards

1. **Engine Status Card (Top Left)**
   - Kill-switch ON/OFF status
   - Risk type & reason
   - Uptime, published/consumed/pending event counts

2. **Positions Card (Top Right)**
   - Latest position snapshot per symbol
   - Qty, avg entry price, mark price, PnL
   - Multi-position indicator

3. **Kill-Switch Control Panel (Middle)**
   - Toggle ON/OFF with required reason
   - Display audit_id after toggle
   - Real-time status feedback

4. **Recent Risks Table (Bottom)**
   - Last 20 risk events (timestamp descending)
   - Level, event type, reason columns
   - Live updates via WebSocket

### Real-Time Updates

- **WebSocket `/api/ws/events`**: 
  - Receives `risk_event`, `position_snapshot`, `engine_state`
  - Auto-updates dashboard cards within 1 second

- **REST Endpoints** (initial load only):
  - `GET /api/state/engine`
  - `GET /api/state/positions`
  - `GET /api/history/risks?limit=20`
  - `POST /api/control/kill-switch`

## 🧪 Test Workflow

### Kill-Switch Test (1 second update validation)

1. Open Dashboard at http://localhost:3000
2. Open browser console (F12 → Console tab)
3. In **Kill-Switch Control Panel** → Enter reason (e.g., "test toggle")
4. Click **Turn ON** → observe:
   - **Console log** shows REST response with `audit_id`
   - **WebSocket log** shows `risk_event` received
   - **UI updates** within 1 second (top-left "KILL-SWITCH: ON" changes)

Expected console logs:
```
[Dashboard] WS Event: risk_event {event_type: 'risk_event', ts: 1707..., data: {...}}
[Kill-Switch] Toggled | audit_id: {audit_id}
RESULT: SUCCESS ✓
```

## 📁 Project Structure

```
src/
├── app/
│   ├── page.tsx           # Main dashboard page
│   ├── layout.tsx         # Root layout
│   └── globals.css        # Tailwind styles
├── components/
│   ├── EngineStatusCard.tsx
│   ├── PositionsCard.tsx
│   ├── RecentRisksTable.tsx
│   └── KillSwitchControlPanel.tsx
├── hooks/
│   └── useWebSocket.ts    # WebSocket hook
├── lib/
│   └── api.ts             # API client
```

## 🔧 Configuration

Edit `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=localhost:8000
```

## 📊 Development

```bash
# Lint check
npm run lint

# Build for production
npm run build
npm run start
```
>>>>>>> feature/ui-stale-001
