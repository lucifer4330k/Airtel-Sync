from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.routers import mock_registry, quotes
from app.services.catalogue import get_catalogue

configure_logging()
settings = get_settings()

app = FastAPI(
    title="Udyam Digital API",
    version="0.1.0",
    description="Advisor, quote, Smart KYC, order tracker and partner console.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")
api.include_router(mock_registry.router)
api.include_router(quotes.router)


@api.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "reference_date": settings.reference_date.isoformat()}


@api.get("/catalogue", tags=["meta"])
def catalogue():
    return list(get_catalogue().values())


app.include_router(api)
