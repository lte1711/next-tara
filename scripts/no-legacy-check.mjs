import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = join(process.cwd(), "src");
const blockedPatterns = [
  "/api/state",
  "/api/history",
  "/api/dev",
  "state/engine",
  "history/risks",
  "dev/emit-event",
];

const allowedFiles = new Set([
  join(process.cwd(), "src", "lib", "api.ts"),
]);

const targetExtensions = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs"]);
const violations = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const fullPath = join(dir, name);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      walk(fullPath);
      continue;
    }

    const ext = fullPath.slice(fullPath.lastIndexOf("."));
    if (!targetExtensions.has(ext)) continue;
    if (allowedFiles.has(fullPath)) continue;

    const content = readFileSync(fullPath, "utf-8");
    const lines = content.split(/\r?\n/);
    lines.forEach((line, index) => {
      for (const pattern of blockedPatterns) {
        if (line.includes(pattern)) {
          violations.push({ file: fullPath, line: index + 1, pattern, source: line.trim() });
        }
      }
    });
  }
}

walk(root);

if (violations.length > 0) {
  console.error("[contract:guard] Legacy API usage detected:");
  for (const v of violations) {
    console.error(`- ${v.file}:${v.line} -> ${v.pattern}`);
    console.error(`  ${v.source}`);
  }
  process.exit(1);
}

console.log("[contract:guard] PASS (no forbidden legacy endpoint usage)");
