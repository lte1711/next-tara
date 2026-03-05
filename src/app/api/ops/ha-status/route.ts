import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND}/api/v1/ops/ha_status`, {
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        source: "none",
        stamp: null,
        ha_eval: null,
        ha_pass: null,
        ha_skip: null,
        delta_eval: null,
        delta_pass: null,
        delta_skip: null,
        reason: "ha_status_fetch_failed",
      },
      { status: 200 }
    );
  }
}

