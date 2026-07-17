# Finish-Line Frame Collection App

A browser-based **data-collection tool** for the finish-line rider-number project. It uses
the device camera to capture frames of riders and streams them to a small local back-end
that **writes each frame to disk**, tagged with a human-readable label. The result is an
organized, labeled dataset of real frames.

**This iteration does no computer vision** — the back-end only stores what it receives.
The frames are stored verbatim as JPEG so they drop straight into the existing pipeline
(`src/rider_id/pipeline.py::run`) later. See
[`specs/collection/`](../specs/collection/) for requirements and design.

- **Front-end:** static HTML/JS/CSS (no build step), served on **:8001**.
- **Back-end:** FastAPI, served on **:8000**, in the repo's Python 3.12 `.venv`.

---

## Setup

The back-end reuses the repo's existing **Python 3.12** virtualenv (created for the POC).

```bash
cd comp-vision-results
source .venv/bin/activate            # Python 3.12 — NOT system python3 (3.14)
pip install -r collection/backend/requirements.txt
```

> If `.venv` doesn't exist yet, create it first: `/usr/bin/python3.12 -m venv .venv`
> (see the repo `CLAUDE.md`).

---

## Run

```bash
./collection/run.sh
```

This starts the back-end (:8000) and the static front-end (:8001) and prints the URL.
`Ctrl-C` stops both. Then open **<http://localhost:8001>**.

<details>
<summary>Or start the two processes manually</summary>

```bash
# back-end
cd collection && python -m backend
# front-end (separate terminal)
python -m http.server 8001 --directory collection/frontend
```
</details>

Camera access requires a **secure context**; `localhost` qualifies, so no HTTPS
certificates are needed for local use.

---

## Use

1. Open <http://localhost:8001> and **grant camera permission**.
2. Pick a camera from the dropdown (if the device has more than one).
3. Type a **label** (e.g. `101`, or `lap3-nearside`) — it is attached to every frame
   captured while it's set, and you can change it between bursts.
4. **Start** to begin capturing; the app sends frames continuously at the configured rate.
   **Stop** to end the burst (the preview stays live). Change the label and Start again for
   the next subject.
5. The status line shows recording state, frames sent, frames dropped (backpressure), and
   the last result/error.

---

## Output layout

Everything the back-end writes lives under the storage root (`storage.dir` in
`backend/config.yaml`, default `collected/`). The root is created on first write and is
**gitignored**. Two kinds of thing are written: one **JPEG file per captured frame**
(grouped into a folder per label) and one **append-only `manifest.jsonl`** at the root.

```
collected/                                       # storage root (config: storage.dir)
├── 101/                                          # one folder per sanitized label
│   ├── 101_20260711-093015-482_000000.jpg        # <safe_label>_<timestamp-ms>_<seq>.jpg
│   ├── 101_20260711-093015-648_000001.jpg
│   └── 101_20260711-093015-815_000002.jpg
├── rider-208/                                     # a second label → a second folder
│   ├── rider-208_20260711-093102-104_000000.jpg
│   └── rider-208_20260711-093102-271_000001.jpg
└── manifest.jsonl                                 # append-only index, one line per frame
```

### Frame files

- **Format:** a standard baseline **JPEG**, stored **byte-for-byte** as the browser
  encoded it (`canvas.toBlob('image/jpeg', …)`) — the back-end never re-encodes. So
  `cv2.imread("collected/101/101_….jpg")` decodes it to a **BGR `ndarray`** (e.g.
  `(352, 561, 3)`) — exactly the input `rider_id.pipeline.run(image_bgr, cfg)` takes.
