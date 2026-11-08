# Data privacy and security note — Udyam Digital

We treat the synthetic data as if it were real customers' data and design for India's Digital Personal Data Protection Act, 2023 (DPDP). Each choice below is enforced in code, not just in policy.

**1. Consent before collection.** KYC starts with a plain-language consent screen in the owner's language: what we collect, why, and for how long. KYC consent (required) and marketing (optional, unticked) are separate checkboxes. We store purpose, text version and timestamp (`consents` table). Withdrawing KYC consent in the app deletes every uploaded image and record at once, and blocks further uploads.

**2. Purpose limitation and minimisation.** The advisor asks only business facts (type, size, sites, city, GST yes/no, needs). It never asks for Aadhaar or personal IDs. KYC takes only the four documents the case lists. From the signatory ID we keep only the name and a masked ID number; designation and photo are not extracted.

**3. Masking everywhere.** A logging filter and formatter mask GSTIN, Udyam, PAN, Aadhaar and phone numbers on every log line, including uvicorn access logs, exception tracebacks and lowercase variants (`27XXXXX1234F1Z5`, `XXXXXX3210`). Advisor transcripts are stored masked. The console and owner screens show identifiers masked by default.

**4. Encryption.**
- **In transit:** TLS end to end in deployment (Vercel and Render terminate HTTPS).
- **Database:** GSTIN, Udyam number and phone are encrypted in Postgres at the application level (Fernet).
- **Document images:** encrypted by the API before they reach any storage, local disk or the S3 bucket. Encryption therefore doesn't depend on the storage vendor, and a leaked bucket holds only ciphertext.
- **Retrieval:** documents are served only through an authenticated API call. There are no public URLs, and every view writes an audit row.

**5. Retention.**
- **Image deletion:** each image carries a `purge_after` date. A nightly job (`app.workers.purge_documents`) deletes it **7 days after the case is verified** (the audit window) or **30 days after upload at the latest**, whichever comes first.
- **What we keep:** the extracted fields and check results, needed to show why a case passed.
- **Leads:** lead and quote records are kept for 24 months for service and billing, then anonymised.

**6. Access control.**
- **Owners:** each owner reaches only their own quote, KYC case and order, through a signed capability token. Ids alone return 404, so they can't be probed. OTP login (mobile + JWT) replaces this before production.
- **Console:** console users sign in with scrypt-hashed passwords and receive short-lived JWTs (8 h). Roles are admin, rep and partner. Reps and partners see only their territory's leads plus those assigned to them.
- **Audit:** every console view of a lead's details, each KYC decision and each image purge is written to `audit_log`.

**7. LLM safety.**
- **Optional and narrow:** the LLM only reads free text into a typed schema and rephrases replies.
- **No product choices:** it never chooses products. The deterministic rules engine does, and the server re-validates every quote before showing it and again at checkout.
- **Guarded output:** a rephrased reply is discarded if any price or product name changes.
- **Masked input:** identifiers are masked before any text leaves our servers.
- **No training:** customer data is never used to train models.
- **Fallback:** with no key configured, the advisor runs fully offline.

**8. Upload safety and abuse limits.**
- **File checks:** we accept only JPEG, PNG and PDF up to 5 MB, and decide the type from the file's bytes, not its name or declared type.
- **Storage keys:** keys are random, and path traversal is blocked.
- **Rate limits:** chat, upload, registry lookup and console login are rate-limited.
- **WhatsApp webhooks:** verified with Meta's HMAC signature when an app secret is configured.

**What is mocked in the prototype:** the GSTIN/Udyam registries (case CSVs), DigiLocker / e-sign screens, payments (Razorpay test-mode shape), and WhatsApp when no sandbox token is set. The owner's OTP login is planned; the capability token stands in for it now.
