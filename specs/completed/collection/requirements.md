# Requirements — Finish-Line Video/Frame Collection App

## 1. Background & Purpose

The POC (`specs/completed/poc/`) proved we can detect a rider and read a printed
back-number from **one still image** (`ridersFromThBack.jpg`). To move toward the full
video system — and even to properly tune the POC — we need **real footage from our
actual camera placement**, not a single borrowed frame.

This feature builds a **data-collection tool**: a browser app that uses the device
camera to capture frames of riders and sends them to a local back-end that **writes them
to disk**, each tagged with a **human-readable label** the operator sets. The result is a
labeled on-disk dataset of real frames we can feed straight into the existing CV pipeline
for evaluation and, later, live processing.

This is deliberately a **first iteration**: collect and persist labeled frames. **No
computer vision runs in this feature** — the back-end just stores what it receives.

## 2. Goals

- **G1** — Let an operator capture frames from the device camera in a browser and stream
  them to a local back-end.
- **G2** — Attach a **human-readable label** to every captured frame (operator-set, and
  changeable between capture bursts).
- **G3** — Persist every received frame to disk in an organized, reviewable layout with
  enough metadata (label, timestamp, sequence) to reconstruct the capture.
- **G4** — Produce frames that are **directly consumable by the existing CV pipeline**
  (a standard image the pipeline can decode and run on later) so collection and analysis
  share one data format.
- **G5** — Keep it simple and dependency-light: a static front-end and a small back-end,
  runnable on one laptop.

## 3. Scope

### 3.1 This document / current phase — Collection MVP
- A **static web front-end** with live camera preview that captures frames in a
  **continuous burst** (auto-capture at a configurable rate while "recording" is on) and
  POSTs each frame — with its label — to the back-end.
- A **local back-end** that receives frames and **writes them to disk** with a metadata
  manifest. **No live processing.**
- Front-end and back-end run on the **same device**, on **different localhost ports**.
- **No authentication or authorization** (single-operator, local, trusted).

### 3.2 Later phases (out of scope now, captured for context)
- **Live processing:** the back-end feeds each received frame (or clip) into the CV
  pipeline (`src/rider_id/pipeline.py::run`) to detect crossings / read numbers in real
  time, instead of only storing it.
- Multi-device / remote capture, authentication, and transport security (TLS/auth).
- Recording full encoded video clips (vs. frame bursts) if temporal fidelity demands it.
- A review/annotation UI over the collected dataset (labeling corrections, gallery).

## 4. Key Facts & Assumptions

- **A1** — **Single device, single operator.** Front-end and back-end are on the same
  laptop, reached via `localhost` on two ports. The network is trusted; no auth needed.
- **A2** — **Continuous burst capture.** While recording is toggled on, frames are
  captured automatically at a configurable rate (not one-shot per click). The operator
  toggles recording and edits the label; every frame captured carries the label current
  at capture time.
- **A3** — **Per-shot label.** The label identifies *what is being captured* (e.g. a
  rider number like `101`, or a descriptor like `lap3-nearside`) and is **encoded into
  each frame's filename**. The operator can change it between bursts.
- **A4** — **Browser camera access is available** on the device; the app is served over a
  secure context (`localhost` qualifies) so `getUserMedia` works without HTTPS certs.
- **A5** — **The device may expose more than one camera.** The operator must be able to
  pick which system camera to use.
- **A6** — **Collected frames are the pipeline's input format.** A stored frame is a
  standard image that `cv2.imread` decodes to a BGR array — exactly what the POC pipeline
  already consumes.
- **A7** — Capture rate and image size are **modest** (a laptop CPU and local disk can
  keep up); the app must nonetheless not silently corrupt or block when a frame fails.

## 5. Functional Requirements

### 5.1 Front-end (browser)
- **FR1** — Request and display a **live camera preview** using the device camera.
- **FR2** — Let the operator **select which camera** to use when multiple are present.
- **FR3** — Provide a **label input** the operator sets; the current value is attached to
  every frame captured. The label may be changed between bursts.
- **FR4** — Provide a **start/stop recording** control. While recording, frames are
  **auto-captured at a configurable rate** and sent to the back-end.
- **FR5** — For each captured frame, transmit to the back-end: the **image**, its
  **label**, a **client timestamp**, and a **monotonic sequence number** for the session.
- **FR6** — Show a **status line**: recording state, frames sent this session, and the
  result of the last send (success / error), without blocking capture.
- **FR7** — A **failed frame send must not stop the capture loop** — surface the error in
  status and continue.

