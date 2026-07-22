# Requirements — Page Split, Configurable Back-end URL & Crossings Download

## 1. Background & Purpose

Today the front-end is a **single page**. `collection/frontend/index.html` mounts *both*
Preact roots on the same document:

```html
<div id="capture-root"></div>   <!-- CaptureApp: camera/video → live CV processing -->
<div id="results-root"></div>   <!-- ResultsApp: timeline, sidebar, frame browser -->
```

The FastAPI back-end serves that page via a `StaticFiles` mount at `/` **and** serves the
API from the same origin. Two consequences shape this spec:

- **The two apps are welded together.** An operator running the collector sees the results
  timeline on the same screen, and there is no way to open *just* the viewer (e.g. for a
  results table, or a second person reviewing) without also loading the capture machinery.
- **The back-end origin is hard-wired.** `config.js` ships `BACKEND_URL: ""` (same-origin),
  and `api.js` is *inconsistent* about honoring it — the capture calls route through a
  `BASE()` helper, but every results read (`/runs`, `/results`, `/candidates`, `/status`,
  `/frames`, `/roster`) and the frame-image URL builder use **bare, same-origin paths**.
  There is no way for an operator to point the front-end at a back-end running elsewhere.

Separately, **there is no way to get the crossings out.** The back-end already produces
`crossings.json` (rich reviewed state) and `crossings.csv` (append-only log) per run on
disk, and `/results` serves the composed, reviewed crossing list — but the viewer offers
no download. Results leave the machine only by someone copying files off disk.

This iteration restructures the front-end into **three standalone pages** — a landing page
that links to the other two, a **collector** page, and a **viewer** page — lets **each of
the collector and viewer choose its back-end URL from the UI** (persisted so it survives
reloads), and adds a **crossings download** to the viewer. Live CV processing stays exactly
where it is today: on the collector page, driven by the camera (and by uploading a video
file).

This document is *what & why*. The three product decisions already made during scoping are
recorded in §3; everything mechanical (page filenames, how the URL is stored and injected
into the fetch layer, the download endpoint shape, CORS specifics) belongs in `design.md`.

## 2. Goals

- **G1 — Three separate pages.** The unified page is split into a **landing** page whose
  only job is to link to the other two, a **collector** page (capture + live processing
  only), and a **viewer** page (results/timeline/review only). Each page loads only the
  code it needs.
- **G2 — Operator-chosen back-end URL, persisted.** On both the collector and the viewer,
  the operator can set the back-end base URL from the UI. The choice persists across
  reloads (cookie) and is honored by **every** request that page makes — no bare
  same-origin paths left behind.
- **G3 — Download crossings from the viewer.** The viewer can download the current run's
  crossings as **CSV and as JSON**, reflecting the reviewed state (edits, deletions,
  order) — the same picture the timeline shows, not the raw append log.
- **G4 — Processing unchanged.** Live CV processing continues to run exactly as today,
  on the collector page: frames are captured live from the camera, or by uploading a
  video file, and uploaded to the back-end where the engine reads numbers. No processing
  moves to the viewer, the landing page, or a separate service; the pipeline, its config,
  and its on-disk layout are untouched.
- **G5 — Behavior parity within each page.** Splitting is a re-hosting, not a redesign:
  every capture behavior lands on the collector page and every review behavior lands on
  the viewer page, each working as it does today.

## 3. Resolved Decisions

Made by the product owner during scoping; baked into the requirements below.

- **D1 — Separate HTML files (not an SPA router).** The split is physical: a landing
  `index.html` plus one HTML file per app (e.g. `collect.html`, `view.html`), each mounting
  only its own Preact root. This matches the current buildless, checked-in ES-module +
  Preact/htm setup — no client-side router, no bundler. Exact filenames are a design detail.
