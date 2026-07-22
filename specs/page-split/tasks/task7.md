# task7 — Back-end: crossings export endpoint (Wave B)

**Model:** sonnet · Independent of the FE tasks.

Source of truth: `../design.md` (§6.1, §7, §8), `tasks/README.md` (FROZEN-3). **Additive
only** — do not touch the engine, pipeline, `models.py`, `config.py`, or the `runs/` layout.
Venv per CLAUDE.md: `.venv/bin/pytest` from repo root.

## Owns (exclusive)
- `collection/backend/app.py`
- `collection/backend/config.yaml` (data/comment only)
- `collection/backend/tests/test_export.py` (new)

## Do — `app.py`

1. **Refactor:** extract the crossing-dict list currently built inline in `get_results` into a
   helper defined inside `create_app` (it closes over `engine`/`FrameStore`):
   ```python
   def _compose_crossings(run: str) -> tuple[str, list[dict]]:
       run_id = FrameStore.safe_label(run)
       if engine is None:
           return run_id, []
       run_id, crossings = engine.crossings(run)
       return run_id, [ { …exact same dict as today… } for c in crossings ]
   ```
   Rewrite `get_results` to `run_id, dicts = _compose_crossings(run); return {"run": run_id,
   "crossings": dicts}` — byte-identical response (guarded by existing `/results` tests).

2. **Add** the export route **before** the StaticFiles mount (FROZEN-3):
   ```python
   @app.get("/results/export")
   async def export_results(run: str = "", format: str = "json"):
       run_id, crossings = _compose_crossings(run)
       if format == "json":
           body = json.dumps({"run": run_id, "crossings": crossings})
           return Response(body, media_type="application/json",
               headers={"Content-Disposition": f'attachment; filename="crossings_{run_id}.json"'})
       if format == "csv":
           text = _crossings_csv(crossings)
           return Response(text, media_type="text/csv",
               headers={"Content-Disposition": f'attachment; filename="crossings_{run_id}.csv"'})
       raise HTTPException(status_code=400, detail="format must be 'csv' or 'json'")
   ```
   - `_crossings_csv(crossings)`: use `io.StringIO` + `csv.writer`; header
     **`number,time,name,category`**; rows sorted by **`order_key` ascending**; map each
     crossing dict → `[number, time, name or "", category or ""]`. Return `buf.getvalue()`.
   - Add `import json`, `import csv`, `import io` and `from fastapi.responses import Response`
     (alongside the existing response imports).

3. **`config.yaml`** — add a comment above `server.allowed_origins` noting that to host the
   front-end on another origin you add that exact origin here (scheme+host+port, no trailing
   slash) and restart. No behavioral change to the default list.

## Do — `tests/test_export.py`
Follow the style of the existing `collection/backend/tests/`. Cover:
- **JSON** export equals the `GET /results` body for the same run (composition parity).
- **CSV** has header `number,time,name,category`, one row per crossing, in `order_key` order,
  with correct quoting for a name containing a comma.
- **Empty run** → 200 with header-only CSV and `{"crossings": []}` JSON.
- **Engine disabled** (app built without live) → 200 empty, not an error.
- **Bad format** (`format=xml`) → 400 with the documented detail.

## Done when
- `.venv/bin/pytest collection/backend/tests/` is green (new `test_export.py` + unchanged
  `/results` tests). No non-owned files touched; engine/pipeline untouched.
