"""
Continuous 24h Testnet Trading Runner
NEXT-TRADE-TESTNET-24H-EXEC-001

Purpose:
- Execute market orders every 10 minutes for 24 hours (144 total trades)
- Monitor Net PnL and enforce DD cap at -10 USDT (auto-stop)
- Validate real-time WS ORDER_TRADE_UPDATE transmission

Requirements:
- Binance Testnet API credentials (BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_API_SECRET)
- WebSocket server running at ws://127.0.0.1:8100/ws/events
- UI server at http://127.0.0.1:3001/ops

Usage:
    python -m next_trade.execution.continuous_testnet_runner --run-id RUN_20260221_1430
"""

import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from next_trade.execution.binance_testnet_adapter import BinanceTestnetAdapter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SYMBOL = "BTCUSDT"
ORDER_QTY = 0.002
INTERVAL_SECONDS = 600  # 10 minutes
DD_CAP_USDT = -10.0
MAX_TRADES = 144  # 24h with 10min interval

# Evidence paths
EVIDENCE_ROOT = Path("C:/projects/NEXT-TRADE/evidence/testnet_24h")


class ContinuousTestnetRunner:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_path = EVIDENCE_ROOT / run_id
        self.logs_path = self.run_path / "logs"
        self.screens_path = self.run_path / "screens"
        self.reports_path = self.run_path / "reports"
        
        # Initialize adapter
        api_key = os.getenv("BINANCE_TESTNET_API_KEY")
        api_secret = os.getenv("BINANCE_TESTNET_API_SECRET")
        
        if not api_key or not api_secret:
            raise ValueError("Missing BINANCE_TESTNET_API_KEY or BINANCE_TESTNET_API_SECRET env vars")
        
        self.adapter = BinanceTestnetAdapter(
            api_key=api_key,
            api_secret=api_secret,
            base_url="https://demo-fapi.binance.com"
        )
        
        # Stats
        self.start_time: Optional[float] = None
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.initial_balance: Optional[float] = None
        self.current_balance: Optional[float] = None
        self.min_balance: Optional[float] = None
        self.stop_reason: Optional[str] = None
        
    def setup_evidence_folders(self):
        """Create evidence directory structure"""
        self.run_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(exist_ok=True)
        self.screens_path.mkdir(exist_ok=True)
        self.reports_path.mkdir(exist_ok=True)
        logger.info(f"Evidence folders created: {self.run_path}")
        
    def record_start_time(self):
        """Record run start timestamp"""
        self.start_time = time.time()
        start_dt = datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S %z")
        
        start_file = self.reports_path / "START_TIME.txt"
        start_file.write_text(f"{start_dt}\nRun ID: {self.run_id}\n", encoding="utf-8")
        logger.info(f"Run started at: {start_dt}")
        
    def get_account_balance(self) -> dict:
        """Fetch current account balance and PnL"""
        try:
            account = self.adapter.get_account_info()
            balance = float(account.get("totalWalletBalance", 0))
            unrealized_pnl = float(account.get("totalUnrealizedProfit", 0))
            
            return {
                "balance": balance,
                "unrealized_pnl": unrealized_pnl,
                "net_pnl": balance - (self.initial_balance or balance)
            }
        except Exception as e:
            logger.error(f"Failed to fetch account balance: {e}")
            return {"balance": 0, "unrealized_pnl": 0, "net_pnl": 0}
    
    def check_dd_cap(self, net_pnl: float) -> bool:
        """Check if DD cap is breached"""
        if net_pnl <= DD_CAP_USDT:
            self.stop_reason = f"DD_CAP_BREACHED: Net PnL={net_pnl:.4f} USDT <= {DD_CAP_USDT} USDT"
            logger.warning(self.stop_reason)
            return True
        return False
    
    def execute_order(self) -> dict:
        """Execute a single market order (BUY or SELL alternating)"""
        # Alternate between BUY and SELL
        side = "BUY" if self.total_trades % 2 == 0 else "SELL"
        
        try:
            logger.info(f"Trade #{self.total_trades + 1}: {side} {ORDER_QTY} {SYMBOL}")
            result = self.adapter.place_market_order(SYMBOL, side, ORDER_QTY)
            
            # Log to file
            log_entry = {
                "timestamp": time.time(),
                "trade_num": self.total_trades + 1,
                "side": side,
                "symbol": SYMBOL,
                "qty": ORDER_QTY,
                "order_id": result.get("orderId"),
                "status": result.get("status"),
                "success": True
            }
            
            log_file = self.logs_path / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            self.total_trades += 1
            return result
            
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            log_entry = {
                "timestamp": time.time(),
                "trade_num": self.total_trades + 1,
                "side": side,
                "symbol": SYMBOL,
                "qty": ORDER_QTY,
                "error": str(e),
                "success": False
            }
            
            log_file = self.logs_path / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            return {}
    
    async def run(self):
        """Main 24h continuous trading loop"""
        logger.info(f"Starting 24h continuous testnet runner (Run ID: {self.run_id})")
        
        # Setup
        self.setup_evidence_folders()
        self.record_start_time()
        
        # Get initial balance
        balance_info = self.get_account_balance()
        self.initial_balance = balance_info["balance"]
        self.current_balance = self.initial_balance
        self.min_balance = self.initial_balance
        
        logger.info(f"Initial balance: {self.initial_balance:.4f} USDT")
        
        try:
            while self.total_trades < MAX_TRADES:
                # Execute order
                self.execute_order()
                
                # Update balance
                balance_info = self.get_account_balance()
                self.current_balance = balance_info["balance"]
                net_pnl = balance_info["net_pnl"]
                
                # Track min balance (for max drawdown)
                if self.current_balance < self.min_balance:
                    self.min_balance = self.current_balance
                
                logger.info(
                    f"Balance: {self.current_balance:.4f} USDT | "
                    f"Net PnL: {net_pnl:.4f} USDT | "
                    f"Trades: {self.total_trades}/{MAX_TRADES}"
                )
                
                # Check DD cap
                if self.check_dd_cap(net_pnl):
                    break
                
                # Wait for next interval
                if self.total_trades < MAX_TRADES:
                    logger.info(f"Waiting {INTERVAL_SECONDS}s until next trade...")
                    await asyncio.sleep(INTERVAL_SECONDS)
                    
        except KeyboardInterrupt:
            self.stop_reason = "USER_INTERRUPTED"
            logger.warning("Run interrupted by user")
        except Exception as e:
            self.stop_reason = f"ERROR: {str(e)}"
            logger.error(f"Run failed: {e}", exc_info=True)
        finally:
            self.generate_final_report()
    
    def generate_final_report(self):
        """Generate final 24h report"""
        end_time = time.time()
        duration_hours = (end_time - self.start_time) / 3600 if self.start_time else 0
        
        balance_info = self.get_account_balance()
        final_balance = balance_info["balance"]
        net_pnl = final_balance - self.initial_balance
        max_drawdown = self.min_balance - self.initial_balance
        
        # Calculate win rate (simplified: positive PnL = win)
        # In real scenario, would track per-trade P&L
        win_rate = 0.0  # Placeholder - needs per-trade P&L tracking
        
        report = f"""
[NEXT-TRADE TESTNET 24H REPORT]

1) 기간: {datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M')} ~ {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M')} (KST)
   Duration: {duration_hours:.2f} hours

2) base_url: https://demo-fapi.binance.com
3) symbol/qty: {SYMBOL} / {ORDER_QTY}

4) 결과:
- Total Closed Trades: {self.total_trades}
- Win Rate: {win_rate:.2f}% (not tracked per-trade)
- Initial Balance: {self.initial_balance:.4f} USDT
- Final Balance: {final_balance:.4f} USDT
- Net PnL: {net_pnl:.4f} USDT
- Max Drawdown: {max_drawdown:.4f} USDT

5) WS:
- /ws/events 101 단일 유지: (manual verification required)
- ORDER_TRADE_UPDATE 수신: (manual verification required)

6) 증거 경로:
- {self.run_path}

7) Stop Reason: {self.stop_reason or 'COMPLETED'}
"""
        
        report_file = self.reports_path / "FINAL_REPORT.txt"
        report_file.write_text(report, encoding="utf-8")
        
        logger.info("=" * 60)
        logger.info(report)
        logger.info("=" * 60)
        
        print(report)


async def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="24h Continuous Testnet Runner")
    parser.add_argument(
        "--run-id",
        type=str,
        default=f"RUN_{datetime.now().strftime('%Y%m%d_%H%M')}",
        help="Unique run identifier"
    )
    
    args = parser.parse_args()
    
    runner = ContinuousTestnetRunner(run_id=args.run_id)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
