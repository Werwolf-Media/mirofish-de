# MiroFish — ein Container für Backend (Flask) + Frontend (Vite-Build).
# Flask liefert die gebauten statischen Dateien selbst aus (kein nginx nötig,
# vermeidet die Coolify-Falle "zwei Apps, getrennte Docker-Netze").

# ---- Stage 1: Frontend bauen ----
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci
COPY frontend/ frontend/
# i18n wird zur Build-Zeit per Glob aus ../locales importiert
COPY locales/ locales/
RUN cd frontend && npm run build

# ---- Stage 2: Backend + statisches Frontend ----
FROM python:3.12-slim

# Debug-Reloader wuerde den Prozess doppeln und Orchestrator-Threads killen
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    FLASK_DEBUG=False \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5001

# build-essential: einzelne Python-Wheels (camel-ai-Kette) kompilieren nach
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

# Dependencies zuerst (Docker-Layer-Cache: aendert sich selten)
COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project

COPY backend/ backend/
COPY locales/ locales/
COPY --from=frontend /build/frontend/dist frontend/dist

EXPOSE 5001

WORKDIR /app/backend
CMD ["uv", "run", "--no-sync", "python", "run.py"]
