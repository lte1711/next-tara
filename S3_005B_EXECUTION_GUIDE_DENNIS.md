# S3-005B 실행 절차 (Dennis용)

**목표**: Testnet 실주문 1건 + 멱등성 검증 (OK_DUPLICATE)

---

## ⚠️ 주의사항 (필수 확인)

### 1. **audit 파일 제어**

- 1차 실행: `NEXT_TRADE_CLEAR_AUDIT=1` (초기화)
- 2차 실행: `NEXT_TRADE_CLEAR_AUDIT=0` (보존)

### 2. **client_order_id 재사용 보장**

- `NEXT_TRADE_FIXED_RUN_ID` 설정 (양쪽 실행에서 동일 값 필수)
- symbol/side/qty 동일 유지
- → 같은 client_order_id 생성 → OK_DUPLICATE 검출

---

## 🚀 실행 단계

### STEP 0: 자격증명 확보

Binance Testnet 가입: https://testnet.binancefuture.com

- API Key 발급
- Secret 복사

---

### STEP 1: PowerShell 환경 설정

```powershell
cd C:\projects\NEXT-TRADE

# Testnet 자격증명
$env:BINANCE_TESTNET_API_KEY="<your_testnet_api_key>"
$env:BINANCE_TESTNET_SECRET="<your_testnet_secret>"

# Two-Man Rule (Dennis 발급 토큰)
$env:NEXT_TRADE_LIVE_TRADING="1"
$env:NEXT_TRADE_APPROVAL_TOKEN="DENNIS_S3_005B_PROOF_20260224"
$env:DENNIS_APPROVED_TOKEN=$env:NEXT_TRADE_APPROVAL_TOKEN

# 멱등성 보장: 고정 run_id (양쪽 실행 동일)
$env:NEXT_TRADE_FIXED_RUN_ID="S3_005B_IDEMPOTENCY_PROOF_001"
```

---

### STEP 2: 1차 실행 (실주문 발행)

```powershell
# audit 초기화
$env:NEXT_TRADE_CLEAR_AUDIT="1"

# 실행
python run_s3_005_real_order_test.py 2>&1 | Tee-Object -FilePath "s3_005b_1st_run.txt"
```

**기대 출력**:

```
✅ Order placed successfully
  Order ID: 12345678
  Client Order ID: s2b_S3_005B_IDEMPOTENCY_PROOF_001_BTCUSDT_BUY_0.001
  Status: NEW
```

**증거 1**: `execution_audit.jsonl` 확인

```powershell
Get-Content evidence/phase-s3-runtime/execution_audit.jsonl -Tail 10
```

예상:

```json
{
  "ts": 1771912000000,
  "response_status": "OK",
  "client_order_id": "s2b_S3_005B...",
  "response_order_id": "12345678"
}
```

---

### STEP 3: 2차 실행 (즉시 재실행 - 중복 감지)

**⏱️ 중요**: 1차 실행 직후 **즉시** 실행 (10초 이내)

```powershell
# audit 보존 (중복 감지 위해)
$env:NEXT_TRADE_CLEAR_AUDIT="0"

# 재실행 (같은 run_id, 같은 symbol/side/qty)
python run_s3_005_real_order_test.py 2>&1 | Tee-Object -FilePath "s3_005b_2nd_run.txt"
```

**기대 출력**:

```
⚠️ Duplicate order detected
  Client Order ID: s2b_S3_005B_IDEMPOTENCY_PROOF_001_BTCUSDT_BUY_0.001
  Existing Order ID: 12345678 (reused)
  Status: OK_DUPLICATE
```

**증거 2**: audit 다시 확인

```powershell
Get-Content evidence/phase-s3-runtime/execution_audit.jsonl -Tail 30
```

예상:

```json
{"ts":1771912000000,"response_status":"OK","client_order_id":"s2b_S3_005B...","response_order_id":"12345678"}
{"ts":1771912005000,"response_status":"OK_DUPLICATE","client_order_id":"s2b_S3_005B...","response_order_id":"12345678"}
```

