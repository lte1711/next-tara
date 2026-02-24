interface HealthPanelProps {
  health: {
    engine_pid: number | null;
    engine_alive: boolean;
    checkpoint_status: "FRESH" | "STALE" | "EXPIRED" | "UNKNOWN";
    health_status: "OK" | "WARN" | "CRITICAL";
    restart_count: number;
    flap_detected: boolean;
    task_state: string;
  } | null;
}

export default function HealthPanel({ health }: HealthPanelProps) {
  if (!health) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div className="h-8 bg-gray-200 rounded mb-2"></div>
        </div>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "OK":
        return "text-green-600 bg-green-100";
      case "WARN":
        return "text-yellow-600 bg-yellow-100";
      case "CRITICAL":
        return "text-red-600 bg-red-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "OK":
        return "✓";
      case "WARN":
        return "⚠";
      case "CRITICAL":
        return "✕";
      default:
        return "?";
    }
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6">
        {/* Overall Status LED */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">System Health</h2>
          <div
            className={`px-4 py-2 rounded-full font-bold ${getStatusColor(health.health_status)}`}
          >
            <span className="text-xl mr-2">
              {getStatusIcon(health.health_status)}
            </span>
            {health.health_status}
          </div>
        </div>

        {/* Engine Status */}
        <div className="space-y-4">
          <div className="border-b border-gray-200 pb-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">
                Engine Process
              </span>
              <div className="flex items-center space-x-2">
                <div
                  className={`w-2 h-2 rounded-full ${health.engine_alive ? "bg-green-500" : "bg-red-500"}`}
                ></div>
                <span
                  className={`text-sm font-semibold ${health.engine_alive ? "text-green-600" : "text-red-600"}`}
                >
                  {health.engine_alive ? "ALIVE" : "DEAD"}
                </span>
              </div>
            </div>
            <div className="mt-2">
              <span className="text-xs text-gray-500">PID: </span>
              <span className="text-sm font-mono text-gray-900">
                {health.engine_pid || "—"}
              </span>
            </div>
          </div>

          {/* Task State */}
          <div className="border-b border-gray-200 pb-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">
                Task Scheduler
              </span>
              <span
                className={`text-sm font-semibold px-2 py-1 rounded ${
                  health.task_state === "Running"
                    ? "bg-blue-100 text-blue-700"
                    : health.task_state === "Ready"
                      ? "bg-gray-100 text-gray-700"
                      : "bg-red-100 text-red-700"
                }`}
              >
                {health.task_state}
              </span>
            </div>
          </div>

          {/* Restart Count */}
          <div className="border-b border-gray-200 pb-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">
                Recent Restarts
              </span>
              <span
                className={`text-lg font-bold ${
                  health.restart_count === 0
                    ? "text-green-600"
                    : health.restart_count < 3
                      ? "text-yellow-600"
                      : "text-red-600"
                }`}
              >
                {health.restart_count}
              </span>
            </div>
            <div className="mt-1 text-xs text-gray-500">Last 50 events</div>
          </div>

          {/* Flap Detection */}
          {health.flap_detected && (
            <div className="bg-red-50 border border-red-200 rounded p-3">
              <div className="flex items-start">
                <span className="text-red-600 text-xl mr-2">⚠</span>
                <div>
                  <div className="text-sm font-semibold text-red-800">
                    Anti-Flap Triggered
                  </div>
                  <div className="text-xs text-red-600 mt-1">
                    Excessive restart detected. Check logs immediately.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
