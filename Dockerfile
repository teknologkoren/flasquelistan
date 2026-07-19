# --- Stage 1: songbook (optional; skipped gracefully if unavailable) --------
FROM node:24.18.0-bookworm-slim AS songbook
WORKDIR /build
# The submodule directory always exists in a checkout (empty if uninitialized),
# so this COPY never fails. songs.json and public/Flerstämt.pdf are gitignored
# out-of-band files; .dockerignore deliberately lets them into the context.
COPY songbook-viewer/ ./songbook-viewer/
RUN mkdir -p /out/songbook_dist && \
    if [ -f songbook-viewer/package.json ] && [ -f songbook-viewer/songs.json ]; then \
        [ -f "songbook-viewer/public/Flerstämt.pdf" ] || \
            echo "WARNING: Flerstämt.pdf missing; songbook builds but the PDF view will break"; \
        cd songbook-viewer && npm ci && npm run build && cp -r dist/. /out/songbook_dist/; \
    else \
        echo "WARNING: songbook submodule or songs.json missing; building without the songbook (/bok/ will 404)"; \
    fi

# --- Stage 2: app -----------------------------------------------------------
FROM python:3.13.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

# Venv outside /app so a dev bind mount of the repo does not shadow it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

WORKDIR /app

# Dependency layer: cached unless the lockfile changes. The project is
# "virtual" in uv.lock, so this installs dependencies only.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --compile-bytecode

COPY . .
COPY --from=songbook /out/songbook_dist/ ./flasquelistan/songbook_dist/
RUN cd flasquelistan && pybabel compile -d translations

# UID 1000 matches the typical owner of the bind-mounted instance/ and
# uploads/ directories on the host; override with `user:` in compose if not.
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
CMD ["gunicorn", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", \
     "-w", "1", "-b", "0.0.0.0:8000", "app:app"]