- **Dimensions & quality are capture-time settings, not a fixed format:** width is the
  front-end `TARGET_WIDTH` (downscaled preserving aspect, or camera-native when `0`) and
  compression is `JPEG_QUALITY` (see [Configuration](#configuration)).
- **Folder** = the frame's `safe_label` (see below). Frames from every burst sharing that
  label accumulate in the same folder.

### Filename scheme

```
<safe_label>_<YYYYmmdd-HHMMSS-mmm>_<seq>.jpg
   │              │                   └─ zero-padded session sequence, 6 digits (000123)
   │              └─ UTC server-receive time, millisecond precision
   └─ sanitized label (also the folder name)
```

Example: `101_20260711-093015-482_000000.jpg` → label `101`, received `2026-07-11
09:30:15.482 UTC`, first frame of the session. The **millisecond** timestamp plus the
per-session sequence keep names unique even during a fast burst.

**`safe_label`** is derived from the raw label you type: lowercased; every run of
characters outside `[a-z0-9]` collapses to a single `-`; leading/trailing `-` stripped;
empty result → `unlabeled`; capped at 64 chars. Examples: `101` → `101`,
`"Lap 3 / Nearside"` → `lap-3-nearside`, `""` → `unlabeled`.

### `manifest.jsonl`

An append-only [JSON Lines](https://jsonlines.org/) file — **one JSON object per stored
frame**, in the order received. Append-only means restarting the back-end never rewrites
or clobbers earlier entries. One line, pretty-printed:

```json
{
  "label": "Lap 3 / Nearside",
  "safe_label": "lap-3-nearside",
  "filename": "lap-3-nearside/lap-3-nearside_20260711-093015-482_000123.jpg",
  "seq": 123,
  "session_id": "9f1c2e7a-....",
  "client_ts": "2026-07-11T09:30:15.482Z",
  "server_ts": "2026-07-11T09:30:15.501Z",
  "bytes": 48213,
  "content_type": "image/jpeg"
}
```

| field | type | meaning |
|---|---|---|
| `label` | string | the **raw** label as typed in the browser (un-sanitized) |
| `safe_label` | string | sanitized label = the folder name (rules above) |
| `filename` | string | frame path **relative to the storage root** (`<safe_label>/<file>.jpg`) — join with `storage.dir` to open it |
| `seq` | int | monotonic per-recording-session counter, starts at `0`, resets each **Start** |
| `session_id` | string \| null | client UUID for the recording session (one page-load/Start); `null` if the client didn't send one |
| `client_ts` | string | **capture** time in the browser, ISO-8601 UTC |
| `server_ts` | string | **receive/write** time on the back-end, ISO-8601 UTC, millisecond precision (matches the filename timestamp) |
| `bytes` | int | size of the stored JPEG on disk |
| `content_type` | string | MIME type of the stored frame (`image/jpeg`) |

> **`client_ts` vs `server_ts`:** the first is when the browser grabbed the frame; the
> second is when the back-end persisted it. They differ by transit/queue latency — use
> `client_ts` for capture ordering, `server_ts` (which the filename encodes) for storage
> identity.

### Reading the dataset back

```python
import json, os, cv2
ROOT = "collected"
with open(os.path.join(ROOT, "manifest.jsonl")) as fh:
    for line in fh:
        rec = json.loads(line)
        img = cv2.imread(os.path.join(ROOT, rec["filename"]))   # BGR ndarray, pipeline-ready
        # img -> rider_id.pipeline.run(img, cfg)  (later phase)
```

---

## Configuration

**Front-end — `frontend/config.js`:**

| key | default | meaning |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | where frames are POSTed |
| `CAPTURE_FPS` | `6` | burst capture rate while recording |
| `JPEG_QUALITY` | `0.85` | `canvas.toBlob` quality |
| `TARGET_WIDTH` | `1280` | downscale width (`0` = camera-native) |
| `MAX_IN_FLIGHT` | `3` | in-flight send cap; excess frames are dropped, not queued |

**Back-end — `backend/config.yaml`:** `server.host/port/version`,
`server.allowed_origins` (CORS — must include the front-end origin), `storage.dir`,
`storage.manifest_name`, `limits.max_frame_bytes`, `limits.allowed_content_types`.

---

## HTTP API

- `GET /health` → `200 {"status":"ok","version":"…"}`
- `POST /frames` (`multipart/form-data`: `image` JPEG, `label`, `client_ts`, `seq`,
  optional `session_id`) → `201 {"status":"ok","stored":"<label>/<file>.jpg","seq":N,"server_ts":"…"}`.
  Errors return `{"status":"error","detail":"…"}` with `400` (missing/blank field, bad
  `seq`, empty image), `413` (too large), `415` (not JPEG), `500` (disk write failed).

---

## Troubleshooting

- **No camera / permission denied** — the status line reports it. Ensure you opened the
  page over `http://localhost:8001` (a secure context), not a `file://` path or LAN IP.
- **Frames not landing / CORS error in console** — `server.allowed_origins` in
  `backend/config.yaml` must list the front-end origin (`http://localhost:8001`).
- **Back-end down** — the front-end keeps capturing and reports send errors in the status
  line; nothing freezes. Restart the back-end and captures resume.
- **Wrong Python** — always `source .venv/bin/activate` first; system `python3` is 3.14 and
  breaks the shared CV wheels.

---

## Verified end-to-end

- Frames stream to `collected/<label>/…jpg` at the configured rate with one manifest line
  each; re-labeling creates a separate folder without disturbing the first.
- A stored frame decodes with `cv2.imread` to a BGR array (e.g. `(352, 561, 3)`) — pipeline-ready.
- Oversized / non-JPEG / missing-field requests are rejected with the documented status and
  the service stays up.
- Back-end test suite: `pytest collection/backend/tests/` (23 passing).

> **Note:** the live-camera capture loop was verified by serving the front-end and by
> code review; the on-disk / manifest / `cv2.imread` path was verified end-to-end with
> real multipart POSTs (no physical camera was available in the build environment). Run
> `./collection/run.sh` and open the page to exercise the full camera path in a browser.

## Next: live processing

The back-end stores frames as one **sink**. The later live-processing phase adds a second
sink on the same received frame — `cv2.imdecode` → `rider_id.pipeline.run(image_bgr, cfg)`
— reusing the POC pipeline unchanged. Because the back-end already lives in the CV venv,
that's a direct import, not a new service. See design §8.
