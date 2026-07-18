# Requirements — Review & Editing: Frames, Manual Crossings, Order, Queue Status

## 1. Background & Purpose

The live pipeline (`specs/completed/live-pipeline/`) closes the capture→CV→timeline loop:
frames stream to disk, a worker runs the CV pipeline over them in order, confident number
reads dedup into **crossings**, and the timeline renders them live with a sidebar showing
each crossing's annotated frame.

The results are good, but the system is **read-only** and shows **only its successes**:

- The timeline shows only crossings produced by **confident** OCR reads. The pipeline
  already detects riders and returns a per-rider result (including `needs_review` and
  `rejected`) for **every** frame — but the engine discards everything non-confident.
  A rider whose number was folded, fell off, or was unreadable **crosses invisibly**.
- The operator can only see one frame per crossing (the annotated representative). The
  thousands of captured frames on disk are otherwise unreachable from the UX.
- Nothing can be corrected: a missed rider cannot be added, a wrong read cannot be fixed,
  and the crossing order — the actual product of the whole system — cannot be edited.
- The operator has no visibility into the processing queue: during a burst the timeline
  silently lags capture (by design), but the UX gives no indication of how far behind
  processing is or when the timeline is fully caught up.

This iteration makes the operator a **first-class editor of the result**: browse frames,
see likely-but-unidentified crossings, annotate riders manually, correct and reorder
crossings, and always know where processing stands.

This document is *what & why* only. Technology choices belong in `design.md`.

## 2. Goals

- **G1 — Frame visibility.** The operator can **view captured frames beyond** the one
  representative frame per successful detection — enough to find a rider the pipeline
  missed and to verify any crossing against its surrounding frames.
- **G2 — Manual annotation.** The operator can **manually record that a rider appeared**
  (a manual crossing): pick the moment/frame, assign a number (or leave unidentified),
  and have it join the timeline like any other crossing.
- **G3 — Editable order.** The operator can **edit the crossing order** — the finish
  order the timeline presents — and the edited order is the order of record.
- **G4 — Missed riders are visible.** Rider detections that never produced a confident
  read (folded/missing/unreadable number) surface in the timeline as **candidate
  crossings** — in a way that is **not invasive**: the successful timeline stays clean
  and readable, candidates are visually subordinate and easy to ignore or dismiss.
- **G5 — Processing transparency.** The UX shows the **state of the processing queue**:
  how many frames are captured, processed, and pending, and whether the timeline is
  live/caught-up or still draining a backlog.

## 3. Resolved Product Decisions

Baked into the requirements below:

- **D1 — Everything is per-run.** Frame browsing, candidates, manual crossings, edits,
  order, and queue status are all scoped to a run (`runs/<label>/`), consistent with
  live-pipeline D9. Editing a past run is the same UX as editing the active one.
- **D2 — Edits are persistent and restart-safe.** Every manual action (create, edit,
  reorder, dismiss, delete) is persisted to disk as it happens, like crossings today
  (live-pipeline D8). Reloading the page or restarting the back-end loses nothing.
- **D3 — Provenance is always visible.** Every crossing carries how it came to be:
  produced automatically, produced automatically then edited, or created manually.
  The timeline and sidebar make the distinction visible; an export/consumer can tell
  them apart. Automatic (re)processing never silently overwrites a manual edit.
- **D4 — Candidates are subordinate, not peers.** Candidate crossings (G4) must not
  dilute the primary timeline: they render with a clearly secondary treatment and/or
  behind a lightweight affordance, are individually dismissible, and can be **promoted**
  — the operator resolves a candidate into a real crossing by assigning a number (or
  confirming it as an unidentified rider crossing).
- **D5 — No re-run of the CV pipeline for editing.** Editing works over what capture and
  processing already produced (frames on disk, per-frame pipeline results, crossings).
  This iteration does not add "re-process this run" or model tuning; a candidate is
  resolved by a human, not by re-OCR.
