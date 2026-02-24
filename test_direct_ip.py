#!/usr/bin/env python3
"""
Direct IP Connection Test (DNS Bypass)

Uses resolved IP address directly to bypass DNS issues.
"""
import asyncio
import socket
import aiohttp


async def test_direct_ip():
    """Test connection using IP address directly"""
    print("\n" + "="*70)
    print("DIRECT IP CONNECTION TEST (DNS BYPASS)")
    print("="*70)

    # Use resolved IP from previous test
    ip = "18.67.51.87"
    host = "testnet.binancefuture.com"
    url = f"https://{ip}/fapi/v1/ping"

    print(f"\n[Test] Target: {host}")
    print(f"[Test] Using IP: {ip}")
    print(f"[Test] URL: {url}")

    try:
        connector = aiohttp.TCPConnector(
            family=socket.AF_INET,
            ssl=False  # Skip SSL for test
        )

        headers = {
            "Host": host,  # Important: Host header for virtual hosting
        }

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                result = await resp.json()

                print(f"\n✅ Connection SUCCESS with direct IP!")
                print(f"  Status: {resp.status}")
                print(f"  Response: {result}")
                print(f"\n[Result] DNS bypass works - issue confirmed as DNS resolver ✅")
                return True

    except Exception as e:
        print(f"\n❌ Connection FAILED")
        print(f"  Error: {e}")
        print(f"  Error type: {type(e).__name__}")

        # Check if it's SSL issue
        if "SSL" in str(e) or "CERTIFICATE" in str(e):
            print(f"\n[Diagnosis] SSL verification issue (expected without proper SSL)")

        return False


async def test_with_ssl_disabled():
    """Test with SSL completely disabled using TCPConnector"""
    print("\n" + "="*70)
    print("HTTP (non-HTTPS) TEST")
    print("="*70)

    ip = "18.67.51.87"
    host = "testnet.binancefuture.com"
    url = f"http://{ip}/fapi/v1/ping"

    print(f"\n[Test] Using HTTP (not HTTPS)")
    print(f"[Test] URL: {url}")

    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        headers = {"Host": host}

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                result = await resp.json()

                print(f"\n✅ HTTP connection SUCCESS!")
                print(f"  Response: {result}")
                return True

    except Exception as e:
        print(f"\n❌ HTTP connection failed: {e}")
        return False


if __name__ == "__main__":
    print("\n[Strategy] Bypass DNS by using direct IP address")

    # Test 1: Direct IP with HTTPS
    success1 = asyncio.run(test_direct_ip())

    # Test 2: Direct IP with HTTP (if HTTPS fails)
    if not success1:
        success2 = asyncio.run(test_with_ssl_disabled())

    print("\n" + "="*70)
    print("DIAGNOSIS SUMMARY")
    print("="*70)
    print("\nIf direct IP works: DNS resolver is the issue")
    print("Solution: Use IP address mapping or custom DNS resolver")
