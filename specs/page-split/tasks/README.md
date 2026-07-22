# Tasks — Page Split, Configurable Back-end URL & Crossings Download

The map for the parallel-agent run. **Read this before spawning any agent.** Source of
truth is `../requirements.md` + `../design.md`; this file adds the dependency graph,
execution waves, exclusive-file ownership, and the **frozen contracts** every task codes
against.

## Execution waves

| Wave | Tasks | Model | Gate |
|------|-------|-------|------|
| **A — Scaffold (blocking)** | task1 | sonnet | must land + `npm run check` green (stubs only) before Wave B starts |
| **B — Parallel** | task2 · task3 · task4 · task5 · task6 · task7 | sonnet (task4 haiku-ok) | FE tasks pass `npm run typecheck`; task2 also `npm run unit`; task7 passes backend pytest |
| **C — Integration** | task8 | sonnet | `npm run check` green + backend pytest + parity checklist + docs |

```
        task1  (scaffold: backend-url.js + test, types, STUB BackendSettings.js & download.js)
          │
   ┌──────┼──────┬──────┬──────┬──────┐
 task2  task3  task4  task5  task6   task7            ← Wave B (exclusive file owners)
 api+   Backend Pages  Capture Results Backend
 dl     Settings &entry App    App    export
   └──────┴──────┴──────┴──────┴──────┘
          │
        task8  (styles.css, config.js, docs, component test, parity, grep)
```

Wave B tasks **fill stubs task1 created** (or edit existing files) — each owns its file(s)
exclusively and never touches another task's file. Because task1 provides `backend-url.js`
in full and stubs `BackendSettings.js` / `download.js`, all cross-task imports resolve and
`tsc` is incremental from the start. task5/task6 render `<${BackendSettings}/>` against its
**frozen `{}` props**, not its implementation, so they are Wave-B-parallel-safe with task3.

## Delegation protocol (per CLAUDE.md)

- Give each agent its `taskN.md` **plus** `requirements.md` + `design.md` as source of truth.
- **Contracts are frozen for this run.** An agent that believes a frozen signature is
  genuinely wrong must **stop and flag it**, never silently diverge — siblings depend on it.
- One wave at a time; **gate each wave on explicit human go-ahead**; commit + push a
  checkpoint between waves. Keep subagent scratch/artifacts out of commits.
- FE components import Preact primitives from `../../vendor/preact-setup.js` and annotate
  props via `import('…/types').XxxProps` (extension-less), matching the existing codebase.
- **Do not touch the CV engine, frame pipeline, dedup/candidates, `models.py`,
  `config.py`, or the `runs/` layout** — this spec is additive on the back-end (design §8).

## Exclusive file ownership

| Task | Owns (create/edit) | Deletes |
|------|--------------------|---------|
| task1 | `backend-url.js`, `tests/backend-url.test.js`, `types.d.ts` (add typedefs), **stub** `components/common/BackendSettings.js`, **stub** `components/results/download.js` | — |
| task2 | `api.js`, `components/results/download.js` (fill) | — |
| task3 | `components/common/BackendSettings.js` (fill) | — |
| task4 | `index.html` (→ landing), `collect.html`, `view.html`, `collect.js`, `view.js` | `main.js` |
| task5 | `components/capture/CaptureApp.js` | — |
| task6 | `components/results/ResultsApp.js` | — |
| task7 | `collection/backend/app.py`, `collection/backend/config.yaml`, `collection/backend/tests/test_export.py` | — |
| task8 | `styles.css`, `config.js` (comment), `README.md`, `collection/README.md`, `collection/frontend/README.md`, optional `tests/backend-url-dom.test.js` | — |

No two Wave-B tasks share a file. `styles.css` is edited **only** by task8 (Wave C) — Wave B
components must reuse existing classes or the **frozen class names in FROZEN-4**; a component
that needs a class not listed there **flags it to task8** rather than editing `styles.css`.

---

## FROZEN-1 · `backend-url.js` surface (design §3)

Full implementation lands in task1. Everyone else imports from it; **do not change names**.

```
normalizeBackendUrl(raw: string): string   // trim; strip one trailing '/'; '' = same-origin
getBackendUrl(): string                     // cookie value (decoded+normalized) else config default
setBackendUrl(url: string): void            // write cookie + notify subscribers ('' clears override)
onBackendUrlChange(cb: (url:string)=>void): () => void   // returns unsubscribe
backendLabel(url: string): string           // '' → 'same-origin', else host[:port]
```

