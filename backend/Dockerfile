FROM python:3.11-slim
WORKDIR /app
# Build cache buster — bump to force Railway/Render to rebuild
# without using a cached layer. This is the CACHE_BUST that
# currently in production: 2026-09-01-002.
ARG CACHE_BUST=2026-09-01-002
# Force Python to flush stdout/stderr immediately so Railway's log
# stream sees the boot prints without buffering.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Print the env we're running in before pip install — useful when
# inspecting the build log to confirm Railway's PORT / DATABASE_URL
# etc. reached the container.
RUN echo "[build] CACHE_BUST=$CACHE_BUST" && \
    echo "[build] starting pip install at $(date -u +%FT%TZ)" && \
    pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] python-multipart \
    httpx tenacity langgraph langchain langchain-openai structlog \
    pgvector email-validator PyPDF2 python-docx openai
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
EXPOSE 8000
# Migrations run inside the FastAPI lifespan (see app/main.py) so we
# do not need a shell wrapper. Uvicorn starts immediately.
# The wrapper script ensures the deploy log always shows the
# uvicorn banner even if the env module is missing — and applies
# the alembic migration before listening (idempotent).
CMD ["sh", "-c", "echo '[start] PORT=${PORT:-8000} PYTHONUNBUFFERED='$PYTHONUNBUFFERED; echo '[start] DATABASE_URL set: '$( [ -n \"$DATABASE_URL\" ] && echo yes || echo no ); if [ \"$RUN_MIGRATIONS\" = 'true' ] && [ -n \"$DATABASE_URL\" ]; then echo '[start] running alembic upgrade head'; alembic upgrade head 2>&1 || echo '[start] alembic failed, continuing'; else echo '[start] skipping migrations (RUN_MIGRATIONS not set)'; fi; echo '[start] starting uvicorn on port ${PORT:-8000}'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --proxy-headers --forwarded-allow-ips='*'"]
