# Requirements — Finish-Line Rider Number Recognition

## 1. Background & Purpose

We time a road-cycling race in which riders complete multiple laps of a circuit.
A fixed camera at the finish line watches riders cross after each lap. Each rider
wears a number printed in black on a white cloth panel, pinned to the **lower back**
of their jersey.

Today, lap crossings are logged/reviewed manually. We want a computer-vision system
that **automatically detects each rider crossing the finish line and reads their back
number**, producing a per-lap crossing log. Genuinely ambiguous cases will still be
reviewed by a human, so the system does **not** need to be perfect — it needs to
correctly capture the large majority of crossings and make the rest easy to review.

## 2. Goals

- **G1** — Automatically read the back number of riders as they cross the finish line.
- **G2** — Record each crossing as a structured event: `number`, `lap`, `timestamp`.
- **G3** — Capture the **bulk** of crossings correctly; flag low-confidence ones for
  fast human review rather than silently guessing.
- **G4** — Use free / open-source software wherever possible (see §7 Licensing).

## 3. Scope

### 3.1 This document / current phase — Proof of Concept (POC)
The POC is built and validated against a **single still image**
(`ridersFromThBack.jpg` in this folder), representative of our real camera placement:
elevated, slightly behind and to the side of the riders, looking at their backs.

POC objective: prove that we can **detect riders and read the printed back numbers**
from a frame like our real footage, with usable accuracy and confidence scores.

### 3.2 Full system (later phases — out of scope for the POC build, listed for context)
- Ingest live or recorded video at the finish line.
- Detect the finish-line crossing event per rider.
- Maintain per-rider lap counts across the whole race.
- Real-time (or faster-than-real-time offline) operation.

## 4. Key Facts & Assumptions (established with stakeholder)

- **A1** — Camera is **fixed** at the finish line; riders cross one region of the
  frame at the moment that matters.
- **A2** — In that near "crossing zone," a rider's back number is **large and clearly
  legible** (unlike riders far up the road, whose numbers are small/occluded — those
  do **not** need to be read).
- **A3** — Video runs at **~24 fps**, so each rider appears in many frames while
  crossing. **Only one good frame per rider is needed** to read the number; we do not
  require multi-frame voting for the POC.
- **A4** — Numbers are **printed digits on a white cloth panel** pinned to the lower
  back (not handwritten, consistent style).
- **A5** — Numbers observed are multi-digit (e.g. `101`, `102`, `103`, `108`).
- **A6** — Line-crossing timing does **not** need to be highly precise; contentious or
  low-confidence results are acceptable to resolve by hand.

## 5. Functional Requirements

### 5.1 POC (still image)
- **FR1** — Accept a single still image as input.
- **FR2** — Detect riders / back-number regions present in the image.
- **FR3** — Read (OCR) the number for each rider whose number is legible in the
  crossing zone.
- **FR4** — For each read, output: the recognized **number**, a **confidence score**,
  and the **bounding box / crop** it came from.
- **FR5** — Produce an **annotated output image** (boxes + recognized numbers overlaid)
  for visual inspection.
- **FR6** — Produce a **structured result file** (e.g. JSON/CSV) listing every detected
  number with its confidence and location.
- **FR7** — Save a **cropped image of each detected number** to support fast human
  review.
- **FR8** — Flag reads below a configurable confidence threshold as
  **"needs review"** rather than dropping or asserting them.

### 5.2 Full system (future — captured now, not built in POC)
- **FR9** — Define a virtual finish line on the camera view.
- **FR10** — Detect and track each rider across frames and fire a **crossing event**
  when they pass the line.
- **FR11** — Associate the read number with the crossing event and increment that
  rider's **lap count**.
- **FR12** — Emit a per-crossing log: `number`, `lap`, `timestamp`, `confidence`,
  `crop image reference`.
- **FR13** — Handle a rider whose number is unreadable on a given lap by emitting an
  "unknown / needs review" event rather than skipping it.

## 6. Non-Functional Requirements

- **NFR1 (Accuracy)** — Correctly read the **majority** of legible crossing-zone
  numbers. Precise target to be set after the POC baseline; the design bias is toward
  *flagging uncertainty* over *confident wrong answers*.
- **NFR2 (Reviewability)** — Every automated decision must be traceable to an image
  crop so a human can verify or correct it quickly.
- **NFR3 (Offline-capable)** — POC must run on recorded/still input without live
  camera or network dependencies. CPU-only execution is acceptable for the POC;
  GPU acceleration is a later performance concern.
- **NFR4 (Configurability)** — Confidence threshold and the crossing-zone region
  should be adjustable without code changes where practical.
- **NFR5 (Cost)** — No paid software licenses required for the intended internal use.

## 7. Licensing Constraint

- **LR1** — Prefer permissively-licensed OSS (MIT / Apache-2.0).
- **LR2** — Any **AGPL-3.0** component (e.g. some YOLO distributions) is acceptable
  **only for internal use**. If the system is ever distributed or offered as a network
  service to third parties, AGPL components must be replaced with permissive
  alternatives or covered by a commercial license. To be revisited at design time.

## 8. Out of Scope

- Reading numbers of riders **not** in the crossing zone (small/occluded up the road).
- Transponder / RFID hardware timing.
- Identity beyond the printed number (face recognition, etc.).
- Race-management UI, results publishing, and scoreboard integration.
- Precise photo-finish ordering of near-simultaneous crossings.

## 9. POC Success Criteria

- **SC1** — Running the POC on `ridersFromThBack.jpg` detects the clearly legible
  back number(s) in the crossing zone and outputs the correct digits.
- **SC2** — Output includes an annotated image, a structured results file, and
  per-number crops (per FR5–FR7).
- **SC3** — Each result carries a confidence score, and low-confidence reads are
  flagged for review (per FR8).
- **SC4** — Results are good enough to justify proceeding to the full video-based
  design phase.

## 10. Open Questions

### Resolved
- **OQ2 — Two riders crossing near-simultaneously.** ✅ Each rider still produces their
  own crossing event. A rider's crossing **timestamp is the time of the first frame in
  which they are detected crossing**; when two riders are close, order follows whichever
  is detected first. Genuinely contentious ties are resolved by hand (A6).
- **OQ3 — Roster available?** ✅ Yes. OCR is validated against the start-list
  (see design §3 step 5); on by default.
- **OQ4 — Number format.** ✅ 1–3 digits, black on white, no leading zeros.
- **OQ5 — Deployment target.** ✅ **Single laptop** — the whole system runs locally on
  one laptop (no server/GPU box, no network dependency). Drives model-size and
  performance choices (see design §11).

### Still open
- **OQ1** — Exact accuracy target for the full system (which % of crossings must be
  auto-captured before human review is acceptable). To be set after the POC baseline.
