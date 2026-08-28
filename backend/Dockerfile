FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] python-multipart \
    httpx tenacity langgraph langchain langchain-openai redis apscheduler structlog \
    pgvector email-validator PyPDF2 python-docx openai
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
