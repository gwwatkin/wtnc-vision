# task4 — Pages & entries: landing + collect + view (Wave B)

**Model:** sonnet (haiku-ok) · Depends on task1 (stubs so imports resolve).

Source of truth: `../design.md` (§2), `tasks/README.md` (FROZEN-4, FROZEN-5). Run FE
commands from `collection/frontend/`.

## Owns (exclusive)
- `collection/frontend/index.html` (repurpose → landing)
- `collection/frontend/collect.html`, `collection/frontend/view.html`
- `collection/frontend/collect.js`, `collection/frontend/view.js`
- **Delete** `collection/frontend/main.js`

## Do

1. **`index.html` → landing** (FR2). Links only — no `config.js`, no module, no roots:
   ```html
   <body>
     <main class="landing">
       <h1>WTNC Vision</h1>
       <div class="landing__links">
         <a class="landing__link" href="collect.html">Collector — capture & process live</a>
         <a class="landing__link" href="view.html">Viewer — results, review & download</a>
       </div>
     </main>
   </body>
   ```
   Keep the `<head>`/stylesheet link. Use FROZEN-4 landing classes (task8 styles them).

2. **`collect.html`** — capture page shell:
   - `<div id="capture-root"></div>` (no results-root, **no** datalist).
   - `<script src="config.js"></script>` then `<script type="module" src="collect.js"></script>`.
   - Title e.g. "Frame Collector".

3. **`view.html`** — viewer page shell:
   - `<div id="results-root"></div>` and the shared `<datalist id="roster-numbers"></datalist>`
     (moved here from the old index — used only by the results overlays).
   - `config.js` then `<script type="module" src="view.js"></script>`.
   - Title e.g. "Results Viewer".

4. **`collect.js`** / **`view.js`** — mirror the old `main.js`, one root each:
   ```js
   import { h, render } from './vendor/preact-setup.js';
   import CaptureApp from './components/capture/CaptureApp.js';   // collect.js
   render(h(CaptureApp, null), document.getElementById('capture-root'));
   ```
   ```js
   import { h, render } from './vendor/preact-setup.js';
   import ResultsApp from './components/results/ResultsApp.js';   // view.js
   render(h(ResultsApp, null), document.getElementById('results-root'));
   ```

5. **Delete `main.js`.**

## Notes
- You import `CaptureApp` / `ResultsApp` (already exist); do **not** edit them (task5/task6 do).
- Each page loads only its own app — no page mounts both roots (SC1, SC7).

## Done when
- `npm run typecheck` green. The three pages exist with the FROZEN-5 structure; `main.js` gone;
  datalist lives only in `view.html`.
