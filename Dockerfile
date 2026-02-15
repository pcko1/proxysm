FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --no-create-home appuser

FROM base AS deps

COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM deps AS app

COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080 9080 9081

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--loop", "uvloop"]
