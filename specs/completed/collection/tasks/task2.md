# Task 2 — Back-end API & Storage

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task4
**Milestone:** M2 (design §13)  **Runs in parallel with:** task3

## Objective
Implement the real `POST /frames` behaviour: validate the request, store the JPEG bytes
to disk under a per-label folder, and append a manifest line — exactly per the frozen
HTTP API (design §4) and on-disk layout (design §5). After this task, frames actually
land on disk with metadata.

## Read first
`../requirements.md` (§5.2 back-end FRs, §6 NFRs), `../design.md` (§4 HTTP API, §5 disk
layout, §6 signatures), and **task1's final report** for the exact frozen signatures.

## Files you own
```
comp-vision-results/collection/backend/
  storage.py             # IMPLEMENT FrameStore fully
  app.py                 # REPLACE the stub POST /frames body with the real handler
  tests/test_frames.py   # ADD storage/validation tests (keep task1's health test)
```
Do **not** touch `models.py`, `config.py`, `config.yaml`, `__main__.py` (task1's frozen
contracts), and do **not** touch anything under `frontend/` (task3 owns it).

## Implement — `storage.py`

```python
class FrameStore:
    def __init__(self, root: str, manifest_name: str): ...
    @staticmethod
    def safe_label(label: str) -> str: ...
    def save(self, frame_bytes: bytes, meta: FrameMeta) -> StoredFrame: ...
```

- **`safe_label(label)`** (design §5): lowercase; collapse every run of chars outside
  `[a-z0-9]` to a single `-`; strip leading/trailing `-`; empty result → `"unlabeled"`;
  cap at 64 chars. Pure/deterministic — cover it directly in tests.
- **`__init__`** stores `root` and `manifest_name`; create `root` if missing (`os.makedirs(..., exist_ok=True)`).
- **`save(frame_bytes, meta)`**:
  1. `safe = safe_label(meta.label)`; ensure `<root>/<safe>/` exists.
  2. `server_ts` = current UTC, ISO-8601 **ms precision** (e.g. `...T09:30:15.501Z`).
  3. filename = `<safe>_<YYYYmmdd-HHMMSS-mmm>_<seq:06d>.jpg` (timestamp from `server_ts`,
     ms included so bursts don't collide — design §5).
  4. write `frame_bytes` to `<root>/<safe>/<filename>` (binary, verbatim — **no
     re-encode**, per NFR1).
  5. append one JSON line to `<root>/<manifest_name>` with the manifest schema from
     design §5 (`label, safe_label, filename, seq, session_id, client_ts, server_ts,
     bytes, content_type`); `filename` is **relative to root** = `<safe>/<filename>`.
     Open in append mode + write `json.dumps(...) + "\n"` so restarts never clobber (FR13).
  6. return `StoredFrame(filename=<safe>/<filename>, safe_label=safe, server_ts=..., bytes=len(frame_bytes))`.

Keep manifest appends safe against interleaving (single `open(..., "a")` write per line is
atomic enough for one local process; do not hold the file open across requests).

## Implement — `app.py` `POST /frames` handler

Replace the task1 stub body. Wire a module-level `FrameStore(cfg.storage_dir,
cfg.manifest_name)` built inside `create_app`. Handler steps (design §4):

1. Parse multipart form: `image` (`UploadFile`), `label`, `client_ts`, `seq`,
   `session_id` (optional). FastAPI: `image: UploadFile = File(...)`, others `Form(...)`.
2. **Validate** → return the documented error + JSON `{"status":"error","detail":...}`:
   - `415` if `image.content_type` not in `cfg.allowed_content_types`.
   - `400` if `label`/`client_ts` blank, `seq` not a non-negative int, or image body empty.
   - `413` if `len(bytes) > cfg.max_frame_bytes` (read the upload, then check).
3. Build `FrameMeta(label, seq=int(seq), session_id, client_ts, content_type=image.content_type)`.
4. `stored = store.save(data, meta)`.
5. On success return **201** `{"status":"ok","stored": stored.filename, "seq": meta.seq,
   "server_ts": stored.server_ts}`.
6. On write failure (`OSError`) return **500** `{"status":"error","detail":...}` — do not
   let the exception escape uncaught (service stays up, FR11/NFR2).

Use FastAPI so validation errors return **your** JSON shape/status codes (raise
`HTTPException(status_code=..., detail=...)` and confirm the body matches §4 — add an
exception handler if needed to emit `{"status":"error","detail":...}`). Keep the CORS
middleware task1 added (`cfg.allowed_origins`).

## Tests — `tests/test_frames.py`
Use FastAPI `TestClient`. Point the store at a **tmp dir** (build an `AppConfig` with
`storage_dir=tmp_path`). Cover:
- `safe_label`: `"101"→"101"`, `"Lap 3 / Nearside"→"lap-3-nearside"`, `""→"unlabeled"`,
  over-long input capped at 64.
- **Happy path:** POST a tiny valid JPEG (generate in-memory) with label `101`, seq `0` →
  201; assert the file exists under `<tmp>/101/…jpg`, bytes match, and `manifest.jsonl`
  gained exactly one line with the expected fields.
- **415** wrong content-type, **400** missing label / bad seq, **413** oversized (set a
  tiny `max_frame_bytes` in the test config).
- **Restart-safe:** two saves append two manifest lines; existing files untouched.
- Keep the existing `/health` smoke test.

Generate a minimal valid JPEG without new deps, e.g. a tiny bytes literal or
`open(...,'rb')` of an existing sample. (`../../ridersFromThBack.jpg` exists in the repo
root if you need a real JPEG — read its bytes.)

## Acceptance criteria
- `source ../../.venv/bin/activate && pytest collection/backend/tests/` all green.
- Running the service (`cd collection && python -m backend`) + a real `curl -F
  image=@../../ridersFromThBack.jpg -F label=101 -F client_ts=... -F seq=0
  http://127.0.0.1:8000/frames` returns 201 and writes `collected/101/101_*.jpg` +
  a `collected/manifest.jsonl` line.
- A stored file is byte-identical to the uploaded JPEG (verbatim store; verify with `cmp`).
- Invalid requests return the documented 400/413/415 and the service keeps running.

## Out of scope
Front-end, `run.sh`, README, and end-to-end browser verification — task3/task4.

## Final report to include
Confirm acceptance criteria; note the exact error bodies/status codes produced and any
deviation you had to flag (you must **not** change the frozen §4/§5 contracts — stop and
flag instead).
