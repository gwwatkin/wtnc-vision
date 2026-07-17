# Task 7 — Integration, tuning & cleanup

**Agent:** sonnet  **Depends on:** tasks 2–6 (all of wave B)  **Blocks:** ship

## Objective
Wire-check the whole feature end-to-end with the real models, exercise the failure
modes the design promises to survive, tune the dedup window against a real burst,
collapse `run.sh` to one process, and retire the standalone viewer (`web/`). This is
the only task that runs real inference.

## Read first
`../requirements.md` §8 (SC1–SC9 — your checklist); `../design.md` §10 (run/serve),
§11 (risks — each mitigation you're validating), §3.1 consolidation note (deleting
`web/`); **every wave-B final report** (deviations, flagged issues).

## Files you own
```
collection/run.sh          # collapse to the single back-end process
collection/README.md       # unified-page instructions
README.md                  # repo root: drop standalone-viewer instructions, describe live flow
web/                       # DELETE the tree (after the e2e pass, see below)
collection/backend/config.yaml  # dedup_window_s tuning only, if the burst test demands it
```
Plus **glue-level bug fixes anywhere** — with restraint: integration may fix wiring
bugs in any file, but a contract-level problem (frozen signature, API shape, disk
layout) must be **flagged for human review**, not redesigned on the fly. Note every
cross-file fix in your final report.

## Steps

1. **Suites first.** `.venv/bin/pytest collection/backend/tests/ tests/` — all green
   before any e2e.
2. **Boot & smoke (SC1).** `../.venv/bin/python -m backend` from `collection/` (first
   run may pull
   models — allowed). Page on :8000: capture UI top, empty timeline, hidden sidebar.
3. **Scripted e2e without a camera (SC2, SC3, SC7, SC9 backbone).** Upload a roster
   containing the number visible in `ridersFromThBack.jpg` (see `roster.txt` /
   `EVALUATION.md` for what the POC reads) via `curl -F run=e2e -F roster=@…
   /roster`. Then simulate a burst: POST `ridersFromThBack.jpg` ~10× with `client_ts`
   values 200 ms apart, then 2 more with `client_ts` > `dedup_window_s` later.
   Verify via `GET /results?run=e2e`: **one** crossing for the burst + **one** for the
   late pair (FR9/FR10); name/category enriched; `GET /crossings/<id>/image` returns a
   JPEG with box + number drawn. On disk under `runs/e2e/`: `collected/`, per-run
   manifest, `processed_offset` == manifest lines, `crossings.csv`/`crossings.json`,
   `annotated/<id>.jpg` (SC9 layout).
4. **Kill-and-restart mid-burst (design §11).** Re-run the burst against a fresh run
   label; `kill -9` the back-end mid-way; restart; keep POSTing. The worker resumes
   from `processed_offset`; final `/results` shows no missing and no duplicate
   crossings; previously produced crossings still present (SC9).
5. **Poison frame (FR6).** POST a deliberately corrupt "JPEG" (e.g. `head -c 400
   ridersFromThBack.jpg` — passes content-type/size checks, fails `cv2.imread`)
   mid-burst. Verify: a logged skip, the offset advances past it, later frames still
   produce results.
6. **Unknown rider (A3).** POST frames under a run whose roster **lacks** the read
   number (or has no roster): the crossing appears `matched: false`, "Unknown rider"
   card in the unknown lane (FR20 degrade path).
7. **Disabled regression (SC6).** `live.enabled: false` → boots without CV imports,
   captures/stores frames, page loads, `/results` empty, `/roster` → 503.
8. **Browser pass (SC1–SC5, SC7, SC8).** With a real camera if available — otherwise
   the video-file source **is** the required path (SC8): record/obtain a short clip of
   the sample image or any rider, choose it as source, Start; watch crossings appear
   live, click into the sidebar, replace/close it, upload a roster from the page and
   see later crossings enriched. Confirm live re-render steals no scroll/focus while
   typing in the label field (FR4). Tune `dedup_window_s` if the burst splits or
   merges crossings wrongly; record the final value and why.
9. **Collapse `run.sh`** to the single process per design §10 (drop the :8001 static
   server; keep the venv check). Update `collection/README.md` accordingly.
10. **Retire `web/`** — only after step 8 passes: `git rm -r web/`; update the root
    `README.md` (results are now on the unified page; remove standalone-viewer
    sections; document the roster-upload flow and the `runs/` layout briefly).
    `specs/completed/results-ux/` stays — history, not instructions.
11. Re-run both test suites one final time.

## Acceptance criteria
- Every SC1–SC9 verified, each with a one-line note of *how* (steps above map onto
  them); both suites green; `web/` gone; one-process `run.sh` works from a clean shell.

## Out of scope
New features, contract changes, moving the spec to `specs/completed/` (the human does
that at ship time).

## Final report to include
The SC1–SC9 checklist with evidence per item; every cross-file fix you made and why it
was glue (not contract); the tuned `dedup_window_s`; anything flagged for human review.
