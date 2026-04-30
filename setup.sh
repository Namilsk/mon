#!/bin/bash

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Server Monitor - Node Setup          ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Check for OpenSSL
if ! command -v openssl &> /dev/null; then
    echo "Error: openssl is required but not installed"
    exit 1
fi

# Generate JWT Secret
echo -e "${BLUE}[1/3]${NC} Generating JWT secret..."
JWT_SECRET=$(openssl rand -base64 32)
echo -e "${GREEN}✓${NC} JWT_SECRET generated"

# Get Node ID
echo ""
echo -e "${BLUE}[2/3]${NC} Configure node identification"
echo -n "Enter Node ID (e.g., web-server-01, db-master): "
read -r NODE_ID

if [ -z "$NODE_ID" ]; then
    NODE_ID="node-$(openssl rand -hex 4)"
    echo -e "${YELLOW}!${NC} No ID provided, using random: $NODE_ID"
fi

# Get Central Server URL
echo ""
echo -e "${BLUE}[3/3]${NC} Configure central server connection"
echo -n "Enter Central Server URL (default: http://localhost:5000): "
read -r CENTRAL_URL

if [ -z "$CENTRAL_URL" ]; then
    CENTRAL_URL="http://localhost:5000"
fi

# Detect if running in Docker
if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; then
    RUNNING_IN_DOCKER=true
else
    RUNNING_IN_DOCKER=false
fi

# Create .env file
ENV_FILE=".env"
echo ""
echo -e "${BLUE}Creating configuration...${NC}"

cat > "$ENV_FILE" << EOF
# Server Monitor - Node Configuration
# Generated: $(date)

# Authentication (keep secret!)
JWT_SECRET=${JWT_SECRET}

# Node Identification
NODE_ID=${NODE_ID}

# Central Server Connection
CENTRAL_URL=${CENTRAL_URL}

# Polling interval in seconds
POLL_INTERVAL=5
EOF

echo -e "${GREEN}✓${NC} Configuration saved to $ENV_FILE"
echo ""

# Output summary
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}   Configuration Summary${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo -e "  Node ID:        ${GREEN}${NODE_ID}${NC}"
echo -e "  Central URL:    ${GREEN}${CENTRAL_URL}${NC}"
echo -e "  JWT Secret:     ${GREEN}${JWT_SECRET:0:20}...${NC}"
echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Download node-only compose file if not present
COMPOSE_FILE="docker-compose.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${BLUE}Downloading docker-compose configuration...${NC}"
    curl -sL https://raw.githubusercontent.com/namilsk/server-monitor/main/docker-compose.node.yml -o "$COMPOSE_FILE" 2>/dev/null || \
    wget -q https://raw.githubusercontent.com/namilsk/server-monitor/main/docker-compose.node.yml -O "$COMPOSE_FILE" 2>/dev/null || \
    cat > "$COMPOSE_FILE" << 'COMPOSE'
services:
  node-agent:
    image: namilsk/monitor:latest
    container_name: monitor-agent
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    env_file: .env
    privileged: true
    restart: unless-stopped
COMPOSE
    echo -e "${GREEN}✓${NC} docker-compose.yml created"
fi

# Show run command based on environment
if [ "$RUNNING_IN_DOCKER" = true ]; then
    echo -e "${YELLOW}Running inside Docker container${NC}"
    echo "To start the agent, run:"
    echo ""
    echo -e "  ${GREEN}python agent.py${NC}"
    echo ""
else
    echo -e "Run options:"
    echo ""
    echo -e "  ${GREEN}1. Docker Compose (recommended):${NC}"
    echo -e "     docker-compose up -d"
    echo ""
    echo -e "  ${GREEN}2. Docker Run:${NC}"
    echo -e "     docker run -d --env-file .env --privileged -v /proc:/host/proc:ro --name monitor-agent namilsk/monitor:latest"
    echo ""
    echo -e "  ${GREEN}3. Local Python:${NC}"
    echo -e "     python3 -m venv venv && source venv/bin/activate"
    echo -e "     pip install psutil pyjwt requests"
    echo -e "     python -c \"import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/namilsk/server-monitor/main/node/agent.py').read())\""
    echo ""
fi

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo -e "To check status: ${GREEN}docker logs -f monitor-agent${NC}"
