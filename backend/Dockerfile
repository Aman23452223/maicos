FROM python:3.11-slim
WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] python-multipart \
    httpx tenacity langgraph langchain langchain-openai structlog asyncpg \
    pgvector email-validator PyPDF2 python-docx openai
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/start.sh /app/start.sh
RUN chmod +x /app/start.sh
EXPOSE 8000
# `start.sh` waits for DATABASE_URL, runs migrations, then execs uvicorn.
CMD ["/app/start.sh"]
