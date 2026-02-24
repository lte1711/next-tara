================================================================
  NEXT-TRADE TESTNET 24H RUN 이전 패키지
  Package ID: RUN_20260221_0529_MIGRATION
  Created: 2026-02-23
================================================================

📦 패키지 구성
================================================================

1. 증거 폴더 (MUST COPY - 우선순위 1)
   ────────────────────────────────────────
   Source:  C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529\
   Target:  NEW_PC\C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529\
   
   Contents:
   ├── logs/
   │   └── trades_20260221.jsonl ............ 144개 거래 기록
   ├── reports/
   │   ├── START_TIME.txt .................. 시작 시간 (2026-02-21 05:29)
   │   └── FINAL_REPORT.txt ................ 최종 결과 (DD_CAP_BREACHED)
   └── screens/ ............................ 매시간 스크린샷 (선택)
   
   Copy Command (PowerShell):
   ──────────────────────────
   $source = "C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529"
   $target = "C:\projects\NEXT-TRADE\evidence\testnet_24h\"
   Copy-Item -Path $source -Destination $target -Recurse -Force

2. 소스 코드 (MUST COPY - 우선순위 2)
   ────────────────────────────────────────
   Source:  C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py
   Target:  NEW_PC\C:\projects\NEXT-TRADE\src\next_trade\execution\
   
   File Size: ~10 KB
   Lines: 245
   Language: Python 3.14
   
   Copy Command:
   ──────────────
   Copy-Item -Path "C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py" `
             -Destination "NEW_PC_PATH:\NEXT-TRADE\src\next_trade\execution\"

3. 문서 (SHOULD COPY - 우선순위 3)
   ────────────────────────────────────────
   Files:
   - MIGRATION_GUIDE_RUN_20260221_0529.md .... 완전 이전 가이드
   - MIGRATION_CHECKLIST.txt ................. 체크리스트
   - THIS FILE (패키징 정보)
   
   Location: C:\projects\NEXT-TRADE\

4. 환경 설정 (MUST RECONFIGURE - 우선순위 4)
   ────────────────────────────────────────
   필수 환경변수 (새 PC에서 재설정):
   - BINANCE_TESTNET_API_KEY
   - BINANCE_TESTNET_API_SECRET
   
   주의: API 키는 파일에 저장하지 말 것 (보안)

================================================================
🚀 빠른 이전 절차 (5분)
================================================================

STEP 1: USB/네트워크에서 증거 폴더 복사
───────────────────────────────────────
cd C:\projects\NEXT-TRADE
Copy-Item -Path "\\SOURCE_PC\evidence\testnet_24h\RUN_20260221_0529" `
          -Destination ".\evidence\testnet_24h\" -Recurse

