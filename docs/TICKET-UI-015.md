# TICKET-UI-015 — OrderPanel: Prevent Price input overflow (Layout bugfix)

Priority: P0
Owner: UI Team / Honey

## 개요
`OrderPanel` 카드에서 `Price` 입력이 카드의 오른쪽 경계를 넘어 튀어나오는 레이아웃 버그를 수정합니다. 문제는 `qty/price` row가 `flex`(혹은 자식에 고정 폭/min-width)로 되어 있어 축소가 불가능해 발생합니다.

## 원인
- 한 줄(row)을 구성하는 컨테이너가 `flex`이며, 자식 요소(또는 입력)에 `min-width:auto` 또는 고정폭이 있어 줄어들지 못함.

## 해결안 (권장, B안 유지)
- `qty/price` row를 `grid` 2컬럼(예: `grid-template-columns: 1fr 1fr`)으로 변경
- 래퍼의 직계 자식에 `min-width: 0` 강제
- 입력 요소에 `width:100%` 및 `box-sizing: border-box` 적용
- KILL/DOWNGRADE 모드에서도 동일하게 동작하도록 검증

## 변경 파일(예)
- `src/components/OrderPanel.tsx`
- (필요 시) `src/app/globals.css` 또는 컴포넌트 전용 CSS

## 구현 단계
1. `OrderPanel.tsx`에서 `qty/price` 래퍼를 `grid` 2컬럼으로 변경
2. 래퍼의 직접 자식(`.op-field` 또는 인라인 스타일)에 `minWidth: 0` 적용
3. 각 `input`에 `width: '100%'`, `minWidth: 0`, `boxSizing: 'border-box'` 적용
4. 로컬 빌드/서버에서 렌더링 확인
5. SSR 증거 캡처 (아래 절차)

## 검증 절차 (증거 캡처)
1. Normal 상태 SSR 저장
   - `curl.exe "http://localhost:3000/institutional" -o "logs/ui_institutional_orderpanel_ui015_ok.html" --silent --show-error --fail`
2. DownGRADE 상태 SSR 저장
   - 서버/MockProvider를 통해 `initialMode=DOWNGRADE` 또는 DEV 하니스로 강제 후 저장
   - 파일: `logs/ui_institutional_orderpanel_ui015_downgrade.html`
3. KILL 상태 SSR 저장
   - 강제 `initialMode=KILL` 후 저장
   - 파일: `logs/ui_institutional_orderpanel_ui015_kill.html`
4. 파일 존재/크기 확인
   - `dir "logs\ui_institutional_orderpanel_ui015_*.html" | Select-Object Name,Length`
5. 레이아웃 정상성 확인(ASCII 토큰 검색)
   - `Select-String -Path "logs\ui_institutional_orderpanel_ui015_kill.html" -Pattern "Price" -List | Select-Object -First 1`
   - (또는 스크린샷 비교)

## DoD (Definition of Done)
- KILL/DOWNGRADE/NORMAL 모든 모드에서 `Price` 입력이 카드 경계를 넘지 않음
- 위 3모드 SSR 스냅샷이 `logs/`에 저장되어 있고, 파일 크기 및 핵심 토큰 검증 통과
- 변경사항은 feature 브랜치로 커밋되고 리뷰 요청됨

## 증거 파일명 템플릿
- `logs/ui_institutional_orderpanel_ui015_ok.html`
- `logs/ui_institutional_orderpanel_ui015_downgrade.html`
- `logs/ui_institutional_orderpanel_ui015_kill.html`

## 비고
- 이번 티켓은 UI 레이아웃 버그에 해당하므로 디자인팀과 시각 QA를 권장합니다.
- 이미 TICKET-UI-014에서 수행한 힌트/validation 작업과 충돌하지 않도록 주의하십시오.

---

작성: Honey (자동 생성)

