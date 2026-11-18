# StockShield 2.0 Production Container
FROM python:3.11-slim

# Set working directory and environment variables
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements and install
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --no-deps google-adk==2.13.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code, config, and data fixtures
COPY src/ /app/src/
COPY config/ /app/config/
COPY data/ /app/data/

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Launch FastAPI server with Uvicorn (binds to Render's dynamic $PORT or 8000)
CMD ["sh", "-c", "uvicorn stockshield.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
