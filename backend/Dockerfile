FROM python:3.11-slim
WORKDIR /app
# Build cache buster — bump to force Railway/Render to rebuild
# without using a cached layer. CACHE_BUST = 2026-09-01-004.
ARG CACHE_BUST=2026-09-01-005
# Force Python to flush stdout/stderr immediately so Railway's log
# stream sees the boot prints without buffering.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTEBYTECODE=1 \
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
COPY backend/start.sh /app/start.sh
RUN chmod +x /app/start.sh
COPY backend/diagnose.sh /app/diagnose.sh
RUN chmod +x /app/diagnose.sh
EXPOSE 8000
CMD ["/app/start.sh"]
