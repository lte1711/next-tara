import { useState } from "react";

interface RuntimeEvent {
  ts: string;
  level: "INFO" | "WARN" | "ERROR" | "CRITICAL";
  action: string;
  pid?: number;
  old_pid?: number | null;
  new_pid?: number | null;
}

interface RuntimeTimelineProps {
  events: RuntimeEvent[];
}

export default function RuntimeTimeline({ events }: RuntimeTimelineProps) {
  const [levelFilter, setLevelFilter] = useState<string>("ALL");
  const [actionFilter, setActionFilter] = useState<string>("");

  const getLevelColor = (level: string) => {
    switch (level) {
      case "INFO":
        return "bg-blue-100 text-blue-800";
      case "WARN":
        return "bg-yellow-100 text-yellow-800";
      case "ERROR":
        return "bg-red-100 text-red-800";
      case "CRITICAL":
        return "bg-red-200 text-red-900";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case "HEALTH_OK":
        return "✓";
      case "ENGINE_START":
        return "▶";
      case "RESTART":
        return "🔄";
      case "PIDFILE_MISSING":
        return "⚠";
      case "FLAP_DETECTED":
        return "🚨";
      case "WATCHDOG_START":
        return "👁";
      case "EXIT_ALREADY_RUNNING":
        return "🔒";
      default:
        return "•";
    }
  };

  const formatTimestamp = (ts: string) => {
    try {
      const date = new Date(ts);
      return date.toLocaleTimeString();
    } catch {
      return ts;
    }
  };

  const getEventDetails = (event: RuntimeEvent) => {
    const parts: string[] = [];
    if (event.pid !== undefined) parts.push(`PID: ${event.pid}`);
    if (event.old_pid !== undefined)
      parts.push(`Old: ${event.old_pid || "null"}`);
    if (event.new_pid !== undefined) parts.push(`New: ${event.new_pid}`);
    return parts.join(", ");
  };

  const filteredEvents = events.filter((event) => {
    if (levelFilter !== "ALL" && event.level !== levelFilter) return false;
    if (
      actionFilter &&
      !event.action.toLowerCase().includes(actionFilter.toLowerCase())
    )
      return false;
    return true;
  });

  // Get unique actions for filter
  const uniqueActions = Array.from(new Set(events.map((e) => e.action))).sort();

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Runtime Timeline
          </h2>
          <div className="text-sm text-gray-500">
            {filteredEvents.length} of {events.length} events
          </div>
        </div>

        {/* Filters */}
        <div className="mb-4 flex flex-wrap gap-3">
          {/* Level Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">Level:</label>
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All</option>
              <option value="INFO">INFO</option>
              <option value="WARN">WARN</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>

          {/* Action Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">Action:</label>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Actions</option>
              {uniqueActions.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
          </div>

          {/* Reset */}
          {(levelFilter !== "ALL" || actionFilter !== "") && (
            <button
              onClick={() => {
                setLevelFilter("ALL");
                setActionFilter("");
              }}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              Reset Filters
            </button>
          )}
        </div>

        {/* Timeline */}
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {filteredEvents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No events match the current filters
            </div>
          ) : (
            filteredEvents.map((event, index) => (
              <div
                key={index}
                className="flex items-start space-x-3 p-3 rounded hover:bg-gray-50 border border-gray-100"
              >
                {/* Timestamp */}
                <div className="flex-shrink-0 w-24 text-xs text-gray-500 font-mono pt-1">
                  {formatTimestamp(event.ts)}
                </div>

                {/* Level Badge */}
                <div className="flex-shrink-0">
                  <span
                    className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getLevelColor(event.level)}`}
                  >
                    {event.level}
                  </span>
                </div>

                {/* Action */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-lg">
                      {getActionIcon(event.action)}
                    </span>
                    <span className="font-semibold text-gray-900">
                      {event.action}
                    </span>
                  </div>
                  {getEventDetails(event) && (
                    <div className="text-xs text-gray-600 mt-1 font-mono">
                      {getEventDetails(event)}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Legend */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="text-xs text-gray-500">
            <div className="font-semibold mb-2">Event Icons:</div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="font-mono">✓</span> HEALTH_OK
              </div>
              <div>
                <span className="font-mono">▶</span> ENGINE_START
              </div>
              <div>
                <span className="font-mono">🔄</span> RESTART
              </div>
              <div>
                <span className="font-mono">⚠</span> PIDFILE_MISSING
              </div>
              <div>
                <span className="font-mono">🚨</span> FLAP_DETECTED
              </div>
              <div>
                <span className="font-mono">👁</span> WATCHDOG_START
              </div>
              <div>
                <span className="font-mono">🔒</span> EXIT_ALREADY_RUNNING
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
