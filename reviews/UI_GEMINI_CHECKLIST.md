# Gemini UI Review Checklist — feature/ui-001-institutional-theme

Purpose: verifier (Gemini) should inspect the following aspects *without running the app*.

1. Contrast & Readability
   - Verify color variables in `src/app/globals.css` meet WCAG AA for normal text and AA/AAA for large text where applicable.
   - Confirm `--text` on `--bg` is high contrast.

2. Status Color Usage
   - Ensure `--warn`, `--kill`, `--downgrade` are used sparingly and map to clear semantic states.
   - Check `GlobalRiskBar` labels and borders are not using ambiguous colors.

3. Kill/Downgrade UX
   - Confirm the mode switch is explicit and labels are non-alarming for operators.
   - Suggest alternative labels if necessary (e.g., `CRITICAL` vs `KILL`).

4. Information Density
   - Ensure Binance layout placeholders would allow one-screen glance of: market chart, orderbook, positions.
   - Confirm font sizes and spacing in scaffold are adequate for dense operator UIs.

5. Non-Functional
   - No runtime wiring to WS or process control.
   - Files added: `src/components/GlobalRiskBar.tsx`, `src/components/BinanceLayout.tsx` (presentational only).

Action: Add notes/comments below and mark "Reviewed" with timestamp.

---

Reviewed: 

Notes:
