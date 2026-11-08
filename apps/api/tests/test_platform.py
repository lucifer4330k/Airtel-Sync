import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models import ConsoleUser, Lead, Order, Product


def test_production_refuses_weak_config():
    weak = Settings(
        environment="production", jwt_secret="change-me", field_encryption_key="", cors_origins="*"
    )
    problems = weak.problems()
    assert any("JWT_SECRET" in p for p in problems)
    assert any("FIELD_ENCRYPTION_KEY" in p for p in problems)
    assert any("CORS_ORIGINS" in p for p in problems)


def test_strong_config_has_no_problems():
    from cryptography.fernet import Fernet

    ok = Settings(
        jwt_secret="s" * 40, field_encryption_key=Fernet.generate_key().decode(), cors_origins="https://x.app"
    )
    assert ok.problems() == []


def test_hosted_postgres_urls_use_psycopg3():
    assert Settings(database_url="postgres://u:p@h/db").database_url.startswith("postgresql+psycopg://")


def test_root_redirects_to_docs_and_health_reports_db(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308) and r.headers["location"] == "/docs"
    assert client.get("/favicon.ico").status_code == 204
    h = client.get("/api/v1/health").json()
    assert h["database"] in ("ok", "unreachable") and "llm" in h


def test_bootstrap_seeds_an_empty_database_once(test_db_url, monkeypatch, capsys):
    import app.models  # noqa: F401
    from app import bootstrap
    from app.core.config import get_settings
    from app.db import Base

    engine = create_engine(test_db_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(bootstrap, "SessionLocal", Session)
    monkeypatch.setattr(get_settings(), "seed_on_start", True)
    monkeypatch.setenv("CONSOLE_DEMO_PASSWORD", "demo-pass-123")

    bootstrap.main()
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Product)) == 25
        assert db.scalar(select(func.count()).select_from(Lead).where(Lead.external_id.is_not(None))) == 5000
        assert db.scalar(select(func.count()).select_from(ConsoleUser)) == 4
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        scored = db.scalar(select(func.count()).select_from(Lead).where(Lead.propensity_score.is_not(None)))
        assert scored >= 5000

    bootstrap.main()  # second boot: untouched
    assert "already seeded" in capsys.readouterr().out
    engine.dispose()


@pytest.mark.parametrize("qty", [1, 5, 12])
def test_unit_price_stays_in_range_and_rewards_volume(qty):
    from app.services.catalogue import get_catalogue
    from app.services.eligibility import BusinessProfile
    from app.services.pricing import unit_price

    biz = BusinessProfile("multi", 1, 30, 4, True)
    for p in get_catalogue().values():
        price = unit_price(p, biz, qty)
        assert p.price_min <= price <= p.price_max
        assert unit_price(p, biz, 12) <= unit_price(p, biz, 1)