- **D2 — Same back-end, add a download (no cross-backend transfer).** The collector and
  viewer normally point at the **same** back-end: the collector's captured frames are
  processed there (crossings are "uploaded" via the existing frame-upload → engine path),
  and the viewer reads/downloads from there. The configurable URL exists to decouple *where
  the front-end is hosted* from *which API it talks to* — **not** to move crossings between
  two independent back-ends. No import endpoint, no portable bundle format this iteration.
- **D3 — Download is CSV *and* JSON.** The viewer offers both: a CSV (number, time, name,
  category, …) for spreadsheets, and a full JSON crossing record for archival/re-use. Both
  reflect current reviewed state.
- **D4 — Back-end URL persists in a cookie.** The chosen URL is stored in a cookie so it
  survives reloads and new tabs on the same browser. (Storage mechanism is fixed by the
  product owner; the design wires it into the fetch layer.)

## 4. Key Facts (what already exists to build on)

- **A1 — Both apps are already independent Preact roots.** `CaptureApp` and `ResultsApp`
  are self-contained components mounted separately in `main.js`; they share no state, only
  the `COLLECTION_CONFIG` globals, an `api.js` module, and a static `<datalist>` used by the
  results overlays. Splitting them onto separate pages is a mount-point and asset-loading
  change, not a component rewrite.
- **A2 — A `BASE()` indirection already exists, just unused by half the layer.** `api.js`
  already reads `COLLECTION_CONFIG.BACKEND_URL` via a `BASE()` helper for capture calls.
  The results reads and `frameUrl()` bypass it with bare paths. Making the URL truly
  configurable is primarily *routing every call through one base* plus sourcing that base
  from persisted operator input instead of a frozen constant.
- **A3 — Crossings already exist server-side in reviewed form.** `/results?run=` composes
  the current crossing list (numbers, times, names, order, edited/source flags, excluding
  soft-deleted) from engine state; `crossings.json` on disk holds the rich state and
  `crossings.csv` is an append-only log. A download that matches the timeline should derive
  from the composed/reviewed state, not the append log.
- **A4 — The back-end is served buildless via StaticFiles and has CORS middleware.** The
  app mounts `../frontend` at `/` (html=True) and already installs `CORSMiddleware` with
  `cfg.allowed_origins`. Serving new HTML files is "add files"; allowing a front-end hosted
  on a different origin to call the API is a CORS-configuration concern the design must
  address.
- **A5 — The capture page's live behaviors are the parity bar for the collector.** Camera
  preview, source selector, video-file ingest, capture start/stop with back-pressure and
  in-flight/frame counters, roster upload + status, and the health probe — these must all
  survive on the collector page.
- **A6 — The results page's review behaviors are the parity bar for the viewer.** Run
  selector, live polling with per-concern re-render economy, timeline with packs/lanes/gap
  separators, candidate rendering + toggle, sidebar edit/delete/reorder, frame browser
  overlay + manual crossing creation, and the status readout — these must all survive on
  the viewer page.
- **A7 — Environment (unchanged).** One session, hundreds of crossings, thousands of
  frames, CPU-only laptop, single operator, latest-Chromium-class browser. No
  legacy-browser support required.

## 5. Functional Requirements

### 5.1 Page split & landing (G1)
- **FR1** — The application is served as three pages: a **landing** page, a **collector**
  page, and a **viewer** page. Opening the back-end root serves the landing page.
- **FR2** — The landing page's primary content is clear links to the collector page and the
  viewer page (with enough labeling that an operator knows which is which). It does not load
  the capture or results app code.
- **FR3** — The collector page mounts only the capture app; it does **not** load or render
  the results timeline/sidebar/frame-browser. The viewer page mounts only the results app;
  it does **not** load or render the camera/capture machinery.
- **FR4** — Each of the collector and viewer offers a way to navigate back to the landing
  page (and thereby to the other app).
- **FR5** — Starting the app is unchanged for the operator: `run.sh` → one back-end process
  serving both the API and the three static pages. No new run step, no node in the run loop.

### 5.2 Configurable back-end URL (G2)
- **FR6** — The collector and the viewer each expose a UI control to view and set the
  back-end base URL the page will talk to.
