# task9 — Integration: entries, HTML, config.js, dist mount, delete old, build, parity, docs (Wave C)

**Model:** sonnet · **Depends on:** all of Wave B (task2–task8) landed and `npm run check`
green. This is the wave that makes the tree buildable, deletes the old world, and proves
parity.

Source of truth: `../requirements.md` (FR6–FR8, FR14, FR17–FR18, NFR2, NFR5, SC1–SC7) +
`../design.md` §3, §6, §7, §11 + `tasks/README.md` FROZEN-5, FROZEN-7. Paths under
`collection/frontend/` unless noted.

## What you own

Entries + HTML + config placement + git-ignore + the single back-end line + deletions +
build/parity + docs.

## Steps

1. **Entry modules (FROZEN-7).** Fill `collect.tsx` →
   `render(<CaptureApp />, document.getElementById('capture-root')!)` and `view.tsx` →
   `render(<ResultsApp />, document.getElementById('results-root')!)` (`render` from
   `preact`, JSX). Preserve the `page-split` roots / `#roster-numbers` datalist behavior.

2. **HTML wiring (FROZEN-5).** Update `collect.html` / `view.html` so each has, in order, the
   classic `<script src="/config.js"></script>` then `<script type="module"
   src="/collect.tsx">` (resp. `/view.tsx`). `index.html` stays the static landing (no
   config, no module) but remains a Vite input (already in `vite.config.ts` — OQ-D4).

3. **`config.js` relocation (FROZEN-5).** Move `config.js` **unchanged** to
   `public/config.js` so Vite copies it verbatim to `dist/config.js`, served at `/config.js`,
   operator-editable post-build with no rebuild (SC6). Delete the old root `config.js`.

4. **`.gitignore` (OQ1/NFR4).** Ignore `collection/frontend/dist/` and
   `collection/frontend/node_modules/`.

5. **Back-end serving — the ONE Python line (FROZEN-7, design §6).** In
   `collection/backend/app.py`, point `StaticFiles` at `…/frontend/dist` instead of
   `…/frontend`. Update the Python test that asserts the mount dir (if any). **No** route,
   payload, or handler change. Run it with `.venv/bin/pytest` from repo root (per CLAUDE.md —
   never `source … && …`).

6. **Delete the old world (FR14/SC4).** Remove every remaining `.js` FE source (`api.js`,
   `backend-url.js`, `collect.js`, `view.js`, `results/data.js`, all `components/**/*.js`),
   `results/data.d.ts`, `types.d.ts`, the old `tests/*.test.js`, `tests/setup-dom.js`, and
   any `vendor/` residue. `grep` afterwards to confirm **no** `.js` FE source, no `vendor/`,
   no `htm`, no `preact-setup.js`, no `@param {import(...)}` typing, and no
   `checkJs`/`allowJs` in `tsconfig` (SC4).

7. **Build + check green (SC1/SC2).** `npm ci` then `npm run build` emits `dist/` with the
   three page bundles + hashed assets + `config.js` unhashed; `npm run check` (typecheck +
   all ported suites) passes. Sanity-check with `npm run preview`.

8. **Parity checklist (NFR5) against a real run.** With `npm run build` + FastAPI serving
   `dist/` (and `npm run dev` against a running back-end for the HMR check, SC5), verify both
   pages at parity: timeline render, sidebar edit/reorder, frame browser, candidate toggle,
   status; capture camera/video/roster; export/download; backend-URL settings. Confirm
   editing `dist/config.js` re-points the backend with no rebuild (SC6). Record results.

9. **Docs (FR17/FR18/FR8).** Update `collection/frontend/README.md` (new layout; dev/build/
   check commands; multi-page entries; runtime `config.js` injection; how to add a component;
   npm-managed deps). Update `../../CLAUDE.md`'s FE guidance to the TS/Vite workflow
   (superseding the vendored/no-build description) as a sibling to the untouched Python rules.
   Update `run.sh`/top-level `README.md` so the operator flow documents the one-time
   `npm ci && npm run build` prerequisite before starting the back-end.

## Definition of done

- `npm run build` **and** `npm run check` green; `dist/` produced; `.venv/bin/pytest` for the
  back-end passes.
- SC4 grep is clean (single-idiom TS, no dead files); SC2 spot-check: a deliberately mistyped
  prop at a JSX call-site fails `npm run check` (then revert it).
- Parity checklist passed against a real run; docs updated.

## Do NOT

- Change any endpoint/payload/wire contract or any back-end file beyond the single
  `StaticFiles` line + its test (NFR2/D5). Touch the engine, `config.py`, `models.py`, or
  `runs/`.
</content>