- **D6 — Live capture stays untouched.** The capture controls, frame POST path, and
  processing throughput keep their current behavior; review/editing must never block or
  slow capture (live-pipeline NFR2/NFR3). Reviewing while a capture is running is
  allowed but the design may keep heavier browsing off the hot path.

## 4. Key Facts (what already exists to build on)

- **A1 — Every frame is already on disk**, timestamped and indexed: `collected/*.jpg` +
  `manifest.jsonl` (filename, `client_ts`, seq). Frame browsing is a UX/serving problem,
  not a capture problem.
- **A2 — The pipeline already reports non-confident riders.** `pipeline.run` returns one
  result per detected rider with `status ∈ {confident, needs_review, rejected}` and the
  rider box — but today the engine keeps only statuses configured as confident and drops
  the rest **without persisting them**. Candidates (G4) need those per-frame outcomes to
  be retained and grouped. A rider the *detector* never saw at all is out of reach of
  candidates — that gap is what manual annotation (G2) covers.
- **A3 — Queue depth is already derivable**: frames captured = manifest length; frames
  processed = `processed_offset`; pending = the difference. No new instrumentation is
  conceptually required — only exposure and presentation.
- **A4 — Order today is implicit.** The timeline orders by crossing `time` (first
  confident read). There is no explicit order-of-record; G3 introduces one.
- **A5 — Volume** (per live-pipeline A6): one race/session, thousands of frames,
  hundreds of crossings, CPU-only laptop, localhost, single operator.

## 5. Functional Requirements

### 5.1 Frame browsing (G1)
- **FR1** — From the UX the operator can **browse a run's captured frames**, ordered by
  capture time, without leaving the unified page's context.
