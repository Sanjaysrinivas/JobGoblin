FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies first (better layer caching)
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Migrations
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

# Migrations are wired into startup once models/migrations exist:
#   sh -c "alembic upgrade head && uvicorn ..."
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
