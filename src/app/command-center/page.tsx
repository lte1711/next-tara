"use client";

import PhaseBVisibilityCards from "@/components/PhaseBVisibilityCards";
import Dashboard from "../page";

export default function CommandCenterPage() {
  return (
    <div className="command-center-shell">
      <div className="sticky top-0 z-50 border-b border-neutral-800 bg-black/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-3">
          <PhaseBVisibilityCards />
        </div>
      </div>

      <div className="command-center-body">
        <Dashboard />
      </div>
    </div>
  );
}
