"""app.py — FastAPI application factory.

create_app(cfg, live=None) is FROZEN (design §6).
"""
from __future__ import annotations

import asyncio
import dataclasses
import os
import urllib.parse
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import AppConfig, FrameMeta
from .storage import FrameStore

if TYPE_CHECKING:
    from .live_config import LiveConfig


def create_app(cfg: AppConfig, live: "LiveConfig | None" = None) -> FastAPI:
    """Create and return the FastAPI application.

    Routes:
      GET  /health                      -> 200 {"status": "ok", "version": cfg.version}
      POST /frames                      -> validate -> FrameStore.save -> 201 body per design §4
      GET  /runs                        -> {"runs": [...]}
      GET  /results?run=<label>         -> {"run": "<safe>", "crossings": [...]}
      POST /roster                      -> set run roster; 200 or 400/503
      GET  /crossings/{id}/image        -> FileResponse or 404

    CORS middleware allows cfg.allowed_origins.
    Static files mount last so API routes take precedence.
    """
    # ------------------------------------------------------------------
    # Conditionally import and initialise the engine (live mode only).
    # Pure collection must NOT import rider_id / cv2.
    # ------------------------------------------------------------------
    engine = None
    if live and live.enabled:
        # Import engine first — its module-level sys.path shim inserts <repo>/src
        # so that the subsequent rider_id import resolves correctly.
        from .engine import ResultsEngine  # noqa: E402 (triggers sys.path shim)
        from rider_id.config import load_config as load_cv_config  # type: ignore[import]

        cv_cfg = load_cv_config(live.cv_config_path)
        engine = ResultsEngine(live, cv_cfg, cfg.storage_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if engine is not None:
            await engine.start()
        yield
        if engine is not None:
            await engine.stop()

    app = FastAPI(title="Collection Back-end", version=cfg.version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Single FrameStore instance for the lifetime of the app
    store = FrameStore(cfg.storage_dir, cfg.manifest_name)

    # Custom exception handler so HTTPException bodies match the documented shape:
    # {"status": "error", "detail": "<msg>"}
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "detail": exc.detail},
        )

    # Missing/invalid required form fields are rejected by FastAPI *before* the
    # handler runs. Map them to the documented 400 + error body (design §4) rather
    # than FastAPI's default 422.
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errs = exc.errors()
        missing = [str(e["loc"][-1]) for e in errs if e.get("type") == "missing"]
        if missing:
            detail = f"Missing required field(s): {', '.join(missing)}"
        else:
            detail = errs[0].get("msg", "Invalid request") if errs else "Invalid request"
        return JSONResponse(status_code=400, content={"status": "error", "detail": detail})

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": cfg.version}

    # ------------------------------------------------------------------
    # GET /runs
    # ------------------------------------------------------------------
    @app.get("/runs")
    async def get_runs():
        """List known run ids.

        Disabled mode (README refinement 3): returns {"runs": []}.
        """
        if engine is None:
            return {"runs": []}
        return {"runs": engine.runs()}

    # ------------------------------------------------------------------
    # GET /results?run=<label>
    # ------------------------------------------------------------------
    @app.get("/results")
    async def get_results(run: str = ""):
        """Return crossings for one run.

        Disabled mode: returns {"run": <safe>, "crossings": []}.
        Crossing dicts gain: source, edited, order_key, order_overridden (§5).
        """
        run_id = FrameStore.safe_label(run)
        if engine is None:
            return {"run": run_id, "crossings": []}

        run_id, crossings = engine.crossings(run)
        crossing_dicts = [
            {
                "crossing_id": c.crossing_id,
                "run": c.run,
                "number": c.number,
                "time": c.time,
                "confidence": c.confidence,
                "name": c.name,
                "category": c.category,
                "matched": c.matched,
                "annotated_url": f"/crossings/{c.crossing_id}/image",
                "last_seen": c.last_seen,
                "source": c.source,
                "edited": c.edited,
                "order_key": c.order_key,
                "order_overridden": c.order_overridden,
            }
            for c in crossings
        ]
        return {"run": run_id, "crossings": crossing_dicts}

    # ------------------------------------------------------------------
    # POST /roster
    # ------------------------------------------------------------------
    @app.post("/roster")
    async def post_roster(
        run: str = Form(...),
        roster: UploadFile = File(...),
    ):
        """Set one run's roster.

        Disabled mode: 503 {"status": "error", "detail": "live processing disabled"}.
        """
        if engine is None:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "live processing disabled"},
            )

        csv_text = (await roster.read()).decode("utf-8", errors="replace")
        try:
            run_id, count = engine.set_roster(run, csv_text)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": str(exc)},
            )

        return {"status": "ok", "run": run_id, "count": count}

    # ------------------------------------------------------------------
    # GET /crossings/{crossing_id}/image
    # ------------------------------------------------------------------
    @app.get("/crossings/{crossing_id}/image")
    async def get_crossing_image(crossing_id: str):
        """Serve the annotated jpg for a crossing.

        Disabled mode (engine is None): 404.
        """
        if engine is None:
            raise HTTPException(status_code=404, detail="Not found")

        path = engine.annotated_path(crossing_id)
        if path is None or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Not found")

        return FileResponse(path, media_type="image/jpeg")

    # ------------------------------------------------------------------
    # Helper: 503 disabled response
    # ------------------------------------------------------------------
    def _disabled_503() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "live processing disabled"},
        )

    # ------------------------------------------------------------------
    # GET /status?run=
    # ------------------------------------------------------------------
    @app.get("/status")
    async def get_status(run: str = ""):
        """Queue status for a run.

        Disabled mode: {"enabled": false}.
        """
        if engine is None:
            return {"enabled": False}
        run_id = FrameStore.safe_label(run)
        try:
            result = await asyncio.to_thread(engine.status, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return result

    # ------------------------------------------------------------------
    # GET /roster?run=  (refinement 2)
    # ------------------------------------------------------------------
    @app.get("/roster")
    async def get_roster(run: str = ""):
        """Return roster entries for a run.

        Disabled mode: {"run": <safe>, "riders": []}.
        """
        run_id = FrameStore.safe_label(run)
        if engine is None:
            return {"run": run_id, "riders": []}

        roster = engine._rosters.get(run_id)
        riders = sorted(
            [
                {
                    "number": number,
                    "name": entry[0],
                    "category": entry[1],
                }
                for number, entry in roster.entries.items()
            ],
            key=lambda r: r["number"],
        )
        return {"run": run_id, "riders": riders}

    # ------------------------------------------------------------------
    # GET /frames?run=&center=&span=&limit=
    # ------------------------------------------------------------------
    @app.get("/frames")
    async def get_frames(
        run: str = "",
        center: str = "",
        span: float = 12.0,
        limit: int = 300,
    ):
        """Return frame browser payload.

        Disabled mode: {"run": <safe>, "meta": {"count": 0, "first_ts": null,
        "last_ts": null}, "frames": []}.
        span default 12 s; limit default/max 300.
        """
        run_id = FrameStore.safe_label(run)
        if engine is None:
            return {
                "run": run_id,
                "meta": {"count": 0, "first_ts": None, "last_ts": None},
                "frames": [],
            }

        center_ts = center if center else None
        capped_limit = min(limit, 300)

        try:
            result = await asyncio.to_thread(
                engine.frames, run_id, center_ts, span, capped_limit
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # Add "url" to each frame dict (refinement 9)
        for frame in result.get("frames", []):
            fname = frame.get("filename", "")
            frame["url"] = (
                f"/frames/image?run={urllib.parse.quote(run_id)}"
                f"&filename={urllib.parse.quote(fname)}"
            )

        return result

    # ------------------------------------------------------------------
    # GET /frames/image?run=&filename=
    # ------------------------------------------------------------------
    @app.get("/frames/image")
    async def get_frame_image(run: str = "", filename: str = ""):
        """Serve a raw collected frame image.

        Disabled mode (engine is None): 404.
        """
        if engine is None:
            raise HTTPException(status_code=404, detail="Not found")

        run_id = FrameStore.safe_label(run)
        path = engine.frame_path(run_id, filename)
        if path is None or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Not found")

        return FileResponse(path, media_type="image/jpeg")

    # ------------------------------------------------------------------
    # POST /crossings
    # ------------------------------------------------------------------
    @app.post("/crossings", status_code=201)
    async def post_crossings(body: dict):
        """Manually create a crossing (POST /crossings).

        Body: {"run", "filename", "client_ts", "number": ""}
        Returns 201 crossing dict.
        Disabled mode: 503.
        """
        if engine is None:
            return _disabled_503()

        run = body.get("run", "")
        filename = body.get("filename", "")
        client_ts = body.get("client_ts", "")
        number = body.get("number", "")

        if not run or not filename or not client_ts:
            raise HTTPException(
                status_code=400,
                detail="Missing required field(s): run, filename, or client_ts",
            )

        try:
            crossing = await asyncio.to_thread(
                engine.create_crossing, run, filename, client_ts, number
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return JSONResponse(status_code=201, content=dataclasses.asdict(crossing))

    # ------------------------------------------------------------------
    # PATCH /crossings/{crossing_id}
    # ------------------------------------------------------------------
    @app.patch("/crossings/{crossing_id}")
    async def patch_crossing(crossing_id: str, body: dict):
        """Edit a crossing's number or soft-delete it.

        Body must contain ≥1 of: {"number"?: str, "deleted"?: bool}
        Disabled mode: 503.
        """
        if engine is None:
            return _disabled_503()

        has_number = "number" in body
        has_deleted = "deleted" in body
        if not has_number and not has_deleted:
            raise HTTPException(
                status_code=400,
                detail="Body must contain at least one of: 'number', 'deleted'",
            )

        kwargs: dict[str, Any] = {}
        if has_number:
            kwargs["number"] = str(body["number"])
        if has_deleted:
            kwargs["deleted"] = bool(body["deleted"])

        try:
            crossing = await asyncio.to_thread(
                engine.edit_crossing, crossing_id, **kwargs
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return dataclasses.asdict(crossing)

    # ------------------------------------------------------------------
    # POST /crossings/{crossing_id}/position
    # ------------------------------------------------------------------
    @app.post("/crossings/{crossing_id}/position")
    async def set_crossing_position(crossing_id: str, body: dict):
        """Reorder a crossing.

        Body: {"earlier_id": str|null, "later_id": str|null}
        Disabled mode: 503.
        """
        if engine is None:
            return _disabled_503()

        earlier_id = body.get("earlier_id")
        later_id = body.get("later_id")

        if earlier_id is None and later_id is None:
            raise HTTPException(
                status_code=400,
                detail="At least one of 'earlier_id' or 'later_id' must be provided",
            )

        try:
            crossing = await asyncio.to_thread(
                engine.set_position, crossing_id, earlier_id, later_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return dataclasses.asdict(crossing)

    # ------------------------------------------------------------------
    # GET /candidates?run=
    # ------------------------------------------------------------------
    @app.get("/candidates")
    async def get_candidates(run: str = ""):
        """Return all candidates for a run (all states).

        Disabled mode: {"run": <safe>, "candidates": []}.
        """
        run_id = FrameStore.safe_label(run)
        if engine is None:
            return {"run": run_id, "candidates": []}

        try:
            run_id, candidate_list = await asyncio.to_thread(engine.candidates, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        candidate_dicts = []
        for c in candidate_list:
            d = dataclasses.asdict(c)
            d["image_url"] = f"/candidates/{c.candidate_id}/image"
            candidate_dicts.append(d)

        return {"run": run_id, "candidates": candidate_dicts}

    # ------------------------------------------------------------------
    # POST /candidates/{candidate_id}/resolve
    # ------------------------------------------------------------------
    @app.post("/candidates/{candidate_id}/resolve")
    async def resolve_candidate(candidate_id: str, body: dict):
        """Promote or dismiss a candidate.

        Body: {"action": "promote"|"dismiss", "number": ""}
        Disabled mode: 503.
        """
        if engine is None:
            return _disabled_503()

        action = body.get("action", "")
        number = body.get("number", "")

        if action not in ("promote", "dismiss"):
            raise HTTPException(
                status_code=400,
                detail="'action' must be 'promote' or 'dismiss'",
            )

        try:
            result = await asyncio.to_thread(
                engine.resolve_candidate, candidate_id, action, number
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return result

    # ------------------------------------------------------------------
    # GET /candidates/{candidate_id}/image
    # ------------------------------------------------------------------
    @app.get("/candidates/{candidate_id}/image")
    async def get_candidate_image(candidate_id: str):
        """Serve the representative raw frame for a candidate.

        Disabled mode (engine is None): 404.
        """
        if engine is None:
            raise HTTPException(status_code=404, detail="Not found")

        path = engine.candidate_image_path(candidate_id)
        if path is None or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Not found")

        return FileResponse(path, media_type="image/jpeg")

    # ------------------------------------------------------------------
    # POST /frames (extended: adds "run" field + engine notify)
    # ------------------------------------------------------------------
    @app.post("/frames", status_code=201)
    async def post_frame(
        image: UploadFile = File(...),
        label: str = Form(...),
        client_ts: str = Form(...),
        seq: str = Form(...),
        session_id: str | None = Form(default=None),
    ):
        """Validate, store, and record one captured frame (design §4).

        Returns 201 on success; 400/413/415/500 on failure.
        Body gains "run": stored.safe_label compared to the previous spec.
        After store.save, calls engine.notify(stored.safe_label) if live.
        """
        # --- 415: wrong content-type ---
        if image.content_type not in cfg.allowed_content_types:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Unsupported content type '{image.content_type}'. "
                    f"Allowed: {', '.join(cfg.allowed_content_types)}"
                ),
            )

        # --- 400: blank required fields ---
        if not label or not label.strip():
            raise HTTPException(status_code=400, detail="Field 'label' must not be blank.")
        if not client_ts or not client_ts.strip():
            raise HTTPException(status_code=400, detail="Field 'client_ts' must not be blank.")

        # --- 400: seq must be a non-negative integer ---
        try:
            seq_int = int(seq)
            if seq_int < 0:
                raise ValueError("negative")
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Field 'seq' must be a non-negative integer, got: {seq!r}",
            )

        # Read image bytes (do this before size check so we only read once)
        data = await image.read()

        # --- 400: empty image body ---
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="Field 'image' must not be empty.")

        # --- 413: image exceeds limit ---
        if len(data) > cfg.max_frame_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Image size {len(data)} bytes exceeds limit of "
                    f"{cfg.max_frame_bytes} bytes."
                ),
            )

        # Build metadata object
        meta = FrameMeta(
            label=label,
            seq=seq_int,
            session_id=session_id if session_id else None,
            client_ts=client_ts,
            content_type=image.content_type,
        )

        # --- Store; map disk errors to 500 (service stays up, FR11/NFR2) ---
        try:
            stored = store.save(data, meta)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Disk write failed: {exc}",
            )

        # Notify engine (if live) — O(1), never blocks the response
        if engine is not None:
            engine.notify(stored.safe_label)

        return JSONResponse(
            status_code=201,
            content={
                "status": "ok",
                "stored": stored.filename,
                "run": stored.safe_label,
                "seq": meta.seq,
                "server_ts": stored.server_ts,
            },
        )

    # ------------------------------------------------------------------
    # Static files — MUST be mounted LAST so API routes take precedence
    # ------------------------------------------------------------------
    _frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    _frontend_dir = os.path.normpath(_frontend_dir)
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="static")

    return app
