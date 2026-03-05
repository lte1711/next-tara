# NEXT-TRADE UI Restart Runbook

Document ID: NEXT-TRADE-CC-OPS-RUNBOOK-UI-RESTART-042  
Status: Operational  
Effective Date: 2026-03-03

## Purpose

Standard restart and recovery procedures for recurring UI incidents:

- 038: UI unchanged after patch
- 041: `/_next/static/*` responds `400 Bad Request`
- 035: Recharts `width(-1)/height(-1)` warning

---

## Scenario A (038): UI not reflecting recent code changes

Symptoms:

- Page looks unchanged after successful build
- New route/component updates not visible

Procedure:

1. Kill old node processes serving `3001`.
2. Confirm `:3001` has no lingering LISTEN.
3. Rebuild and restart from UI root:
   - `npm run build`
   - `npm run start -- -p 3001`
4. Validate route targets:
   - `/command-center` uses `src/app/command-center/page.tsx`
   - `/command-center/events` uses `src/app/command-center/events/page.tsx`
5. Hard refresh browser (`Ctrl+Shift+R`).

Pass criteria:

- Correct UI appears with current route structure.

---

## Scenario B (041): `/_next/static/*` returns 400

Symptoms:

- HTML returns 200
- CSS/JS chunk requests under `/_next/static/*` return 400
- UI shows unstyled plain text

Procedure:

1. Stop node process on `3001`.
2. Remove stale build output:
   - delete `.next`
3. Rebuild and restart:
   - `npm run build`
   - `npm run start -- -p 3001`
4. Verify the HTML-referenced asset hashes exist in `.next/static/*`.
5. Verify status code:
   - `/_next/static/css/...` -> 200/304
   - `/_next/static/chunks/...` -> 200/304
6. Confirm no middleware/rewrite/basePath/assetPrefix rule mutates `/_next`.

Pass criteria:

- CSS/JS assets load successfully and UI styling recovers.

---

## Scenario C (035): Recharts `width(-1)/height(-1)` warning

Symptoms:

- Build/runtime warning from Recharts container sizing

Procedure (v1.7 frozen baseline):

1. Use fixed chart dimensions (`720x260`) in `src/app/ops/page.tsx`.
2. Wrap chart in `overflow-x-auto`.
3. Keep `min-h-0` in relevant flex/grid card containers.
4. Rebuild:
   - `npm run build`

Pass criteria:

- Recharts warning no longer appears.

---

## Common Validation Checklist

1. `npm run build` success
2. `http://localhost:3001/command-center` reachable
3. `http://localhost:3001/command-center/events` reachable
4. Browser console free of:
   - `/_next/static/* 400`
   - Recharts `width(-1)/height(-1)`

