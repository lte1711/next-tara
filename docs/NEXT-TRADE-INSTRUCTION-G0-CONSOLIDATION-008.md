# 📜 NEXT-TRADE 통합 지시서 (배포용)

문서번호: **NEXT-TRADE-INSTRUCTION-G0-CONSOLIDATION-008**
발신: **총괄 백설(Orchestrator)**
수신: **Dennis(결재/최종 책임), Honey(실행), Gemini(검증)**
효력: **즉시**
상태: **운영 고정(Constitution-001 준수)**

---

## 0) 목적 (1문장)

**로드맵(1→3→2)을 유지하되, “정리 게이트(G0)”를 먼저 통과하여 보안/형상/실행 표준화를 완료한 뒤에만 PDE 확장 및 알고리즘 고도화를 진행한다.**

---

## 1) 최상위 규칙 (헌법 고정 / 위반 시 즉시 중단)

### 1.1 헌법 고정 3대 원칙 (절대 변경 금지)

* `ENGINE_MODE=MR_ONLY`
* `ENGINE_APPLY_STATUS=DISABLED`
* `Engine-unmodified / Shadow-only` (엔진 코드/실거래 영향 **0**)

> **즉시 중단 트리거(하드스톱)**
> 아래 3개 중 1개라도 만족하면 **모든 작업 즉시 중단 + Dennis 보고**

* `ENGINE_APPLY_STATUS != DISABLED`
* `UNKNOWN_RATE_LAST_24H > 5%`
* `SCHEDULE_LAST_RESULT_* != 0` (**단, 트리거 실행 전 초기값 267011은 예외**. 실행 후에도 0이 아니면 중단)

---

## 2) 로드맵 고정 (진행 순서 변경 금지)

### 2.1 공식 로드맵

* **1 → 3 → 2**

  1. **Pattern Discovery Engine(PDE)**: 후보 풀 확장
  2. **Market Regime Detector**: 맥락 필터링
  3. **Backtest Engine**: 정밀 검증

### 2.2 단, 예외 규칙(필수)

* **G0(Consolidation Gate) 통과 전에는 PDE 확장/Regime/Backtest 신규 개발 금지**
* 허용되는 작업은 오직:

  * 보안 정리(Secrets 제거)
  * 커밋/브랜치/업스트림 정리
  * 프로세스 표준화
  * Gate-E1 관측(자동 실행 증거 확보)

---

## 3) 현재 판정 요약 (2026-03-05 기준)

* **헌법 Apply Disabled 유지:** ✅ PASS
* **PH7E 자동화(22:10 KST) 준비:** ✅ READY
* **Critical 리스크:** ❌ FAIL

  * `creds.py` 및 민감정보 탐지로 인해 핵심 파일 커밋 미완결
* **운영 리스크:** ⚠️ 요확인

  * 3000/3001 동시 리슨(중복 프로세스 가능)
  * NO_UPSTREAM 저장소 존재
  * 대규모 변경셋(회귀 추적 어려움)

---

# 4) “G0 정리 게이트” 정의 (이번 지시서의 핵심)

## 4.1 G0 목적

**보안(Secrets) + 형상관리(Git) + 실행 표준화(프로세스) 를 “운영 가능한 상태”로 고정**

## 4.2 G0 통과 조건 (모두 만족해야 PASS)

1. **Secrets 완전 제거/환경변수화**

   * 코드/스크립트 내 **하드코딩 키/시크릿 0**
   * `creds.py`는 `os.getenv()` 로더 역할만 수행
2. **NEXT-TRADE 잔여 핵심 파일 커밋 완결**

   * `git status` → clean
3. **Upstream 통일**

   * NEXT-TRADE / evergreen-ops-ui → `--set-upstream origin <branch>` 완료
   * NEXT-TRADE-UI → ahead 해소(푸시 후 ahead 0)
4. **프로세스 표준화**

   * dev 서버/노드/파이썬 중복 인스턴스 제거
   * “표준 기동 스크립트 1개”로만 실행
5. **최소 게이트 자동화**

   * pre-push 또는 수동 스모크 체크로 아래를 항상 확인:

     * `ENGINE_APPLY_STATUS=DISABLED`
     * Secret scan PASS
     * 기본 API health PASS

---

# 5) 역할별 실행 지시서

---

## 5.A) [Honey] 실행 지시서 (Execution)

**목표:** G0 통과 조건 1~5를 “증거 파일”로 남기고 완료

### A1. Secrets 제거(최우선 / 오늘 완료)

* 대상: `C:\projects\NEXT-TRADE\src\next_trade\config\creds.py` 및 훅이 막은 파일군
* 실행 규칙:

  * 비밀값은 `.env` 또는 OS 환경변수로 이동
  * 코드에는 `os.getenv("KEY")` 형태만 남김
  * `.env*`는 **git 추적 금지** (`.gitignore` 확인)

**증거 파일 생성**

* `evidence/security/g0_secret_sanitized_YYYYMMDD_HHMMSS.txt`

  * 포함: 변경 요약(파일명), 훅 재스캔 결과, `git diff --stat` 출력

### A2. 잔여 13개 핵심 파일 “커밋 가능 상태”로 정리

* 커밋 분리 규칙(강제):

  1. `fix/security:` (creds/env/secret 관련만)
  2. `feat/api:` (API 라우트/스키마)
  3. `feat/runtime:` (엔진/런타임)
  4. `ops:` (ps1/스케줄/운영)
  5. `docs:` (문서)

