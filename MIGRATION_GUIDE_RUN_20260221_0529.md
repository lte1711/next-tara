# 🔄 NEXT-TRADE TESTNET 24H 검증 이전 가이드

**마이그레이션 대상**: NEXT-TRADE-TESTNET-24H-EXEC-001 실행 결과  
**실행 ID**: RUN_20260221_0529  
**기간**: 2026-02-21 05:29 ~ 2026-02-23 07:01 (49.53시간)  
**상태**: ✅ 완료 (DD_CAP_BREACHED)

---

## 📋 이전 체크리스트

### 1️⃣ **증거 패키지** (필수)
```
C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529\
├── logs/
│   └── trades_20260221.jsonl          # 144개 거래 기록 ⭐
├── reports/
│   ├── START_TIME.txt                 # 시작 시간
│   └── FINAL_REPORT.txt               # 최종 결과 보고서 ⭐
└── screens/                           # 매시간 스크린샷 (수동 수집)
```

**이전 방법**:
```powershell
# 새 PC에서
Copy-Item -Path "\\OLD_PC\C$\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529" `
          -Destination "C:\projects\NEXT-TRADE\evidence\testnet_24h\" -Recurse
```

---

### 2️⃣ **소스 코드** (필수)
```
C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py
```

**복사 대상**:
```powershell
Copy-Item -Path "C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py" `
          -Destination "NEW_PC:\NEXT-TRADE\src\next_trade\execution\"
```

---

### 3️⃣ **환경 설정** (필수)
**Binance Testnet API 키** (기존 유지):
- `BINANCE_TESTNET_API_KEY`
- `BINANCE_TESTNET_API_SECRET`

설정 위치:
```
Windows 환경변수 → 사용자 환경변수
또는
C:\projects\NEXT-TRADE\.env (Git 무시됨)
```

---

### 4️⃣ **실행 가이드** (참고)

#### 기본 실행
```powershell
cd C:\projects\NEXT-TRADE
$env:PYTHONPATH="C:\projects\NEXT-TRADE\src"
python -m next_trade.execution.continuous_testnet_runner --run-id RUN_$(Get-Date -Format 'yyyyMMdd_HHmm')
```

#### 백그라운드 실행
```powershell
$env:PYTHONPATH="C:\projects\NEXT-TRADE\src"
Start-Process -NoNewWindow -PassThru `
  python -m next_trade.execution.continuous_testnet_runner `
  --run-id RUN_$(Get-Date -Format 'yyyyMMdd_HHmm')
```

#### 로그 모니터링
```powershell
Get-Content evidence\testnet_24h\RUN_yyyyMMdd_HHmm\runner_stdout.log -Wait
```

---

### 5️⃣ **거래 기록 형식** (trades_20260221.jsonl)
```json
{
  "timestamp": "2026-02-21T05:29:00Z",
  "trade_number": 1,
  "symbol": "BTCUSDT",
  "side": "BUY",
  "quantity": 0.002,
  "order_id": 12424299948,
  "status": "NEW/FILLED",
  "net_pnl": -0.1234
}
```

---

## 🔐 보안 주의사항

⚠️ **API 키 재설정 필수**:
1. Binance Testnet 계정 접근
2. API Management → Testnet API Key 확인/재발급
3. 새 PC 환경변수에 설정

⚠️ **Git 저장소 클린**:
- `.env` 파일은 `.gitignore`에 포함됨 (안전)
- 로그 경로도 무시됨

---

## 📊 최종 결과 요약

| 항목 | 값 |
|------|-----|
| **총 거래** | 144건 |
| **승률** | 0.00% (시장가 주문) |
| **초기 잔액** | 4014.0927 USDT |
| **최종 잔액** | 4004.0348 USDT |
| **순손실** | -10.0579 USDT |
| **종료사유** | DD_CAP_BREACHED (-10 USDT) |
| **실행시간** | 49.53시간 |

---

## 🛠️ 새 PC 설정 순서

1. **Python 3.14+ 설치** (기존과 동일 버전 권장)
   ```powershell
   python --version
   ```

2. **venv 생성 및 패키지 설치**
   ```powershell
   cd C:\projects\NEXT-TRADE
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **증거 폴더 복사**
   ```powershell
   # 네트워크 드라이브 또는 USB로 이전
   Copy-Item -Path "\\증거\폴더\경로" -Destination "C:\projects\NEXT-TRADE\evidence\" -Recurse
   ```

4. **환경변수 설정**
   ```powershell
   # Windows 환경변수 편집기 (Win+R → sysdm.cpl)
   # 또는 PowerShell로
   [System.Environment]::SetEnvironmentVariable("BINANCE_TESTNET_API_KEY", "YOUR_KEY", "User")
   [System.Environment]::SetEnvironmentVariable("BINANCE_TESTNET_API_SECRET", "YOUR_SECRET", "User")
   ```

5. **동작 확인**
   ```powershell
   python -c "from next_trade.execution.continuous_testnet_runner import ContinuousTestnetRunner; print('✅ Import OK')"
   ```

---

## 📁 이전 경로 정리

### 보관할 파일
- ✅ `evidence/testnet_24h/RUN_20260221_0529/` - **전체 증거**
- ✅ `src/next_trade/execution/continuous_testnet_runner.py` - **소스**
- ✅ `MIGRATION_GUIDE_RUN_20260221_0529.md` - **이 문서**

### 선택 사항
- 📸 스크린샷 (수동 수집분)
- 📋 로그 파일 (분석용)

### 제외 가능
- ❌ 임시 폴더 (`__pycache__`, `.pytest_cache`)
- ❌ 개발 중 테스트 파일
- ❌ `.git/history` (Git 재설정 가능)

---

## 🚀 새 PC에서 재실행

```powershell
# 1. 환경 설정
cd C:\projects\NEXT-TRADE
$env:PYTHONPATH="C:\projects\NEXT-TRADE\src"

# 2. 새 런 시작
python -m next_trade.execution.continuous_testnet_runner --run-id RUN_$(Get-Date -Format 'yyyyMMdd_HHmm')

# 3. 증거 폴더에서 새 폴더 자동 생성됨
# evidence/testnet_24h/RUN_20260223_0000/
```

---

**완료 일시**: 2026년 2월 23일  
**최종 상태**: ✅ 성공  
**이전 준비**: 완료  

문의: `continuous_testnet_runner.py` 참고 코드 확인 가능
