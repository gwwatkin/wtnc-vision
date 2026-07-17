"""app.py — FastAPI application factory.

create_app(cfg, live=None) is FROZEN (design §6).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

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