---

### STEP 4: 증거 수집

#### 증거 1: execution_audit.jsonl (전체)

```powershell
Get-Content evidence/phase-s3-runtime/execution_audit.jsonl | Out-File -FilePath "s3_005b_audit_full.txt"
```

#### 증거 2: 콘솔 로그

- `s3_005b_1st_run.txt` (1차 실행 로그)
- `s3_005b_2nd_run.txt` (2차 실행 로그)

#### 증거 3: client_order_id 비교

```powershell
# 1차 실행 client_order_id 추출
Select-String -Path "s3_005b_1st_run.txt" -Pattern "Client Order ID" | Out-File "s3_005b_client_id_comparison.txt"

# 2차 실행 client_order_id 추출
Select-String -Path "s3_005b_2nd_run.txt" -Pattern "Client Order ID" | Out-File "s3_005b_client_id_comparison.txt" -Append
```

#### 증거 4: order_id 비교

```powershell
# 1차/2차 order_id가 동일한지 확인
Select-String -Path "s3_005b_1st_run.txt" -Pattern "Order ID"
Select-String -Path "s3_005b_2nd_run.txt" -Pattern "Order ID"
```

#### 증거 5: Testnet base_url 고정 증거

```powershell
# 코드에서 base_url 확인
Select-String -Path "src/next_trade/runtime/execution_binance_testnet.py" -Pattern "testnet.binancefuture.com"
```

#### 증거 6: Response status 비교

```powershell
# audit에서 response_status 추출
Get-Content evidence/phase-s3-runtime/execution_audit.jsonl | Select-String "response_status"
```

---

## ✅ 성공 조건

### DoD-B 체크리스트

- [ ] 1차 실행: `response_status: OK`
- [ ] 1차 실행: `response_order_id` 존재 (숫자)
- [ ] 2차 실행: `response_status: OK_DUPLICATE`
- [ ] 2차 실행: `response_order_id`는 1차와 동일
- [ ] client_order_id: 1차와 2차가 **완전히 동일**
- [ ] audit 파일: OK → OK_DUPLICATE 순서 확인

---

## 🐛 트러블슈팅

### 문제 1: "Missing BINANCE_TESTNET credentials"

**원인**: API_KEY 또는 SECRET 누락
**해결**: STEP 1 환경변수 재확인

### 문제 2: "Two-Man Rule blocked"

**원인**: LIVE_TRADING=0 또는 Token mismatch
**해결**:

```powershell
$env:NEXT_TRADE_LIVE_TRADING="1"
$env:NEXT_TRADE_APPROVAL_TOKEN="<token>"
$env:DENNIS_APPROVED_TOKEN=$env:NEXT_TRADE_APPROVAL_TOKEN
```

### 문제 3: 2차 실행에서 "새 주문"이 생성됨

**원인**: client_order_id가 달라짐
**진단**:

```powershell
# 1차/2차 client_order_id 비교
Select-String -Path "s3_005b_1st_run.txt" -Pattern "Client Order ID"
Select-String -Path "s3_005b_2nd_run.txt" -Pattern "Client Order ID"
```

**해결**: `NEXT_TRADE_FIXED_RUN_ID`가 양쪽 실행에서 동일한지 확인

### 문제 4: "Network error" (DNS)

**해결**: 이미 requests 라이브러리로 해결됨 (aiohttp 대신)

---

## 📊 예상 타임라인

- STEP 1 (환경 설정): 5분
- STEP 2 (1차 실행): 5초
- STEP 3 (2차 실행): 5초
- STEP 4 (증거 수집): 10분
- **Total**: 약 20분

---

**문서 작성**: 2026-02-24
**작성자**: Honey (AI Assistant)
**검증**: Gemini (AI Co-Pilot)
**승인 대기**: Dennis (총괄)
