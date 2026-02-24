# [총괄 지시서] NEXT-TARA 최초 Git 설정 확정 + 안전 푸시 루틴

문서번호: NEXT-TARA-GIT-BOOT-001
발신: 총괄 백설
수신: 허니(Honey)
효력: 즉시

## 목적

- 로컬 C:\projects\NEXT-TRADE를 GitHub lte1711/next-tara(main)에 정상 연결 상태로 확정한다.
- S4-A 엔진 실행 중에도 안전하게 커밋/푸시 가능한 표준 루틴을 고정한다.

---

## STEP 0 — 전제 확인 (필수)

1. 현재 repo 위치 고정

```powershell
cd C:\projects\NEXT-TRADE
git rev-parse --show-toplevel
git branch --show-current
```

기대: C:/projects/NEXT-TRADE, main

2. 원격(remote) 확인

```powershell
git remote -v
```

---

## STEP 1 — origin을 lte1711/next-tara로 확정

1-A) origin이 없으면 add

```powershell
git remote add origin https://github.com/lte1711/next-tara.git
```

1-B) origin이 있는데 주소가 다르면 set-url

```powershell
git remote set-url origin https://github.com/lte1711/next-tara.git
```

확인:

```powershell
git remote -v
```

---

## STEP 2 — 최초 사용자 정보 설정 (Machine/Repo 단위)

2-A) 글로벌 설정

```powershell
git config --global user.name "lte1711"
git config --global user.email "YOUR_EMAIL@example.com"
git config --global init.defaultBranch main
```

확인:

```powershell
git config --global --list | Select-String "user.name|user.email|init.defaultBranch"
```

email은 GitHub 계정 이메일과 동일 권장

---

## STEP 3 — 인증 방식 고정 (권장: PAT)

3-A) Windows Credential Manager 사용(기본)

- 첫 push 시 Git이 로그인 요구 → GitHub 사용자명 + PAT 입력
- 이후 자동 저장됨

---

## STEP 4 — S4-A 운영 중 안전 커밋 규칙

4-A) 운영 중 금지

- 엔진 프로세스(PID 6820) 강제 종료/재시작 없이 실시간 로직 변경 금지
- runtime 파라미터(run_id, executor, audit writer 등) 변경 커밋을 즉시 적용 금지
  - T+2h 재기동 체크포인트에서만 반영

4-B) 운영 중 허용

- 문서(보고서/지시서) 업데이트
- tools(검증 스크립트) 추가
- evidence 정리(민감정보/키 포함 금지)

---

## STEP 5 — 푸시 전 보안 스캔 (필수)

```powershell
cd C:\projects\NEXT-TRADE
git status --porcelain
git diff --stat
```

절대 커밋 금지 패턴(하나라도 있으면 중지):

- .env
- _secret_, _key_
- var/
- evidence/phase-s3-runtime/\*.jsonl
- venv/

이미 .env.example이 있으니 .env는 로컬 전용 유지

---

## STEP 6 — 표준 커밋/푸시 루틴 (가장 안전)

6-A) 커밋 (예: 문서/지시서만)

```powershell
git add -A
git commit -m "docs(s4): add T+2h hotpatch runbook and checkpoint notes"
```

6-B) 원격 최신화 후 푸시

```powershell
git pull --rebase origin main
git push origin main
```

---

## STEP 7 — 최종 확인(필수 보고)

아래 결과를 3줄로 보고:

1. git remote -v (origin 주소만)
2. git status --porcelain (빈 출력이면 clean)
3. git log -n 1 --oneline (마지막 커밋 1줄)

---

## DoD (완료 조건)

- origin = https://github.com/lte1711/next-tara.git 확정
- user.name / user.email 설정 완료
- 푸시 성공(또는 인증 단계까지 정상 진행)
- .env/키/운영 로그 미포함 확인

---

## 즉시 실행 지시

허니는 STEP 0 → STEP 7 순서로 집행하고, 결과 3줄 보고 제출
