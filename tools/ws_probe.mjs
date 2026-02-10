// Usage: node tools/ws_probe.mjs ws://localhost:8000/api/ws/events 10
import WebSocket from "ws";

const url = process.argv[2] || "ws://localhost:8000/api/ws/events";
const target = Number(process.argv[3] || "10");

let count = 0;
const ws = new WebSocket(url);

ws.on("open", () => {
  console.log(`[WS] CONNECTED url=${url}`);
});

ws.on("message", (data) => {
  count += 1;
  const line = data.toString();
  console.log(`[WS] #${count} ${line}`);
  if (count >= target) {
    console.log(`[WS] DONE collected=${count}`);
    ws.close();
  }
});

ws.on("close", (code, reason) => {
  console.log(`[WS] CLOSED code=${code} reason=${reason?.toString?.() ?? ""}`);
  process.exit(0);
});

ws.on("error", (err) => {
  console.log(`[WS] ERROR ${err?.message ?? err}`);
  process.exit(1);
});
