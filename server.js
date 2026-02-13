const http = require('http');
const { WebSocketServer } = require('ws');
const url = require('url');

const PORT = 8100;

// Mock Data
const healthData = {
  service_status: "running",
  last_heartbeat_age_sec: 2,
  last_heartbeat_ts: Math.floor(Date.now() / 1000),
  grade: "GOLD",
  mission: "Maintain 99.9% availability",
  next_milestone: "User Base Growth",
  next_milestone_eta: 3600 * 24 * 2 + 1800, // 2 days 30 mins
  last_update_ts: Math.floor(Date.now() / 1000),
};

const statusData = {
  status: "running",
  heartbeat_sec_ago: 2,
  last_heartbeat_age_sec: 2,
  last_heartbeat_ts: Math.floor(Date.now() / 1000),
  grade: "GOLD",
  mission: "Maintain 99.9% availability",
  cumulative_runtime_sec: 3600 * 48,
  cumulative_runtime_h: 48.0,
  progress_percent: 85.5,
  remaining_h: 12.0,
  restart_count: 3,
  target_h: 168,
  total_ticks: 15400,
  last_update_ts: Math.floor(Date.now() / 1000),
  milestones: { "24h": true, "72h": false, "168h": false },
};

const historyData = {
  points: Array.from({ length: 24 }, (_, i) => ({
    ts: Math.floor(Date.now() / 1000) - (23 - i) * 3600,
    runtime_h: 24 + i,
    cumulative_runtime_sec: (24 + i) * 3600,
    progress_168h_pct: ((24 + i) / 168) * 100,
    restart_count: Math.floor(i / 10),
  })),
};

const alertsData = {
  items: [
    { ts: Math.floor(Date.now() / 1000) - 300, event: "status_change", severity: "info", msg: "Service started" },
    { ts: Math.floor(Date.now() / 1000) - 1500, event: "alert", severity: "warn", msg: "High CPU usage detected" },
  ],
};

const stdoutData = { lines: ["[INFO] Server initialized.", "[INFO] Listening on port 8100"] };
const stderrData = { lines: [] };

// Helper to write JSON response
const jsonResponse = (res, data) => {
  res.writeHead(200, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-OPS-TOKEN',
  });
  res.end(JSON.stringify(data));
};

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;

  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-OPS-TOKEN',
    });
    res.end();
    return;
  }

  if (pathname === '/api/ops/health') return jsonResponse(res, healthData);
  if (pathname === '/api/ops/evergreen/status') return jsonResponse(res, statusData);
  if (pathname === '/api/ops/history') return jsonResponse(res, historyData);
  if (pathname === '/api/ops/alerts') return jsonResponse(res, alertsData);
  if (pathname === '/api/ops/logs/stdout') return jsonResponse(res, stdoutData);
  if (pathname === '/api/ops/logs/stderr') return jsonResponse(res, stderrData);

  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

const wss = new WebSocketServer({ server, path: '/ws/events' });

wss.on('connection', (ws) => {
  console.log('Client connected');
  ws.send(JSON.stringify({
    ts: Math.floor(Date.now() / 1000),
    event: "ws_connected",
    severity: "info",
    msg: "Connected to mock backend"
  }));

  const interval = setInterval(() => {
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({
        ts: Math.floor(Date.now() / 1000),
        event: "heartbeat",
        severity: "info",
        msg: "System healthy",
        cumulative_runtime_sec: statusData.cumulative_runtime_sec + Math.floor(process.uptime()),
      }));
    }
  }, 5000);

  ws.on('close', () => {
    console.log('Client disconnected');
    clearInterval(interval);
  });
});

server.listen(PORT, () => {
  console.log(`Backend server running at http://localhost:${PORT}`);
  console.log(`WebSocket server running at ws://localhost:${PORT}/ws/events`);
});
