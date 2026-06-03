# Production image for the Knowledge Hub backend.
#
# Slim and fast to build now that embeddings are hosted (Voyage AI) — there's
# no torch / sentence-transformers, so the image is small and runs in ~512 MB.
#
# Migrations are NOT run here; Render's preDeployCommand runs
# `python -m alembic upgrade head` before each deploy (see render.yaml).
FROM python:3.12-slim

# - PYTHONUNBUFFERED: logs flush immediately (visible in Render logs)
# - PYTHONDONTWRITEBYTECODE: no .pyc clutter in the image
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first so the layer caches across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application (alembic/ included so preDeployCommand can migrate).
COPY . .

# Render injects $PORT; default to 8000 for local `docker run`.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
