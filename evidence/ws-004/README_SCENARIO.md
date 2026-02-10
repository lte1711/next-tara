#!/usr/bin/env python3
"""
TICKET-WS-004 증거 수집 시나리오 스크립트.
각 증거 항목별 실행 절차와 예상 결과 정의.
"""

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                      TICKET-WS-004 증거 수집 시나리오                        ║
╚════════════════════════════════════════════════════════════════════════════╝

## 사전 준비

1. 백엔드 시작:
   cd c:\\projects\\NEXT-TRADE
   python -m uvicorn next_trade.api.app:app --host 0.0.0.0 --port 8000 --reload

2. 프론트엔드 시작:
   cd c:\\projects\\NEXT-TRADE-UI
   npm run dev

3. 브라우저에서 열기:
   http://localhost:3000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 증거 1️⃣: 01_terminal_6_events.png

목표: AuditTerminal에 6종 이벤트가 누적되는 화면

절차:
1. Dev 10k 버튼 클릭 (또는 콘솔에서 curl 명령)
2. 5~10초 대기하여 Audit 터미널에 여러 이벤트가 표시될 때까지
3. 아래 항목이 모두 보일 때 캡처:
   ✓ [RISK_TRIGGERED]
   ✓ [ORDER_REJECTED]
   ✓ [LEVEL_DOWNGRADED]
   ✓ [LEVEL_RESTORED]
   ✓ [SYSTEM_GUARD]
   ✓ [AUDIT_LOG]

콘솔 명령(대안):
  curl -X POST http://localhost:8000/api/dev/emit-10k

예상: Audit 터미널 하단에 다양한 색상의 이벤트가 스크롤됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 증거 2️⃣: 02_level_downgraded_modal.png

목표: LEVEL_DOWNGRADED 모달이 떠있고 trace_id가 명확히 보이는 화면

절차:
1. 콘솔에서 LEVEL_DOWNGRADED 이벤트만 발행:
   curl -X POST http://localhost:8000/api/dev/emit-event \\
     -H "Content-Type: application/json" \\
     -d '{"event_type":"LEVEL_DOWNGRADED","index":0,"total":1}'

2. 즉시 UI에 빨간색 경보 모달이 떠남
3. 아래 항목이 모두 보일 때 캡처:
   ✓ 모달 제목: "⚠️ RISK LEVEL DOWNGRADED"
   ✓ 레벨 변화: Level 4 → Level 1 (또는 유사)
   ✓ trace_id 필드
   ✓ Timestamp
   ✓ "✓ Acknowledged" 버튼

예상: 검은색 배경 위에 빨간색 테두리 모달

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 증거 3️⃣: 03_loadtest_10k_ws_dropped.png

목표: Dev 10k 실행 중 진행률 + WS_DROPPED 카운터

절차:
1. Dev Load Test Panel이 보이는 상태 확보
2. "Emit 10,000 Events (Stress Test)" 버튼 클릭
3. 진행 중(약 1~5초 사이) 스크린샷:
   ✓ "Events Sent: X" (0 < X < 10,000)
   ✓ "Dropped: Y" (가능하면 Y > 0 이어야 backpressure 동작 증거)
   ✓ "Success Rate: Z%"

예상:
- 만약 큐가 포화된다면 Dropped > 0 표시
- 만약 큐가 충분하다면 Dropped = 0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 증거 4️⃣: 04_reconnect_backoff.png

목표: 서버 중단 → Disconnected → Backoff 시간이 증가하는 증거

절차:
1. 백엔드 서버 중단 (Ctrl+C in backend terminal)
2. 프론트엔드 콘솔 열기 (F12)
3. 약 30초 대기하면서 아래 로그 관찰:
   - "[WS] Disconnected" 직후
   - "[WS] Backoff: 1000ms" → "2000ms" → "4000ms" ... 증가

4. 콘솔 로그가 보이는 상태로 스크린샷:
   ✓ "[WS] Disconnected"
   ✓ "[WS] Error" 또는 재연결 로그
   ✓ 또는 UI 헤더의 "WebSocket Disconnected" 상태

예상: 브라우저 콘솔에서 재연결 시도 로그 (1s, 2s, 4s, 8s... 백오프)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 증거 5️⃣: 05_trace_id_filter.png

목표: trace_id 클릭 후 필터가 적용되어 해당 trace_id만 표시

절차:
1. Dev 10k 실행하여 Audit 터미널에 여러 이벤트 누적
2. 터미널의 아무 이벤트나 trace_id(파란색, underline) 클릭
3. 필터가 적용되면 해당 trace_id만 남음
4. 이때 스크린샷:
   ✓ 헤더: "🔍 Filtered by trace_id: stress-00..."
   ✓ 터미널: 동일한 trace_id를 가진 이벤트만 표시
   ✓ 카운터: 필터된 이벤트 개수(보통 1~3개)

예상: 필터 적용 전: 1000+ 이벤트 → 필터 후: 1~3 이벤트

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 캡처 저장 위치

evidence/ws-004/
  ├── 01_terminal_6_events.png
  ├── 02_level_downgraded_modal.png
  ├── 03_loadtest_10k_ws_dropped.png
  ├── 04_reconnect_backoff.png
  └── 05_trace_id_filter.png

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

실행 순서 권장:
1. 백엔드 + 프론트엔드 시작
2. 증거 1️⃣ (6 events)
3. 증거 2️⃣ (modal)
4. 증거 3️⃣ (load test)
5. 증거 4️⃣ (backoff - 서버 중단 필요)
6. 증거 5️⃣ (trace filter)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
