# Task 4 — Roster Validation + Confidence Scoring

**Agent:** sonnet  **Depends on:** task1  **Parallel with:** task2, task3
**Milestone:** part of M4 (design §10)

## Objective
Turn raw OCR reads into a validated rider number using the roster, and classify each
result's confidence into `confident` / `needs_review` / `rejected` (design §3 steps 5–6).
This is the biggest accuracy lever (roster is available — design §12 D1).

## Read first
`../requirements.md` (§5 FR3/FR4/FR8, NFR1), `../design.md` (§3 steps 5–6, §7 config).
Do NOT change `types.py` or any signatures from task1.

## Files you own
```
src/rider_id/validate.py
src/rider_id/score.py
```
(Optional `tests/test_validate.py` for your own unit checks.)

## Specification

### validate.py
- `load_roster(cfg) -> set[str] | None`:
  - Read `cfg["validate"]["roster"]` (a path). One number per line. Return a set of
    normalized strings. If path is null/missing, return `None` (validation degrades to
    accept-on-confidence — but for the POC the roster exists).
- `validate(ocr_results, roster, cfg)` -> `(number: str|None, raw_text: str|None, conf: float)`:
  1. From `ocr_results`, extract **numeric** candidate tokens (strip non-digits). Honor
     `cfg["validate"]`: `min_digits`, `max_digits` (=3), `leading_zeros: false` (reject
     `007`-style; a leading-zero read should be normalized or rejected — document choice).
  2. Pick the best candidate (highest `ocr_conf`; if tie, longest plausible).
  3. **Roster match:** if `roster` is not None:
     - Exact match → accept, `number = candidate`.
     - Else find the nearest roster number within `cfg["validate"]["max_edit_distance"]`
       (Levenshtein on the digit string; e.g. `108`→`103` if 103 is in roster and 108 is
       not). If a unique nearest match exists, snap to it (record `raw_text` = original).
       If ambiguous or none within budget → `number = None` (rejected).
  4. `conf` = the OCR confidence of the chosen read, optionally lightly penalized when a
     snap (edit-distance ≥ 1) was needed. Keep the penalty simple and documented.
  5. `raw_text` = the original OCR string for the chosen candidate (for human review).
  - If no numeric candidate at all → return `(None, None, 0.0)`.

### score.py — `classify(number, confidence, cfg) -> str`
- `"rejected"` if `number is None`.
- Else `"confident"` if `confidence >= cfg["score"]["confidence_threshold"]`,
  otherwise `"needs_review"`.

## Acceptance criteria
- Unit-testable without any CV: feed synthetic `OcrResult` lists and assert behavior:
  - `[OcrResult("101", 0.94, box)]` with roster {101,102,103} → `("101", "101", ~0.94)`,
    classify → `confident`.
  - `[OcrResult("108", 0.9, box)]` with roster {101,102,103} (108 absent, max_edit=1) →
    snaps to `103`? No — edit distance("108","103")=1 (only middle differs? "108" vs
    "103": positions: 1=1, 0=0, 8≠3 → distance 1) → snaps to `103`, `raw_text="108"`.
    (Adjust example to your Levenshtein; the point: near-miss within budget snaps.)
  - `[OcrResult("577", 0.9, box)]` with roster {101,102,103}, max_edit=1 → no match →
    `rejected`.
  - `[OcrResult("skyprocycling", 0.8, box)]` → no numeric → `rejected`.
- No changes to `types.py` or other modules.

## Coordination note
You don't need real OCR output — construct `OcrResult` instances directly for tests. Do
NOT import `ocr.py`/`detector.py`.

## Out of scope
Detection, localization, OCR itself, final output/pipeline wiring (task5).

## Final report
Show the passing test cases (including a snap and a rejection), and document your
leading-zero handling and the snap-penalty on confidence.
