// src/types/domain.ts
// NT-UI-BASELINE-001-FIX-01: Baseline type restore (additive-only)

export type RiskMode = "SAFE" | "WATCH" | "RISK" | "KILL";
export type DataMode = "LIVE" | "SIM" | "REPLAY" | "STALE" | "DOWN" | "DEMO";

export type HealthStatus = {
  grade?: string;
  next_milestone?: string;
  next_milestone_eta?: string;
  last_heartbeat_age_sec?: number;
  service_status?: string;
} | "OK" | "WARN" | "DOWN";

export type EvergreenStatus = {
  status?: string;
  heartbeat_sec_ago?: number;
  restart_count?: number;
} | "RUNNING" | "STOPPED" | "DEGRADED" | "UNKNOWN";

export type HistoryPoint = {
  ts: number;              // epoch ms preferred
  value: number;
  label?: string;
};

export type AlertEvent = {
  ts?: number;              // epoch ms preferred
  level?: "info" | "warn" | "error";
  message?: string;
  msg?: string;
  code?: string;
  event?: string;
  severity?: "info" | "warn" | "error";
};

export type Event = {
  ts?: number;
  event?: string;
  severity?: string;
  cumulative_runtime_sec?: number;
  restart_count?: number;
  [key: string]: any;
};
