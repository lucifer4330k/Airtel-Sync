import csv
import os
import tempfile

import pytest

os.environ.setdefault("MOCK_REGISTRY_MIN_DELAY_MS", "0")
os.environ.setdefault("MOCK_REGISTRY_MAX_DELAY_MS", "0")
# Tests never touch MinIO or the dev storage folder.
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="udyam-test-storage-")
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32  # >= 32 bytes, like production
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["WHATSAPP_ALLOW_UNSIGNED"] = "true"  # one test switches it on explicitly
if not os.environ.get("FIELD_ENCRYPTION_KEY"):
    from cryptography.fernet import Fernet

    os.environ["FIELD_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402


@pytest.fixture(scope="session")
def leads() -> list[dict[str, str]]:
    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """A throwaway udyam_test database next to the dev one. Skips if Postgres is down."""
    base = os.environ.get("TEST_DATABASE_URL", get_settings().database_url)
    url = make_url(base).set(database="udyam_test")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("select 1 from pg_database where datname = 'udyam_test'"))
            if not exists:
                conn.execute(text("create database udyam_test"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable for DB tests: {exc.__class__.__name__}")
    finally:
        admin.dispose()
    return url.render_as_string(hide_password=False)


@pytest.fixture
def client(test_db_url):
    from fastapi.testclient import TestClient

    import app.models  # noqa: F401
    from app.db import Base, get_db
    from app.main import app

    engine = create_engine(test_db_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    from app.core.security import hash_password
    from app.models import ConsoleUser
    from app.seed import seed_products

    with Session() as s:
        seed_products(s)
        for username, role, city in [
            ("admin", "admin", None),
            ("rep.pune", "rep", "Pune"),
            ("partner.mumbai", "partner", "Mumbai"),
        ]:
            s.add(
                ConsoleUser(
                    username=username,
                    name=username,
                    role=role,
                    city=city,
                    password_hash=hash_password("pw-" + username),
                )
            )
        s.commit()

    def _db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
