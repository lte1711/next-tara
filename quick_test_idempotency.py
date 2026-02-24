#!/usr/bin/env python3
"""
Quick test: Verify deterministic client_order_id generation

Tests:
1. FIXED_RUN_ID generates same client_order_id twice
2. Different run_id generates different client_order_id
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("="*70)
print("IDEMPOTENCY TEST: Deterministic client_order_id")
print("="*70)

# Test 1: Fixed run_id
print("\n[Test 1] Fixed run_id (deterministic)")
os.environ["NEXT_TRADE_FIXED_RUN_ID"] = "TEST_RUN_001"

from src.next_trade.runtime.execution_binance_testnet import BinanceTestnetAdapter

adapter1 = BinanceTestnetAdapter(Path(__file__).parent)
client_id_1 = adapter1._generate_client_order_id("BTCUSDT", "BUY", 0.001, 1000000)

adapter2 = BinanceTestnetAdapter(Path(__file__).parent)
client_id_2 = adapter2._generate_client_order_id("BTCUSDT", "BUY", 0.001, 9999999)  # Different ts_ms

print(f"  Adapter 1 client_order_id: {client_id_1}")
print(f"  Adapter 2 client_order_id: {client_id_2}")
print(f"  Match: {'✅ YES' if client_id_1 == client_id_2 else '❌ NO'}")

# Test 2: No fixed run_id (auto-generated)
print("\n[Test 2] Auto run_id (non-deterministic)")
del os.environ["NEXT_TRADE_FIXED_RUN_ID"]

# Force module reload to get new adapters
import importlib
import src.next_trade.runtime.execution_binance_testnet as mod
importlib.reload(mod)

adapter3 = mod.BinanceTestnetAdapter(Path(__file__).parent)
client_id_3 = adapter3._generate_client_order_id("BTCUSDT", "BUY", 0.001, 1000000)

adapter4 = mod.BinanceTestnetAdapter(Path(__file__).parent)
client_id_4 = adapter4._generate_client_order_id("BTCUSDT", "BUY", 0.001, 1000000)

print(f"  Adapter 3 client_order_id: {client_id_3}")
print(f"  Adapter 4 client_order_id: {client_id_4}")
print(f"  Different: {'✅ YES' if client_id_3 != client_id_4 else '❌ NO'}")

# Summary
print("\n" + "="*70)
print("RESULT")
print("="*70)

test1_pass = client_id_1 == client_id_2
test2_pass = client_id_3 != client_id_4

print(f"✓ Test 1 (Fixed run_id = deterministic): {'✅ PASS' if test1_pass else '❌ FAIL'}")
print(f"✓ Test 2 (Auto run_id = unique per adapter): {'✅ PASS' if test2_pass else '❌ FAIL'}")

if test1_pass and test2_pass:
    print("\n✅ ALL TESTS PASS - Idempotency mechanism verified")
else:
    print("\n❌ TESTS FAILED")
    sys.exit(1)
