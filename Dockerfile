FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# The package is built from pyproject.toml, which also reads README.md.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Railway sets PORT. Locally it falls back to 8000.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn sar_scout.api:app_from_env --factory --host 0.0.0.0 --port ${PORT:-8000}"]