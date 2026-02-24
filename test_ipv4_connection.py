#!/usr/bin/env python3
"""
Quick IPv4 Connection Test to Binance Testnet

Verifies that the IPv4 patch works before running full order test.
"""
import asyncio
import socket
import aiohttp


async def test_ipv4_connection():
    """Test connection to Binance Testnet with IPv4 forced"""
    print("\n" + "="*70)
    print("IPv4 CONNECTION TEST")
    print("="*70)

    url = "https://testnet.binancefuture.com/fapi/v1/ping"

    print(f"\n[Test] Connecting to: {url}")
    print(f"[Test] Using IPv4 (socket.AF_INET) forced")

    try:
        # IPv4 강제 connector
        connector = aiohttp.TCPConnector(
            family=socket.AF_INET,  # IPv4 only
            ssl=False  # Testnet
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                result = await resp.json()

                print(f"\n✅ Connection SUCCESS!")
                print(f"  Status: {resp.status}")
                print(f"  Response: {result}")
                print(f"\n[Result] IPv4 patch is working correctly ✅")
                return True

    except aiohttp.ClientConnectorError as e:
        print(f"\n❌ Connection FAILED")
        print(f"  Error: {e}")
        print(f"\n[Result] IPv4 patch did NOT resolve the issue ❌")
        return False

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_ipv4_connection())

    if success:
        print("\n" + "="*70)
        print("✅ READY FOR S3-005B")
        print("="*70)
        print("\nNext: Dennis should set credentials and run:")
        print("  python run_s3_005_real_order_test.py")
    else:
        print("\n" + "="*70)
        print("❌ IPv4 patch issue - needs further investigation")
        print("="*70)
