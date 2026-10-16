# Use official lightweight Python 3.12 slim image
FROM python:3.12-slim

# Prevent Python from writing .pyc files to disk and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    DATABASE_PATH=/app/data/inventory.db \
    LOG_FILE_PATH=/app/logs/app.log \
    LOG_LEVEL=INFO

WORKDIR /app

# Install curl for container health check and clean up apt lists to minimize image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root application group and user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Install Python dependencies first for efficient layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Create persistent storage directories for SQLite and logs, and set ownership
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 5000

# Native Docker health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Launch production WSGI application with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]
