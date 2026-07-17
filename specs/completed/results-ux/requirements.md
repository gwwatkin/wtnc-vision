# Requirements — Race Results Timeline UX

## 1. Background & Purpose

The CV pipeline (see the completed POC) detects riders crossing the finish line and
reads their printed back-number. A later iteration will emit those crossings as a
simple CSV. Separately, race organisers hold a roster CSV mapping each number to a
rider's name and category.

Right now there is **no way to view these crossings** as they happen. We want a
**web-based results timeline** that merges the two CSVs and displays crossings as a
scrollable, human-readable feed — the kind of thing an official or spectator can watch
at the finish line to see who just came through, in order, with the gaps between them
made obvious.

This document is *what & why* only. Technology choices belong in `design.md`.

## 2. Goals

- **G1** — Present finish-line crossings as a **vertical timeline**, newest at the top.
- **G2** — Enrich each crossing with the rider's **name and category** from the roster.
- **G3** — Make **time gaps** between crossings visually obvious, so packs vs. stragglers
  read at a glance.
- **G4** — Separate categories into **side-by-side lanes** while keeping a single shared
  time axis, so each category reads as its own race yet crossings stay interspersed in
  real time-order.
- **G5** — Be usable on a phone or laptop at the finish line with no install step.

## 3. Scope

### 3.1 This phase
- Consume two CSV inputs (crossings + roster), described in §4.
- Render a single scrollable timeline view of crossings.
- Group/separate entries by the time gap rule (§5, FR4).

### 3.2 Out of scope (captured for context, not built now)
- Producing the crossings CSV — that is the CV pipeline's job (upstream).
- Editing/correcting crossings or roster data in the UI.
- Lap counting, finish placings, elapsed/race time, or category standings.
- Authentication, multi-race management, and results publishing/export.
- Live streaming/websocket updates (see OQ1 — refresh model still open).

## 4. Inputs

### 4.1 Crossings CSV
Columns: `time` (ISO 8601 with offset), `race_number`.

```
2026-07-11T14:47:00-07:00,412
2026-07-11T14:51:15-07:00,456
2026-07-11T14:51:17-07:00,422
```

### 4.2 Roster CSV
Columns: `race_number`, `name`, `category`.

```
412,"George Watkins","Cat 3"
456,"Matthew Wahl","Cat 3"
422,"Alex Clement","Cat 4"
```

### 4.3 Assumptions
- **A1** — A crossing's `race_number` *usually* has a roster match, but not always
  (unread/misread numbers upstream). The UI must degrade gracefully (§5, FR5).
- **A2** — Crossings are not guaranteed to arrive time-sorted; the UI sorts them.
- **A3** — All times share a sensible offset; display uses local wall-clock
  `hour:min:sec`.
- **A4** — Volume is a single race's worth of crossings (hundreds, not millions).

## 5. Functional Requirements

- **FR1** — Load and merge the crossings CSV and roster CSV on `race_number`.
- **FR2** — Display crossings as a **vertical, scrollable timeline, most recent at the
  top** (descending time).
- **FR3** — Each crossing row shows: **rider name**, **race number**, **time of day**
  (`hh:mm:ss`), and **category**.
- **FR4** — When the gap between two consecutive crossings (**across all lanes**, ordered
  globally by time) **exceeds 3 seconds**, insert a **separator** carrying the time (a
  gap label) spanning the full width; consecutive crossings within 3s are shown tightly
  grouped as one "pack" with no separator.
- **FR5** — A crossing with **no roster match** still appears, showing the number and a
  clear "unknown rider" treatment instead of a name/category.
- **FR6** — The gap threshold (default **3s**) should be adjustable without code edits
  where practical.
- **FR7** — Each **category is its own vertical lane, shown side by side**. All lanes
  share **one time axis**: a crossing's vertical position is driven by its time, while
  its lane is driven by its category. Crossings therefore stay **interspersed in true
  time order** across lanes (a later Cat 3 crossing sits above an earlier Cat 4 one),
  each still in its own column.
- **FR8** — Lanes appear only for categories **present in the data**, with a labelled
  header per lane. Unknown-rider / unmatched crossings (FR5) go in their own lane or a
  designated "unknown" column.

## 6. Non-Functional Requirements

- **NFR1 (Zero-install)** — Runs in a standard browser; no client software to install.
- **NFR2 (Readable at a glance)** — Legible on a phone at arm's length; name and number
  are the dominant elements of a row.
