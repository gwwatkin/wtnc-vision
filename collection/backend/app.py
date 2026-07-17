"""app.py — FastAPI application factory.

create_app(cfg) is FROZEN (design §6). Task2 implements the real POST /frames handler
with validation, FrameStore.save, and documented 201/400/413/415/500 responses.
"""
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import AppConfig, FrameMeta
from .storage import FrameStore


def create_app(cfg: AppConfig) -> FastAPI:
    """Create and return the FastAPI application.

    Routes:
      GET  /health  -> 200 {"status": "ok", "version": cfg.version}
      POST /frames  -> validate -> FrameStore.save -> 201 body per design §4
    CORS middleware allows cfg.allowed_origins.
    """
    app = FastAPI(title="Collection Back-end", version=cfg.version)

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

        return JSONResponse(
            status_code=201,
            content={
                "status": "ok",
                "stored": stored.filename,
                "seq": meta.seq,
                "server_ts": stored.server_ts,
            },
        )

    return app
