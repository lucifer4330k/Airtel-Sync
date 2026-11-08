import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import engine
from app.routers import advisor, console, judge, kyc, mock_registry, orders, quotes, whatsapp
from app.services.catalogue import get_catalogue

configure_logging()
log = logging.getLogger("udyam")
settings = get_settings()

if problems := settings.problems():
    if settings.environment == "production":
        raise RuntimeError("Unsafe configuration: " + "; ".join(problems))
    for p in problems:
        log.warning("Config (fine for local dev only): %s", p)


async def _purge_loop() -> None:
    """Nightly KYC image purge for hosts without a cron service."""
    from app.workers.purge_documents import main as purge

    while True:
        await asyncio.sleep(settings.purge_interval_hours * 3600)
        try:
            await asyncio.to_thread(purge)
        except Exception:  # noqa: BLE001 - never take the API down for housekeeping
            log.exception("Scheduled document purge failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_purge_loop()) if settings.run_purge_in_api else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="Udyam Digital API",
    version="1.0.0",
    description="Advisor, quote and checkout, Smart KYC, order tracker and partner console.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")
api.include_router(mock_registry.router)
api.include_router(quotes.router)
api.include_router(kyc.router)
api.include_router(orders.router)
api.include_router(advisor.router)
api.include_router(console.router)
api.include_router(whatsapp.router)
api.include_router(judge.router)


@api.get("/health", tags=["meta"])
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        db = "ok"
    except Exception:  # noqa: BLE001
        db = "unreachable"
    return {
        "status": "ok" if db == "ok" else "degraded",
        "database": db,
        "llm": "on" if (settings.google_api_key or settings.openai_api_key) else "offline rules",
        "reference_date": settings.reference_date.isoformat(),
        "version": app.version,
    }


@api.get("/catalogue", tags=["meta"])
def catalogue():
    return list(get_catalogue().values())


app.include_router(api)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
