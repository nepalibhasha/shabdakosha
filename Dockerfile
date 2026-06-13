FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:${PATH}"
ENV SHABDAKOSHA_DB_PATH=/app/data/dictionary.db
ENV SHABDAKOSHA_DATA_DIR=/app/data/dictionaries

EXPOSE 8000

CMD ["uvicorn", "shabdakosha.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