**증거 파일**

* `evidence/git/g0_commits_YYYYMMDD_HHMMSS.txt`

  * 포함: 커밋 해시 목록, 커밋 메시지, `git status` clean

### A3. Upstream 통일 + PUSH

* NEXT-TRADE-UI: `ahead 0` 만들기 (push)
* NEXT-TRADE / evergreen: upstream 설정 후 push

**증거 파일**

* `evidence/git/g0_upstream_status_YYYYMMDD_HHMMSS.txt`

  * 포함: `git remote -v`, `git branch -vv`, `git status -sb`

### A4. 프로세스 표준화(중복 제거)

* 목표: `3000/3001/8100`이 “의도된 구성”으로만 존재
* 규칙:

  * 불필요 dev 프로세스 종료
  * 표준 기동 스크립트 1개로만 실행

**증거 파일**

* `evidence/ops/g0_ports_process_YYYYMMDD_HHMMSS.txt`

  * 포함: `netstat` 또는 포트 점유 PID, 실행 커맨드 라인

### A5. Gate-E1(22:10) 관측 준비 유지

* 오늘 22:12~22:20 사이 실행:

  * `check_ph7e_gate_e1.ps1`

---

## 5.B) [Gemini] 검증 지시서 (Verification)

**목표:** Honey 결과를 “독립 판정서”로 PASS/FAIL 확정

### B1. 헌법 준수 검증(무조건)

* `ENGINE_APPLY_STATUS=DISABLED` 유지 확인
* Shadow-only 출력 경로 확인: `evidence/analysis`만 변경되는지 확인

### B2. Secrets 완전 제거 검증

* 커밋/변경 파일에서 키/시크릿 패턴 재탐지(문자열/형식)
* `git log --all -p`에서 과거 유출 흔적 여부 점검(가능 범위)

### B3. Git 정합성 검증

* 커밋 단위가 규칙대로 분리됐는지 확인
* upstream/push 상태 확인

**Gemini 산출물**

* `docs/VAL_G0_CONSOLIDATION_YYYYMMDD.md`

  * Verdict: PASS / FAIL
  * FAIL이면 “차단 항목 1~3개만” 명확히 명시

---

## 5.C) [Dennis] 결재/운영 지시 (Owner)

**목표:** “중단/승인” 판단만 수행(코드 수정 금지)

### C1. 승인 기준

* **G0 PASS** + **Gemini PASS** 일 때만 다음 단계 승인:

  * **PDE v1 확장 착수**

### C2. 오늘 밤 Gate-E1 확인

* 22:12~22:20 결과에서

  * `LastResult=0` 이 아니면 **즉시 중단 지시**

---

# 6) Gate-E1 운영 규칙 (오늘 밤 자동화)

## 6.1 Gate-E1 통과 조건

* `SCHEDULE_LAST_RESULT == 0`
* `ph7e_framework_20260305.log` 생성
* `ph7e_daily_health.txt` = PASS
* `ENGINE_APPLY_STATUS=DISABLED` 유지

## 6.2 Gate-E1 실패 시 즉시 조치

* Honey: 원인 분해(권한/경로/환경변수/작업 디렉토리)
* Gemini: 독립 판정서로 FAIL 근거 작성
* Dennis: “자동화 중단 or 재시도 승인” 결정

---

# 7) 롤백 절차 (5줄 고정)

1. **ZIP 선택**
2. **SHA256 검증**
3. **압축 해제**
4. **서비스 재기동**
5. **health 확인(8100/3000/3001 + DISABLED 확인)**

---

# 8) 보고 포맷 (모든 팀원 공통 / 복붙 고정)

## 8.1 Honey 보고(실행 완료 시)

```text
G0_SECRET_SANITIZE=PASS/FAIL
G0_COMMITS=PASS/FAIL
G0_UPSTREAM=PASS/FAIL
G0_PROCESS_STANDARD=PASS/FAIL
GATE_E1_STATUS=WAITING/PASS/FAIL
EVIDENCE_FILES=[...paths]
```

## 8.2 Gemini 판정(독립 검증)

```text
VAL_G0_CONSOLIDATION=PASS/FAIL
VAL_CONSTITUTION=PASS/FAIL
VAL_SECRET_SCAN=PASS/FAIL
VAL_GIT_HYGIENE=PASS/FAIL
BLOCKERS_TOP3=...
```

---

# 9) 다음 단계(조건부)

✅ **G0 PASS + Gate-E1 PASS** 이면 → **PDE v1 확장(패턴 60개 목표) 착수**
❌ 그 외에는 → **확장 개발 금지, 정리/복구만 허용**

---

## ✅ 배포 메모 (팀 공지 문구)

> “NEXT-TRADE는 현재 **운영 전환 단계**이며, 로드맵(1→3→2)을 유지한다.
> 단, **G0(Consolidation Gate) 통과 전에는 PDE/Regime/Backtest 확장 개발을 금지**한다.
> 오늘의 목표는 **Secrets 제거 + 커밋 완결 + upstream 통일 + 프로세스 표준화 + Gate-E1 증거 확보**다.”

---

원하시면 위 지시서를 **파일로 저장하는 PowerShell 5줄 템플릿**까지 바로 붙여드릴게요. (경로는 `C:\projects\NEXT-TRADE\docs\NEXT-TRADE-INSTRUCTION-G0-CONSOLIDATION-008.md`로 고정)
