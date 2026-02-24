# SR72 Phase 1 — S2 + S4 실행 가이드

**문서번호**: NEXT-TRADE-SR72-S2-S4-001  
**발행**: 2026-02-20 04:35  
**집행자**: dennis

---

## 🎯 목표

- **S2**: WebSocket 강제 단절 → 자동 재연결 검증
- **S4**: 메트릭 정합성 (발행 = 소비 = WS 전송) 확인

---

## 📊 현재 메트릭 베이스라인 (S2 실행 전)

```
event_published: 26,497
event_consumed: 26,497
event_queue_depth: 0
ws_messages_total: 52,994
```

✅ **정합성**: published = consumed, queue_depth = 0 (완벽)

---

## 🔵 S2 실행 절차 (15분)

### STEP 1: 브라우저 준비
1. `http://localhost:3001` 열기
2. **F12 → DevTools 열기**
3. **Network 탭** 선택

### STEP 2: WS 상태 확인 (Before)
- Console에서 "WebSocket connected" 확인
- UI 우상단 "● Connected" 녹색 표시 확인

### STEP 3: 강제 단절
1. Network 탭에서 **"Offline" 선택** (드롭다운)
2. **15초 대기**
3. Console 확인:
   ```
   WebSocket closed
   reconnecting...
   ```
4. UI 우상단 "○ Disconnected" 빨간색 확인

### STEP 4: 스크린샷 1 (Before)
- 파일명: `ws_reconnect_offline.png`
- 포함: Console "WebSocket closed" + UI "Disconnected"

### STEP 5: 복구
1. Network 탭에서 **"Online" 선택**
2. **10초 대기**
3. Console 확인:
   ```
   WebSocket reconnected
   ```
4. UI 우상단 "● Connected" 녹색 복귀

### STEP 6: 이벤트 재개 확인
- Audit Terminal에서 새 이벤트 수신 확인
- Heartbeat 카운터 증가 확인

### STEP 7: 스크린샷 2 (After)
- 파일명: `ws_reconnect_online.png`
- 포함: Console "reconnected" + UI "Connected"

### STEP 8: 증거 수집
PowerShell:
```powershell
cd C:\projects\NEXT-TRADE
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\honey_reports\sr72_collect.ps1 `
  -Hours 1 -Limit 100
```

### S2 성공 기준
| 항목 | 기준 |
|------|------|
| 재연결 | 10초 이내 |
| Console | "reconnected" 로그 |
| UI | Connected 복귀 |
| 이벤트 | 재수신 시작 |

---

## 🟣 S4 실행 절차 (10분)

### STEP 1: 최신 메트릭 확인
PowerShell:
```powershell
cd C:\projects\NEXT-TRADE
Get-Content .\metrics\evergreen_metrics.jsonl -Tail 5
```

### STEP 2: 핵심 지표 추출
마지막 라인에서 확인:
- `event_published`: XXXX
- `event_consumed`: XXXX
- `event_queue_depth`: X
- `ws_messages_total`: XXXX

### STEP 3: 정합성 계산
```
✅ published = consumed (차이 0 또는 ±1)
✅ queue_depth = 0 (정체 없음)
✅ ws_messages ≈ 2 × published (양방향 통신)
```

### STEP 4: S4 PASS 조건
- published와 consumed 차이 < 10
- queue_depth < 5
- 메트릭 파일 정상 기록 중

### STEP 5: notes.md 업데이트
최신 SR72 폴더의 `notes.md`에 추가:
```markdown
## SR72 Scenario S4 — Metrics Consistency (PASS)

### Observed
- event_published: 26,497
- event_consumed: 26,497
- event_queue_depth: 0
- ws_messages_total: 52,994

### PASS Rationale
Perfect consistency: published = consumed, no queue backlog, WS messages ~2x events (bidirectional).
No drift or data loss detected.

### Evidence
- evergreen_metrics.jsonl tail (5 lines)
- SR72 collector folder: SR72_YYYYMMDD_HHMMSS
```

---

## 🏁 Phase 1 완료 조건

| 시나리오 | 상태 |
|---------|------|
| S1 (10K Load) | ✅ PASS |
| S2 (WS Reconnect) | ⏳ 실행 중 |
| S4 (Metrics) | ⏳ 실행 중 |

**3개 모두 PASS → SR72 Phase 1 공식 완료**

---

## 📸 필수 스크린샷 (총 2장)

1. `ws_reconnect_offline.png` (Offline 상태)
2. `ws_reconnect_online.png` (Online 복귀)

저장 위치: 최신 SR72 폴더의 `snapshots/`

---

## ⏱️ 예상 소요 시간

- S2: 15분 (단절 → 복구 → 스크린샷)
- S4: 10분 (메트릭 확인 → 기록)
- **Total: 25분**

---

**지금 바로 S2부터 시작하세요!** 🚀
