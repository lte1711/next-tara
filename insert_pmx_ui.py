path = r"C:\projects\NEXT-TRADE-UI\src\components\PhaseBVisibilityCards.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1) state import에 useRef 확인 (이미 있음) - useEffect, useState, useCallback 있음

# 2) PmxCard 컴포넌트를 PhaseBVisibilityCards 함수 바로 앞에 삽입
pmx_component = '''
type PmxCardProps = {
  summary: Record<string, unknown>;
  events: Record<string, unknown>[];
};

function PmxCard({ summary, events }: PmxCardProps) {
  const pnl = typeof summary.session_realized_pnl === "number" ? summary.session_realized_pnl : 0;
  const posOpen = !!summary.position_open;
  const killed = !!summary.kill;
  return (
    <article className="rounded-lg border border-border-subtle bg-panel p-4 col-span-full">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold text-text-strong">PROFITMAX v1</h3>
        <span className={"inline-flex items-center rounded px-2 py-0.5 text-[11px] font-bold " + (killed ? "bg-red-200 text-red-800" : posOpen ? "bg-green-200 text-green-800" : "bg-blue-100 text-blue-800")}>
          {killed ? "KILL" : posOpen ? "IN POSITION" : "WATCHING"}
        </span>
        <span className={"inline-flex items-center rounded px-2 py-0.5 text-[11px] font-bold " + (pnl >= 0 ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800")}>
          {"PnL: " + (pnl >= 0 ? "+" : "") + pnl.toFixed(4) + " USDT"}
        </span>
      </div>
      <div className="max-h-48 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-panel-2">
            <tr className="text-xs font-semibold text-text-strong">
              <th className="px-2 py-1 text-left">Time</th>
              <th className="px-2 py-1 text-left">Event</th>
              <th className="px-2 py-1 text-left">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {events.map((ev, idx) => {
              const t = String(ev.event_type ?? "");
              const p = (ev.payload as Record<string, unknown>) ?? {};
              const d =
                t === "ENTRY"
                  ? String(p.side) + " " + String(p.qty) + " BTC @ " + String(p.entry_price) + " | " + String(p.strategy_id) + " (" + String(p.regime) + ")"
                  : t === "EXIT"
                  ? "pnl=" + (typeof p.pnl === "number" ? (p.pnl as number).toFixed(4) : "-") + " reason=" + String(p.reason)
                  : t === "HEARTBEAT"
                  ? "price=" + String(p.price) + " regime=" + String(p.regime) + " pnl=" + String(p.session_realized_pnl)
                  : t === "QTY_ADJUSTED"
                  ? String(p.qty_before) + " -> " + String(p.qty_after) + " BTC"
                  : JSON.stringify(p).slice(0, 70);
              const bg = t === "ENTRY" ? "bg-green-50" : t === "EXIT" ? "bg-blue-50" : t === "KILL_SWITCH" ? "bg-red-50" : "";
              return (
                <tr key={idx} className={"text-xs text-text hover:bg-panel-2 " + bg}>
                  <td className="px-2 py-1 font-mono">{String(ev.ts ?? "").slice(11, 19)}</td>
                  <td className="px-2 py-1 font-bold">{t}</td>
                  <td className="px-2 py-1 text-muted">{d}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </article>
  );
}

'''

# 3) PhaseBVisibilityCards 함수 내 state 추가 + fetch useEffect 추가
# state 추가: [pnl, setPnl] 바로 뒤에 pmx state 추가
pmx_state = "  const [pmxSummary, setPmxSummary] = useState<Record<string, unknown>>({});\n  const [pmxEvents, setPmxEvents] = useState<Record<string, unknown>[]>([]);\n"
target_state = "  const [lastEventAgeSec, setLastEventAgeSec] = useState<number | null>(null);\n"
content = content.replace(target_state, target_state + "\n" + pmx_state, 1)

# 4) useEffect for pmx polling (5s) - insert before the final return
pmx_effect = """
  useEffect(() => {
    const fetchPmx = async () => {
      try {
        const r = await fetch("/api/profitmax/status?limit=20");
        if (r.ok) {
          const data = await r.json();
          setPmxSummary((data.summary as Record<string, unknown>) ?? {});
          setPmxEvents((data.events as Record<string, unknown>[]) ?? []);
        }
      } catch { /* ignore */ }
    };
    fetchPmx();
    const iv = window.setInterval(fetchPmx, 5000);
    return () => window.clearInterval(iv);
  }, []);

"""
target_return = "  return (\n    <div className=\"grid grid-cols-1 gap-3 lg:grid-cols-3\">"
content = content.replace(target_return, pmx_effect + target_return, 1)

# 5) JSX에 PmxCard 추가 (PnlCard 바로 뒤, </div> 앞)
pmx_jsx = "\n      <PmxCard summary={pmxSummary} events={pmxEvents} />\n"
target_jsx = "\n    </div>\n  );\n}"
content = content.replace(target_jsx, pmx_jsx + "\n    </div>\n  );\n}", 1)

# 6) PmxCard 컴포넌트를 export default 앞에 삽입
target_export = "export default function PhaseBVisibilityCards()"
content = content.replace(target_export, pmx_component + target_export, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("DONE")
