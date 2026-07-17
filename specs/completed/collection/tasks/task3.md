# Task 3 — Front-end Capture UI

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task4
**Milestone:** M3 (design §13)  **Runs in parallel with:** task2

## Objective
Implement the static browser app: live camera preview with a camera picker, a label
input, a start/stop control, a continuous burst capture loop that POSTs each frame to the
back-end per the frozen HTTP API (design §4), and a status line with per-frame error
isolation. No build step — plain HTML/JS/CSS + browser APIs.

## Read first
`../requirements.md` (§5.1 front-end FRs, §6 NFRs), `../design.md` (§4 HTTP API request
shape, §7 front-end structure + capture loop + `config.js` keys), and **task1's final
report** for the `config.js` keys and the `/frames` request contract.

## Files you own
```
comp-vision-results/collection/frontend/
  index.html     # flesh out the skeleton: preview, camera <select>, label, start/stop, status
  app.js         # IMPLEMENT camera init + capture loop + POST + status/error handling
  styles.css     # minimal, readable layout
```
Do **not** edit `config.js` (task1 froze its keys — read them via `window.COLLECTION_CONFIG`)
and do **not** touch anything under `backend/` (task2 owns it).

## Implement — behaviour (design §7)

Read config from `window.COLLECTION_CONFIG`: `BACKEND_URL`, `CAPTURE_FPS`, `JPEG_QUALITY`,
`TARGET_WIDTH`, `MAX_IN_FLIGHT`.

**Camera init (FR1–FR2):**
- On load, `navigator.mediaDevices.getUserMedia({video:true})` once to unlock labels,
  then `enumerateDevices()` → populate a camera `<select>` (videoinput devices).
- Stream the selected `deviceId` into a `<video autoplay playsinline muted>` preview.
- Re-acquire the stream when the `<select>` changes (stop old tracks first).
- If permission is denied / no camera, show a clear message in the status line and stop.

**Label (FR3):** a text input; its **current value at capture time** is sent with each
frame. Changeable any time; no restart needed.

**Start/Stop (FR4):** a toggle button.
- **Start:** begin a `setInterval` (or self-rescheduling timeout) at `1000/CAPTURE_FPS` ms.
  Initialise a session: `session_id = crypto.randomUUID()`, `seq = 0`.
- **Stop:** clear the timer. Preview stream stays live. Next Start begins a new session
  (new `session_id`, `seq` reset).

**Capture tick (FR5, NFR3):**
1. If in-flight sends ≥ `MAX_IN_FLIGHT`, **skip this tick** (drop the frame) — do not
   queue. Increment a "dropped" counter for status.
2. Draw the current `<video>` frame to an offscreen `<canvas>`. If `TARGET_WIDTH > 0` and
   the video is wider, scale down to `TARGET_WIDTH` preserving aspect; else native size.
3. `canvas.toBlob(blob => …, 'image/jpeg', JPEG_QUALITY)`.
4. Build `FormData`: `image` (blob, filename e.g. `frame.jpg`), `label` (input value),
   `client_ts` (`new Date().toISOString()`), `seq` (then `seq++`), `session_id`.
5. `fetch(BACKEND_URL + '/frames', {method:'POST', body: formData})`. Track in-flight
   count around the await.

**Status line + error isolation (FR6/FR7, NFR2):**
- Show: recording state, frames sent (2xx), dropped (backpressure), and the last result
  (e.g. `last: 201 101/101_…jpg` or `last error: 413 too large`).
- A failed/thrown `fetch`, or a non-2xx response, updates the status but **must not stop
  the loop** — catch per-send, keep going.
- Optionally poll `GET BACKEND_URL + '/health'` once on load to show back-end reachability;
  a failure here is informational, not fatal.

**index.html:** semantic skeleton wiring the elements (`<video>`, camera `<select>`,
label `<input>`, start/stop `<button>`, status `<div>`), loads `config.js` **before**
`app.js`. **styles.css:** minimal, legible; preview visible; no framework.

## Constraints
- **No build step, no npm, no frameworks, no CDN libs.** Vanilla ES modules / plain script.
- One frame per POST (no batching) — matches design §4/§5.
- Camera needs a secure context; `localhost` qualifies (design §7) — assume the page is
  served over `http://localhost:8001` (task4 provides the static server).

## Acceptance criteria (verifiable without the back-end where possible)
- Served via `python -m http.server 8001 --directory collection/frontend`, the page loads,
  requests camera permission, shows a live preview, and lists cameras in the `<select>`.
- Start begins periodic POSTs to `BACKEND_URL/frames` (observable in the Network tab at
  ~`CAPTURE_FPS`); Stop halts them; the status line updates sent/dropped/last.
- With the back-end **down**, Start does not freeze the tab — status shows send errors and
  capture keeps ticking (FR7). (Full on-disk verification is task4.)
- No console errors on load; `config.js` values are read (not hard-coded).

## Out of scope
Back-end/storage, `run.sh`, README, and the end-to-end on-disk check — task2/task4.

## Final report to include
Confirm acceptance criteria, note browser(s) tested, and flag any place the §4 request
contract felt wrong (stop and flag — do not silently diverge; task2 depends on it).
