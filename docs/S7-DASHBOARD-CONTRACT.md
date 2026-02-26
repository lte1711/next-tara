# S7 Dashboard Contract Freeze (SSOT)

- 문서 ID: NEXT-TRADE-DASH-CONST-009
- 버전: v1.0.0 (Frozen)
- 기준일: 2026-02-26
- 상태: Breaking change 금지

## Contract 원칙

UI는 아래 3개 공개 인터페이스만 소비한다.

1. `GET /api/ops/runtime-health`
2. `GET /api/ops/runtime-events?limit=`
3. `WS /ws/events`

엔진 내부 파일/로그/구조를 UI가 직접 파싱하는 행위는 금지한다.

## Capture 근거

- `runtime-health`, `runtime-events` 샘플: `next_trade.api.app`의 실제 엔드포인트 함수 호출 결과(2026-02-26 16:32 KST)
- `ws/events` 샘플: 운영 캡처 로그 `c:\projects\ws_listen_out.log`
- 참고: 본 문서 작성 시점 포트 `8100` HTTP 직접 호출은 연결 실패(서버 재기동은 dennis 전용)

---

## 1) GET /api/ops/runtime-health

### Request

- Method: `GET`
- Query: 없음
- Headers: 없음(현재)

### Response Schema

| Field                 | Type                                           | Required | Notes                      |
| --------------------- | ---------------------------------------------- | -------- | -------------------------- |
| `engine_pid`          | `number \| null`                               | Y        | 엔진 PID                   |
| `engine_alive`        | `boolean`                                      | Y        | PID 생존 여부              |
| `engine_cmdline_hint` | `string \| null`                               | Y        | 프로세스 cmdline 힌트      |
| `checkpoint_age_sec`  | `number \| null`                               | Y        | 체크포인트 경과 초         |
| `checkpoint_status`   | `'FRESH' \| 'STALE' \| 'EXPIRED' \| 'UNKNOWN'` | Y        | 체크포인트 상태            |
| `health_status`       | `'OK' \| 'WARN' \| 'CRITICAL'`                 | Y        | 종합 상태                  |
| `last_health_ok`      | `string \| null`                               | Y        | 마지막 HEALTH_OK timestamp |
| `restart_count`       | `number`                                       | Y        | 최근 재시작 횟수           |
| `flap_detected`       | `boolean`                                      | Y        | 플랩 감지 여부             |
| `task_state`          | `string`                                       | Y        | watchdog task 상태         |
| `timestamp`           | `string`                                       | Y        | 응답 생성 시각             |

### Example (실측 스냅샷)

```json
{
  "engine_pid": 908,
  "engine_alive": true,
  "engine_cmdline_hint": "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -u -m next_trade.runtime",
  "checkpoint_age_sec": 2.1,
  "checkpoint_status": "FRESH",
  "health_status": "OK",
  "last_health_ok": "2026-02-26T07:32:37.184589+00:00",
  "restart_count": 0,
  "flap_detected": false,
  "task_state": "UNKNOWN",
  "timestamp": "2026-02-26T16:32:46.946776"
}
```

---

## 2) GET /api/ops/runtime-events?limit=

### Request

- Method: `GET`
- Query:
  - `limit`: `number` (optional, default `50`, range `1..500`)
- Headers: 없음(현재)

### Response Schema

Top-level:

| Field    | Type             | Required | Notes              |
| -------- | ---------------- | -------- | ------------------ |
| `events` | `RuntimeEvent[]` | Y        | 최신순 이벤트 목록 |
| `count`  | `number`         | Y        | 반환된 이벤트 수   |

RuntimeEvent:

| Field     | Type                                        | Required | Notes       |
| --------- | ------------------------------------------- | -------- | ----------- |
| `ts`      | `string`                                    | Y        | 이벤트 시각 |
| `level`   | `'INFO' \| 'WARN' \| 'ERROR' \| 'CRITICAL'` | Y        | 심각도      |
| `action`  | `string`                                    | Y        | 이벤트 액션 |
| `pid`     | `number`                                    | N        | 관련 PID    |
| `old_pid` | `number \| null`                            | N        | 이전 PID    |
| `new_pid` | `number \| null`                            | N        | 신규 PID    |

### Example (실측 스냅샷)

```json
{
  "events": [
    {
      "ts": "2026-02-26T07:32:37.184589+00:00",
      "level": "INFO",
      "action": "HEALTH_OK",
      "pid": 908
    },
    {
      "ts": "2026-02-26T07:32:06.964902+00:00",
      "level": "INFO",
      "action": "HEALTH_OK",
      "pid": 908
    },
    {
      "ts": "2026-02-26T07:31:36.778011+00:00",
      "level": "INFO",
      "action": "HEALTH_OK",
      "pid": 908
    }
  ],
  "count": 3
}
```

---

## 3) WS /ws/events

### Request

- Protocol: `ws://` or `wss://`
- Path: `/ws/events`
- Query/Header: 계약상 필수 없음(현재)

### Message Schema

서버 메시지는 아래 2가지 형태를 허용한다.

#### A. 도메인 이벤트

| Field        | Type     | Required | Notes          |
| ------------ | -------- | -------- | -------------- |
| `event_type` | `string` | Y        | 이벤트 타입    |
| `ts`         | `number` | Y        | epoch ms       |
| `trace_id`   | `string` | N        | 추적 ID        |
| `data`       | `object` | Y        | 이벤트 payload |

#### B. 하트비트 이벤트

| Field      | Type     | Required | Notes              |
| ---------- | -------- | -------- | ------------------ |
| `type`     | `string` | Y        | 예: `ws_heartbeat` |
| `ts`       | `number` | Y        | epoch ms           |
| `severity` | `string` | N        | 예: `info`         |
| `msg`      | `string` | N        | 예: `heartbeat`    |

### Example (실측 캡처)

```json
{
  "event_type": "ROUTE_DECIDED",
  "ts": 1770970741144,
  "trace_id": "route-test-L4-001",
  "data": {
    "trace_id": "route-test-L4-001",
    "risk_level": 4,
    "policy_version": "p10.v1",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "qty": 100.0,
    "price": 50000.0,
    "route": "BINANCE",
    "strategy": "ROUTE_NORMAL",
    "reason": "Low risk — normal routing approved",
    "metadata": {}
  }
}
```

```json
{
  "type": "ws_heartbeat",
  "ts": 1770970749186,
  "severity": "info",
  "msg": "heartbeat"
}
```

---

## Versioning / 변경 규칙

- 본 문서의 필수 필드 제거/이름 변경/타입 변경은 **Breaking Change**로 간주한다.
- Breaking Change는 문서 버전 업(`v2+`) + 소비자(UI) 합의 없이는 금지한다.
- 엔진 내부 변경은 Adapter 레이어에서 흡수하고 본 Contract는 유지한다.
