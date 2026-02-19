import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = url.searchParams.get("limit") ?? "50";
  const r = await fetch(`http://127.0.0.1:8000/api/ops/alerts?limit=${limit}`, { cache: "no-store" });
  const j = await r.json();
  return NextResponse.json(j);
}