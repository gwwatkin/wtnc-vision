# Task 1 — Scaffold, Frozen Contracts & Environment

**Agent:** sonnet  **Depends on:** nothing  **Blocks:** all other tasks
**Milestone:** M1 (design §13)

## Objective
Stand up the collection app skeleton so the back-end and front-end agents each have a
fixed structure, the **frozen contracts** (design §4/§5/§6/§7) as code stubs, the web deps
installed in the repo venv, and a back-end that serves `GET /health` and a **stub**
`POST /frames` (validates nothing yet, writes nothing, returns 201) plus a static page
that loads. This proves the plumbing before any real capture or storage logic.

## Read first
`../requirements.md`, `../design.md` (esp. §4 HTTP API, §5 disk layout, §6 signatures,
§7 front-end config, §9 config, §11 structure).

## Files you own (create all)
```
comp-vision-results/
  collection/
    backend/
      __init__.py
      __main__.py            # `python -m backend` → uvicorn (reads config.yaml)
      app.py                 # create_app(cfg) with GET /health + STUB POST /frames
      storage.py             # FrameStore — signatures + NotImplementedError stubs
      config.py              # load_config(path) -> AppConfig  (IMPLEMENT this one)
      models.py              # FROZEN dataclasses (AppConfig, FrameMeta, StoredFrame)
      config.yaml            # design §9 verbatim
      requirements.txt       # web deps
      tests/__init__.py
      tests/test_frames.py   # ONE smoke test: GET /health == 200 {"status":"ok",...}
    frontend/
      index.html             # static skeleton: preview area, camera select, label,
                             #   start/stop button, status line (no JS logic yet)
      app.js                 # empty/stub (console.log("collection ready"))
      styles.css             # minimal layout
      config.js              # window.COLLECTION_CONFIG with the frozen keys (design §7)
    README.md                # one-line placeholder ("see specs/collection")
```
Also update `comp-vision-results/.gitignore` to add `collected/`.

Downstream tasks fill in the stubs: task2 implements `storage.py` + the real `/frames`
handler in `app.py`; task3 implements `app.js` + fleshes out `index.html`.

## Contracts to define (exact — downstream must not change these)

`models.py` — reproduce design §6 dataclasses **verbatim**:
`AppConfig`, `FrameMeta`, `StoredFrame` (fields and types exactly as specified).

`storage.py` — signatures only (stub bodies raise `NotImplementedError`, except
`safe_label` which task2 implements — leave it stubbed here):
```python
class FrameStore:
    def __init__(self, root: str, manifest_name: str): ...
    @staticmethod
    def safe_label(label: str) -> str: ...
    def save(self, frame_bytes: bytes, meta: FrameMeta) -> StoredFrame: ...
```

`app.py`:
```python
def create_app(cfg: AppConfig) -> FastAPI:
    # GET /health  -> 200 {"status": "ok", "version": cfg.version}
    # POST /frames -> STUB: return 201 {"status":"ok","stored":None,"seq":0,"server_ts":...}
    #   (no validation, no write yet — task2 replaces this body)
    # CORS middleware allowing cfg.allowed_origins
```

`config.py` — **implement** `load_config(path) -> AppConfig`: parse `config.yaml`
(`server`, `storage`, `limits`) into `AppConfig`, coercing `allowed_content_types` to a
tuple. This is real code so task2 can rely on it.

`config.js` — the frozen keys from design §7:
```js
window.COLLECTION_CONFIG = {
  BACKEND_URL: "http://localhost:8000",
  CAPTURE_FPS: 6,
  JPEG_QUALITY: 0.85,
  TARGET_WIDTH: 1280,
  MAX_IN_FLIGHT: 3,
};
```

## config.yaml
Reproduce design §9 verbatim (server host/port/version/allowed_origins, storage
dir/manifest_name, limits max_frame_bytes/allowed_content_types).

## requirements.txt (back-end web deps only)
```
fastapi
uvicorn[standard]
python-multipart
```
(`pyyaml` is already in the repo venv from the POC.)

## Environment
The back-end uses the **repo's existing Python 3.12 venv** (created by the POC at
`comp-vision-results/.venv`). Do **not** create a new venv and do **not** use system
`python3` (3.14 — breaks the shared CV wheels; see CLAUDE.md).

```bash
cd comp-vision-results
source .venv/bin/activate
python --version                 # must print Python 3.12.x
pip install -r collection/backend/requirements.txt
python -c "import fastapi, uvicorn, multipart; print('web deps OK')"
```
If `.venv` does not exist, create it exactly as CLAUDE.md/POC task1 specify
(`/usr/bin/python3.12 -m venv .venv`) and note it in your report.

`__main__.py` must launch uvicorn against `create_app(load_config("collection/backend/config.yaml"))`
on `cfg.host:cfg.port` so `python -m backend` (run from `collection/`) boots the service.

## Acceptance criteria
- `source .venv/bin/activate && cd collection && python -m backend` boots without error and
  serves `GET http://127.0.0.1:8000/health` → `200 {"status":"ok","version":"0.1.0"}`.
- `POST /frames` (stub) returns **201** with the shape above (no file written yet).
- `pytest collection/backend/tests/test_frames.py` passes (health smoke test).
- `python -m http.server 8001 --directory collection/frontend` serves `index.html`; the
  page loads and `app.js` logs "collection ready" in the console.
- `models.py` matches design §6 exactly; all stub modules import cleanly.
- `.gitignore` includes `collected/`.

## Out of scope
Real frame validation, storage, the capture loop, `run.sh`, and full README — tasks 2–4.

## Final report to include
Confirm acceptance criteria, note any venv/deps issues, and list the exact frozen
signatures (`models.py` dataclasses + `FrameStore`/`create_app`/`config.js` keys) so
task2 and task3 can rely on them.
