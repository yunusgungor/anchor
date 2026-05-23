FROM python:3.12-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

# Uygulama kodu
COPY src/ ./src/
COPY rules/ ./rules/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# UI port
EXPOSE 8080

# Varsayılan: Chat UI
CMD ["python", "-m", "uvicorn", "anchor.ui.app:app", "--host", "0.0.0.0", "--port", "8080"]
