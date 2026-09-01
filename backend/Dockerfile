FROM python:3.11-slim
WORKDIR /app
# Build cache buster — bump to force Railway/Render to rebuild
# without using a cached layer. CACHE_BUST = 2026-09-01-003.
ARG CACHE_BUST=2026-09-01-003
# Force Python to flush stdout/stderr immediately so Railway's log
# stream sees the boot prints without buffering.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN echo "[build] CACHE_BUST=$CACHE_BUST" && \
    echo "[build] starting pip install at $(date -u +%FT%TZ)" && \
    pip install --no-cache-dir -U pip
# Install from requirements.txt (more reliable than pyproject.toml editable)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
EXPOSE 8000
CMD ["sh", "-c", "echo '[start] PORT=${PORT:-8000} PYTHONUNBUFFERED='$PYTHONUNBUFFERED DATABASE_URL_present='$([ -n \"$DATABASE_URL\" ] && echo yes || echo no)'; echo '[start] running pre-flight checks'; python -c 'import sys; print(\"[start] python=\" + sys.version)' || { echo '[start] python import failed'; exit 1; }; if [ \"$RUN_MIGRATIONS\" = 'true' ] && [ -n \"$DATABASE_URL\" ]; then echo '[start] running alembic upgrade head'; alembic upgrade head 2>&1 || echo '[start] alembic failed, continuing'; else echo '[start] skipping migrations'; fi; echo '[start] starting uvicorn on port ${PORT:-8000}'; if [ \"$SMOKE_TEST\" = 'true' ]; then echo '[start] SMOKE_TEST=true'; exec uvicorn app.__smoke_main__:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --proxy-headers --forwarded-allow-ips='*'; else exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --proxy-headers --forwarded-allow-ips='*' 2>&1; fi"]
