# S8 Dashboard Contract v1

문서번호: NEXT-TRADE-S8-CONTRACT-001
상태: Locked v1.1 (Phase B)
포트 고정: UI=3001, API+WS=8100

## Overview

S8의 목적은 UI/엔진 간 관찰·제어·이력 인터페이스를 단일 계약으로 통일하는 것이다.
UI는 Contract Client(`src/lib/api.ts`)만 경유하며, 레거시 경로는 병행 운영 후 폐기한다.

- Contract Version: `v1`
- Base URL: `http://127.0.0.1:8100`
- REST Prefix: `/api/v1`
- WS Endpoint: `/ws/events`

## REST Endpoints

### GET /api/v1/ops/health

런타임 상태 요약(헬스) 조회.

```json
{
  "contract_version": "v1",
  "ts": "2026-02-26T02:00:00+00:00",
  "status": "OK",
  "data": {
    "engine_pid": 12345,
    "engine_alive": true,
    "engine_cmdline_hint": "python -m next_trade.runtime",
    "checkpoint_age_sec": 2.4,
    "checkpoint_status": "FRESH",
    "last_health_ok": "2026-02-26T01:59:59+00:00",
    "restart_count": 0,
    "flap_detected": false,
    "task_state": "Running"
  }
}
```

### GET /api/v1/ops/state

대시보드가 사용하는 통합 상태(엔진 + kill + counters + freshness).

```json
{
  "contract_version": "v1",
  "ts": "2026-02-26T02:00:00+00:00",
  "engine": {
    "pid": 12345,
    "alive": true,
    "cmdline_hint": "python -m next_trade.runtime",
    "task_state": "Running",
    "health_status": "OK"
  },
  "kill": {
    "is_on": false,
    "reason": "Running"
  },
  "counters": {
    "published": 0,
    "consumed": 1,
    "pending_total": 0,
    "restart_count": 0
  },
  "freshness": {
    "checkpoint_age_sec": 2.4,
    "checkpoint_status": "FRESH",
    "is_stale": false,
    "last_health_ok": "2026-02-26T01:59:59+00:00",
    "flap_detected": false
  }
}
```

### GET /api/v1/ops/positions

현재 포지션 스냅샷 조회.

```json
{
  "contract_version": "v1",
  "ts": 1772061600,
  "positions": []
}
```

### GET /api/v1/ops/risks?limit=20

최근 리스크/운영 이벤트 조회.

```json
{
  "contract_version": "v1",
  "count": 2,
  "items": [
    {
      "timestamp": 1772061600123,
      "event_id": "trace-1-0",
      "event_type": "RISK_TRIGGERED",
      "severity": "WARN",
      "reason": "limit_guard",
      "trace_id": "trace-1",
      "data": {}
    }
  ]
}
```

### POST /api/v1/dev/emit-event

개발/검증 이벤트를 저장하고 WS로 브로드캐스트.

요청:

```json
{
  "event_type": "RISK_TRIGGERED",
  "trace_id": "dev-1",
  "severity": "INFO",
  "index": 1,
  "total": 10000,
  "metadata": {}
}
```

응답:

```json
{
  "ok": true,
  "contract_version": "v1",
  "emitted": "RISK_TRIGGERED",
  "trace_id": "dev-1",
  "ts": 1772061600123
}
```

### GET /api/v1/trading/orders?limit=20

최근 주문 내역 조회.

```json
{
  "items": [
    {
      "order_id": "ORD-12345",
      "symbol": "BTCUSDT",
      "side": "BUY",
      "type": "LIMIT",
      "status": "FILLED",
      "price": 52000.5,
      "qty": 0.01,
      "ts": 1708970000
    }
  ],
  "count": 1,
  "server_ts": "2026-02-26T02:00:00+00:00",
  "contract_version": "v1"
}
```

### GET /api/v1/trading/fills?limit=20

최근 체결 내역 조회.

```json
{
  "items": [
    {
      "trade_id": "TRD-67890",
      "order_id": "ORD-12345",
      "symbol": "BTCUSDT",
      "side": "BUY",
      "price": 52000.5,
      "qty": 0.01,
      "fee": 0.05,
      "ts": 1708970005
    }
  ],
  "count": 1,
  "server_ts": "2026-02-26T02:00:00+00:00",
  "contract_version": "v1"
}
```

### GET /api/v1/ledger/pnl

PnL/자산 상태 조회.

```json
{
  "realized_pnl": 150.25,
  "unrealized_pnl": -12.4,
  "equity": 10137.85,
  "peak_equity": 10200.0,
  "worst_dd": -0.62,
  "equity_curve": [
    { "ts": 1708960000, "equity": 10000.0 },
    { "ts": 1708970000, "equity": 10137.85 }
  ],
  "server_ts": "2026-02-26T02:00:00+00:00",
  "contract_version": "v1"
}
```

## WS Events

### WS URL

- `ws://127.0.0.1:8100/ws/events`

### Envelope (v1)

모든 이벤트는 아래 envelope를 따른다.

```json
{
  "type": "RISK_TRIGGERED",
  "event_type": "RISK_TRIGGERED",
  "ts": 1772061600123,
  "trace_id": "trace-1",
  "severity": "WARN",
  "data": {
    "source": "runtime"
  },
  "contract_version": "v1"
}
```

필드 규칙:

- `type`: 이벤트 타입(필수, string)
- `event_type`: 하위 호환용 별칭(필수, string)
- `ts`: epoch milliseconds(필수, integer)
- `trace_id`: 트레이스 식별자(optional)
- `severity`: `INFO|WARN|ERROR|CRITICAL` (기본값 `INFO`)
- `data`: 이벤트 본문(기본값 `{}`)
- `contract_version`: 항상 `v1`

## Error Policy

- 타임아웃: 클라이언트 기본 20초
- 재시도: 읽기 GET은 최대 1회(네트워크 오류/5xx), 쓰기 POST는 무재시도
- 404: Phase B에서는 레거시 fallback 금지 (guard로 차단)
- 5xx: UI는 fail-soft(빈 데이터/경고 표시)

오류 응답 권장 포맷:

```json
{
  "error": "message",
  "code": "CONTRACT_ERROR",
  "contract_version": "v1"
}
```

## Versioning

- `contract_version`은 REST/WS payload에 포함한다.
- 호환 정책:
  - Phase A: `v1` 우선 + 레거시 fallback 허용
  - Phase B: `v1` 강제, 레거시 호출 guard + visibility 카드(v1 trading/ledger)
  - Phase C: 레거시 sunset 이후 제거

## Deprecation Table

| Legacy Route           | Status     | Sunset     | Replacement              |
| ---------------------- | ---------- | ---------- | ------------------------ |
| `/api/state/engine`    | Deprecated | 2026-06-30 | `/api/v1/ops/state`      |
| `/api/state/positions` | Deprecated | 2026-06-30 | `/api/v1/ops/positions`  |
| `/api/history/risks`   | Deprecated | 2026-06-30 | `/api/v1/ops/risks`      |
| `/api/dev/emit-event`  | Deprecated | 2026-06-30 | `/api/v1/dev/emit-event` |
