FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY pyproject.toml .
COPY ai_service/ ./ai_service/

RUN pip install --no-cache-dir .

CMD ["uvicorn", "ai_service.main:app", "--host", "0.0.0.0", "--port", "4102"]
