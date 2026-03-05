"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type RegressionApiResponse = {
  ok: boolean;
  available: boolean;
  message?: string;
  file?: string;
  values?: Record<string, string>;
  history?: Array<{ file: string; values: Record<string, string> }>;
  alert_file?: string | null;
  alert_hits?: Record<string, string> | null;
};

type StatusLevel = "OK" | "WARN" | "CRITICAL";
type DayLine = {
  label: "D0" | "D-1" | "D-2";
  u: number | null;
  r: number | null;
  w: number | null;
  a: number | null;
  status: "OK" | "WARN";
};

function toNum(value: string | undefined): number | null {
  if (!value) return null;
  const n = Number(String(value).replace("%", "").trim());
  return Number.isFinite(n) ? n : null;
}

function toInt(value: string | undefined): number | null {
  const n = toNum(value);
  return n === null ? null : Math.trunc(n);
}

function badgeClass(level: StatusLevel): string {
  if (level === "CRITICAL") {
    return "border-nt-down/40 bg-nt-down/10 text-nt-down";
  }
  if (level === "WARN") {
    return "border-nt-warn/40 bg-nt-warn/10 text-nt-warn";
  }
  return "border-nt-up/40 bg-nt-up/10 text-nt-up";
}

function dayBadgeClass(level: "OK" | "WARN"): string {
  if (level === "WARN") {
    return "border-nt-warn/40 bg-nt-warn/10 text-nt-warn";
  }
  return "border-nt-up/40 bg-nt-up/10 text-nt-up";
}

