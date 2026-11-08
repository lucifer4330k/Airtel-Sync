# API image. Build from the repo root so the case data ships with it:
#   docker build -f apps/api/Dockerfile .
# Runs on Hugging Face Spaces (Docker, uid 1000), Render, or docker compose.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
# rapidocr depends on full opencv-python, which links X11/GL libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY apps/api/pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY apps/api/ ./
COPY data/ /app/data/
COPY scripts/seed_db.py /app/scripts/seed_db.py
# Files edited on Windows may carry CRLF; the shell needs LF.
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

ENV DATA_DIR=/app/data \
    STORAGE_DIR=/tmp/udyam-storage \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Warm the OCR models into the image so the first upload isn't slow.
RUN python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"

# Hugging Face Spaces runs containers as uid 1000.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
CMD ["/app/start.sh"]
