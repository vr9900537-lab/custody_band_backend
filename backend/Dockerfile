# =====================================================================
# CUSTODY WATCH PLATFORM - DOCKERFILE
# =====================================================================
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata

# Install system dependencies (curl for healthchecks, tzdata for IST timezone)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition first for optimal Docker caching
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY . .

# Ensure persistent directories exist
RUN mkdir -p /app/logs/tcp_logs /app/logs/gps_logs /app/secrets

# Expose Ports:
# 8000     : FastAPI REST API & Swagger UI (/docs)
# 9001/tcp : Huaten C05 GPS Custody Watch TCP Receiver
# 9001/udp : Huaten C05 GPS Custody Watch UDP Receiver
EXPOSE 8000
EXPOSE 9001/tcp
EXPOSE 9001/udp

# Healthcheck to verify HTTP service availability
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the backend platform
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

