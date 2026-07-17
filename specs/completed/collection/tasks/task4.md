# Task 4 — Integration, Run Scripts & End-to-End Verification

**Agent:** sonnet  **Depends on:** task2 **and** task3  **Blocks:** nothing
**Milestone:** M4 (design §13)

## Objective
Wire the two halves into a runnable collector: a `run.sh` that starts the back-end and the
static front-end on their two ports, a README that documents setup/run/verify, and a real
end-to-end check that frames captured in the browser land on disk and are **pipeline-ready**
(decode with `cv2.imread`). Tune the default capture rate/quality if the end-to-end run
shows a problem.

## Read first
`../requirements.md` (§8 success criteria — this task proves SC1–SC6), `../design.md`
(§8 extension/pipeline parity, §10 run/serve, §11 structure), and the **final reports from
task2 and task3**.

## Files you own
```
comp-vision-results/collection/
  run.sh          # start back-end (:8000) + static front-end (:8001); print the URL
  README.md       # setup, run, verify, troubleshooting
```
Plus **only if a genuine bug is found** during end-to-end: minimal fixes to
`backend/*.py` or `frontend/*` — but prefer to **report** contract issues rather than
change frozen §4/§5/§6/§7 contracts. Do not rewrite task2/task3 logic wholesale.

## Implement — `run.sh`
- Activate the repo venv (`source ../.venv/bin/activate` relative to `collection/`, or an
  absolute path) — Python 3.12 (CLAUDE.md).
- Start the back-end: `python -m backend` (from `collection/`) on `:8000`.
- Start the static front-end: `python -m http.server 8001 --directory frontend`.
- Print `Open http://localhost:8001` and wait; on `Ctrl-C`, stop **both** child processes
  (trap EXIT/INT to kill the back-end + http.server). Keep it POSIX-sh/bash simple.

## Implement — `README.md`
Concise, in the style of the repo README. Cover:
- What this is (browser collector → local back-end writing labeled frames to disk;
  **no CV yet**) and how it feeds the pipeline later (design §8).
- **Setup:** repo venv active, `pip install -r backend/requirements.txt` (design §11).
- **Run:** `./run.sh` (or the two manual commands), then open `http://localhost:8001`.
- **Use:** pick a camera, type a label, Start/Stop; where files appear
  (`collected/<label>/…jpg` + `manifest.jsonl`) and the filename scheme (design §5).
- **Config:** front-end `frontend/config.js` (rate/quality/size/URL), back-end
  `backend/config.yaml` (ports/paths/limits/CORS origins).
- **Troubleshooting:** camera permission (secure-context/localhost), CORS (origins must
  list the front-end port), back-end down (status line shows errors, capture continues).

## End-to-end verification (must actually perform)
1. `./run.sh`; confirm `GET http://localhost:8000/health` is 200 and the page loads.
2. In a browser, grant camera, set label `test-101`, Start for a few seconds, Stop.
3. Confirm `collected/test-101/` filled with `test-101_<ts>_<seq>.jpg` files at roughly
   `CAPTURE_FPS`, and `collected/manifest.jsonl` gained one line per file with matching
   fields (design §5).
4. **Pipeline-readiness (SC4, NFR1):** run
   `python -c "import cv2,sys; im=cv2.imread(sys.argv[1]); print(im.shape)"` on one stored
   frame — it must print a valid BGR shape (this is the same input `pipeline.run` takes).
5. Change the label, capture again → a **new** folder, first one undisturbed (SC3).
6. **Robustness (SC5):** stop the back-end mid-capture (or send an oversized frame) →
   status shows the error, the tab keeps ticking, and the service (once back) still serves.
7. Record results in the README (or a short `VERIFY.md` note) with the observed fps and any
   default you tuned (`CAPTURE_FPS`/`JPEG_QUALITY`).

If a browser isn't available in the agent environment, drive the equivalent with `curl`
against `/frames` (multipart) to prove the on-disk + manifest + `cv2.imread` path, and
**clearly note** that the live-camera step was verified by script, not a real browser.

## Acceptance criteria
- `./run.sh` starts both services and cleanly stops both on Ctrl-C.
- The end-to-end run produces labeled frames + manifest lines on disk, and a stored frame
  decodes via `cv2.imread` (SC1–SC4).
- Re-labeling yields a separate folder without touching the first (SC3); a failed frame is
  isolated and non-fatal (SC5).
- README lets a new user set up, run, and verify from scratch.

## Out of scope
CV/OCR processing (the live-processing spec), auth, and any multi-device concerns.

## Final report to include
Confirm SC1–SC6 with observed evidence (frame counts, a `cv2.imread` shape, manifest
sample), the final tuned defaults, how the live-camera step was verified (browser vs.
curl), and any contract issue you had to flag rather than fix.