STEP 2: 소스 코드 복사
──────────────────────
Copy-Item -Path "continuous_testnet_runner.py" `
          -Destination ".\src\next_trade\execution\"

STEP 3: 환경변수 설정
──────────────────────
[System.Environment]::SetEnvironmentVariable("BINANCE_TESTNET_API_KEY", "YOUR_KEY", "User")
[System.Environment]::SetEnvironmentVariable("BINANCE_TESTNET_API_SECRET", "YOUR_SECRET", "User")

STEP 4: 검증
────────────
python -c "
import os
key = os.getenv('BINANCE_TESTNET_API_KEY')
print(f'✅ API Key Set: {key is not None}')
print(f'✅ Evidence Exists: {os.path.exists(\"evidence/testnet_24h/RUN_20260221_0529\")}')
"

STEP 5: 완료
───────────
Get-Content evidence\testnet_24h\RUN_20260221_0529\reports\FINAL_REPORT.txt

================================================================
📊 증거 데이터 통계
================================================================

거래 기록:
  - 파일: logs/trades_20260221.jsonl
  - 라인: 144 (각 거래 1줄)
  - 크기: ~5KB
  
  구조:
  {
    "timestamp": "ISO-8601",
    "trade_number": 1-144,
    "symbol": "BTCUSDT",
    "side": "BUY/SELL",
    "quantity": 0.002,
    "order_id": integer,
    "status": "NEW/FILLED",
    "net_pnl": float
  }

최종 보고서:
  - 파일: reports/FINAL_REPORT.txt
  - 크기: ~1KB
  - 내용: 실행 요약, 거래 통계, 손익, 종료 사유

시간 기록:
  - 파일: reports/START_TIME.txt
  - 내용: 2026-02-21T05:29:00Z

스크린샷 (선택):
  - 폴더: screens/
  - 형식: PNG 이미지
  - 용도: 수동 증거 (매시간 수집)

================================================================
🔐 보안 고려사항
================================================================

이전 전 체크:
  ☐ API 키가 Git 히스토리에 없음 (확인됨)
  ☐ .env 파일이 .gitignore에 포함됨 (안전)
  ☐ 로그 파일에 민감정보 없음 (JSON 형식)
  ☐ 환경변수 사용 (파일 저장 안함)

이전 후 체크:
  ☐ 기존 PC 환경변수 제거
  ☐ 새 PC에서만 API 키 설정
  ☐ 필요시 Binance API 키 재발급
  ☐ 접근 권한 확인

================================================================
🛠️ 설치 요구사항 (새 PC)
================================================================

시스템:
  - OS: Windows 10/11
  - 디스크 공간: 500MB 최소
  - 메모리: 4GB 최소

소프트웨어:
  - Python 3.14.2
  - pip (Python 패키지 관리자)
  - Git (선택)

Python 패키지:
  - aiohttp
  - python-dotenv
  - pydantic
  - (requirements.txt 참고)

네트워크:
  - 인터넷 연결 (Binance Testnet API)
  - Testnet 액세스 (https://demo-fapi.binance.com)

================================================================
✅ 이전 완료 확인 방법
================================================================

1. 파일 존재 확인:
   ──────────────
   Test-Path "C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529\reports\FINAL_REPORT.txt"
   → TRUE 필수

2. 거래 기록 검증:
   ──────────────
   (Get-Content "C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529\logs\trades_20260221.jsonl" | Measure-Object -Line).Lines
   → 144 필수

3. 소스 코드 검증:
   ──────────────
   python -m py_compile "C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py"
   → 에러 없음 필수

4. 환경 확인:
   ──────────
   python -c "import sys; print(f'Python {sys.version}')"
   → 3.14+ 필수

5. 동작 테스트:
   ──────────
   python -c "from next_trade.execution.continuous_testnet_runner import ContinuousTestnetRunner; print('✅')"
   → 에러 없음 필수

================================================================
📋 용량 및 시간 예상
================================================================

이전 용량:
  - 증거 폴더: ~10-50 MB (스크린샷 포함 시 더 큼)
  - 소스 코드: ~1 MB
  - 문서: ~100 KB
  - 총합: ~50-100 MB (USB로 충분)

이전 시간:
  - 로컬 복사: 2-5분
  - USB 이전: 10-15분
  - 환경 설정: 5-10분
  - 검증: 5분
  - 총 소요: 30-45분

================================================================
🔗 참고 자료
================================================================

파일 위치:
  - 증거: C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529\
  - 소스: C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py
  - 문서: C:\projects\NEXT-TRADE\MIGRATION_*

이전 명령:
  PowerShell 전체 스크립트 (한번에 실행):
  
  $evidence = "C:\projects\NEXT-TRADE\evidence\testnet_24h\RUN_20260221_0529"
  $source = "C:\projects\NEXT-TRADE\src\next_trade\execution\continuous_testnet_runner.py"
  $newPC = "D:\Backup\"  # USB/네트워크 경로
  
  Copy-Item -Path $evidence -Destination "$newPC\evidence\" -Recurse
  Copy-Item -Path $source -Destination "$newPC\continuous_testnet_runner.py"
  Write-Host "✅ 이전 완료"

================================================================
최종 상태: ✅ READY TO MIGRATE
생성일: 2026년 2월 23일
버전: 1.0
================================================================
