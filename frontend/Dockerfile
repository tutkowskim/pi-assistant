FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS schema
WORKDIR /workspace/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY backend/scripts ./scripts
RUN mkdir -p /schema && uv run --no-sync python scripts/export_openapi.py /schema/openapi.json

FROM node:22-alpine AS build
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY --from=schema /schema/openapi.json /tmp/openapi.json
RUN OPENAPI_SCHEMA_PATH=/tmp/openapi.json npm run build

FROM nginx:1.29-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
