FROM python:3.11-slim
WORKDIR /app
# Build cache buster — referenced by the next COPY so the pip-install
# layer is invalidated every time CACHE_BUST is bumped. This forces
# Railway/Render to actually rebuild instead of serving a stale
# cached image.
ARG CACHE_BUST=2025-08-31-003
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir fastapi uvicorn[standard]
# Smoke-test main module — replaced app/main.py with this for
# diagnostic deploys to verify the Railway build pipeline.
# Revert by checking out the real app/main.py from git.
COPY backend/app/__smoke__.py ./app/__smoke__.py
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.__smoke__:app --host 0.0.0.0 --port ${PORT:-8000}"]
