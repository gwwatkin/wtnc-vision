# Tasks — Race Results Timeline UX

Map for the parallel-agent build. **Read this before spawning any agent.**
Source of truth for every task: `../requirements.md` and `../design.md`. Contracts in
`design.md` §4–5 are **frozen** — an agent that finds a signature genuinely wrong must
**stop and flag it**, not silently diverge (siblings depend on it).

## Dependency graph & waves

```
Wave 0 (blocking):   task1  scaffold ─────────────┐
                                                   ▼
Wave 1 (parallel):   task2 csv.js   task3 data.js   task4 render.js   task5 styles.css
                                                   │
                                                   ▼
Wave 2 (integration): task6 app.js  (wire + end-to-end verify)
```

- **Wave 0 must fully land before anything else starts.** It creates `web/`, all files as
  frozen stubs, sample data, and run instructions.
- **Wave 1 tasks run concurrently** — each owns exactly one file and codes against the
  frozen stubs from Wave 0.
- **Wave 2** wires it together and verifies end-to-end.

## Exclusive file ownership

| Task | Model | Owns (writes) | May read |
|------|-------|---------------|----------|
| task1 | sonnet | *all of `web/` (skeleton/stubs)* | requirements, design |
| task2 | sonnet | `web/csv.js` | — |
| task3 | sonnet | `web/data.js` | `web/csv.js` |
| task4 | sonnet | `web/render.js` | `web/data.js` |
| task5 | haiku  | `web/styles.css` | `web/index.html` |
| task6 | sonnet | `web/app.js` | all of `web/` |

No two Wave-1 tasks write the same file. `index.html`, sample CSVs, and `web/README.md`
are finalised in Wave 0 and not edited afterward.

## Shared conventions

- **Plain ES modules**, no framework, no build step, no runtime npm deps (design §2).
- **No network** beyond `fetch()` of the local CSVs.
- `import`/`export` between `web/*.js` files by relative path (`"./data.js"`).
- Keep functions **pure** in `data.js` (no DOM, no fetch). DOM only in `render.js`;
  fetch/orchestration only in `app.js`.
- Times are native `Date`. Display strings come only from `render.js` formatters.
- Match existing code density/naming; comment sparingly.
- Verify locally with `python -m http.server` from `web/` (see `web/README.md`).
