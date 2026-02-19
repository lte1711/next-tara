# TICKET-WS-004 Evidence Pack

## 증거 수집 현황

### ✅ 준비 완료
- [x] 05개 증거 항목 정의
- [x] evidence/ws-004/ 폴더 생성
- [x] 실행 시나리오 문서 작성

### 🔶 수집 대기 중
- [ ] 01_terminal_6_events.png (AuditTerminal + 6종 이벤트)
- [ ] 02_level_downgraded_modal.png (경보 모달 + trace_id)
- [ ] 03_loadtest_10k_ws_dropped.png (진행률 + 드랍 카운터)
- [ ] 04_reconnect_backoff.png (백오프 로그)
- [ ] 05_trace_id_filter.png (필터링)

## 실행 방법

`README_SCENARIO.md` 참고

## 커밋 정보

**UI 레포 (NEXT-TRADE-UI):**
- f83ee03: LevelDowngradedAlert + AuditTerminal + DevLoadTestPanel
- a721d18: useWebSocket (Exponential Backoff)
- 5553108: page.tsx (통합)

**백엔드 레포 (NEXT-TRADE):**
- a721d18: routes_dev.py + app.py (Dev 엔드포인트)
- d05a886: routes_dev 라우터 등록