- **FR7** — The chosen URL persists (cookie) and is applied on the next load without
  re-entry. A page with no stored value falls back to same-origin (today's behavior), so a
  default install "just works" with nothing configured.
- **FR8** — **Every** request a page issues — reads, mutations, uploads, and constructed
  image/frame URLs — targets the configured base. No call path may remain hard-wired to
  same-origin. (This closes the current `api.js` inconsistency.)
- **FR9** — The page surfaces whether the configured back-end is reachable (a health
  indicator), so a wrong or unreachable URL is diagnosable from the UI rather than as silent
  failures.
- **FR10** — Changing the URL takes effect for subsequent requests without requiring the
  operator to hand-edit files or restart the back-end. (Whether it applies live or on the
  next reload is a design choice, but no file editing.)
- **FR11** — When the front-end is served from one origin and points at a back-end on
  another, the cross-origin requests succeed against a correctly configured back-end. The
  spec defines what "correctly configured" means (CORS) and documents it; it does not
  require the default localhost install to change.

### 5.3 Crossings download from the viewer (G3)
- **FR12** — The viewer provides a control to download the currently selected run's
  crossings as **CSV** and as **JSON**.
- **FR13** — Both downloads reflect the **current reviewed state** of the run: applied
  number edits, manual/promoted crossings, ordering overrides, and exclusion of
  soft-deleted crossings — i.e. what the viewer's timeline shows, not the raw append-only
  log.
- **FR14** — The CSV is spreadsheet-friendly (a header row; at least number, time, and — when
  a roster matched — name and category). The JSON carries the full per-crossing record the
  viewer already receives. Exact columns/fields are frozen in the design.
- **FR15** — Downloading targets the configured back-end (FR8) and names the file
  recognizably per run (e.g. includes the run label). Downloading a run with no crossings
  yields a valid empty export (header-only CSV / empty list JSON), not an error.

### 5.4 Processing stays put (G4)
- **FR16** — Live CV processing remains on the collector page and runs as today: frames
  captured live from the camera are uploaded and processed by the back-end engine; choosing
  a video file and starting capture streams its frames the same way. No processing moves off
  the collector page.
- **FR17** — The CV pipeline, its configuration, the frame-upload contract, the engine, and
  the on-disk run layout are unchanged by this spec. The only back-end additions are what the
  download (FR12–FR15) and cross-origin serving (FR11) require.

## 6. Non-Functional Requirements

- **NFR1 (Buildless & lean, unchanged)** — The three pages stay buildless: checked-in ES
  modules served by StaticFiles, no bundler, no node in the run/deploy loop (parity with the
  current setup). Splitting must not regress first-load weight of either app — each page
  should load *less* than today's combined page, not more.
- **NFR2 (Parity)** — Within each page, behavior and performance match today: the viewer's
  polling economy (no DOM churn on unchanged payloads) and the collector's capture
  back-pressure/counters are preserved.
- **NFR3 (No silent misconfig)** — A wrong/unreachable back-end URL is visibly diagnosable
  (FR9), never a blank page with no explanation.
- **NFR4 (Back-end isolation)** — The CV pipeline, engine, and Python workflow are untouched
  except for the additive download endpoint(s) and any CORS/config needed for FR11. No
  changes to frame processing behavior or on-disk layout.
- **NFR5 (Single-implementation end state)** — When the split lands, the old unified page is
  gone: no page that mounts both roots, no dead `main.js` mounting both, no bare same-origin
  paths left in the fetch layer.
- **NFR6 (Docs)** — `README.md` / `collection/README.md` are updated to describe the three
  pages, how to set the back-end URL, the cross-origin/CORS note, and how to download
  results.

## 7. Scope

### 7.1 This phase
- Landing page + collector page + viewer page as separate HTML files, each mounting only
  its own root; back-to-landing navigation (G1).
- A back-end-URL control on the collector and viewer, persisted to a cookie, wired through a
  single fetch base so **all** calls honor it, with a reachability indicator (G2).
- CSV + JSON crossings download on the viewer, reflecting reviewed state, via additive
  back-end download endpoint(s) (G3).
- CORS/config so a differently-hosted front-end can talk to the back-end (FR11).
- Deletion of the unified page and the last bare same-origin paths (NFR5); doc updates
  (NFR6).

### 7.2 Out of scope (captured for context)
- **Cross-back-end crossings transfer / import.** No portable bundle, no upload-to-a-second-
  back-end, no import endpoint (D2). "Uploaded from the collector" means the existing
  frame-upload → engine path to the *same* back-end.
- **Moving or changing CV processing.** No server-side batch processing, no processing on the
  viewer, no pipeline/engine/config changes beyond the additive download + CORS (G4, FR17).
- **A ZIP/annotated-image results bundle.** Download is CSV + JSON of crossing records; the
  annotated-image package is a possible later item, not this phase (D3).
- **Auth / transport security for a remote back-end.** Pointing at another origin is enabled
  and documented (CORS), but authentication and TLS for multi-device/remote capture remain
  out of scope (as in prior specs).
- **A client-side router / in-app navigation framework.** Separate HTML files only (D1).
- **New results/timeline features, visual redesign.** Parity only (G5); feature work resumes
  on the split pages.

## 8. Success Criteria

- **SC1** — From the back-end root, the operator lands on a page that links to a collector
  page and a viewer page; each opens standalone and loads only its own app (FR1–FR3).
- **SC2** — On both the collector and viewer, setting a back-end URL in the UI, reloading,
  and returning shows the value retained, and every request (verified in DevTools Network)
  targets that base — including results reads and frame/image URLs that are bare today
  (FR6–FR8).
- **SC3** — With the front-end served from a different origin than the API and the back-end
  configured per the spec, the viewer loads results and the collector uploads frames without
  CORS errors (FR11).
- **SC4** — A wrong/unreachable URL produces a visible "unreachable" indication, not a silent
  blank (FR9, NFR3).
- **SC5** — From the viewer, a run with edits, a manual crossing, a reorder, and a deletion
  downloads as CSV and as JSON; both match the timeline (edit applied, manual present,
  order honored, deleted excluded) — not the raw append log (FR12–FR14). An empty run
  downloads valid empty files (FR15).
- **SC6** — The collector still captures and processes live from the camera and from an
  uploaded video file, with results appearing on the viewer (pointed at the same back-end);
  no pipeline/engine/on-disk change is required to make this work (FR16–FR17, NFR4).
- **SC7** — `grep` finds no remaining page that mounts both roots and no bare same-origin
  fetch/URL path in the fetch layer; `run.sh` starts the app with no node involvement
  (NFR1, NFR5).

## 9. Open Questions (resolved)

- **OQ1 — Where the URL control lives.** ✅ **Resolved** — a **collapsible settings
  affordance** on the collector and viewer (not an always-visible header field). Collapsed by
  default; the current target is still discoverable via the status line (OQ2).
- **OQ2 — Live-apply vs. reload-to-apply the URL change.** ✅ **Resolved** — **live re-apply**:
  changing the URL re-points subsequent requests (polling, uploads) without a reload, and the
  **processing/status line shows which back-end the page is currently pointing at**. This
  makes the active target visible on both pages even while the settings panel is collapsed.
- **OQ3 — Download source.** ✅ **Resolved** — **reuse the composed `/results` shape** as the
  source of truth so CSV/JSON stay in lockstep with the timeline. The download may be served
  as a **plain-text response** (no zip/attachment machinery required); a recognizable filename
  is still desirable but a plain `text/csv` / `application/json` body is acceptable.
- **OQ4 — Collector live feedback.** ✅ **Resolved** — **keep the status line** and its live
  processing information on the collector (sent/dropped/last result + the active back-end from
  OQ2). No rich timeline and no new "last N recognized" widget on the collector; the viewer
  (same back-end, second tab) remains where crossings are watched.
