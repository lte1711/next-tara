import { NextResponse } from "next/server";

export async function GET() {
  const upstream =
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_HTTP ||
    "http://127.0.0.1:8100";
  const r = await fetch(`${upstream.replace(/\/+$/, "")}/api/ops/health`, {
    cache: "no-store",
  });
  const j = await r.json();
  return NextResponse.json(j);
}
