# Deploying Udyam Digital for free

Three free services, no credit card needed for any of them:

| Part | Host | Free tier | Why this one |
| --- | --- | --- | --- |
| Web app (Next.js) | **Vercel** (Hobby) | Unlimited personal projects | Made for Next.js; zero config |
| API + OCR (Docker) | **Hugging Face Spaces** (Docker, CPU basic) | 2 vCPU, **16 GB RAM** | OCR peaks around 1.2 GB; Render/Koyeb free tiers (512 MB, 0.1 CPU) would crash or crawl |
| Database | **Neon** (Postgres) | 0.5 GB, never expires | The data needs ~60 MB |

No Redis or worker is needed: OCR runs inside the API (`KYC_QUEUE=inline`), and the nightly document purge runs as a timer in the API (`RUN_PURGE_IN_API=true`).

Free-tier limits to know before a demo:
- **Space sleeps:** a Hugging Face Space sleeps after 48 h without traffic. The first request wakes it in about a minute; the landing page shows "API waking up" meanwhile. Open the site a few minutes before presenting.
- **Neon cold start:** Neon suspends compute when idle and resumes in about a second.
- **Uploaded images:** with `STORAGE_BACKEND=local`, uploaded KYC images live in the container and vanish on restart. Check results stay in the database, so the demo is unaffected. For persistence, see "Optional: keep KYC images" below.

Deploy in this order: **database → API → web → link them**.

---

## 1. Database: Neon (5 minutes)

1. Sign up at https://neon.tech and create a project (region: Singapore / `ap-southeast-1`, closest to India).
2. Copy the **connection string** from the dashboard. It looks like
   `postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.

That's all. Tables and data are created by the API on first boot.

## 2. API: Hugging Face Space (10 minutes)

1. Sign up at https://huggingface.co. Under **Settings → Access Tokens**, create a token with **Write** access.
2. Generate two secrets on your machine:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
3. Copy `deploy/space.env.example` to `deploy/space.env` and fill it in:
   - `DATABASE_URL`: the Neon string from step 1.
   - `FIELD_ENCRYPTION_KEY`, `JWT_SECRET`: the two values you just generated.
   - `CONSOLE_DEMO_PASSWORD`: the password for the console logins.
   - `CORS_ORIGINS` and `PUBLIC_WEB_URL`: leave as `https://udyam-digital.vercel.app` for now; you fix them in step 4.
   - `GOOGLE_API_KEY` (optional): a free Gemini key from https://aistudio.google.com makes the advisor smarter.

   `deploy/space.env` is git-ignored.
4. Deploy, from the repo root:

   ```bash
   pip install huggingface_hub
   ```
   ```bash
   set HF_TOKEN=hf_your_write_token
   ```
   ```bash
   python deploy/hf_space.py --space YOUR-HF-USERNAME/udyam-api --env-file deploy/space.env
   ```

   (On macOS/Linux use `export HF_TOKEN=...`.) The script creates the Space, sets the secrets and uploads the code.
5. Watch the build at `https://huggingface.co/spaces/YOUR-HF-USERNAME/udyam-api` (about 5–8 minutes the first time). When it says **Running**, open:
   - `https://YOUR-HF-USERNAME-udyam-api.hf.space/api/v1/health`, which should show `"database":"ok"`.
   - `https://YOUR-HF-USERNAME-udyam-api.hf.space/docs` for the interactive API.

   The first boot runs migrations and seeds the 5,000 leads, console accounts and a demo order (`SEED_ON_START=true`). Later restarts skip seeding.

**Automatic redeploys (optional):** in GitHub → Settings → Secrets and variables → Actions, add the secret `HF_TOKEN` and the variable `HF_SPACE` = `YOUR-HF-USERNAME/udyam-api`. The **Deploy API** workflow then redeploys on every push to `main` that touches the backend.

## 3. Web: Vercel (5 minutes)

1. Push the repo to GitHub. Sign in at https://vercel.com with GitHub and click **Add New → Project**, then pick the repo.
2. Set **Root Directory** to `apps/web`. The framework (Next.js) is detected automatically.
3. Add the environment variables:
   - `NEXT_PUBLIC_API_URL` = `https://YOUR-HF-USERNAME-udyam-api.hf.space/api/v1`
   - `NEXT_PUBLIC_REPO_URL` = your GitHub repo URL (optional; shows a "Code" link on the landing page)
4. Click **Deploy**. You get a URL like `https://udyam-digital.vercel.app`.

## 4. Link them (2 minutes)

In the Space, under **Settings → Variables and secrets**, set:
- `CORS_ORIGINS` = your exact Vercel URL, e.g. `https://udyam-digital.vercel.app` (no trailing slash).
- `PUBLIC_WEB_URL` = the same URL. WhatsApp tracker links point here.
- `CORS_ORIGIN_REGEX` (optional) = `https://udyam-digital-.*\.vercel\.app`, so Vercel preview deployments work too.

The Space restarts by itself. Open your Vercel URL: the landing page should say **API live**.

## 5. Check it works

1. **Landing page:** shows "API live".
2. **Owner app** (`/start` → advisor): describe a business, open the plan, toggle an add-on, pay with any 10-digit mobile.
3. **Documents:** upload the sample documents from the landing page's "Test it in two minutes" section. The order moves to "Documents verified".
4. **Console** (`/console`): sign in as `admin` with your `CONSOLE_DEMO_PASSWORD`, then advance the order. The tracker updates.

## Optional: keep KYC images across restarts

Any S3-compatible bucket works; images are encrypted by the API before upload either way. Supabase Storage is free (1 GB):

1. Create a Supabase project, then a private bucket `kyc-documents`.
2. Under **Project Settings → Storage → S3 Connection**, create access keys.
3. Set these in the Space:

   ```
   STORAGE_BACKEND=s3
   S3_ENDPOINT=https://<project-ref>.supabase.co/storage/v1/s3
   S3_BUCKET=kyc-documents
   S3_ACCESS_KEY=...
   S3_SECRET_KEY=...
   ```

## Optional: WhatsApp

Create a Meta developer app with the WhatsApp product and use the test number:
- **Space settings:** set `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_APP_SECRET`.
- **Webhook URL:** `https://YOUR-HF-USERNAME-udyam-api.hf.space/api/v1/whatsapp/webhook`.
- **Verify token:** `udyam-dev-verify`, or your own `WHATSAPP_VERIFY_TOKEN`.

Without these, messages still appear in the console's WhatsApp outbox, marked "mocked".

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Space log says `Unsafe configuration: …` | A secret is missing or weak. `JWT_SECRET` needs ≥ 32 characters; `FIELD_ENCRYPTION_KEY` must be a Fernet key; `CORS_ORIGINS` can't be `*`. |
| Landing page stuck on "API waking up" | The Space is still building or asleep. Check its logs on huggingface.co. |
| Browser console shows a CORS error | `CORS_ORIGINS` must match the Vercel URL exactly: `https`, no trailing slash. |
| `bootstrap: set CONSOLE_DEMO_PASSWORD` | Add that secret; it's required in production before console accounts are created. |
| Login says wrong password after changing it | Seeding runs once. To reseed, empty the Neon database (or create a new branch) and restart the Space. |

## Alternatives

- **Everything on one machine:** `docker compose up --build` (API, OCR worker, Postgres, Redis, SeaweedFS, web).
- **Render:** `render.yaml` describes the API, worker, cron and databases. It needs paid instances, because the free 512 MB instance can't hold the OCR models.