- Cookie name **`wtnc_backend_url`**; `path=/; max-age=31536000; SameSite=Lax`; value
  `encodeURIComponent(url)`.
- Default = `window.COLLECTION_CONFIG?.BACKEND_URL ?? ''` (config.js stays the fallback).

## FROZEN-2 · `api.js` surface (design §4 — supersedes fe-modernization FROZEN-6)

Every existing function keeps its name/signature; the change is **where the base comes from**
and **that all paths use it**:

- `const BASE = () => getBackendUrl();` (imported from `backend-url.js`).
- `_fetch(path, init)` prepends `BASE()` **once**; all `_fetch` callers inherit it.
- `checkHealth` uses `fetch(BASE() + '/health')`; `frameUrl` returns `BASE() + '/frames/image?…'`.
- `postFrame`/`uploadRoster` pass `'/frames'`/`'/roster'` to `_fetch` and **drop** their manual
  `${BASE()}` prefixes (no double base).
- **New:** `exportUrl(run, format): string` → `BASE()+'/results/export?run=…&format=…'`;
  `fetchExportBlob(run, format): Promise<Blob>` (pure fetch via `_fetch`, returns `resp.blob()`).

After task2, **no bare same-origin path may remain** in `api.js` (SC7).

## FROZEN-3 · Export endpoint (design §6.1 — task7 back-end, task2 front-end call)

```
GET /results/export?run=<label>&format=csv|json
```
- Server composes crossings via a refactored `_compose_crossings(run)` shared with `GET /results`.
- **CSV**: `media_type="text/csv"`, header row **`number,time,name,category`**, one row per
  crossing in **`order_key` ascending**, written with the stdlib `csv` module. Empty number/
  name/category allowed. `Content-Disposition: attachment; filename="crossings_<safe>.csv"`.
- **JSON**: body identical to `GET /results` (`{"run","crossings":[…]}`); disposition
  `crossings_<safe>.json`.
- **Empty / engine-disabled** → HTTP 200 with header-only CSV / `{"run":…, "crossings":[]}`.
- **Unknown format** → 400 `{"status":"error","detail":"format must be 'csv' or 'json'"}`.
- Route registered **before** the StaticFiles mount.

## FROZEN-4 · New CSS class names (task8 owns `styles.css`; Wave B uses these verbatim)

Components must emit exactly these classes; task8 defines them.

```
Landing (task4):   .landing · .landing__links · a.landing__link
BackendSettings (task3):
  .backend-settings · .backend-settings__summary · .backend-settings__label
  .backend-settings__dot  (+ modifier --ok | --bad | --checking)
  .backend-settings__toggle · .backend-settings__panel
  .backend-settings__input · .backend-settings__save · .backend-settings__default
Download (task6 ResultsApp toolbar): .results__download · button.download-btn
```

Reuse existing button/toolbar styling where sensible; the above are the only **new** classes.

## FROZEN-5 · Page set & mounts (design §2)

- `index.html` — landing: links only, **no** `config.js`, **no** module, **no** roots.
- `collect.html` — `<div id="capture-root">`, then `config.js` (classic) then
  `collect.js` (`type="module"`). **No** datalist.
- `view.html` — `<div id="results-root">` + `<datalist id="roster-numbers">`, then
  `config.js` then `view.js` (module).
- `collect.js` → `render(h(CaptureApp, null), document.getElementById('capture-root'))`.
- `view.js` → `render(h(ResultsApp, null), document.getElementById('results-root'))`.
- `main.js` is **deleted** (it mounted both roots).

## FROZEN-6 · `BackendSettings` props (design §5)

`export interface BackendSettingsProps {}` — self-contained via `backend-url.js` + `api.checkHealth`.
Rendered as `<${BackendSettings} />` in both `CaptureApp` and `ResultsApp`.

## Shared conventions

- **No edits to** `results/data.js`, the vendored files, `models.py`, `config.py`, the engine,
  or the `runs/` layout. Back-end changes are limited to task7's three files.
- Every new/edited FE `.js` passes `npm run typecheck` before its task is done. task1 adds a
  passing `node --test` suite for `backend-url.js`; task2 keeps `npm run unit` green.
- Venv commands per CLAUDE.md: `.venv/bin/pytest`, `.venv/bin/python` from repo root; never
  `source … && …`.

---
