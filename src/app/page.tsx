"use client";

import { AuditLogEntry, AuditTerminal } from "@/components/AuditTerminal";
import { DevLoadTestPanel } from "@/components/DevLoadTestPanel";
import { EngineStatusCard } from "@/components/EngineStatusCard";
import { KillSwitchControlPanel } from "@/components/KillSwitchControlPanel";
import {
  LevelDowngradedAlert,
  LevelDowngradedEvent,
} from "@/components/LevelDowngradedAlert";
import {
  PnlCard,
  ProgressCard,
  TradesCard,
} from "@/components/PhaseBVisibilityCards";
import { PositionsCard } from "@/components/PositionsCard";
import { RecentRisksTable } from "@/components/RecentRisksTable";
import { useWebSocket, WSEvent } from "@/hooks/useWebSocket";
import {
  apiClient,
  ContractHealth,
  ContractState,
  EngineState,
  Position,
  RiskEvent,
  V1FillItem,
  V1OrderItem,
  V1PnlResponse,
} from "@/lib/api";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function Dashboard() {
  const pathname = usePathname();
  const showInlinePhaseBCards = pathname !== "/command-center";
  const [engine, setEngine] = useState<EngineState | null>(null);
  const [positions, setPositions] = useState<Position[] | null>(null);
  const [risks, setRisks] = useState<RiskEvent[]>([]);
  const [loadingEngine, setLoadingEngine] = useState(true);
  const [loadingPositions, setLoadingPositions] = useState(true);
  const [loadingRisks, setLoadingRisks] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(true);
  const [loadingTrades, setLoadingTrades] = useState(true);
  const [loadingPnl, setLoadingPnl] = useState(true);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [pnlError, setPnlError] = useState<string | null>(null);
  const [contractHealth, setContractHealth] = useState<ContractHealth | null>(
    null,
  );
  const [contractState, setContractState] = useState<ContractState | null>(
    null,
  );
  const [orders, setOrders] = useState<V1OrderItem[]>([]);
  const [fills, setFills] = useState<V1FillItem[]>([]);
  const [pnl, setPnl] = useState<V1PnlResponse | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const showDevPanel = process.env.NODE_ENV === "development";

  // TICKET-WS-004: New state for 6 event types
  const [levelDowngradedAlert, setLevelDowngradedAlert] =
    useState<LevelDowngradedEvent | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [filteredAuditLogs, setFilteredAuditLogs] = useState<AuditLogEntry[]>(
    [],
  );
  const [auditFilterTraceId, setAuditFilterTraceId] = useState<string | null>(
    null,
  );

  const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;
  const asNumber = (value: unknown, fallback = 0): number =>
    typeof value === "number" && Number.isFinite(value) ? value : fallback;
  const asString = (value: unknown, fallback = ""): string =>
    typeof value === "string" ? value : fallback;
  const asBoolean = (value: unknown, fallback = false): boolean =>
    typeof value === "boolean" ? value : fallback;
  const asStringArray = (value: unknown): string[] | undefined =>
    Array.isArray(value)
      ? value.filter((v): v is string => typeof v === "string")
      : undefined;

  // Load initial data
  const loadData = useCallback(async () => {
    try {
      setLoadingEngine(true);
      const engineData = await apiClient.getEngineState();
      if (engineData) {
        setEngine(engineData);
        console.log("[Dashboard] Engine state loaded:", engineData);
      }
    } catch {
      // Fail silent - engine state is optional
    } finally {
      setLoadingEngine(false);
    }

    try {
      setLoadingPositions(true);
      const positionsData = await apiClient.getPositions();
      if (positionsData) {
        setPositions(positionsData.positions);
        console.log("[Dashboard] Positions loaded:", positionsData);
      }
    } catch {
      // Fail silent - positions are optional
    } finally {
      setLoadingPositions(false);
    }

    try {
      setLoadingRisks(true);
      const risksData = await apiClient.getRiskHistory(20);
      setRisks(risksData);
      console.log("[Dashboard] Risk history loaded:", risksData);
    } catch {
      // Fail silent - risk history is optional
    } finally {
      setLoadingRisks(false);
    }

    try {
      setLoadingProgress(true);
      setProgressError(null);
      const [healthData, stateData] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getState(),
      ]);
      if (!healthData || !stateData) {
        setProgressError("v1_progress_unavailable");
      }
      setContractHealth(healthData);
      setContractState(stateData);
    } catch {
      setProgressError("v1_progress_error");
    } finally {
      setLoadingProgress(false);
    }

    try {
      setLoadingTrades(true);
      setTradesError(null);
      const [ordersData, fillsData] = await Promise.all([
        apiClient.getOrders(10),
        apiClient.getFills(10),
      ]);
      if (!ordersData || !fillsData) {
        setTradesError("v1_trades_unavailable");
      }
      setOrders(ordersData?.items ?? []);
      setFills(fillsData?.items ?? []);
    } catch {
      setTradesError("v1_trades_error");
    } finally {
      setLoadingTrades(false);
    }

    try {
      setLoadingPnl(true);
      setPnlError(null);
      const pnlData = await apiClient.getPnl();
      if (!pnlData) {
        setPnlError("v1_pnl_unavailable");
      }
      setPnl(pnlData);
    } catch {
      setPnlError("v1_pnl_error");
    } finally {
      setLoadingPnl(false);
    }
  }, []);

  // Load data on mount
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle audit log filtering
  useEffect(() => {
    if (auditFilterTraceId) {
      setFilteredAuditLogs(
        auditLogs.filter((log) => log.trace_id === auditFilterTraceId),
      );
    } else {
      setFilteredAuditLogs(auditLogs);
    }
  }, [auditLogs, auditFilterTraceId]);

  // WebSocket message handler (TICKET-WS-004)
  const handleWSMessage = useCallback((event: WSEvent) => {
    console.log("[Dashboard] WS Event:", event.event_type, event);

    switch (event.event_type) {
      // Legacy event types
      case "engine_state":
        if (event.data) {
          const data = event.data;
          const newEngine: EngineState = {
            kill_switch_on: asBoolean(data.kill_switch_on),
            risk_type: asString(data.risk_type) || undefined,
            reason: asString(data.reason) || undefined,
            uptime_sec: asNumber(data.uptime_sec),
            published: asNumber(data.published),
            consumed: asNumber(data.consumed),
            pending_total: asNumber(data.pending_total),
          };
          setEngine(newEngine);
        }
        break;

      case "position_snapshot":
        if (event.data) {
          const data = event.data;
          const newPosition: Position = {
            symbol: asString(data.symbol),
            qty: asNumber(data.qty),
            avg_entry_price: asNumber(data.avg_entry_price),
            mark_price: asNumber(data.current_price),
            pnl: asNumber(data.position_pnl),
          };
          setPositions((prev) => {
            if (!prev) return [newPosition];
            const filtered = prev.filter(
              (p) => p.symbol !== newPosition.symbol,
            );
            return [newPosition, ...filtered];
          });
        }
        break;

      case "risk_event":
        if (event.data) {
          const data = event.data;
          const metadata = isRecord(data.metadata) ? data.metadata : undefined;
          const newRisk: RiskEvent = {
            timestamp: event.ts,
            event_id: asString(metadata?.audit_id) || `risk_${Date.now()}`,
            event_type: asString(data.risk_type) || "unknown",
            level: asString(metadata?.level) || "INFO",
            reason: asString(data.reason),
            risk_type: asString(data.risk_type) || undefined,
            metadata,
          };
          setRisks((prev) => [newRisk, ...prev.slice(0, 19)]);
        }
        break;

      case "heartbeat":
        // Ignore heartbeats
        break;

      // TICKET-WS-003: New 6 event types
      case "RISK_TRIGGERED":
        // Add to audit logs
        setAuditLogs((prev) => [
          {
            event_type: "RISK_TRIGGERED",
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;

      case "ORDER_REJECTED":
        setAuditLogs((prev) => [
          {
            event_type: "ORDER_REJECTED",
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;

      case "LEVEL_DOWNGRADED":
        // Trigger alert
        const levelDowngradedEvent: LevelDowngradedEvent = {
          previous_level: asNumber(event.data.previous_level),
          new_level: asNumber(event.data.new_level),
          reason: asString(event.data.reason),
          affected_symbols: asStringArray(event.data.affected_symbols) || [],
          trace_id: event.trace_id || "",
          ts: event.ts,
        };
        setLevelDowngradedAlert(levelDowngradedEvent);

        // Add to audit logs
        setAuditLogs((prev) => [
          {
            event_type: "LEVEL_DOWNGRADED",
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;

      case "LEVEL_RESTORED":
        setAuditLogs((prev) => [
          {
            event_type: "LEVEL_RESTORED",
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;

      case "SYSTEM_GUARD":
        setAuditLogs((prev) => [
          {
            event_type: "SYSTEM_GUARD",
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;

      case "AUDIT_LOG":
        setAuditLogs((prev) => [
          {
            event_type: "AUDIT_LOG",
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;

      // PHASE 10: Router WS events
      case "ROUTE_DECIDED":
      case "ROUTE_SPLIT":
      case "ROUTE_REJECTED_SOFT":
      case "ROUTE_REJECTED_HARD":
        setAuditLogs((prev) => [
          {
            event_type: event.event_type,
            ts: event.ts,
            trace_id: asString(event.trace_id) || asString(event.data.trace_id),
            data: event.data,
          },
          ...prev.slice(0, 999),
        ]);
        break;
    }
  }, []);

  const [wsUrl, setWsUrl] = useState("");

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsEnv =
      process.env.NEXT_PUBLIC_WS_URL || process.env.NEXT_PUBLIC_API_WS;
    const finalUrl = wsEnv
      ? wsEnv.includes("/ws/events")
        ? wsEnv
        : `${wsEnv.replace(/\/+$/, "")}/ws/events`
      : `${protocol}//${window.location.hostname}:8100/ws/events`;
    console.log("[Dashboard] Setting wsUrl:", finalUrl);
    setWsUrl(finalUrl);
  }, []);

  useWebSocket({
    url: wsUrl,
    onMessage: handleWSMessage,
    onConnect: () => {
      setWsConnected(true);
      console.log("[Dashboard] WebSocket connected");
    },
    onDisconnect: () => {
      setWsConnected(false);
      console.log("[Dashboard] WebSocket disconnected");
    },
    onError: (error) => {
      console.error("[Dashboard] WebSocket error:", error);
    },
  });

  const handleKillSwitchToggle = async (success: boolean) => {
    if (success) {
      await loadData();
    }
  };

  const handleEmit10kEvents = async () => {
    // This will be called by DevLoadTestPanel
    // The panel handles the actual emission via Contract v1 client
    console.log("[Dashboard] Dev 10k event emission started");
  };

  return (
    <div className="min-h-screen bg-bg p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 text-text-strong">
          Command Center
        </h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${wsConnected ? "bg-ok" : "bg-danger"}`}
            ></div>
            <span className="text-sm text-muted">
              {wsConnected ? "WebSocket Connected" : "WebSocket Disconnected"}
            </span>
          </div>
          <span className="text-sm text-muted-dark">
            PHASE 9-1 Dashboard MVP + TICKET-WS-004
          </span>
        </div>
      </div>

      {/* LEVEL_DOWNGRADED Alert Modal */}
      <LevelDowngradedAlert
        event={levelDowngradedAlert}
        onAcknowledge={() => setLevelDowngradedAlert(null)}
      />

      {/* Dev Load Test Panel (Dev-only) */}
      {showDevPanel && (
        <DevLoadTestPanel onEmit10kEvents={handleEmit10kEvents} />
      )}

      {/* Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* A. Engine Status Card */}
        <EngineStatusCard engine={engine} loading={loadingEngine} />

        {/* B. Positions Card */}
        <PositionsCard positions={positions} loading={loadingPositions} />
      </div>

      {showInlinePhaseBCards && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <ProgressCard
            loading={loadingProgress}
            error={progressError}
            uptimeSec={contractState?.freshness.checkpoint_age_sec ?? 0}
            sessionState={contractHealth?.status ?? "UNKNOWN"}
            processedEvents={risks.length}
            restartCount={contractState?.counters.restart_count ?? 0}
            onRetry={loadData}
          />
          <TradesCard
            loading={loadingTrades}
            error={tradesError}
            orders={orders}
            fills={fills}
            onRetry={loadData}
          />
          <PnlCard
            loading={loadingPnl}
            error={pnlError}
            pnl={pnl}
            onRetry={loadData}
          />
        </div>
      )}

      {/* D. Kill-Switch Control Panel */}
      <div className="mb-6">
        <KillSwitchControlPanel
          isOn={engine?.kill_switch_on || false}
          onToggle={handleKillSwitchToggle}
        />
      </div>

      {/* C. Recent Risks Table */}
      <RecentRisksTable events={risks} loading={loadingRisks} />

      {/* Audit Terminal Stream (TICKET-WS-004) */}
      <div className="mt-6 h-96">
        <AuditTerminal
          logs={filteredAuditLogs}
          onTraceFilterChange={setAuditFilterTraceId}
        />
      </div>

      {/* Footer Debug Info */}
      <div className="mt-8 p-4 bg-panel rounded-lg border border-border-subtle">
        <p className="text-xs text-muted-dark font-mono">
          API:{" "}
          {process.env.NEXT_PUBLIC_API_URL ||
            process.env.NEXT_PUBLIC_API_HTTP ||
            "http://127.0.0.1:8100"}{" "}
          | WS: {wsUrl}
        </p>
      </div>
    </div>
  );
}
