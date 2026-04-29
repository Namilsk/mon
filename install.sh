#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      Server Monitor - Installer        ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

# Generate secure JWT secret
generate_jwt_secret() {
    openssl rand -hex 32
}

# Generate admin password
generate_admin_password() {
    openssl rand -base64 12
}

# Get server IP
get_server_ip() {
    hostname -I | awk '{print $1}' || echo "127.0.0.1"
}

print_banner

echo -e "${BLUE}[1/5]${NC} Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker found${NC}"

echo ""
echo -e "${BLUE}[2/5]${NC} Generating secure credentials..."
JWT_SECRET=$(generate_jwt_secret)
ADMIN_PASSWORD=$(generate_admin_password)
SERVER_IP=$(get_server_ip)

echo -e "${GREEN}✓ JWT Secret generated${NC}"
echo -e "${GREEN}✓ Admin password generated${NC}"

echo ""
echo -e "${BLUE}[3/5]${NC} Creating configuration files..."

# Create central .env
cat > central/.env << EOF
JWT_SECRET=${JWT_SECRET}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
DATA_DIR=/app/data
EOF

# Create node .env template
cat > node/.env.example << EOF
CENTRAL_URL=https://${SERVER_IP}:5000
NODE_ID=node-$(openssl rand -hex 4)
JWT_SECRET=${JWT_SECRET}
POLL_INTERVAL=5
EOF

# Create docker-compose.yml
cat > docker-compose.yml << EOF
version: '3.8'

services:
  central:
    build: ./central
    ports:
      - "5000:5000"
    volumes:
      - ./central/data:/app/data
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - DATA_DIR=/app/data
    restart: unless-stopped
    networks:
      - monitor-net

networks:
  monitor-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
EOF

echo -e "${GREEN}✓ Configuration files created${NC}"

echo ""
echo -e "${BLUE}[4/5]${NC} Building and starting..."
docker-compose up -d --build

echo ""
echo -e "${GREEN}✓ Server Monitor is running!${NC}"

echo ""
echo -e "${BLUE}[5/5]${NC} Setup complete!"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  Access Information:${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Dashboard URL:   ${GREEN}http://${SERVER_IP}:5000${NC}"
echo -e "  Admin Username:  ${GREEN}admin${NC}"
echo -e "  Admin Password:  ${GREEN}${ADMIN_PASSWORD}${NC}"
echo ""
echo -e "  ${YELLOW}JWT Secret (for nodes):${NC}"
echo -e "  ${GREEN}${JWT_SECRET}${NC}"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Node Setup Instructions:${NC}"
echo ""
echo -e "  1. Copy the JWT secret above to your node agent"
echo -e "  2. Configure node with:"
echo -e "     - Central URL: http://${SERVER_IP}:5000"
echo -e "     - JWT Secret: ${JWT_SECRET:0:16}..."
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "To add external servers, use the '+ Add Server' button in the dashboard."
echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
