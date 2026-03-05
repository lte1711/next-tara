"use client";

import Link from "next/link";
import PhaseBVisibilityCards from "@/components/PhaseBVisibilityCards";

export default function CommandCenterPage() {
  return (
    <main className="min-h-screen bg-nt-bg text-nt-fg">
      <div className="sticky top-0 z-50 border-b border-nt-border bg-black/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <div className="mb-3 flex items-center justify-between">
            <h1 className="text-lg font-semibold">Command Center</h1>
            <Link
              href="/command-center/events"
              className="rounded-lg border border-nt-border px-3 py-1.5 text-xs font-semibold text-nt-fg hover:bg-nt-surface"
            >
              View Events -&gt;
            </Link>
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded border border-nt-border bg-nt-surface px-2 py-0.5 text-[11px] font-semibold">
              MR_ONLY
            </span>
            <span className="inline-flex items-center rounded border border-nt-up/40 bg-nt-up/10 px-2 py-0.5 text-[11px] font-semibold text-nt-up">
              ENGINE_APPLY=DISABLED
            </span>
            <span className="inline-flex items-center rounded border border-nt-warn/40 bg-nt-warn/10 px-2 py-0.5 text-[11px] font-semibold text-nt-warn">
              DESIGN_FREEZE
            </span>
          </div>
          <PhaseBVisibilityCards />
        </div>
      </div>

    </main>
  );
}
