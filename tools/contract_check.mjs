const base = (process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "http://127.0.0.1:8100").replace(/\/+$/, "");

const endpoints = [
  `${base}/api/v1/ops/health`,
  `${base}/api/v1/ops/state`,
  `${base}/api/v1/ops/positions`,
  `${base}/api/v1/ops/risks?limit=20`,
];

let failed = false;
for (const url of endpoints) {
  try {
    const response = await fetch(url, { method: "GET" });
    console.log(`${url} -> ${response.status}`);
    if (response.status !== 200) failed = true;
  } catch (error) {
    failed = true;
    console.log(`${url} -> FAIL ${error?.message || error}`);
  }
}

if (failed) {
  process.exit(2);
}

console.log("contract:check PASS");
