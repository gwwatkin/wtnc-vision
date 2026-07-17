# Finish-Line Frame Collector + Live Results

A browser app that **captures frames from the device camera or a video file** and sends
them to a local back-end that stores them and **runs the CV pipeline asynchronously**,
deduplicated crossings appearing live in the same page below the camera view.

One process, one port: `./run.sh` starts everything on **:8000**. See
[`specs/completed/live-pipeline/`](../specs/completed/live-pipeline/) for requirements and design.

---

## Quick start

```bash
# One-time: install Python deps (Python 3.12 venv)
pip install -r collection/backend/requirements.txt

# Run (from the repo root or collection/)
./collection/run.sh

# Open http://localhost:8000
```

> If `.venv` doesn't exist yet: `/usr/bin/python3.12 -m venv .venv && source .venv/bin/activate`
> (see `CLAUDE.md`).  The first run pulls YOLO/PaddleOCR models — allow a few minutes.

---

## Typical workflow

1. **Upload a roster** (optional but recommended): choose a `number,name,category` CSV
   with the roster-upload button and set the label/run first. Matching numbers will show
   rider names in the timeline.
2. **Pick a frame source**: *Camera* (default) or *Video file* — choose from the Source
   selector. For a video file, click the file input to choose the clip.
3. **Set a label** (e.g. `lap3-nearside`) — this is the *run* name. Every frame captured
   with this label, plus all CV results and the roster, live under `runs/<label>/`.
4. **Start** to begin capturing. Frames are stored and queued for the CV pipeline.
   The results timeline below the camera updates live as crossings are detected.
5. **Click a crossing card** to open a sidebar showing the annotated frame (bounding box +
   recognized number drawn). Close it with the × button or click another card to replace.
6. **Stop** when done. Change the label and start again for the next run.
7. **View past runs**: use the *View run* selector (populated from `GET /runs`) to jump
   to a previous run's results.

---

## On-disk layout

Everything lives under `runs/` (created on first write; gitignored):

```
runs/
  <safe_label>/                    # ONE RUN — all inputs + outputs
    collected/*.jpg                # stored frames (sink 1)
    manifest.jsonl                 # append-only index of all frames (the work queue)
    processed_offset               # worker resume point (one integer)
    crossings.csv                  # append-only: time,number per crossing
    crossings.json                 # rich crossing state (served by GET /results)
    annotated/<crossing_id>.jpg    # annotated representative frame per crossing
    roster.csv                     # uploaded name/category table
    roster.txt                     # valid numbers (used by the CV pipeline)
```

`safe_label` is derived from the raw label: lowercased; non-alphanumeric runs → `-`;
leading/trailing `-` stripped; empty → `unlabeled`; capped at 64 chars.

---

## Configuration

**`backend/config.yaml`** — key sections:

| section.key | default | meaning |
|---|---|---|
| `storage.dir` | `runs/` | root for all run data |
| `live.enabled` | `true` | `false` → pure collection, no CV (SC6) |
| `live.cv_config` | `../../config.yaml` | repo POC pipeline config |
| `live.dedup_window_s` | `5.0` | seconds within which same number = one crossing |
| `live.statuses` | `[confident]` | which pipeline statuses become crossings |

**`frontend/config.js`** — front-end tuning:

| key | default | meaning |
|---|---|---|
| `CAPTURE_FPS` | `6` | burst capture rate |
| `JPEG_QUALITY` | `0.85` | canvas JPEG quality |
| `TARGET_WIDTH` | `1280` | downscale to this width (0 = camera-native) |
| `MAX_IN_FLIGHT` | `3` | max concurrent frame POSTs |
| `RESULTS_POLL_MS` | `1500` | results timeline poll cadence (ms) |

---

## HTTP API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | `{"status":"ok","version":"…"}` |
| `POST` | `/frames` | Store a frame + wake the CV worker |
| `GET` | `/runs` | `{"runs": ["label1","label2"]}` — known run ids |
| `GET` | `/results?run=<label>` | `{"run":"…","crossings":[…]}` — enriched crossings |
| `POST` | `/roster` | Upload `number,name,category` CSV for a run |
| `GET` | `/crossings/<id>/image` | Annotated JPEG for a crossing (sidebar) |

All `run`/`label` params are normalized server-side; the response always echoes the
safe id. With `live.enabled: false`, `/roster` → 503 and `/results` → empty; capture
and storage work unchanged.

---

## Troubleshooting

- **Camera permission denied** — ensure `http://localhost:8000` is used (localhost is a
  secure context; a LAN IP is not).
- **First-run model download slow** — YOLO and PaddleOCR models pull once on first
  inference. Subsequent runs are fast.
- **Processing lags capture** — expected on CPU: the worker drains the manifest queue
  after the burst; capture is never blocked.
- **Wrong Python** — always use `.venv/bin/python` or activate the venv first; system
  `python3` is 3.14 and breaks the CV wheels.