export default function PH7CObservabilityCard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<
    Array<{ file: string; values: Record<string, string> }>
  >([]);
  const [alertHits, setAlertHits] = useState<Record<string, string> | null>(
    null,
  );

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const response = await fetch("/api/ops/ph7c-regression", {
          cache: "no-store",
        });
        if (!response.ok) {
          if (mounted) {
            setError(`status_${response.status}`);
            setAvailable(false);
            setValues({});
          }
          return;
        }
        const data = (await response.json()) as RegressionApiResponse;
        if (!mounted) return;
        setAvailable(!!data.available);
        setValues(data.values ?? {});
        setHistory(data.history ?? []);
        setAlertHits(data.alert_hits ?? null);
        setError(null);
      } catch {
        if (!mounted) return;
        setError("fetch_failed");
        setAvailable(false);
        setValues({});
        setHistory([]);
        setAlertHits(null);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    const iv = window.setInterval(load, 5000);
    return () => {
      mounted = false;
      window.clearInterval(iv);
    };
  }, []);

  const driftWarn = useMemo(() => {
    if (history.length < 2) return false;
    const d0 = history[0]?.values ?? {};
    const d1 = history[1]?.values ?? {};
    const rules0 = toInt(d0.RULES_WITH_NONZERO_WEIGHT);
    const rules1 = toInt(d1.RULES_WITH_NONZERO_WEIGHT);
    const sum0 = toNum(d0.WEIGHT_SUM);
    const sum1 = toNum(d1.WEIGHT_SUM);
    const u0 = toNum(d0.UNKNOWN_RATE_LAST_24H);
    const u1 = toNum(d1.UNKNOWN_RATE_LAST_24H);

    if (rules0 !== null && rules1 !== null && rules1 > 0 && rules0 === 0) {
      return true;
    }
    if (sum0 !== null && sum1 !== null && sum1 >= 0.2 && sum0 <= 0.1) {
      return true;
    }
    if (u0 !== null && u1 !== null && u1 === 0 && u0 > 0) {
      return true;
    }
    return false;
  }, [history]);

  const status = useMemo(() => {
    if (!available) return "WARN" as StatusLevel;
    const apply = String(values.ENGINE_APPLY_STATUS ?? "").toUpperCase();
    if (apply && apply !== "DISABLED") return "CRITICAL" as StatusLevel;

    const unknownRate = toNum(values.UNKNOWN_RATE_LAST_24H);
    if (unknownRate !== null && unknownRate > 5) return "WARN" as StatusLevel;

    const rules = toInt(values.RULES_WITH_NONZERO_WEIGHT);
    if (rules !== null && rules === 0) return "WARN" as StatusLevel;

    const corr = toInt(values.SCHEDULE_LAST_RESULT_CORR);
    const guard = toInt(values.SCHEDULE_LAST_RESULT_GUARD);
    if ((corr !== null && corr !== 0) || (guard !== null && guard !== 0)) {
      return "WARN" as StatusLevel;
    }
    if (driftWarn) return "WARN" as StatusLevel;
    return "OK" as StatusLevel;
  }, [available, values, driftWarn]);

  const highlightEvents = status !== "OK";
  const alertCount = useMemo(() => {
    if (!alertHits) return null;
    const keys = [
      "A1_DATA_PIPELINE_HITS",
      "A2_GUARD_OVERBLOCK_HITS",
      "A3_SHADOW_SCORE_RISK_HITS",
      "A4_DD_SIM_DIVERGENCE_HITS",
    ];
    let total = 0;
    let hasAny = false;
    for (const k of keys) {
      const n = toInt(alertHits[k]);
      if (n !== null) {
        total += n;
        hasAny = true;
      }
    }
    return hasAny ? total : null;
  }, [alertHits]);

  const dayLines = useMemo<DayLine[]>(() => {
    const labels: Array<"D0" | "D-1" | "D-2"> = ["D0", "D-1", "D-2"];
    const lines: DayLine[] = [];

    for (let i = 0; i < Math.min(3, history.length); i += 1) {
      const h = history[i]?.values ?? {};
      const u = toNum(h.UNKNOWN_RATE_LAST_24H);
      const r = toInt(h.RULES_WITH_NONZERO_WEIGHT);
      const w = toNum(h.WEIGHT_SUM);
      const a = i === 0 ? alertCount : null;
      const isWarn =
        (u !== null && u > 5) ||
        (r !== null && r === 0) ||
        (w !== null && w > 0.5) ||
        (a !== null && a > 0);

      lines.push({
        label: labels[i],
        u,
        r,
        w,
        a,
        status: isWarn ? "WARN" : "OK",
      });
    }
    return lines;
  }, [history, alertCount]);

  return (
    <article className="rounded-2xl border border-nt-border bg-nt-surface p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-strong">PH7C</h3>
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-semibold ${badgeClass(status)}`}
        >
          {status}
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">
          <div className="h-3 rounded bg-panel-2" />
          <div className="h-3 rounded bg-panel-2" />
          <div className="h-3 rounded bg-panel-2" />
        </div>
      ) : !available ? (
        <div className="space-y-2 text-xs">
          <div className="rounded border border-nt-warn/40 bg-nt-warn/10 px-2 py-1 text-nt-warn">
            PH7C regression not available
          </div>
          {error ? <div className="text-muted">error: {error}</div> : null}
          <Link
            href="/command-center/events"
            className={`inline-flex rounded border border-nt-border px-2 py-1 text-xs font-semibold hover:bg-nt-surface-2 ${highlightEvents ? "text-nt-warn underline" : "text-nt-fg"}`}
          >
            Open Events -&gt;
          </Link>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Unknown(24h)</span>
            <span>{values.UNKNOWN_RATE_LAST_24H ?? "-"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Rules(nonzero)</span>
            <span>{values.RULES_WITH_NONZERO_WEIGHT ?? "-"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Max Weight</span>
            <span>{values.MAX_WEIGHT ?? "-"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Weight Sum</span>
            <span>{values.WEIGHT_SUM ?? "-"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Sched Corr/Guard</span>
            <span>
              {(values.SCHEDULE_LAST_RESULT_CORR ?? "-") +
                "/" +
                (values.SCHEDULE_LAST_RESULT_GUARD ?? "-")}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Apply</span>
            <span>{values.ENGINE_APPLY_STATUS ?? "-"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Alert Hits</span>
            <span>{alertCount === null ? "N/A" : alertCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Replay H/L</span>
            <span className="max-w-[140px] truncate text-right">
              {(values.REPLAY_HIGH_SCORE_PNL_SUM ?? "-") +
                "/" +
                (values.REPLAY_LOW_SCORE_PNL_SUM ?? "-")}
            </span>
          </div>
          {dayLines.length > 0 ? (
            <div className="rounded border border-nt-border bg-nt-surface-2 px-2 py-1 text-[11px]">
              <div className="mb-1 text-muted">Last 3 Days</div>
              {dayLines.map((line) => (
                <div key={line.label} className="mb-1 flex items-center justify-between last:mb-0">
                  <span className="max-w-[170px] truncate">
                    {`${line.label} U=${line.u === null ? "N/A" : line.u.toFixed(2) + "%"} R=${line.r === null ? "N/A" : line.r} W=${line.w === null ? "N/A" : line.w.toFixed(2)} A=${line.a === null ? "N/A" : line.a}`}
                  </span>
                  <span
                    className={`ml-2 inline-flex items-center rounded border px-1.5 py-0 text-[10px] font-semibold ${dayBadgeClass(line.status)}`}
                  >
                    {line.status}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
          {alertHits === null ? (
            <div className="text-[11px] text-muted">Alert file not generated yet</div>
          ) : null}
          {driftWarn ? (
            <div className="rounded border border-nt-warn/40 bg-nt-warn/10 px-2 py-1 text-[11px] text-nt-warn">
              drift detected
            </div>
          ) : null}
          <Link
            href="/command-center/events"
            className={`mt-1 inline-flex rounded border border-nt-border px-2 py-1 text-xs font-semibold hover:bg-nt-surface-2 ${highlightEvents ? "text-nt-warn underline" : "text-nt-fg"}`}
          >
            Open Events -&gt;
          </Link>
        </div>
      )}
    </article>
  );
}
