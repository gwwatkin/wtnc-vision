# task8 — Integration: styles, docs, component test, parity (Wave C)

**Model:** sonnet · Runs after Wave B lands. Gate: `npm run check` + backend pytest green +
parity checklist + docs.

Source of truth: all of `../requirements.md`, `../design.md`, `tasks/README.md`
(FROZEN-4 class names). Run FE commands from `collection/frontend/`; venv per CLAUDE.md.

## Owns (exclusive)
- `collection/frontend/styles.css`
- `collection/frontend/config.js` (comment only)
- `README.md`, `collection/README.md`, `collection/frontend/README.md`
- optional `collection/frontend/tests/backend-url-dom.test.js`

## Do

1. **`styles.css`** — add the FROZEN-4 classes (the only new CSS):
   - **Landing**: `.landing` (centered, roomy), `.landing__links` (stacked), `a.landing__link`
     (card-like tappable link).
   - **BackendSettings**: `.backend-settings` (container), `.backend-settings__summary` (row,
     flex, small), `.backend-settings__label`, `.backend-settings__dot` + `--ok` (green) /
     `--bad` (red) / `--checking` (grey), `.backend-settings__toggle` (bare button),
     `.backend-settings__panel` (input+buttons row), `.backend-settings__input`,
     `.backend-settings__save`, `.backend-settings__default`.
   - **Download**: `.results__download` (inline group in the toolbar), `button.download-btn`
     (reuse the toolbar/button look; muted `:disabled`).
   Match the existing visual language (spacing, colors) — parity, not a redesign.

2. **`config.js`** — update the `BACKEND_URL` comment to note it is now the **default
   fallback** used when no `wtnc_backend_url` cookie is set (still `""` = same-origin). Do not
   change any values.

3. **Docs (NFR6):**
   - `collection/README.md` and top-level `README.md`: describe the three pages (landing →
     collector / viewer), how to set the back-end URL from the UI (collapsible panel, persists
     via cookie, live re-apply), the CORS note (add the FE origin to
     `config.yaml → server.allowed_origins`, exact origin), and how to **download** crossings
     (CSV/JSON from the viewer).
   - `collection/frontend/README.md`: note the new files (`backend-url.js`,
     `components/common/BackendSettings.js`, `components/results/download.js`, `collect.*`,
     `view.*`), that `main.js` is gone, and that `api.js` routes every call through `BASE()`.

4. **(Optional) component/DOM test** for `downloadResults` or a `BackendSettings` render
   against the happy-dom shim (SC-style coverage). Keep `npm run unit` < 10 s.

5. **Wire-up & parity verification** (record results in the PR / checkpoint notes):
   - `grep` the FE for any page mounting **both** roots and any bare same-origin
     `fetch('/…')` or returned `/frames/image` — expect **none** (SC7).
   - `run.sh` starts the app with no node involvement (NFR1).
   - Manual (SC1–SC6): landing links open each app standalone; set a URL, reload, value
     retained, DevTools Network shows **every** call (incl. `frameUrl` images) on the new
     base; wrong URL → red indicator; on an edited/manual/reordered/deleted run, Download CSV
     and JSON match the timeline (deleted excluded, order honored); empty run downloads valid
     empty files; collector captures live from camera + video with results on the viewer
     (same back-end).

## Done when
- `npm run check` and `.venv/bin/pytest collection/backend/tests/` are green; the grep checks
  pass; the parity checklist is walked and noted; docs updated. Single-implementation end
  state — no unified page, no bare paths (NFR5).
