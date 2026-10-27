# syntax=docker/dockerfile:1
#
# Targets
#   runtime         (default, last stage) one process serving the API and the built React app
#   backend-test    runs the Python unit and API tests
#   frontend-test   runs the TypeScript unit tests
#
#   docker build -t wind-day-ahead .
#   docker build --target backend-test -t wind-day-ahead:backend-test .

ARG NODE_VERSION=22
ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- front end
FROM node:${NODE_VERSION}-alpine AS frontend-deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM frontend-deps AS frontend-test
COPY frontend/ ./
CMD ["npx", "vitest", "run"]

FROM frontend-deps AS frontend-build
COPY frontend/ ./
# `npm run build` type-checks (strict) and then bundles; either failing fails the image build.
RUN npm run build

# ------------------------------------------------------------------ python
FROM python:${PYTHON_VERSION}-slim AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# Fixed uid/gid so bind-mounted files can be owned predictably.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

FROM python-base AS backend-test
COPY backend/requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY backend/ ./
USER app
CMD ["python", "-m", "unittest", "discover", "-s", "tests"]

# ----------------------------------------------------------------- runtime
FROM python-base AS runtime
# Application code only: no tests, no dev requirements.
COPY backend/wind_data ./wind_data
COPY backend/wind_analysis ./wind_analysis
COPY backend/wind_api ./wind_api
COPY backend/scripts ./scripts
# The committed January 2026 snapshot (see backend/data/snapshot.sha256).
COPY backend/data ./data
COPY --from=frontend-build /app/frontend/dist /app/static

ENV SNAPSHOT_PATH=/app/backend/data/snapshot.json.gz \
    STATIC_DIR=/app/static \
    PORT=8000
USER app
EXPOSE 8000

# Healthy only if the API answers AND the snapshot file is present.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import json,sys,urllib.request as u; r=json.load(u.urlopen('http://127.0.0.1:8000/api/health', timeout=2)); sys.exit(0 if r.get('status')=='ok' and r.get('data_file_present') else 1)"]

CMD ["python", "-m", "uvicorn", "wind_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
