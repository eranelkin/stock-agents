FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY pyproject.toml .
COPY backend/ ./backend/

RUN pip install --no-cache-dir .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "4101"]
