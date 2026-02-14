# PHASE 10 — Order Routing Optimizer

**상태**: 🚀 OPEN  
**지시서**: NEXT-TRADE-DIR-P10-001  
**브랜치**: `phase-10-order-routing`  
**대상**: Sprint 1 (라우터 코어 + WS 통합)

---

## 🎯 임무

Risk Engine의 **Risk Level 신호**를 받아,
주문을 **최적 경로로 분기·쪼개·보류**하는 지능형 라우터 구축.

```
Risk Engine (L1-L4)
      ↓
OrderRouter.route_order()
      ↓
[PolicyEvaluator] → Risk → Routing Policy
[OrderSizer] → Size cap 적용
[LatencyProbe] → Exchange latency 캐싱
      ↓
RoutingDecision (routes + metadata)
      ↓
WS Event: ROUTE_DECIDED → AuditTerminal 표시
```

---

## 📦 산출물 (Deliverables)

### Code
- ✅ `/src/next_trade/router/` (6개 모듈)
  - `models.py` — RiskLevel, RoutingPolicy, RoutingDecision
  - `policy.py` — PolicyEvaluator (Risk → Policy)
  - `router.py` — OrderRouter (통합 엔진)
  - `sizer.py` — OrderSizer (Size 계산)
  - `latency_probe.py` — LatencyProbe (지연 측정)
  - `__init__.py` — 공개 API

### Documentation
- ✅ `/docs/phase-10/ARCH.md` — 아키텍처 + 정책 + 통합점
- ⏳ `/docs/phase-10/TESTING.md` — 검증 시나리오 (다음 PR)

### Evidence
- ✅ `/evidence/route-010/INDEX.md` — 증거 체크리스트
- ⏳ 6개 시나리오 스크린샷 (구현 후)

---

## 🏗️ 라우팅 정책 v1.0

| Risk | 동작 | Leverage | Size | 경로 | 특징 |
|------|------|----------|------|------|------|
| **L4** | NORMAL | 4.0× | 100% | 1개 | 정상 |
| **L3** | SPLIT | 2.0× | 75% | 2개 | 슬리피지 최소화 |
| **L2** | DELAYED | 1.0× | 50% | 1개 | 5초 모니터링 |
| **L1** | REJECT_HARD | 0.0× | 0% | - | Hard reject |

---

## 📌 핵심 계약 (Event Contract)

### ROUTE_DECIDED
모든 라우팅 결정 후 **즉시** WS 브로드캐스트

```json
{
  "event_type": "ROUTE_DECIDED",
  "ts": 1707571200000,
  "trace_id": "route-xyz",
  "data": {
    "order_id": "ord-12345",
    "risk_level": "L3",
    "action": "ROUTE_SPLIT",
    "policy_version": "1.0",
    "decision_ms": 2.5,
    "routes": [
      {"exchange": "BINANCE", "size": 60},
      {"exchange": "BYBIT", "size": 40}
    ]
  }
}
```

---

## ✅ 검증 체크 (P10-1 중간 게이트)

### P0 (차단 결함)
- [ ] Risk 변화 시 **라우팅 즉시 재평가**
- [ ] Hard/Soft Reject 구분 로그
- [ ] 10k 이벤트에서도 WS 안정

### P1 (주요 기능)
- [ ] L4-L1 정책 정확성
- [ ] 분할(Split) 경로 정확성 (60/40)
- [ ] Leverage cap 적용
- [ ] LatencyProbe 캐시 (TTL=300sec)

### P2 (파생)
- [ ] OrderSizer 엣지 케이스
- [ ] JSON 직렬화
- [ ] Exception 처리

---

## 🚀 다음 단계

### Sprint 1 (현재)
```
[✅] 모듈 스켈레톤 (policy, router, sizer, latency_probe)
[⏳] WS Events 구현 (routes_ws.py 확장 → ROUTE_* emit)
[⏳] 단위 테스트 (pytest)
```

### Sprint 2
```
[⏳] Risk 통합 테스트 (L4→L1 시뮬)
[⏳] AuditTerminal 표시 확인
[⏳] 증거 캡처 (6개 시나리오)
```

### Sprint 3
```
[⏳] 거래소 API 통합
[⏳] 부하 테스트 (10k/sec)
[⏳] 문서 최종화
```

---

## 📖 참고 자료

- **ARCH.md**: 아키텍처 + 정책 + 통합점
- **PHASE 4** (WS-004): 이벤트 브로드캐스트 패턴
- **Risk Engine**: L1-L4 신호 입력

---

**브랜치**: `phase-10-order-routing`  
**커밋**: 스켈레톤 완성 ✅  
**다음**: WS Events 구현 (Sprint 1)
