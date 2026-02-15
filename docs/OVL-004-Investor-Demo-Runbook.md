# OVL-004 — Investor Demo Runbook

작성일: 2026-02-15

목표: 누구든지 문서를 따라하면 2분 데모를 안정적으로 실행하고, 주요 실패 상황을 복구할 수 있도록 한다.

---

## 1) Pre-Demo Checklist (T-5분)

- 서버가 기동 중인지 확인 (uvicorn, 포트 8000)
  ```powershell
  # 프로젝트 루트에서
  .\venv\Scripts\python.exe -m uvicorn ops_web.app:app --host 127.0.0.1 --port 8000
  # 이미 실행중이면 프로세스 확인
  netstat -ano | findstr :8000
  ```
- `/ops` 접속 확인 (브라우저 또는 curl)
  ```powershell
  curl.exe -sS http://127.0.0.1:8000/ | Select-String -Pattern "NEXT-TRADE Ops Dashboard" -SimpleMatch
  ```
- metrics 정상 표시 확인
  ```powershell
  curl.exe -s http://127.0.0.1:8000/api/ops/metrics | ConvertFrom-Json
  ```
- SSE 연결 상태 확인(간단)
  ```powershell
  # 짧게 SSE 리스폰스 확인(최초 라인)
  curl.exe -N http://127.0.0.1:8000/events -m 5 | Select-String -Pattern "data:" -SimpleMatch -First 1
  ```
- curl 테스트: 이벤트 주입 1회
  ```powershell
  curl.exe -s -X POST http://127.0.0.1:8000/api/ops/test-event -H "Content-Type: application/json" -d '{"message":"smoke","source":"demo"}' | Out-File -Encoding utf8 smoke_resp.json
  Get-Content smoke_resp.json
  ```

---

## 2) 2-Minute Live Demo Script (초 단위 흐름)

총 시간: 약 120초

0:00 — 화면 소개 (0~20초)
- 브라우저로 `http://127.0.0.1:8000/ops` 오픈
- 상단 카드(Health / DropCount / Subscribers)를 짧게 설명

0:20 — 실시간 이벤트 주입 (20~45초)
- 터미널에서 이벤트 생성:
  ```powershell
  curl.exe -s -X POST http://127.0.0.1:8000/api/ops/test-event -H "Content-Type: application/json" -d '{"message":"demo","source":"investor"}'
  ```
- 대시보드의 타임라인에 이벤트가 즉시 찍히는 것을 가리킴
- 응답의 `trace_id`를 언급(추적 가능성 강조)

0:45 — Trace 그룹 설명 (45~80초)
- 동일 `trace_id`로 묶인 이벤트들이 그룹으로 모이는 것을 보여줌
- 운영자가 사고의 전후 관계를 한 눈에 보는 장면 시연

1:20 — 필터/검색 (80~100초)
- Type 필터를 변경하여 특정 유형만 남기는 시연
- Trace 검색 상자에 `trace_id` 일부 입력하여 필터링

1:40 — Export (100~115초)
- Export 버튼 클릭(또는 클릭 스크린샷 제시)
- 설명: “이 JSON은 감사/보고용 원본 증거로 사용됩니다.”

1:55 — 정리 멘트 (115~120초)
- 한 줄 요약: 위험을 감지·통제·증거화하는 인프라임을 강조

---

## 3) Failure Recovery Playbook

### 상황 A: `/ops`에 접속 불가

1) 앱 프로세스 상태 확인
  ```powershell
  netstat -ano | findstr :8000
  Get-Process -Id <pid> | Select-Object Id,ProcessName
  Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" | Select-Object CommandLine
  ```
2) uvicorn 재기동(간단)
  ```powershell
  # 기존 프로세스 강제 종료(필요한 경우)
  Stop-Process -Id <pid> -Force
  # 재기동
  .\venv\Scripts\python.exe -m uvicorn ops_web.app:app --host 127.0.0.1 --port 8000
  ```
3) 로그 확인
  - `ops_web`이 stdout으로 로그를 찍고 있으면 터미널에서 확인. 추가 로그가 필요하면 서비스 런처/시스템 로그 확인.

### 상황 B: 이벤트가 대시보드에 표시되지 않음

1) 엔드포인트 직접 호출 확인
  ```powershell
  curl.exe -v -X POST http://127.0.0.1:8000/api/ops/test-event -H "Content-Type: application/json" -d '{"message":"check","source":"replay"}'
  ```
2) SSE 재확인
  ```powershell
  curl.exe -N http://127.0.0.1:8000/events -m 10
  ```
3) 로컬 기록 확인
  ```powershell
  # 실시간 관찰 파일 tail (Windows PowerShell에서)
  Get-Content metrics\live_obs.jsonl -Tail 50 -Wait
  ```
4) 필요시 구독자 수 확인
  ```powershell
  curl.exe -s http://127.0.0.1:8000/api/ops/metrics | ConvertFrom-Json
  ```

### 상황 C: `DropCount` 이상치(드롭 발생)

1) metrics 확인
  ```powershell
  curl.exe -s http://127.0.0.1:8000/api/ops/metrics | ConvertFrom-Json
  ```
2) 테스트 모드(강제 소형 큐) 확인
  ```powershell
  # OPS_BUS_QMAX 환경변수로 재시작한 경우 확인
  $env:OPS_BUS_QMAX
  ```
3) 샘플 이벤트/로그 검사
  ```powershell
  Get-Content metrics\live_obs.jsonl | Select-String -Pattern "backpressure-drop" -SimpleMatch
  ```
4) 일시적 조치: 추가 구독자 제거 또는 대시보드 새로고침

---

## 4) Rehearsal Checklist (사전 리허설)

- 스크린샷 타이밍 표기(예: 0:25 이벤트 찍혔을 때, 1:42 Export 클릭)
- Export 파일 저장 위치 기록(가능하면 자동화 스크립트로 수거)
- 데모 전 1회 전체 리허설(녹화 권장)
- 리허설 시각 및 담당자 로그 기록

---

## 5) Post-Demo Evidence Collection

- 데모 직후 다음 파일을 `evidence/phase-ops/OVL-003-DEMO/`에 저장:
  - 대시보드 스크린샷(타임스탬프 포함)
  - Export된 JSON (있을 경우)
  - 터미널 명령 기록(사용한 curl 명령과 응답)
  - `metrics/live_obs.jsonl`의 tail 스니펫

---

## 6) Quick Reference Commands

- Restart app:
  ```powershell
  Stop-Process -Id <pid> -Force; .\venv\Scripts\python.exe -m uvicorn ops_web.app:app --host 127.0.0.1 --port 8000
  ```
- Fetch metrics:
  ```powershell
  curl.exe -s http://127.0.0.1:8000/api/ops/metrics | ConvertFrom-Json
  ```
- Trigger event:
  ```powershell
  curl.exe -s -X POST http://127.0.0.1:8000/api/ops/test-event -H "Content-Type: application/json" -d '{"message":"demo","source":"investor"}'
  ```

---

작성자: Honey (자동 생성)

