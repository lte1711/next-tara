import { NextResponse } from "next/server";

export async function GET() {
  const r = await fetch("http://127.0.0.1:8000/api/ops/health", { cache: "no-store" });
  const j = await r.json();
  return NextResponse.json(j);
}
