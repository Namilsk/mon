FROM python:3.14-slim

LABEL org.opencontainers.image.title="Server Monitor Agent"
LABEL org.opencontainers.image.description="Monitoring agent for Server Monitor - collects CPU, memory and network metrics"
LABEL org.opencontainers.image.vendor="namilsk"
LABEL org.opencontainers.image.source="https://github.com/namilsk/server-monitor"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "agent.py"]
