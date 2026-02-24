"use client";

import CheckpointCard from "@/components/runtime/CheckpointCard";
import HealthPanel from "@/components/runtime/HealthPanel";
import RuntimeTimeline from "@/components/runtime/RuntimeTimeline";
import { useEffect, useState } from "react";

interface RuntimeHealth {
  engine_pid: number | null;
  engine_alive: boolean;
  checkpoint_age_sec: number | null;
  checkpoint_status: "FRESH" | "STALE" | "EXPIRED" | "UNKNOWN";
  health_status: "OK" | "WARN" | "CRITICAL";
  last_health_ok: string | null;
  restart_count: number;
  flap_detected: boolean;
  task_state: string;
  timestamp: string;
}

interface RuntimeEvent {
  ts: string;
  level: "INFO" | "WARN" | "ERROR" | "CRITICAL";
  action: string;
  pid?: number;
  old_pid?: number | null;
  new_pid?: number | null;
}

export default function RuntimeMonitorPage() {
  const [health, setHealth] = useState<RuntimeHealth | null>(null);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

  const fetchHealth = async () => {
    try {
      const response = await fetch(`${apiBase}/api/ops/runtime-health`);
      if (!response.ok) throw new Error("Failed to fetch health data");
      const data = await response.json();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const fetchEvents = async () => {
    try {
      const response = await fetch(
        `${apiBase}/api/ops/runtime-events?limit=50`,
      );
      if (!response.ok) throw new Error("Failed to fetch events");
      const data = await response.json();
      setEvents(data.events);
    } catch (err) {
      console.error("Failed to fetch events:", err);
    }
  };

  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchHealth(), fetchEvents()]);
      setLoading(false);
    };
    init();

    // Poll every 2 seconds for health
    const healthInterval = setInterval(fetchHealth, 2000);

    // Poll every 5 seconds for events
    const eventsInterval = setInterval(fetchEvents, 5000);

    return () => {
      clearInterval(healthInterval);
      clearInterval(eventsInterval);
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading Runtime Monitor...</p>
        </div>
      </div>
    );
  }

  if (error && !health) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-xl mb-4">⚠️ Connection Error</div>
          <p className="text-gray-600">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Runtime Command Center
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                S7 Ops Dashboard — Full Monitoring
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-xs text-gray-500">
                Last Update:{" "}
                {health ? new Date(health.timestamp).toLocaleTimeString() : "—"}
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-xs text-gray-600">Live</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Health & Checkpoint */}
          <div className="lg:col-span-1 space-y-6">
            <HealthPanel health={health} />
            <CheckpointCard health={health} />
          </div>

          {/* Right Column - Timeline */}
          <div className="lg:col-span-2">
            <RuntimeTimeline events={events} />
          </div>
        </div>
      </div>
    </div>
  );
}
