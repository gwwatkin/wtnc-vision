# Task 9 — Integration, end-to-end verification, docs

**Agent:** sonnet  **Depends on:** tasks 1–8 (wave C, run alone)

## Objective
Prove the assembled feature against the success criteria with real collaborators
(no fakes), fix cross-module friction wave B couldn't see, and update the docs.
File ownership is released — you may edit anything, but keep changes surgical and
list every file you touched.

## Read first
`../requirements.md` §8 (SC1–SC8 — your checklist); `../design.md` in full;
`README.md` here (conventions still apply — especially the command shapes);
every wave-B agent's final report (the operator will paste or point you at them —
they list CSS gaps, `data-*` names, and flagged frictions to resolve).

## Steps

1. **Full test run, real objects.** `.venv/bin/pytest collection/backend/tests/
   tests/` — all suites, no fakes beyond the existing `pipeline.run` monkeypatch.
   Then one integration test of your own in
   `collection/backend/tests/test_review_integration.py`: real engine + real
   `CandidateTracker` + real `FramesIndex` over a scripted frame sequence
   (canned `pipeline.run`) driving SC2 end-to-end at the API level — burst of
   `needs_review` frames ⇒ one open candidate in `GET /candidates`; promote via
   `POST /candidates/{id}/resolve` ⇒ manual-provenance crossing in `GET /results`,
   candidate `promoted`; a confident fold near a second candidate suppresses it
   (SC7 half).
2. **Live smoke (SC1, SC3–SC6).** Start `./collection/run.sh`; use the `video`
   source or a scripted `POST /frames` feed against a test label. Verify in the
   browser: frame scrub + step (SC1); create-from-frame with roster number (SC3);
   edit a misread number, badge shows (SC4); move a crossing, reload the page,
   restart the back-end, confirm order + badge survive and a later arrival slots
   by time (SC5); watch the queue line drain to "up to date" (SC6); toggle
   candidates off — timeline identical to pre-feature (SC7). Fix what fails;
   re-run the suites after every fix.
3. **NFR spot checks.** `/status` on an idle run doesn't re-read the manifest
   (cache hit — add a log/counter temporarily if needed, remove after); browsing
   while a capture drains doesn't stall frame acceptance (SC8 — feed frames
   during a browse session).
4. **CSS + report cleanup.** Apply the style fixes wave-B reports flagged
   (refinement 7 gaps); resolve any flagged contract frictions with the smallest
   compatible change, or STOP and surface them to the operator if a frozen
   contract genuinely has to move.
5. **Docs.** Repo `README.md`: extend the Live Pipeline section with the review
   features (browse, candidates, editing, order, status line) and the new
   `config.yaml` keys. Do NOT move the spec to `specs/completed/` — the operator
   does that at sign-off.

## Acceptance criteria
- All pytest suites green; the new integration test covers SC2 + suppression.
- Each SC1–SC8 item explicitly verified (or explicitly waived with a reason) in
  your final report.
- No stray artifacts: test runs under `collection/runs/` cleaned up, temporary
  counters/logging removed.

## Final report to include
SC-by-SC verdict table; every file you touched and why; remaining known limits
(the design's accepted ones — §4.2 merge heuristic, §7 restart edge — restated so
the operator sees them in one place); anything you had to change in a wave-B
module and whether its owner's contract survived.
