'use client';

import React, { useState, useEffect } from 'react';
import { ArrowUpRight, ArrowDownLeft, TrendingUp, BarChart3, Zap } from 'lucide-react';

export default function Institutional() {
  const [prices, setPrices] = useState({
    BTC: 68420.50,
    ETH: 3580.25,
    BNB: 612.40,
    SOL: 185.30,
  });

  const [changes, setChanges] = useState({
    BTC: 2.45,
    ETH: 1.82,
    BNB: -0.93,
    SOL: 3.12,
  });

  // WS + metrics state
  const [wsStatus, setWsStatus] = useState<"CLOSED" | "CONNECTING" | "OPEN">("CLOSED");
  const [hbCount, setHbCount] = useState(0);
  const [riskLevel, setRiskLevel] = useState<string>("?");
  const [killSwitchOn, setKillSwitchOn] = useState<boolean | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let pollTimer: any = null;

    const WS_URL =
      (process.env.NEXT_PUBLIC_WS_URL as string) ||
      "ws://127.0.0.1:8100/ws/events";

    const API_BASE =
      (process.env.NEXT_PUBLIC_API_URL as string) ||
      "http://127.0.0.1:8100";

    const connect = () => {
      if (cancelled) return;
      setWsStatus("CONNECTING");

      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        if (cancelled) return;
        setWsStatus("OPEN");
      };

      ws.onmessage = (msg) => {
        if (cancelled) return;
        console.log("[WS RAW]", msg.data);
        try {
          const data = JSON.parse(msg.data);

          // 최근 50개만 유지
          setEvents((prev) => {
            const next = [data, ...prev];
            return next.slice(0, 50);
          });

          // heartbeat 카운트 (server.js는 event: "heartbeat" 또는 type: "ws_heartbeat")
          if (data?.event === "heartbeat" || data?.type === "ws_heartbeat") {
            setHbCount((n) => n + 1);
          }

          // guardrail_update 규약 수신: WS 우선으로 RISK/KILL 즉시 반영
          if (data?.type === "guardrail_update" && data?.data) {
            try {
              const d = data.data;
              const rl = typeof d?.risk_level === "string" ? d.risk_level : "?";
              const ks = typeof d?.kill_switch === "boolean" ? d.kill_switch : !!d?.kill_switch;
              if (!cancelled) {
                setRiskLevel(rl);
                setKillSwitchOn(!!ks);
              }
            } catch (e) {
              // ignore malformed guardrail payload
            }
          }
        } catch {
          // ignore non-json
        }
      };

      ws.onerror = () => {
        if (cancelled) return;
        // 오류는 onclose에서 재연결 처리
      };

      ws.onclose = () => {
        if (cancelled) return;
        setWsStatus("CLOSED");
        // 1초 후 재연결
        setTimeout(connect, 1000);
      };
    };

    // metrics 폴링 (1초)
    const startPolling = () => {
      const poll = async () => {
        try {
          const res = await fetch(`${API_BASE}/api/ops/metrics`, { cache: "no-store" });
          const j = await res.json();
          if (!cancelled) setMetrics(j);
        } catch {
          // ignore
        }
      };
      poll();
      pollTimer = setInterval(poll, 1000);
    };

    connect();
    startPolling();

    // initial risk snapshot fetch (do not block page; tolerant to errors)
    (async () => {
      try {
        const res = await fetch("http://127.0.0.1:8100/api/ops/risk-snapshot", { cache: "no-store" });
        if (!res.ok) throw new Error("bad response");
        const j = await res.json();
        // guard against missing values
        const rl = typeof j?.risk_level === "string" ? j.risk_level : "OK";
        const ks = typeof j?.kill_switch === "boolean" ? j.kill_switch : false;
        if (!cancelled) {
          setRiskLevel(rl);
          setKillSwitchOn(ks);
        }
      } catch (err) {
        if (!cancelled) {
          setRiskLevel("?");
          setKillSwitchOn(null);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    };
  }, []);

  const PriceCard = ({ symbol, price, change }: any) => (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700 rounded-xl p-6 hover:border-slate-600 transition-all duration-300 cursor-pointer group">
      <div className="flex justify-between items-start mb-4">
        <div>
          <p className="text-slate-400 text-sm mb-1">Price</p>
          <h3 className="text-2xl font-bold text-white">{symbol}</h3>
        </div>
        <div className={`px-3 py-1 rounded-lg flex items-center gap-1 ${change >= 0 ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'}`}>
          {change >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownLeft size={14} />}
          <span className="text-xs font-semibold">{Math.abs(change).toFixed(2)}%</span>
        </div>
      </div>
      <p className="text-white text-xl font-bold mb-2">${price.toFixed(2)}</p>
      <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
        <div 
          className={`h-full ${change >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`}
          style={{width: `${Math.min(Math.abs(change) * 20, 100)}%`}}
        />
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-slate-950 to-slate-900">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-black/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-yellow-400 to-yellow-600 rounded-lg flex items-center justify-center">
                <span className="text-black font-bold text-lg">E</span>
              </div>
              <h1 className="text-white text-2xl font-bold">Evergreen Institutional</h1>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs px-2 py-1 rounded-lg ring-1 ring-white/10 bg-white/5">
                  WS: {wsStatus}
                </span>
                <span className="text-xs px-2 py-1 rounded-lg ring-1 ring-white/10 bg-white/5">
                  HB: {hbCount}
                </span>
                <span className="text-xs px-2 py-1 rounded-lg ring-1 ring-white/10 bg-white/5">
                  RISK: {riskLevel}
                </span>
                <span className="text-xs px-2 py-1 rounded-lg ring-1 ring-white/10 bg-white/5">
                  KILL: {killSwitchOn === null ? "?" : killSwitchOn ? "ON" : "OFF"}
                </span>
                <span className={"text-xs px-2 py-1 rounded-lg ring-1 ring-white/10 " + (hbCount > 0 ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-slate-400")}>
                  {hbCount > 0 ? "LIVE" : "WAIT"}
                </span>
              </div>
              <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm transition-colors">
                Portfolio
              </button>
              <button className="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-black rounded-lg text-sm font-semibold transition-colors">
                Connect Wallet
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Welcome Section */}
        <div className="mb-12">
          <h2 className="text-4xl font-bold text-white mb-2">Market Overview</h2>
          <p className="text-slate-400 text-lg">Real-time institutional-grade crypto tracking</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          {Object.entries(prices).map(([symbol, price]) => (
            <PriceCard 
              key={symbol}
              symbol={symbol}
              price={price as number}
              change={changes[symbol as keyof typeof changes]}
            />
          ))}
        </div>

        {/* Features Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700 rounded-xl p-8 hover:border-slate-600 transition-all">
            <TrendingUp className="text-emerald-400 mb-4" size={32} />
            <h3 className="text-xl font-bold text-white mb-2">Advanced Analytics</h3>
            <p className="text-slate-400">Real-time market data with institutional-grade charting tools</p>
          </div>

          <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700 rounded-xl p-8 hover:border-slate-600 transition-all">
            <BarChart3 className="text-blue-400 mb-4" size={32} />
            <h3 className="text-xl font-bold text-white mb-2">Portfolio Management</h3>
            <p className="text-slate-400">Comprehensive tools to manage and optimize your positions</p>
          </div>

          <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700 rounded-xl p-8 hover:border-slate-600 transition-all">
            <Zap className="text-yellow-400 mb-4" size={32} />
            <h3 className="text-xl font-bold text-white mb-2">Lightning Fast</h3>
            <p className="text-slate-400">Ultra-low latency execution for institutional traders</p>
          </div>
        </div>

        {/* Footer CTA */}
        <div className="bg-gradient-to-r from-yellow-500/10 to-yellow-600/10 border border-yellow-500/30 rounded-xl p-8 text-center mb-12">
          <h3 className="text-2xl font-bold text-white mb-4">Ready to Trade?</h3>
          <p className="text-slate-400 mb-6">Access institutional-grade crypto markets with Evergreen</p>
          <button className="px-8 py-3 bg-yellow-500 hover:bg-yellow-600 text-black font-bold rounded-lg transition-colors">
            Start Trading Now
          </button>
        </div>

        {/* Realtime Events Log */}
        <div className="rounded-2xl bg-neutral-950/60 ring-1 ring-white/10 overflow-hidden">
          <div className="px-4 py-3 text-xs text-neutral-300 flex items-center justify-between border-b border-white/10">
            <span className="font-medium">📡 Realtime Events</span>
            <span className="text-neutral-500">latest {events.length}/50</span>
          </div>
          <div className="max-h-[280px] overflow-auto px-4 py-3">
            {metrics && (
              <div className="text-xs text-neutral-400 mb-3 pb-2 border-b border-white/10">
                subscribers: <span className="font-mono text-neutral-200">{metrics.subscribers || 0}</span>{" "}
                | drop: <span className="font-mono text-neutral-200">{metrics.drop_count || 0}</span>
              </div>
            )}
            <div className="space-y-1">
              {events.length === 0 ? (
                <div className="text-xs text-neutral-500 py-8 text-center">Waiting for events...</div>
              ) : (
                events.map((e, i) => (
                  <div key={i} className="text-[11px] text-neutral-400 font-mono break-words">
                    <span className="text-neutral-600">[{i+1}]</span> <span className="text-cyan-400">{e?.type || "event"}</span> {JSON.stringify(e).slice(0, 120)}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
