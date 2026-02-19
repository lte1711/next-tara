git pull origin feature/ui-001-institutional-theme
git push origin feature/ui-001-institutional-theme
# feat(ui): institutional OrderPanel validation + layout hardening (UI-011~015)

## 요약
- OrderPanel에 **입력 검증(심볼/수량/가격 규칙)** 및 **raw 입력 → parsed/format 계층 분리**, **blur 힌트 UX**를 추가했습니다. (UI-011 ~ UI-014)
- Qty/Price 영역의 레이아웃 오버플로우를 **grid(1fr 1fr) 고정**으로 해결하여 카드 경계 초과를 방지했습니다. (UI-015)
- SSR 스냅샷 기반의 **증거(로컬 보관)**를 생성했습니다.

## 리스크/영향 (한 문장)
- **거래/리스크 엔진 동작(DOWNGRADE/KILL 포함)은 변경하지 않고**, OrderPanel의 **클라이언트 입력 UI·검증·레이아웃 안정성만 강화**합니다.

---

## 변경 상세

### 1) Validation & UX (UI-011~014)
- Symbol/Qty/Price 입력 규칙을 강화하고, 잘못된 입력에 대해 **inline 힌트/피드백** 제공
- 입력 처리 계층 분리:
  - raw: 사용자가 입력하는 원본 문자열
  - parsed: 검증/파싱된 값
  - formatted: 표시용 포맷 값
- blur 시점에 UX 힌트를 제공하여 입력 실수를 줄임

### 2) Layout hardening (UI-015)
- Qty/Price 입력 영역을 **grid 1fr / 1fr**로 고정
- 1280px 이하 포함 다양한 폭에서 **카드 밖으로 튀는 현상 방지**
- input min-width/overflow 케이스에 대한 방어 로직/스타일 반영

---

## 커밋 하이라이트
- 313a588 — feat(ui): TICKET-UI-014 refactor qty/price to raw input + parsed/formatted layers
- 69de2b8 — fix(ui): prevent OrderPanel Qty/Price overflow — grid layout + input minWidth fixes
- 1209549 — fix(ui): enforce equal columns for Qty/Price (grid 1fr 1fr) — TICKET-UI-015 DoD

## 주요 변경 파일
- src/components/OrderPanel.tsx
- src/components/GlobalRiskBar.tsx
- src/components/DemoControls.tsx
- src/components/BinanceLayout.tsx
- docs/TICKET-UI-015.md
- .gitignore

---

## 증거 (로컬 보관 / 커밋 제외)
> 아래 산출물은 **로컬에만 보관**하며 `.gitignore`로 제외합니다.

- evidence/ui/UI_015_SSR_EVIDENCE.zip (SSR snapshots + README)
- logs/ui_institutional_orderpanel_ui015_ok.html (mode=NORMAL)
- logs/ui_institutional_orderpanel_ui015_downgrade.html (mode=DOWNGRADE)
- logs/ui_institutional_orderpanel_ui015_kill.html (mode=KILL)

---

## 테스트/검증 절차

### 1) 로컬 dev 서버 실행
- Next.js dev server (포트 3000)

### 2) SSR 스냅샷 확인 (증거 재생성)
```powershell
curl.exe "http://localhost:3000/institutional?mode=NORMAL" -o ./logs/ui_institutional_orderpanel_ui015_ok.html
curl.exe "http://localhost:3000/institutional?mode=DOWNGRADE" -o ./logs/ui_institutional_orderpanel_ui015_downgrade.html
curl.exe "http://localhost:3000/institutional?mode=KILL" -o ./logs/ui_institutional_orderpanel_ui015_kill.html
Select-String -Path ./logs/ui_institutional_orderpanel_ui015_kill.html -Pattern "Price"
```

### 3) 시각 QA 체크

* OrderPanel에서 Qty/Price가 항상 **50:50** 비율인지 확인
* 1280px 이하에서도 **카드 밖으로 튀지 않는지** 확인
* NORMAL / DOWNGRADE / KILL 모드 모두에서 입력 UX/레이아웃이 일관적인지 확인

---

## DoD 체크리스트

* [x] Symbol/Qty/Price validation & inline hints implemented (UI-012~014)
* [x] Qty/Price grid 1fr/1fr 고정 (UI-015)
* [x] SSR 증거 캡처 및 로컬 보관 (`evidence/ui/`)
* [x] 산출물은 .gitignore로 제외 처리
* [x] 브랜치 상태: clean, PR-ready

---

## 롤백 플랜

* 문제 발생 시 **이 PR만 revert**하면 입력 UI/레이아웃 강화분이 원복되며,
  DOWNGRADE/KILL 등 런타임 리스크 로직에는 영향이 없습니다.

## 요청 리뷰어

* @ui-team
* @design-lead
* @qa

## 머지 전 확인(권장)

* NORMAL/DOWNGRADE/KILL 스크린샷 1세트
* 접근성(aria) 간단 점검 (labels, error announcement)

