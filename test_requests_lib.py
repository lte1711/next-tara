"""
Test Binance testnet connectivity using requests library (sync)
Bypass aiohttp DNS resolver issues
"""
import requests
import time

BASE_URL = "https://testnet.binancefuture.com"

print("\n" + "="*70)
print("REQUESTS LIBRARY TEST (SYNC HTTP)")
print("="*70)

# Test 1: Standard HTTPS request
print("\n[Test 1] Standard HTTPS request")
print(f"[Test 1] URL: {BASE_URL}/fapi/v1/ping")

try:
    response = requests.get(f"{BASE_URL}/fapi/v1/ping", timeout=10)
    print(f"✅ Connection SUCCESS")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"❌ Connection FAILED")
    print(f"  Error: {e}")
    print(f"  Error type: {type(e).__name__}")

# Test 2: Direct IP with Host header
print("\n" + "="*70)
print("DIRECT IP TEST (with Host header)")
print("="*70)

print("\n[Test 2] Direct IP: 18.67.51.87")
print("[Test 2] URL: https://18.67.51.87/fapi/v1/ping")

try:
    headers = {"Host": "testnet.binancefuture.com"}
    response = requests.get(
        "https://18.67.51.87/fapi/v1/ping",
        headers=headers,
        timeout=10,
        verify=False  # Disable SSL verification for direct IP
    )
    print(f"✅ Direct IP SUCCESS")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"❌ Direct IP FAILED")
    print(f"  Error: {e}")
    print(f"  Error type: {type(e).__name__}")

print("\n" + "="*70)
print("FINAL DIAGNOSIS")
print("="*70)

print("""
If requests works but aiohttp doesn't:
→ Solution: Replace aiohttp with requests in execution_binance_testnet.py

If both fail:
→ Problem: Network/firewall/proxy blocking Binance testnet
""")
