"""
Custom middleware: request ID injection, structured request logging,
global exception handler.
"""
from __future__ import annotations

import time
import traceback
import uuid

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a UUID to every request; exposes it in X-Request-ID header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.error(
                "unhandled_exception",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": request_id},
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        log.info(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
