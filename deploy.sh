#!/bin/bash

# ============================================
# Compliance Audit System - Deployment Script
# ============================================

set -e  # Exit on error

echo "============================================"
echo "  Compliance Audit System Deployment"
echo "============================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# Pre-flight Checks
# ============================================
echo -e "\n${YELLOW}[1/6] Running pre-flight checks...${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Check if running as root or with sudo
if [ "$EUID" -eq 0 ]; then 
    echo -e "${YELLOW}Warning: Running as root. Consider using a regular user in the docker group.${NC}"
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# ============================================
# Environment Setup
# ============================================
echo -e "\n${YELLOW}[2/6] Setting up environment...${NC}"

if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created. Please update it with your settings.${NC}"
    echo -e "${YELLOW}⚠ Edit .env file and run this script again.${NC}"
    exit 0
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

# ============================================
# Stop Existing Containers
# ============================================
echo -e "\n${YELLOW}[3/6] Stopping existing containers (if any)...${NC}"

if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    docker-compose -f docker-compose.prod.yml down
    echo -e "${GREEN}✓ Existing containers stopped${NC}"
else
    echo -e "${GREEN}✓ No running containers found${NC}"
fi

# ============================================
# Build Images
# ============================================
echo -e "\n${YELLOW}[4/6] Building Docker images...${NC}"
echo "This may take 10-15 minutes on first run..."

docker-compose -f docker-compose.prod.yml build --no-cache

echo -e "${GREEN}✓ Images built successfully${NC}"

# ============================================
# Start Services
# ============================================
echo -e "\n${YELLOW}[5/6] Starting services...${NC}"

docker-compose -f docker-compose.prod.yml up -d

echo -e "${GREEN}✓ Services started${NC}"

# ============================================
# Health Checks
# ============================================
echo -e "\n${YELLOW}[6/6] Waiting for services to be healthy...${NC}"

# Function to check if a service is healthy
check_health() {
    local service=$1
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose -f docker-compose.prod.yml ps | grep $service | grep -q "healthy"; then
            echo -e "${GREEN}✓ $service is healthy${NC}"
            return 0
        fi
        
        if docker-compose -f docker-compose.prod.yml ps | grep $service | grep -q "Up"; then
            echo -n "."
        else
            echo -e "${RED}✗ $service failed to start${NC}"
            return 1
        fi
        
        sleep 2
        ((attempt++))
    done
    
    echo -e "${YELLOW}⚠ $service health check timed out (may still be starting)${NC}"
    return 0
}

echo "Checking Postgres..."
check_health "postgres"

echo "Checking Qdrant..."
check_health "qdrant"

echo "Checking n8n..."
check_health "n8n"

# ============================================
# Display Access Information
# ============================================
echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}============================================${NC}"

# Get external IP from .env
EXTERNAL_IP=$(grep EXTERNAL_IP .env | cut -d '=' -f2)

echo -e "\n${YELLOW}Access URLs:${NC}"
echo -e "  n8n Web UI:     ${GREEN}http://${EXTERNAL_IP}:5678${NC}"
echo -e "  Postgres:       ${GREEN}${EXTERNAL_IP}:5432${NC}"
echo -e "  Qdrant:         ${GREEN}http://${EXTERNAL_IP}:6333${NC}"
echo -e "  Ollama API:     ${GREEN}http://${EXTERNAL_IP}:11434${NC}"
echo -e "  Florence API:   ${GREEN}http://${EXTERNAL_IP}:5000${NC}"

echo -e "\n${YELLOW}Default Credentials:${NC}"
N8N_USER=$(grep N8N_USER .env | cut -d '=' -f2)
echo -e "  Username: ${GREEN}${N8N_USER}${NC}"
echo -e "  Password: ${GREEN}(Check .env file)${NC}"

echo -e "\n${YELLOW}Useful Commands:${NC}"
echo "  View logs:           docker-compose -f docker-compose.prod.yml logs -f"
echo "  Stop services:       docker-compose -f docker-compose.prod.yml down"
echo "  Restart services:    docker-compose -f docker-compose.prod.yml restart"
echo "  Check status:        docker-compose -f docker-compose.prod.yml ps"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo "  1. Import workflows from ./workflows/ directory into n8n"
echo "  2. Upload standard documents to build the knowledge base"
echo "  3. Test the /audit API endpoint"

echo -e "\n${GREEN}============================================${NC}"