### 5.2 Back-end (local service)
- **FR8** — Expose an endpoint that **accepts a single captured frame** plus its metadata.
- **FR9** — **Persist each accepted frame to disk**, organized by label, with a filename
  that encodes the **label, timestamp, and sequence** so a human can identify it at a
  glance.
- **FR10** — **Record per-frame metadata** (label, filename, client + server timestamps,
  sequence, size) to a **manifest** for later dataset assembly.
- **FR11** — **Validate input** (content type, size, required fields) and reject bad
  requests with a clear error, without crashing the service.
- **FR12** — Expose a **health/liveness endpoint** so the front-end and run scripts can
  confirm the back-end is up.
- **FR13** — Be **restart-safe**: restarting the back-end must not clobber previously
  collected frames or the manifest (append, don't overwrite).

### 5.3 Configuration
- **FR14** — Front-end **capture rate**, **image quality/size**, and **back-end URL** are
  configurable without editing application logic.
- **FR15** — Back-end **storage directory**, **host/port**, **allowed origins**, and
  **size/type limits** are configurable without code changes.

## 6. Non-Functional Requirements

- **NFR1 (Reusability)** — Stored frames must be a standard, pipeline-ready image format
  (decodable by `cv2.imread` to BGR) so the same files feed the existing CV pipeline
  (G4/A6) with no conversion.
- **NFR2 (Robustness)** — Individual frame failures (network hiccup, oversized frame)
  are isolated: the front-end keeps capturing and the back-end keeps serving.
- **NFR3 (Backpressure)** — The capture/transmit loop must not queue unbounded work if
  the back-end lags; bounded in-flight sends with drop-or-skip is acceptable (imprecise
  collection is fine; a frozen tab is not).
- **NFR4 (Simplicity)** — Front-end is a **static site with no build step**; back-end is
  a small local service. Runnable on one laptop with a couple of commands.
- **NFR5 (Local-only / no auth)** — Runs entirely on `localhost` across two ports; no
  authentication, no external network dependency at runtime.
- **NFR6 (Configurability)** — Rates, sizes, paths, and URLs adjustable via config
  (FR14/FR15).
- **NFR7 (Observability)** — Operator can tell at a glance whether frames are actually
  landing (front-end status + on-disk growth + manifest).

## 7. Out of Scope

- Any computer vision / detection / OCR in this feature (that is the *live processing*
  extension — §3.2).
- Authentication, authorization, TLS, and multi-device or remote capture.
- A dataset review/annotation/gallery UI beyond a simple live status line.
- Encoded video-clip recording (this iteration streams frame bursts, not `.mp4`/`.webm`).
- Deduplication, compression tuning, or cloud upload of the collected dataset.

## 8. Success Criteria

- **SC1** — Opening the app in a browser shows a live camera preview; when multiple
  cameras exist, the operator can pick one (FR1–FR2).
- **SC2** — With label `101` set and recording started, frames land on disk under a
  `101` grouping at roughly the configured rate, each filename encoding label + timestamp
  + sequence, and a manifest gains one entry per frame (FR3–FR5, FR9–FR10).
- **SC3** — Stopping, changing the label to something else, and recording again produces a
  new labeled grouping without disturbing the first (FR3, FR13).
- **SC4** — A collected frame file opens as a valid image and `cv2.imread` decodes it to a
  BGR array — i.e. it is ready to hand to `pipeline.run` (NFR1, G4).
- **SC5** — Killing one frame send (or sending a malformed/oversized frame) yields a clear
  error in status and a rejected/500 response, but capture continues and the service stays
  up (FR7, FR11, NFR2).
- **SC6** — Front-end and back-end run concurrently on two localhost ports with no auth,
  started from documented commands (NFR4, NFR5).

## 9. Open Questions

### Resolved (this spec)
- **OQ1 — Frames vs. clips?** ✅ **Continuous frame burst** (auto-capture at a
  configurable rate). Clips are a later option if temporal fidelity requires it (§3.2).
- **OQ2 — What does the label mean?** ✅ **Per-shot label**, encoded into each frame's
  filename; changeable between bursts (A3).
- **OQ3 — How much UI?** ✅ **Minimal + status** — preview, camera select, label,
  start/stop, and a status line. No gallery/review UI this iteration.
- **OQ4 — Deployment shape?** ✅ **Same device, two localhost ports, no auth** (A1, §3.1).

### Still open
- **OQ5 — Target capture rate & image size.** Start with a modest default (see design);
  confirm against real footage volume and disk once we collect a session.
- **OQ6 — When live processing lands, per-frame vs. buffered/tracked processing.** Deferred
  to the live-processing spec; this iteration only guarantees frames are pipeline-ready.
