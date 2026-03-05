path = r"C:\projects\NEXT-TRADE\src\app\ops\page.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

pmx_card = r"""
        {/* ===== PROFITMAX v1 Runner ===== */}
        {pmxData && (() => {
          const summary = ((pmxData as Record<string, unknown>).summary as Record<string, unknown>) ?? {};
          const evts = ((pmxData as Record<string, unknown>).events as Record<string, unknown>[]) ?? [];
          const pnl = typeof summary.session_realized_pnl === "number" ? summary.session_realized_pnl : 0;
          const posOpen = !!summary.position_open;
          const killed = !!summary.kill;
          return (
            <Card className="rounded-lg border border-border-subtle bg-panel shadow-sm mt-6">
              <CardHeader>
                <CardTitle className="text-xs font-medium text-muted flex items-center gap-2">
                  PROFITMAX v1
                  <span className={"ml-2 px-2 py-0.5 rounded text-xs font-bold " + (killed ? "bg-red-200 text-red-800" : posOpen ? "bg-green-200 text-green-800" : "bg-blue-100 text-blue-800")}>
                    {killed ? "KILL" : posOpen ? "IN POSITION" : "WATCHING"}
                  </span>
                  <span className={"ml-2 px-2 py-0.5 rounded text-xs font-bold " + (pnl >= 0 ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800")}>
                    {"PnL: " + (pnl >= 0 ? "+" : "") + pnl.toFixed(4) + " USDT"}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-panel-2 sticky top-0">
                      <tr className="text-xs font-semibold text-text-strong">
                        <th className="px-3 py-1 text-left">Time (UTC)</th>
                        <th className="px-3 py-1 text-left">Event</th>
                        <th className="px-3 py-1 text-left">Detail</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle bg-panel">
                      {evts.map((ev, idx) => {
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
                            : JSON.stringify(p).slice(0, 60);
                        const bg = t === "ENTRY" ? "bg-green-50" : t === "EXIT" ? "bg-blue-50" : t === "KILL_SWITCH" ? "bg-red-50" : "";
                        return (
                          <tr key={idx} className={"text-xs text-text hover:bg-panel-2 " + bg}>
                            <td className="px-3 py-1 font-mono">{String(ev.ts ?? "").slice(11, 19)}</td>
                            <td className="px-3 py-1 font-bold">{t}</td>
                            <td className="px-3 py-1 text-muted">{d}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          );
        })()}
"""

closing = "      </div>\n    </div>\n  );\n}"
if closing in content:
    new_content = content.replace(closing, pmx_card + closing, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("DONE")
else:
    print("CLOSING_NOT_FOUND")
    print(repr(content[-100:]))