- **NFR3 (Offline-friendly)** — Works from local CSV files without external network
  services (consistent with the pipeline's offline stance).
- **NFR4 (Handles unsorted/duplicate-ish input)** — Sorts by time and does not crash on
  missing roster rows or malformed lines.
- **NFR5 (Cost)** — Open-source / no paid licenses.

## 7. Example UX

Newest crossing sits at the top. Each **category is a lane**; all lanes share one time
axis, so a card's vertical position is its crossing time regardless of lane. Crossings
within 3s form a tight pack; a gap over 3s inserts a time-labelled separator spanning
all lanes.

```
┌─────────────────────────────────────────────────────────┐
│  Race Results — live timeline                     ▲ top  │
├──────────────────┬──────────────────┬───────────────────┤
│      Cat 3       │      Cat 4        │     Unknown       │  ← per-category lane headers
├──────────────────┴──────────────────┴───────────────────┤
│  ══ 14:51 ═══════════════════════════════════════════    │  ← gap separator spans all lanes
│                                                          │
│                    ┌────────────────┐                    │
│                    │ #422 A. Clement│ 14:51:17           │  ← newest, sits in Cat 4 lane
│                    │ Cat 4          │                    │
│  ┌────────────────┐└────────────────┘                    │
│  │ #456 M. Wahl   │ 14:51:15                             │  ← 2s earlier → lower, Cat 3 lane
│  │ Cat 3          │                                      │     (interspersed by time)
│  └────────────────┘                                      │
│                                                          │
│  ══ 14:47 ═══════════════════════════════════════════    │  ← >3s gap → new time label
│                                                          │
│  ┌────────────────┐                                      │
│  │ #412 G. Watkins│ 14:47:00                             │
│  │ Cat 3          │                                      │
│  └────────────────┘                    ┌────────────────┐│
│                                         │ #501 Unknown   ││  ← no roster match (FR5, FR8)
│                                         │ 14:46:58       ││     → Unknown lane
│                                         └────────────────┘│
│                                                  ▼ older  │
└──────────────────────────────────────────────────────────┘
```

Reading it:
- **Columns = categories**, **vertical = time** (down is older). The Cat 4 rider at
  14:51:17 sits *above* the Cat 3 rider at 14:51:15 — ordering is global by time even
  though they're in different lanes.
- A **time separator** (`══ 14:51 ══`) spans every lane and appears only where the gap
  to the previous (older) crossing exceeds 3s.
- Within 3s, cards pack tightly at their true vertical offsets; you still see the bunch
  finish, now split across category lanes.
- Unmatched numbers land in the **Unknown** lane with a distinct treatment.
- On a narrow phone screen lanes may need to collapse — see OQ5.

## 8. Success Criteria

- **SC1** — Given the two example CSVs, the page renders the crossings newest-first with
  name, number, time-of-day, and category (FR2, FR3).
- **SC2** — A pair of crossings within 3s renders as one group; a >3s gap renders a
  time-labelled separator (FR4).
- **SC3** — A crossing whose number is absent from the roster still renders with an
  "unknown rider" treatment (FR5).
- **SC4** — The view is legible and scrollable on a phone-width screen (NFR2).

## 9. Open Questions

- **OQ1 — Refresh model.** Is this a static render of a finished CSV, a page you
  reload, or live-updating as crossings arrive? Affects whether we need polling/streaming
  (currently out of scope §3.2). *To confirm before design.*
- **OQ2 — Duplicate crossings.** Can the same rider legitimately appear multiple times
  (multiple laps) in one CSV? If so, is each a separate timeline entry (assumed yes)?
- **OQ3 — Category display.** ✅ Resolved — categories are **side-by-side lanes on a
  shared time axis** (G4, FR7). Still open: any colour-coding per lane, or header text
  only?
- **OQ4 — Gap value.** Is 3s final, or should the default be tuned against real data?
- **OQ5 — Narrow screens.** With one lane per category, how should lanes behave on a
  phone (horizontal scroll, collapse to a single interleaved column, or a category
  picker)? NFR2 wants phone legibility; lanes trade against it. *To decide at design.*
- **OQ6 — Lane ordering & count.** How are lanes ordered (roster order, alphabetical,
  crossings-so-far), and is there a sane cap before it stops fitting on screen?
