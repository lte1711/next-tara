import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const hours = url.searchParams.get("hours") ?? "24";
  const r = await fetch(`http://127.0.0.1:8000/api/ops/history?hours=${hours}`, { cache: "no-store" });
  const j = await r.json();
  return NextResponse.json(j);
}