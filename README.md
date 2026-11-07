# Udyam Digital

A mobile-first web app where a small business owner chats with an advisor, gets one monthly price, finishes KYC on their phone and tracks the order. A partner console handles the leads the advisor could not close.

Built by Team Stack Overflow for Track A (Project Udyam Digital). All data in `data/` is the synthetic case pack, used as given.

## Layout

```
apps/api     FastAPI + SQLAlchemy + Alembic (rules engine, mock registries, quotes)
apps/web     Next.js 14 + Tailwind + next-intl (owner app + partner console)
data/        case CSVs + kyc_documents/ (untouched)
scripts/     seed_db.py
```

## Run locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22.

1. Create `.env` from the example and fill in `FIELD_ENCRYPTION_KEY`:

   ```bash
   cp .env.example .env
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Start Postgres and Redis:

   ```bash
   docker compose up -d postgres redis
   ```

3. Migrate, seed, and run the API (http://localhost:8000/docs):

   ```bash
   cd apps/api
   uv sync --extra dev
   uv run alembic upgrade head
   uv run python ../../scripts/seed_db.py
   uv run uvicorn app.main:app --reload --port 8000
   ```

4. Run the web app (http://localhost:3000, console at `/console`):

   ```bash
   cd apps/web
   npm install
   npm run dev
   ```

Or run everything in containers: `docker compose up --build`.

## Tests

```bash
cd apps/api && uv run pytest -q && uv run ruff check .
cd apps/web && npm run lint && npm run build
```

`tests/unit/test_pricing.py` replays all 5,000 lead profiles through the bundle builder and fails if any plan contains an ineligible product or a broken dependency. This is the property the judges' advisor scenarios test.

## What works today

| Area | Status |
| --- | --- |
| Rules engine: eligibility, dependencies, Good/Better/Best, quantities, pricing | Done, tested |
| GSTIN format + checksum (all 3,534 registry GSTINs pass) | Done, tested |
| Mock GSTIN / Udyam lookup APIs with 300–800 ms latency | Done |
| Postgres schema (13 tables), Alembic migration, seed; GSTIN/Udyam encrypted at rest | Done |
| PII masking log filter (GSTIN, Udyam, PAN, Aadhaar, phone) | Done, tested |
| Web: advisor (scripted slot-filling), live quote bill, KYC consent shell, tracker shell, console funnel | Done |
| Languages: English, Hindi | Done; Marathi and Tamil need a native-speaker pass |
| LangChain advisor, persisted quotes + add-on toggles, checkout | Week 1 |
| OCR, KYC validators, K01–K12 answer key, tracker state machine | Week 2 |
| Propensity model, WhatsApp, voice, partner lead list | Week 3 |

## Key decisions

- **The LLM never decides eligibility.** `app/services/eligibility.py` does, from `product_catalogue.csv`. The advisor may only present products the engine returned.
- **"Today" is 2026-07-15** for every date rule (`REFERENCE_DATE`), per the case README.
- **Quantity rules and segment templates** were derived from the 368 activated bundles in `smb_leads.csv` (e.g. setup fees are charged per unit in all 368).
