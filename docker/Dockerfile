# Stage 1: Build WebUI
FROM node:20-alpine AS webui-builder
WORKDIR /build
COPY webui/package*.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build

# Stage 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    vainfo \
    mesa-va-drivers \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY --from=webui-builder /build/dist/ ./webui/dist/

# Default config directory for Docker
ENV TRANSCODR_CONFIG_DIR=/config

# Create default directories
RUN mkdir -p /config /media /temp

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import requests; requests.get('http://localhost:8765/api/health').raise_for_status()"

# Bind to 0.0.0.0 in Docker (not localhost)
CMD ["python", "-m", "src.daemon", "--host", "0.0.0.0"]
