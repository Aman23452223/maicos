FROM python:3.11-slim
WORKDIR /app
# Build cache buster — referenced by the next COPY so the pip-install
# layer is invalidated every time CACHE_BUST is bumped. This forces
# Railway/Render to actually rebuild instead of serving a stale
# cached image.
ARG CACHE_BUST=2025-08-31-002
COPY backend/pyproject.toml ./
RUN echo "cache-bust=$CACHE_BUST" \
 && pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] python-multipart \
    httpx tenacity langgraph langchain langchain-openai structlog \
    pgvector email-validator PyPDF2 python-docx openai
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
EXPOSE 8000
# Migrations run inside the FastAPI lifespan (see app/main.py) so we
# do not need a shell wrapper. Uvicorn starts immediately.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
