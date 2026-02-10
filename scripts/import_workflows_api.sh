#!/bin/bash
# Import workflows via n8n REST API
# Requires: jq, curl, basic auth credentials

set -e

N8N_URL="http://172.206.67.83:5678"
N8N_USER="roshanl@unifi-data.com"
N8N_PASSWORD="ComplianceAdmin2026!"
WORKFLOW_DIR="./workflows"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  n8n Workflow Import (REST API)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Login to get session cookie
echo -e "${YELLOW}Logging in to n8n...${NC}"
COOKIE_JAR=$(mktemp)

LOGIN_RESPONSE=$(curl -s -c "$COOKIE_JAR" -X POST \
  "$N8N_URL/rest/login" \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"${N8N_USER}\",\"password\":\"${N8N_PASSWORD}\"}")

if echo "$LOGIN_RESPONSE" | jq -e '.data.id' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Logged in successfully${NC}"
else
    echo -e "${RED}✗ Login failed${NC}"
    echo "Response: $LOGIN_RESPONSE"
    rm -f "$COOKIE_JAR"
    exit 1
fi

echo ""

# Function to import a workflow
import_workflow() {
    local file="$1"
    local name=$(basename "$file" .json | sed 's/workflow-//' | tr '-' ' ' | sed 's/\b\(.\)/\u\1/g')
    
    echo -e "${YELLOW}Importing: $name${NC}"
    
    # Read and prepare workflow JSON
    WORKFLOW_DATA=$(cat "$file" | jq -c '. | {name: .name, nodes: .nodes, connections: .connections, settings: .settings, staticData: .staticData, tags: .tags}')
    
    # Try to import
    IMPORT_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X POST \
      "$N8N_URL/rest/workflows" \
      -H "Content-Type: application/json" \
      -d "$WORKFLOW_DATA")
    
    if echo "$IMPORT_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
        WORKFLOW_ID=$(echo "$IMPORT_RESPONSE" | jq -r '.id')
        echo -e "${GREEN}  ✓ Imported (ID: $WORKFLOW_ID)${NC}"
        
        # Activate workflow
        ACTIVATE_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X PATCH \
          "$N8N_URL/rest/workflows/$WORKFLOW_ID" \
          -H "Content-Type: application/json" \
          -d '{"active": true}')
        
        if echo "$ACTIVATE_RESPONSE" | jq -e '.active == true' > /dev/null 2>&1; then
            echo -e "${GREEN}  ✓ Activated${NC}"
        else
            echo -e "${YELLOW}  ! Could not activate workflow${NC}"
        fi
        
        return 0
    else
        echo -e "${RED}  ✗ Import failed${NC}"
        echo "  Response: $(echo "$IMPORT_RESPONSE" | jq -r '.message // .')"
        return 1
    fi
}

# Import each workflow
WORKFLOWS=(
    "$WORKFLOW_DIR/workflow-c1-audit-entry.json"
    "$WORKFLOW_DIR/workflow-c2-audit-worker.json"
    "$WORKFLOW_DIR/workflow-c3-status-poll.json"
    "$WORKFLOW_DIR/workflow-c4-results-retrieval.json"
)

SUCCESS=0
FAILED=0

for workflow in "${WORKFLOWS[@]}"; do
    if [ -f "$workflow" ]; then
        if import_workflow "$workflow"; then
            ((SUCCESS++))
        else
            ((FAILED++))
        fi
    else
        echo -e "${RED}File not found: $workflow${NC}"
        ((FAILED++))
    fi
    echo ""
done

# Cleanup
rm -f "$COOKIE_JAR"

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Successful: $SUCCESS${NC}"
echo -e "${RED}✗ Failed: $FAILED${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ $SUCCESS -gt 0 ]; then
    echo -e "${GREEN}Workflows imported and activated!${NC}"
    echo "View them at: $N8N_URL"
else
    echo -e "${RED}No workflows were imported${NC}"
    echo "Check n8n logs: docker logs compliance-n8n --tail 50"
fi