- **FR2** — The operator can **jump to the frames around a point in time** — in
  particular, around any existing crossing or candidate (e.g. "show me the frames just
  before/after this crossing") — and step through neighboring frames.
- **FR3** — Frame browsing shows each frame's capture time and, where the pipeline has
  processed the frame, **what the pipeline saw in it** (detected rider(s) and read
  outcome), so the operator can distinguish "nothing there" from "rider there, number
  unreadable".
- **FR4** — Browsing must handle a full run's volume (thousands of frames) without
  loading everything at once and without degrading the live page (D6, NFR2).

### 5.2 Manual crossing annotation (G2)
- **FR5** — While viewing a frame (FR1–FR2), the operator can **create a crossing at
  that moment**: the frame's capture time becomes the crossing time and the frame
  becomes its representative image.
- **FR6** — When creating (or later editing) a crossing the operator can **assign a
  race number** — choosing from the run's roster or entering a number freely — or
  explicitly leave the rider **unidentified**. Roster enrichment (name/category) applies
  exactly as it does for automatic crossings; non-roster numbers get the existing
  "unknown rider" treatment.
- **FR7** — Manual crossings appear in the timeline alongside automatic ones, ordered
  and grouped by the same rules, but **visibly marked as manual** (D3).
- **FR8** — The operator can **edit an existing crossing**: correct its number
  (including fixing a misread on an automatic crossing), change its assigned rider, or
  **delete** it. Edited automatic crossings are visibly marked as edited (D3). Deletion
  must be deliberate (confirmed or undoable — design to choose).

### 5.3 Crossing order editing (G3)
- **FR9** — The run has a single **order of record** for its crossings. By default it is
  time order (as today); the operator can **override the position of any crossing**
  (move it earlier/later relative to its neighbors).
- **FR10** — The timeline presents the order of record. A crossing whose position was
  manually overridden is visibly marked (D3); its recorded capture time is not falsified
  — time and order are separate facts.
- **FR11** — Newly arriving automatic crossings (live processing continues during
  editing) slot into the order by time **without discarding** existing manual position
  overrides.

### 5.4 Candidate crossings — missed riders (G4)
- **FR12** — Frames where the pipeline **detected a rider but produced no confident
  read** are retained and **grouped into candidate crossings** (a burst of consecutive
  such frames is one candidate, not dozens), each with a representative frame and time.
- **FR13** — Candidates appear **in the timeline at their time position**, with a
  clearly subordinate, non-invasive treatment (D4): the operator can see at a glance
  that "something crossed here", without candidates crowding or reordering the primary
  results. Their visibility can be toggled.
- **FR14** — A candidate can be **opened** like a crossing (sidebar: representative
  frame, time, what the pipeline saw) and from there **resolved**: promoted to a real
  crossing (assign number or confirm unidentified — same flow as FR6) or **dismissed**
  (not a rider / duplicate / noise). Resolved and dismissed candidates leave the
  candidate treatment; promotion produces a normal crossing with manual provenance.
- **FR15** — Candidate generation must not create candidates for riders that **did**
  produce a confident crossing at the same moment (the common case: the same rider
  yields both confident and non-confident per-frame reads while passing).

### 5.5 Queue & processing status (G5)
- **FR16** — The page shows, for the active run, **live processing status**: frames
  captured, frames processed, frames pending, and a clear caught-up vs draining
  indication (e.g. "processing 132 behind" → "up to date").
- **FR17** — The timeline communicates **how current it is**: when a backlog is
  draining, the operator can tell that more results are still coming and roughly how
  far processing has advanced (e.g. up to what capture time).
- **FR18** — When viewing a past (non-active) run, its status reflects reality
  (fully processed, or partially processed with a pending count).
- **FR19** — Status updates are live (no manual reload), lightweight, and must not
  disturb operator interaction — consistent with the existing polling model and
  live-pipeline FR4.

### 5.6 Persistence & integrity
- **FR20** — All edits (FR5–FR11, FR14) are **persisted per-run as they happen** and
  survive back-end restart and page reload (D2). The on-disk artifacts remain
  per-run-co-located as today (live-pipeline D9).
- **FR21** — Provenance (automatic / edited / manual / promoted-candidate / dismissed)
  is persisted with each crossing or candidate (D3).
- **FR22** — Continued automatic processing never overwrites or duplicates a manual
  edit: e.g. a late confident read of a number the operator already fixed or created
  must reconcile with (not clobber or double) the operator's version — exact
  reconciliation rules are a design decision (see OQ5).

## 6. Non-Functional Requirements

- **NFR1 (Non-invasive)** — The default view stays as clean as today: an operator who
  never edits sees the same page, plus a small status readout. Candidates and browsing
  are opt-in affordances, not new clutter (D4, G4).
- **NFR2 (Capture unharmed)** — Frame browsing, candidate retention, and status
  reporting must not measurably slow frame acceptance or processing throughput (D6;
  live-pipeline NFR2/NFR3).
- **NFR3 (Volume)** — Browsing and candidate structures stay responsive at one
  session's volume (A5) on a CPU-only laptop; no unbounded memory growth from
  retaining per-frame outcomes.
- **NFR4 (Reuse)** — Extend the existing run model, engine, endpoints, timeline, and
  sidebar; new code is additive (candidate store, edit endpoints, browse view, status)
  — not a rewrite of working pieces.
- **NFR5 (Local-only)** — Localhost, no auth, no new services or external dependencies
  at runtime (unchanged stance).
- **NFR6 (Trustworthy edits)** — Concurrent realities (worker folding new crossings
  while the operator edits) never corrupt state: edits are atomic per action, and the
  UI reflects the merged truth on next poll.

## 7. Scope

### 7.1 This phase
- Frame browsing for a run, anchored to times/crossings, with per-frame pipeline
  outcomes visible.
- Manual crossing creation from a frame; number assignment (roster / free / none).
- Edit and delete existing crossings; provenance marking throughout.
- An explicit, editable order of record presented by the timeline.
- Candidate crossings from non-confident rider detections: retained, grouped,
  subordinate display, promote/dismiss flow.
- Live queue/processing status for the active run and honest status for past runs.

### 7.2 Out of scope (captured for context)
- Re-running the CV pipeline over a run (batch re-process, tuning loops) — D5.
- Multi-object tracking or smarter automatic dedup; candidate grouping is a time
  heuristic like crossing dedup.
- Roster editing in the UI (roster upload flow is unchanged).
- Placings/standings/lap logic beyond the single editable crossing order.
- Multi-operator concurrent editing, auth, remote access.
- Video scrubbing of the *source* video file; browsing operates on captured frames.
- Final-results export (CSV of the edited order) — deferred to the next iteration
  (OQ7 resolved); this iteration ends at the editable order-of-record in the UI.
- Retroactive candidate generation for runs processed before this feature (OQ4
  resolved: going-forward only; old runs are still browsable and annotatable).

## 8. Success Criteria

- **SC1** — For a processed run, the operator can open a frame browser, scrub to any
  point in the run, and step frame-by-frame around a chosen crossing (FR1–FR2, FR4).
- **SC2** — A rider missed by OCR (number folded away) shows up as a **candidate** at
  the right time position; the operator opens it, sees the frame, assigns the correct
  number from the roster, and it becomes a normal (manually-provenanced) crossing in
  the timeline (FR12–FR14, G4, G2).
- **SC3** — A rider missed even by detection can still be added: the operator scrubs
  to the moment, creates a crossing from the frame, assigns a number, and it appears
  correctly placed (FR5–FR7).
- **SC4** — A misread number on an automatic crossing is corrected in place; the
  timeline shows the corrected number with an "edited" marking (FR8, D3).
- **SC5** — The operator moves a crossing up one position in the order; the timeline
  shows the new order of record; a page reload and a back-end restart both preserve it;
  a new automatic crossing arriving later slots in without undoing the move
  (FR9–FR11, FR20).
- **SC6** — During a capture burst the page shows the backlog (e.g. "412 captured /
  280 processed — 132 pending") and visibly reaches "up to date" after draining; a
  half-processed past run says so when opened (FR16–FR18).
- **SC7** — Candidates for a rider who *also* produced a confident crossing do not
  appear (FR15), and with candidates toggled off the timeline is indistinguishable
  from today's (FR13, NFR1).
- **SC8** — With live capture running, doing all of the above never stalls frame
  acceptance or the processing queue (NFR2, D6).

## 9. Open Questions (for human review before design)

- **OQ1 — Meaning of "edit the crossing order".** ✅ **Resolved** — explicit
  **order-of-record with per-crossing position overrides** (FR9/FR10): time stays
  truthful, order is editable (e.g. drag or move-up/down), overridden positions are
  marked. Editing crossing *times* to force order was rejected.
- **OQ2 — Candidate visibility default.** ✅ **Resolved** — candidates are **visible by
  default, inline at their time position with a clearly subdued treatment**, and a
  toggle hides them entirely (FR13, D4).
- **OQ3 — `needs_review` reads.** Live-pipeline deferred these. Here they naturally
  become the *best* candidates (they carry a tentative number). Fold `needs_review`
  into candidates with their tentative number pre-filled? Proposed: yes.
- **OQ4 — Retroactive candidates for existing runs.** ✅ **Resolved** — **going-forward
  only**: candidates exist for frames processed after this feature ships. Past runs
  remain fully browsable and manually annotatable (G1/G2 cover the gap); no re-scan
  action this iteration (consistent with D5).
- **OQ5 — Reconciliation rule (FR22).** When a late confident read matches a
  manually-created/edited crossing within the dedup window: fold into the manual
  crossing silently, or surface as a candidate for the operator? Design proposal
  needed; requirements only mandate "no clobber, no duplicate".
- **OQ6 — Editing while viewing the *active* run vs past runs.** Any UX differences
  (e.g. lock order editing while backlog is draining), or identical everywhere (D1)?
  Proposed: identical, with FR11 handling live arrivals.
- **OQ7 — Final-order export.** ✅ **Resolved** — **deferred to the next iteration**.
  This iteration ends at an editable order-of-record in the UI; an ordered-CSV
  export ships as a fast follow (noted in §7.2).
