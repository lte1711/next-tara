feat(ui): institutional OrderPanel validation + layout hardening (UI-011~015)

Summary

- Stabilizes the institutional `OrderPanel` input layer: separates raw→parsed→formatted flows, adds inline validation and blur hints, and hardens Qty/Price layout to prevent overflow.
- Fixes a layout bug causing `Price` to overflow the card by enforcing a 2-column grid (`1fr 1fr`), `min-width:0` on wrappers, and `width:100%` + `box-sizing:border-box` on inputs.
- Includes deterministic SSR snapshots for NORMAL/DOWNGRADE/KILL modes captured locally and packaged under `evidence/ui/`.

Files changed (high level)

- `src/components/OrderPanel.tsx` (layout, validation, raw/parsed/formatted refactor)
- `src/context/RiskContext.tsx` (mock provider support during dev evidence capture)
- docs: `docs/TICKET-UI-015.md` (ticket + verification)
- `.gitignore` updated to keep `logs/` and `evidence/` out of VCS

Verification & Evidence

- SSR HTML snapshots (local):
  - `logs/ui_institutional_orderpanel_ui015_ok.html`
  - `logs/ui_institutional_orderpanel_ui015_downgrade.html`
  - `logs/ui_institutional_orderpanel_ui015_kill.html`
- Packaged evidence: `evidence/ui/UI_015_SSR_EVIDENCE.zip`

Notes

- I validated the fix locally and captured SSR snapshots. The repository in this environment appears to lack an `origin` remote, so `git push` / `gh pr create` cannot be executed from here. Please run the provided `gh` command locally or in CI where `origin` and GitHub auth are configured.

Suggested `gh` command (run locally):

```powershell
git checkout feature/ui-001-institutional-theme
# ensure branch up-to-date with remote
git pull origin feature/ui-001-institutional-theme
git push origin feature/ui-001-institutional-theme

gh pr create `
  --title "feat(ui): institutional OrderPanel validation + layout hardening (UI-011~015)" `
  --body-file ./PR_BODY_UI_015.md `
  --base main `
  --head feature/ui-001-institutional-theme `
  --reviewer ui-team `
  --reviewer design-lead `
  --reviewer qa
```

If you want, I can still prepare the PR locally (create the body file and verify diffs). To actually open the PR I need `origin` and GitHub auth in this environment.
