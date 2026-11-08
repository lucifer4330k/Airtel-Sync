---
title: Udyam Digital API
emoji: 📶
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
short_description: Advisor, quotes, Smart KYC and order tracker API
---

# Udyam Digital API

FastAPI backend for Udyam Digital: AI advisor, rules engine, quotes and
checkout, quote repair ("what if my budget or needs change?"), Smart KYC
(OCR), order tracker, partner console and the judge challenge endpoints.

- Interactive API docs: `/docs`
- Health: `/api/v1/health`
- Judge scorecard: `/api/v1/judge/scorecard`

This Space is deployed from the project repository by `deploy/hf_space.py`
(or the "Deploy API" GitHub Action). Configure it under
**Settings → Variables and secrets**; see `DEPLOY.md` in the repository.
