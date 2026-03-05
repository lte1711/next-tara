import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

const PERF_DIR = "C:\\projects\\NEXT-TRADE\\evidence\\evergreen\\perf";
const PREFIX = "ph7c_daily_regression_";
const ALERT_PREFIX = "ph7c_alert_hits_";

function parseKvs(content: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of content.split(/\r?\n/)) {
    const idx = line.indexOf("=");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (!key) continue;
    out[key] = value;
  }
  return out;
}

function findReportsByPrefix(prefix: string): string[] {
  if (!fs.existsSync(PERF_DIR)) return [];
  const files = fs
    .readdirSync(PERF_DIR)
    .filter((name) => name.startsWith(prefix) && name.endsWith(".txt"));
  if (!files.length) return [];
  files.sort((a, b) => {
    const pa = path.join(PERF_DIR, a);
    const pb = path.join(PERF_DIR, b);
    return fs.statSync(pb).mtimeMs - fs.statSync(pa).mtimeMs;
  });
  return files.map((f) => path.join(PERF_DIR, f));
}

export async function GET() {
  try {
    const reports = findReportsByPrefix(PREFIX);
    const latest = reports[0] ?? null;
    if (!latest) {
      return NextResponse.json(
        {
          ok: true,
          available: false,
          message: "PH7C regression not available",
        },
        { status: 200 },
      );
    }

    const raw = fs.readFileSync(latest, "utf-8");
    const values = parseKvs(raw);
    const history = reports.slice(0, 3).map((file) => {
      const content = fs.readFileSync(file, "utf-8");
      return {
        file,
        values: parseKvs(content),
      };
    });

    const alertFiles = findReportsByPrefix(ALERT_PREFIX);
    const alertFile = alertFiles[0] ?? null;
    const alertHits = alertFile
      ? parseKvs(fs.readFileSync(alertFile, "utf-8"))
      : null;

    return NextResponse.json(
      {
        ok: true,
        available: true,
        file: latest,
        values,
        history,
        alert_file: alertFile,
        alert_hits: alertHits,
      },
      { status: 200 },
    );
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        available: false,
        error: "ph7c_regression_read_failed",
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 200 },
    );
  }
}
