FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies first against a stub package so this heavy layer is
# cached and only re-runs when pyproject.toml changes (not on app code edits).
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    mkdir -p app && touch app/__init__.py && \
    pip install .

# Now copy real source and (re)install just the package, reusing cached deps.
COPY app ./app
RUN pip install --no-deps .

# Migrations
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

# Migrations are wired into startup once models/migrations exist:
#   sh -c "alembic upgrade head && uvicorn ..."
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
