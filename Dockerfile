# One container: FastAPI serves the API, the built React front end and the report figures (D-017).
# Uses the committed model in backend/model/ (python -m court_delay.train --export backend/model),
# so it builds from a plain Git checkout (Render, D-020).

# --- front end ---------------------------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- API ---------------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src PORT=8000 \
    COURT_DELAY_MODEL_DIR=/app/model
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src/ src/
COPY backend/model/ model/
COPY reports/figures/ reports/figures/
COPY --from=web /web/dist/ frontend/dist/
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % __import__('os').environ['PORT'])"
CMD ["sh", "-c", "uvicorn court_delay.api:app --host 0.0.0.0 --port ${PORT}"]
