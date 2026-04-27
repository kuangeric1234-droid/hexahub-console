from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", debug=settings.DEBUG)
    yield
    log.info("shutdown")


app = FastAPI(
    title="Hexa Hub AI Marketing Portal",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
