import time
import json
import requests
from pathlib import Path

OUT = Path(r"C:\projects\NEXT-TRADE\evidence\final\phase-b")
OUT.mkdir(parents=True, exist_ok=True)

url = "https://testnet.binancefuture.com/fapi/v1/premiumIndex"
params = {"symbol": "BTCUSDT"}

rows = []
start = time.time()
for i in range(300):  # 5분, 1초 간격
    t = time.time()
    r = requests.get(url, params=params, timeout=5)
    r.raise_for_status()
    j = r.json()
    rows.append({
        "i": i+1,
        "ts": t,
        "symbol": j.get("symbol"),
        "markPrice": j.get("markPrice"),
    })
    print(f"[{i+1:03d}] markPrice={j.get('markPrice')} ts={t}")
    time.sleep(1)

(Path(OUT / "markprice_log.json")).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
(Path(OUT / "markprice_log.txt")).write_text("\n".join([f"{x['i']}\t{x['ts']}\t{x['markPrice']}" for x in rows]), encoding="utf-8")

print("DONE. saved:", OUT)
print("elapsed_sec:", round(time.time()-start, 2))
