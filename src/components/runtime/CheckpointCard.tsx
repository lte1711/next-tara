interface CheckpointCardProps {
  health: {
    checkpoint_age_sec: number | null;
    checkpoint_status: "FRESH" | "STALE" | "EXPIRED" | "UNKNOWN";
    last_health_ok: string | null;
  } | null;
}

export default function CheckpointCard({ health }: CheckpointCardProps) {
  if (!health) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="h-12 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  const getCheckpointColor = (status: string) => {
    switch (status) {
      case "FRESH":
        return "text-green-600 bg-green-50 border-green-200";
      case "STALE":
        return "text-yellow-600 bg-yellow-50 border-yellow-200";
      case "EXPIRED":
        return "text-red-600 bg-red-50 border-red-200";
      default:
        return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  const formatLastHealthOk = (timestamp: string | null) => {
    if (!timestamp) return "—";
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    } catch {
      return "—";
    }
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Checkpoint Heartbeat
        </h2>

        {/* Checkpoint Age */}
        <div
          className={`border rounded-lg p-4 mb-4 ${getCheckpointColor(health.checkpoint_status)}`}
        >
          <div className="text-center">
            <div className="text-4xl font-bold mb-2">
              {health.checkpoint_age_sec !== null
                ? `${health.checkpoint_age_sec}s`
                : "—"}
            </div>
            <div className="text-sm font-semibold">
              {health.checkpoint_status}
            </div>
          </div>
        </div>

        {/* Threshold Info */}
        <div className="space-y-2 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-gray-600">Fresh Threshold</span>
            <span className="font-mono text-gray-900">&lt; 15s</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-600">Stale Threshold</span>
            <span className="font-mono text-gray-900">15-60s</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-600">Critical Threshold</span>
            <span className="font-mono text-gray-900">&gt; 120s</span>
          </div>
        </div>

        {/* Last HEALTH_OK */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-gray-600">
              Last HEALTH_OK
            </span>
            <span className="text-sm text-gray-900 font-mono">
              {formatLastHealthOk(health.last_health_ok)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
