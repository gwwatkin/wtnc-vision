# Collection App — Task Plan

Delegation plan for building the finish-line **video/frame collection app** described in
`../requirements.md` and `../design.md`. Each `taskN.md` is scoped for **one subagent**
working from a cold start, so every task file is self-contained and names the files it
owns.

## Read-first (every agent)
- `../requirements.md` — what & why (esp. §5 functional reqs, §8 success criteria)
- `../design.md` — architecture, the three **frozen contracts** (§4 HTTP API, §5 on-disk
  layout, §6 back-end signatures), front-end structure (§7), config (§9)

## Dependency graph

```
task1 (scaffold + frozen contracts + env)
        │  ← BLOCKING: must finish before any other task
        ├──────────────────────┐
        ▼                       ▼
     task2                   task3            ← run in PARALLEL (disjoint files)
   back-end API+storage    front-end capture UI
        └──────────────────────┘
                   ▼
                task4  (integration, run.sh, README, e2e verify)   ← after 2 & 3
```

## Suggested waves
- **Wave A:** task1 alone (scaffold, contracts, venv deps, `/health`, stub `/frames`).
- **Wave B:** task2 (back-end) **and** task3 (front-end) in parallel — no shared files.
- **Wave C:** task4 (wire together, run scripts, README, end-to-end verification).

## Shared conventions (all agents must follow)
- **Do not change the frozen contracts** — design §4 (HTTP API), §5 (on-disk layout), §6
  (back-end dataclasses + signatures) and §7 `config.js` keys. If a contract is genuinely
  wrong, **stop and flag it**; do not silently diverge — the other agent depends on it.
- **File ownership is exclusive.** Only edit files your task lists under "Files you own."
- **One frame per request.** The front-end never batches; the back-end handles exactly one
  `image` per `POST /frames` (design §4).
- **Same device, two ports, no auth.** Back-end `:8000`, front-end `:8001`. CORS on the
  back-end allows the front-end origin (design §3, §9). No authentication anywhere.
- **Back-end runs in the repo's Python 3.12 `.venv`** (`comp-vision-results/.venv`,
  created by the POC). Activate it and add the light web deps; never use system `python3`
  (that's 3.14 and breaks the shared CV wheels). See CLAUDE.md.
- **Front-end is a static site — no build step.** Plain HTML/JS/CSS + browser APIs only.
- **Collected frames are pipeline-ready** (design §1, NFR1): stored verbatim as JPEG so
  `cv2.imread` decodes them to BGR. Do not re-encode or transform on the back-end.

## Generated data
`collected/` (frames + `manifest.jsonl`) is generated output — **gitignored**, never
committed. Task1 adds it to `.gitignore`.
