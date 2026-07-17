# Task 6 — Tune, Evaluate & Document

**Agent:** sonnet  **Depends on:** task5  **Parallel with:** none
**Milestone:** M5 (design §10) — produces the go/no-go baseline (SC4)

## Objective
Tune the thresholds and crossing zone against the sample image, record a baseline of what
the POC captures, and write the project README so a human can run and judge it. This
closes the POC and informs the go/no-go for the video phase.

## Read first
`../requirements.md` (§9 success criteria SC1–SC4, §10 OQ1), `../design.md` (§7 config,
§9 risks, §10 milestone M5).

## Files you own
```
config.yaml            # tuning only — values, not structure
README.md              # NEW: project README (run instructions + results)
EVALUATION.md          # NEW: baseline findings
```
You may run the pipeline and adjust `config.yaml` values. Do **not** rewrite the module
code — if a real bug blocks tuning, report it for a follow-up task rather than editing
another agent's module.

## Tasks

### 1. Tune
- Adjust `crossing_zone`, `locate.back_band`, `detector.person_conf`, and
  `score.confidence_threshold` so that on `../ridersFromThBack.jpg`:
  - the nearest rider reads `101` as `confident`,
  - far/small riders are excluded by the zone (not misread),
  - no obvious false numbers are emitted as `confident`.
- If PaddleOCR under-reads, try the `easyocr` engine switch and compare; record which
  wins and why (uses task3's dual-engine support).

### 2. Evaluate → `EVALUATION.md`
- Table of every result on the sample: `rider_box`, `raw_text`, `number`, `confidence`,
  `status` — and whether it's correct by eye.
- Which numbers were captured vs missed vs misread, and why (occlusion, size, tilt).
- The final tuned config values and the reasoning.
- A concrete recommendation on **OQ1** (realistic auto-capture rate to expect) and a
  **go/no-go** for the video phase (SC4), with the top 2–3 things the video phase should
  add (tracking, multi-frame confirmation, etc. — design §6).

### 3. Document → `README.md`
- One-paragraph what/why (link `requirements.md`, `design.md`).
- Setup: venv + `pip install -r requirements.txt`.
- Run: `python run_poc.py ../ridersFromThBack.jpg`, and what appears in `out/`.
- How to point it at a new image and adjust the zone/threshold in `config.yaml`.
- Known limitations (from EVALUATION) and next steps.

## Acceptance criteria
- SC1–SC3 demonstrably met: sample image yields correct `101` (confident), full artifact
  set, confidence + `needs_review` flagging working.
- `EVALUATION.md` gives the baseline table + go/no-go recommendation.
- `README.md` lets a new person install and run from scratch.
- `config.yaml` retains the design §7 structure (values tuned, keys unchanged).

## Out of scope
Building the video pipeline — only recommend it. No new modules.

## Final report
Summarize the baseline (what the POC reliably captures), the tuned config, and the
go/no-go call for the video phase.
