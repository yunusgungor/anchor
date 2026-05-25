# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install
RUN pip install --no-cache-dir -e .

# Verify installation
RUN python -c "from agent.core.classifier import TaskClassifier; print('✅ Anchor Agent installed')"

# Default: run tests
CMD ["python", "-m", "pytest", "tests/test_agent.py", "-v"]
