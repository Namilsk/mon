FROM python:3.12-slim

LABEL org.opencontainers.image.title="Server Monitor Agent"
LABEL org.opencontainers.image.description="Monitoring agent for Server Monitor - collects CPU, memory and network metrics"
LABEL org.opencontainers.image.vendor="namilsk"
LABEL org.opencontainers.image.source="https://github.com/namilsk/server-monitor"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as root for host PID access
CMD ["python", "agent.py"]
