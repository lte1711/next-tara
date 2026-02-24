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

    Two-Man Rule (절대 규칙):
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
        self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.secret = os.environ.get("BINANCE_TESTNET_SECRET", "")

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

        if not self.api_key or not self.secret:
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
            self.secret.encode(),
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
            "X-MBX-APIKEY": self.api_key,
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
            print(f"[BinanceTestnet.Order] ❌ {msg}")
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
            print(f"[BinanceTestnet.Order] ⚠️  {msg}")
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
                # Prepare order request
                side_binance = "BUY" if req.side == "long" or req.side == "BUY" else "SELL"

                params = {
                    "symbol": req.symbol,
                    "side": side_binance,
                    "quantity": req.qty,
                    "type": req.order_type or "MARKET",
                    "newClientOrderId": client_order_id,
                    "reduceOnly": "true" if req.reduce_only else "false",
                }

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

                    # ✅ Binance duplicate detection (Dennis/백설 지시)
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

                        print(f"[BinanceTestnet.Order] ⚠️  Duplicate detected by exchange: {last_error}")
                        print(f"[BinanceTestnet.Order] ✅ Idempotency confirmed (existing order_id: {existing_order_id})")

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

                        return OrderResult(ok=True, order_id=existing_order_id)

                    # Determine if retryable
                    if code == 429 or code >= 500:
                        # Rate limited or server error - retry
                        if attempt_num < self.max_attempts:
                            delay = self.backoff_delays[attempt_num - 1]
                            print(f"[BinanceTestnet.Order] ⚠️  Error {code}: {last_error}, retrying in {delay}s...")
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

                print(f"[BinanceTestnet.Order] ✅ Order placed: {order_id}")

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

                return OrderResult(ok=True, order_id=order_id)

            except Exception as e:
                last_error = str(e)
                print(f"[BinanceTestnet.Order] ❌ Attempt {attempt_num} failed: {last_error}")

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
