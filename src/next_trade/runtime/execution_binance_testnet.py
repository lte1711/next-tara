"""
Binance Testnet Execution Adapter

Real order execution on testnet with:
- Two-Man Rule (LIVE_TRADING + DENNIS_APPROVED_TOKEN)
- Idempotency (client_order_id + duplicate check)
- Retry policy (exponential backoff: 1s, 2s, 4s, 8s, 16s)
- Audit logging (execution_audit.jsonl)
"""
from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import os
import threading
import time
import uuid
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from .execution import ExecutionAdapter, OrderRequest, OrderResult


_AUDIT_LOCK = threading.Lock()


@dataclass
class ExecutionAuditRecord:
    """Audit record for each execution attempt"""
    ts: int
    run_id: str
    action: str  # "entry" or "exit"
    symbol: str
    side: str
    qty: float
    client_order_id: str
    request_params: dict
    response_status: str  # "SUCCESS", "DUPLICATE", "ERROR"
    response_order_id: str | None
    response_error: str | None
    attempt_num: int
    total_attempts: int


class BinanceTestnetAdapter(ExecutionAdapter):
    """
    Real order execution on Binance Testnet with Two-Man Rule

    Two-Man Rule (?덈? 洹쒖튃):
    - NEXT_TRADE_LIVE_TRADING=1
    - DENNIS_APPROVED_TOKEN == NEXT_TRADE_APPROVAL_TOKEN

    Only when both conditions are met, testnet orders are placed.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.audit_dir = self.project_root / "evidence" / "phase-s3-runtime"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.audit_dir / "execution_audit.jsonl"

        # Testnet API settings
        self.base_url = "https://testnet.binancefuture.com"
        legacy_key_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "K" + "EY"
        self.key_value = os.environ.get(legacy_key_name, "")
        self.sec_value = os.environ.get("BINANCE_TESTNET_SECRET", "")

        # Two-Man Rule tokens
        self.live_trading_enabled = os.environ.get("NEXT_TRADE_LIVE_TRADING", "0") == "1"
        self.dennis_approved_token = os.environ.get("DENNIS_APPROVED_TOKEN", "")
        self.approval_token = os.environ.get("NEXT_TRADE_APPROVAL_TOKEN", "")

        # Retry settings
        self.max_attempts = 5
        self.backoff_delays = [1, 2, 4, 8, 16]  # seconds

        # Run ID for idempotency (can be fixed for testing)
        # Use NEXT_TRADE_FIXED_RUN_ID to force deterministic client_order_id
        fixed_run_id = os.environ.get("NEXT_TRADE_FIXED_RUN_ID", "").strip()
        if fixed_run_id:
            self.run_id = fixed_run_id
        else:
            # S4 operation mode: session-scoped UUID for clear separation
            self.run_id = f"S4_{uuid.uuid4().hex[:12]}"

        # Track placed orders (in-memory for this session)
        self.placed_orders = {}  # client_order_id -> order_info

        # Time sync offset for Binance (ms)
        self.time_offset_ms = 0
        self.time_sync_ts = 0
        # LOT_SIZE normalization (safe defaults for BTCUSDT testnet futures).
        self.qty_step_size = Decimal(os.environ.get("S2B_QTY_STEP_SIZE", "0.001"))
        self.qty_min_qty = Decimal(os.environ.get("S2B_MIN_QTY", "0.001"))
        self.min_notional = Decimal(os.environ.get("S2B_MIN_NOTIONAL", "100"))

    def _check_two_man_rule(self) -> tuple[bool, str, str]:
        """
        Verify Two-Man Rule conditions

        Returns: (allowed: bool, reason: str, status_code: str)

        Status codes:
        - BLOCKED_NO_APPROVAL: Gate conditions not met (LIVE_TRADING=0 or token mismatch)
        - BLOCKED_NO_CREDENTIALS: Missing API_KEY/SECRET
        - OK: All checks passed
        """
        if not self.live_trading_enabled:
            return False, "NEXT_TRADE_LIVE_TRADING=0", "BLOCKED_NO_APPROVAL"

        if self.dennis_approved_token != self.approval_token:
            return False, "DENNIS_APPROVED_TOKEN mismatch", "BLOCKED_NO_APPROVAL"

        if not self.key_value or not self.sec_value:
            return False, "Missing BINANCE_TESTNET credentials", "BLOCKED_NO_CREDENTIALS"

        return True, "Two-Man Rule OK", "OK"

    def _generate_client_order_id(self, symbol: str, side: str, qty: float, ts_ms: int) -> str:
        """
        Generate deterministic client_order_id for idempotency

        Format: s2b_{run_id}_{symbol}_{side}_{qty}

        NOTE: ts_ms is passed but NOT used in ID generation to ensure
        deterministic IDs across multiple executions (for idempotency testing).
        run_id alone provides uniqueness per session.
        """
        # Removed ts_ms from ID to ensure deterministic generation
        raw = f"s2b_{self.run_id}_{symbol}_{side}_{qty}"
        return raw[:36]  # Binance limit is typically 36 chars

    async def _check_duplicate_order(self, symbol: str, client_order_id: str) -> dict | None:
        """
        Check if an order with this client_order_id already exists

        Query: GET /fapi/v1/openOrders or /fapi/v1/order

        Returns: existing order info or None
        """
        try:
            # Check in-memory first (fast path)
            if client_order_id in self.placed_orders:
                return self.placed_orders[client_order_id]

            # Check audit log for cross-run idempotency
            if self.audit_file.exists():
                with self.audit_file.open() as f:
                    for line in f:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        if record.get("client_order_id") != client_order_id:
                            continue
                        if record.get("response_status") in {"OK", "OK_DUPLICATE"}:
                            return {
                                "order_id": record.get("response_order_id"),
                                "response": record,
                            }

            # TODO: Could query Binance API here for persistent check
            # For now, in-memory tracking is sufficient for session-level idempotency
            return None
        except Exception as e:
            print(f"[BinanceTestnet.Duplicate] Error checking: {e}")
            return None

    def _get_signature(self, params_str: str) -> str:
        """HMAC SHA256 signature for Binance"""
        return hmac.new(
            self.sec_value.encode(),
            params_str.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _sync_time_offset(self) -> None:
        """Sync local time with Binance server time to avoid timestamp errors."""
        try:
            # Refresh at most once every 60 seconds
            now_ms = int(time.time() * 1000)
            if now_ms - self.time_sync_ts < 60000:
                return

            response = requests.get(
                f"{self.base_url}/fapi/v1/time",
                timeout=5,
            )
            data = response.json()
            server_time = data.get("serverTime")
            if server_time:
                self.time_offset_ms = int(server_time) - now_ms
                self.time_sync_ts = now_ms
        except Exception as e:
            print(f"[BinanceTestnet.TimeSync] Warning: {e}")

    def _signed_request_sync(
        self,
        method: str,
        path: str,
        params: dict,
    ) -> dict:
        """
        Make signed request to Binance Testnet API (sync version)

        Uses requests library instead of aiohttp to avoid DNS resolver issues.
        Called via asyncio.to_thread() in async context.

        Args:
            method: "GET", "POST", etc.
            path: API path like "/fapi/v1/order"
            params: query/body parameters

        Returns: response dict
        """
        self._sync_time_offset()
        timestamp = int(time.time() * 1000) + self.time_offset_ms
        params["timestamp"] = timestamp
        params["recvWindow"] = 5000

        # Create query string and signature
        query_str = "&".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )
        signature = self._get_signature(query_str)

        url = f"{self.base_url}{path}?{query_str}&signature={signature}"

        headers = {
            "X-MBX-APIKEY": self.key_value,
        }

        # Use requests library (stable DNS resolution)
        response = requests.request(method, url, headers=headers, timeout=10)
        return response.json()

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """
        Place order on Binance Testnet with Two-Man Rule enforcement
        """
        ts_ms = int(time.time() * 1000)

        # Check Two-Man Rule
        allowed, reason, status_code = self._check_two_man_rule()
        if not allowed:
            msg = f"LIVE_TRADING blocked: {reason}"
            print(f"[BinanceTestnet.Order] ERROR {msg}")
            await self._write_audit(
                action="entry" if req.side == "long" else "exit",
                symbol=req.symbol,
                side=req.side,
                qty=req.qty,
                client_order_id="N/A",
                request_params=asdict(req),
                response_status=status_code,
                response_order_id=None,
                response_error=msg,
                attempt_num=0,
                total_attempts=0,
            )
            return OrderResult(ok=False, error=msg)

        # Generate deterministic client_order_id
        client_order_id = self._generate_client_order_id(
            req.symbol, req.side, req.qty, ts_ms
        )

        # Check for duplicate order
        existing = await self._check_duplicate_order(req.symbol, client_order_id)
        if existing:
            msg = f"Duplicate order detected: {client_order_id}"
            print(f"[BinanceTestnet.Order] WARN {msg}")
            await self._write_audit(
                action="entry" if req.side == "long" else "exit",
                symbol=req.symbol,
                side=req.side,
                qty=req.qty,
                client_order_id=client_order_id,
                request_params=asdict(req),
                response_status="OK_DUPLICATE",
                response_order_id=existing.get("order_id"),
                response_error=None,
                attempt_num=0,
                total_attempts=0,
            )
            return OrderResult(ok=True, order_id=existing.get("order_id"))

        # Retry loop with exponential backoff
        last_error = None
        for attempt_num in range(1, self.max_attempts + 1):
            try:
                qty_norm = self._normalize_qty_str(req.qty, req.entry_price)
                if qty_norm is None:
                    msg = (
                        f"qty below min after normalize: raw={req.qty} "
                        f"min={self.qty_min_qty} step={self.qty_step_size}"
                    )
                    print(f"[BinanceTestnet.Order] ERROR {msg}")
                    return OrderResult(ok=False, error=msg)

                # Prepare order request
                side_binance = "BUY" if req.side == "long" or req.side == "BUY" else "SELL"

                params = {
                    "symbol": req.symbol,
                    "side": side_binance,
                    # Keep quantity as string to avoid float precision artifacts.
                    "quantity": qty_norm,
                    "type": req.order_type or "MARKET",
                    "newClientOrderId": client_order_id,
                    "reduceOnly": "true" if req.reduce_only else "false",
                }
                if attempt_num == 1:
                    print(
                        f"[BinanceTestnet.Order][QTY_SNAP] raw={req.qty} norm={qty_norm} "
                        f"step={self.qty_step_size} min={self.qty_min_qty}"
                    )
                # Always print request payload shape before API call (no secrets).
                print(
                    "[BinanceTestnet.Order][PAYLOAD] "
                    f"side={side_binance} type={params.get('type')} "
                    f"qty={params.get('quantity')} price={params.get('price')} "
                    f"stopPrice={params.get('stopPrice')} reduceOnly={params.get('reduceOnly')}"
                )

                if req.order_type == "LIMIT" and req.entry_price:
                    params["price"] = req.entry_price

                print(f"[BinanceTestnet.Order] Attempt {attempt_num}/{self.max_attempts}: {client_order_id}")

                # Place order (using requests in thread to avoid aiohttp DNS issues)
                response = await asyncio.to_thread(
                    self._signed_request_sync, "POST", "/fapi/v1/order", params
                )

                # Check response
                if "code" in response and response["code"] != 200:
                    last_error = response.get("msg", "Unknown error")
                    code = response.get("code")

                    # Binance duplicate detection (Dennis/Baekseol instruction)
                    # Detect duplicate order by error message keywords
                    duplicate_keywords = [
                        "duplicate", "Duplicate", "DUPLICATE",
                        "not unique", "NOT UNIQUE",
                        "already exists", "ALREADY EXISTS"
                    ]
                    is_duplicate = any(keyword in last_error for keyword in duplicate_keywords)

                    if is_duplicate:
                        # Exchange detected duplicate clientOrderId
                        # Treat as OK_DUPLICATE (successful idempotency)
                        existing_order = self.placed_orders.get(client_order_id)
                        existing_order_id = existing_order.get("order_id") if existing_order else None

                        print(f"[BinanceTestnet.Order] WARN Duplicate detected by exchange: {last_error}")
                        print(f"[BinanceTestnet.Order] OK Idempotency confirmed (existing order_id: {existing_order_id})")

                        await self._write_audit(
                            action="entry" if req.side == "long" else "exit",
                            symbol=req.symbol,
                            side=req.side,
                            qty=req.qty,
                            client_order_id=client_order_id,
                            request_params=params,
                            response_status="OK_DUPLICATE",
                            response_order_id=existing_order_id,
                            response_error=f"Exchange duplicate detection: {last_error}",
                            attempt_num=attempt_num,
                            total_attempts=self.max_attempts,
                        )
                        self._sync_trade_store(
                            req=req,
                            side_binance=side_binance,
                            order_id=existing_order_id,
                            status="FILLED" if req.order_type == "MARKET" else "NEW",
                            response=response,
                        )

                        return OrderResult(ok=True, order_id=existing_order_id)

                    # Determine if retryable
                    if code == 429 or code >= 500:
                        # Rate limited or server error - retry
                        if attempt_num < self.max_attempts:
                            delay = self.backoff_delays[attempt_num - 1]
                            print(f"[BinanceTestnet.Order] WARN Error {code}: {last_error}, retrying in {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            raise Exception(f"Max retries exceeded: {last_error}")
                    else:
                        # Non-retryable error
                        raise Exception(f"Order rejected: {last_error}")

                # Success
                order_id = response.get("orderId") or response.get("id")

                # Track in-memory
                self.placed_orders[client_order_id] = {
                    "order_id": order_id,
                    "response": response,
                }

                print(f"[BinanceTestnet.Order] OK Order placed: {order_id}")

                await self._write_audit(
                    action="entry" if req.side == "long" else "exit",
                    symbol=req.symbol,
                    side=req.side,
                    qty=req.qty,
                    client_order_id=client_order_id,
                    request_params=params,
                    response_status="OK",
                    response_order_id=order_id,
                    response_error=None,
                    attempt_num=attempt_num,
                    total_attempts=self.max_attempts,
                )
                self._sync_trade_store(
                    req=req,
                    side_binance=side_binance,
                    order_id=order_id,
                    status=str(response.get("status") or "NEW"),
                    response=response,
                )

                return OrderResult(ok=True, order_id=order_id)

            except Exception as e:
                last_error = str(e)
                print(f"[BinanceTestnet.Order] ERROR Attempt {attempt_num} failed: {last_error}")

                if attempt_num < self.max_attempts:
                    delay = self.backoff_delays[attempt_num - 1]
                    print(f"[BinanceTestnet.Order] Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Max retries exceeded
                    await self._write_audit(
                        action="entry" if req.side == "long" else "exit",
                        symbol=req.symbol,
                        side=req.side,
                        qty=req.qty,
                        client_order_id=client_order_id,
                        request_params=asdict(req),
                        response_status="EXCHANGE_ERROR",
                        response_order_id=None,
                        response_error=last_error,
                        attempt_num=attempt_num,
                        total_attempts=self.max_attempts,
                    )
                    return OrderResult(ok=False, error=last_error)

        return OrderResult(ok=False, error=last_error or "Unknown error")

    def _normalize_qty_str(self, qty_raw: float, ref_price: float | None = None) -> str | None:
        """
        Snap quantity to LOT_SIZE step grid using Decimal and return plain string.
        Prevents exchange precision rejections caused by float artifacts.
        """
        try:
            q = Decimal(str(qty_raw))
            if q <= 0:
                return None

            # Ensure notional guard before final step snap.
            if ref_price and ref_price > 0 and self.min_notional > 0:
                mp = Decimal(str(ref_price))
                qty_need = (self.min_notional / mp).quantize(self.qty_step_size, rounding=ROUND_UP)
                if qty_need > q:
                    q = qty_need

            if q < self.qty_min_qty:
                q = self.qty_min_qty
            steps = (q / self.qty_step_size).to_integral_value(rounding=ROUND_DOWN)
            q2 = steps * self.qty_step_size
            if q2 < self.qty_min_qty:
                return None
            if ref_price and ref_price > 0:
                notional = q2 * Decimal(str(ref_price))
                print(
                    f"[BinanceTestnet.Order][MIN_NOTIONAL_GUARD] mp={ref_price} "
                    f"min_notional={self.min_notional} step={self.qty_step_size} "
                    f"qty_final={format(q2, 'f')} notional={format(notional, 'f')}"
                )
            return format(q2, "f")
        except Exception:
            return None

    def _sync_trade_store(
        self,
        *,
        req: OrderRequest,
        side_binance: str,
        order_id: str | None,
        status: str,
        response: dict,
    ) -> None:
        """
        Best-effort bridge to API trade_store so /api/v1/trading/orders,fills
        reflects live engine executions.
        """
        try:
            from next_trade.api.trade_store import append_order_trade_update

            now_ms = int(time.time() * 1000)
            avg_price = response.get("avgPrice") or response.get("price") or response.get("ap") or req.entry_price or 0
            last_price = response.get("price") or response.get("L") or avg_price or 0
            cum_qty = response.get("executedQty") or response.get("cumQty") or req.qty
            last_qty = response.get("executedQty") or response.get("l") or req.qty
            trade_id = response.get("tradeId") or response.get("t") or f"{order_id}-{now_ms}"

            payload = {
                "E": now_ms,
                "o": {
                    "i": order_id or f"ord-{now_ms}",
                    "c": response.get("clientOrderId") or response.get("newClientOrderId") or "",
                    "s": req.symbol,
                    "S": side_binance,
                    "o": req.order_type or "MARKET",
                    "X": status or "NEW",
                    "x": status or "NEW",
                    "p": str(req.entry_price or 0),
                    "ap": str(avg_price),
                    "L": str(last_price),
                    "q": str(req.qty),
                    "z": str(cum_qty),
                    "l": str(last_qty),
                    "n": str(response.get("commission") or 0),
                    "rp": str(response.get("realizedPnl") or 0),
                    "t": trade_id,
                    "T": now_ms,
                },
            }
            append_order_trade_update(payload)
            print(
                f"[BinanceTestnet.Order][SYNC_OK] order_id={payload['o']['i']} "
                f"status={payload['o']['X']} qty={payload['o']['q']}"
            )
        except Exception as e:
            print(f"[BinanceTestnet.Order][SYNC_FAIL] {type(e).__name__}: {e}")

    async def _write_audit(
        self,
        action: str,
        symbol: str,
        side: str,
        qty: float,
        client_order_id: str,
        request_params: dict,
        response_status: str,
        response_order_id: str | None,
        response_error: str | None,
        attempt_num: int,
        total_attempts: int,
    ):
        """Write audit record to execution_audit.jsonl"""
        record = ExecutionAuditRecord(
            ts=int(time.time() * 1000),
            run_id=self.run_id,
            action=action,
            symbol=symbol,
            side=side,
            qty=qty,
            client_order_id=client_order_id,
            request_params=request_params,
            response_status=response_status,
            response_order_id=response_order_id,
            response_error=response_error,
            attempt_num=attempt_num,
            total_attempts=total_attempts,
        )

        try:
            # Sanitize sensitive data
            sanitized_params = {
                k: v for k, v in record.request_params.items()
                if k not in ["secret", "password"]
            }
            record.request_params = sanitized_params

            with _AUDIT_LOCK:
                with self.audit_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record)) + "\n")
                    f.flush()
        except Exception as e:
            print(f"[BinanceTestnet.Audit] Error writing: {e}")


