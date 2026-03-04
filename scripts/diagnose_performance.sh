#!/bin/bash

# Performance Diagnostic Script for NPC Compliance AI System
# Analyzes execution times, GPU utilization, and identifies bottlenecks
# Usage: ./scripts/diagnose_performance.sh [session_id]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Performance Diagnostic Tool${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if session_id provided
SESSION_ID=$1

# Database connection details from .env
if [ -f .env ]; then
    source .env
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-compliance_db}
DB_USER=${DB_USER:-n8n}

# Function to run SQL queries
run_query() {
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A -c "$1"
}

echo -e "${YELLOW}[1/7] Checking GPU Availability${NC}"
echo "-----------------------------------"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory --format=csv
    echo ""
    echo -e "${GREEN}✓ GPU detected${NC}"
else
    echo -e "${RED}✗ nvidia-smi not found - GPU may not be available${NC}"
fi
echo ""

echo -e "${YELLOW}[2/7] Checking Service Status${NC}"
echo "-----------------------------------"
# Check if services are responding
check_service() {
    local name=$1
    local url=$2
    if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" | grep -q "200\|404\|401"; then
        echo -e "${GREEN}✓ $name is responding${NC}"
    else
        echo -e "${RED}✗ $name is not responding${NC}"
    fi
}

check_service "n8n" "http://localhost:5678"
check_service "Ollama" "http://localhost:11434"
check_service "Florence" "http://localhost:5000/health"
check_service "Qdrant" "http://localhost:6333/health"
check_service "Redis" "http://localhost:6379"
echo ""

echo -e "${YELLOW}[3/7] Analyzing Recent Executions${NC}"
echo "-----------------------------------"
if [ -z "$SESSION_ID" ]; then
    echo "Getting last 5 sessions..."
    QUERY="
    SELECT 
        session_id,
        status,
        EXTRACT(EPOCH FROM (updated_at - created_at)) as duration_seconds,
        created_at
    FROM audit_sessions 
    ORDER BY created_at DESC 
    LIMIT 5;
    "
    run_query "$QUERY" | while IFS='|' read -r sid status duration created; do
        echo "Session: $sid"
        echo "  Status: $status"
        echo "  Duration: ${duration}s"
        echo "  Created: $created"
        echo ""
    done
    
    # Get the most recent session for detailed analysis
    SESSION_ID=$(run_query "SELECT session_id FROM audit_sessions ORDER BY created_at DESC LIMIT 1;")
    echo -e "${BLUE}Using most recent session for detailed analysis: $SESSION_ID${NC}"
else
    echo -e "${BLUE}Analyzing session: $SESSION_ID${NC}"
fi
echo ""

echo -e "${YELLOW}[4/7] Detailed Step-by-Step Timing${NC}"
echo "-----------------------------------"
QUERY="
SELECT 
    step_name,
    status,
    EXTRACT(EPOCH FROM (updated_at - created_at)) as duration_seconds,
    created_at,
    updated_at
FROM audit_logs 
WHERE session_id = '$SESSION_ID'
ORDER BY created_at ASC;
"

echo "Step breakdown for session $SESSION_ID:"
run_query "$QUERY" | while IFS='|' read -r step status duration created updated; do
    if (( $(echo "$duration > 5" | bc -l) )); then
        echo -e "${RED}  ⚠ $step: ${duration}s (SLOW)${NC}"
    else
        echo -e "${GREEN}  ✓ $step: ${duration}s${NC}"
    fi
    echo "    Status: $status"
    echo "    Start: $created"
    echo "    End: $updated"
    echo ""
done

echo -e "${YELLOW}[5/7] Evidence Extraction Analysis${NC}"
echo "-----------------------------------"
QUERY="
SELECT 
    file_hash,
    file_name,
    COALESCE(jsonb_array_length(extracted_data->'pages'), 0) as page_count,
    LENGTH(extracted_data::text) as data_size_bytes,
    created_at
FROM audit_evidence 
WHERE session_id = '$SESSION_ID'
ORDER BY created_at ASC;
"

echo "Evidence files processed:"
run_query "$QUERY" | while IFS='|' read -r hash filename pages size created; do
    echo "  File: $filename"
    echo "    Hash: $hash"
    echo "    Pages: $pages"
    echo "    Data size: $size bytes"
    echo "    Extracted at: $created"
    echo ""
done

echo -e "${YELLOW}[6/7] Cache Performance${NC}"
echo "-----------------------------------"
QUERY="
SELECT 
    COUNT(*) FILTER (WHERE step_name = 'cache_hit') as cache_hits,
    COUNT(*) FILTER (WHERE step_name = 'cache_miss') as cache_misses,
    COUNT(*) FILTER (WHERE step_name = 'completed') as completed_evaluations,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE step_name = 'completed') as avg_eval_time
FROM audit_logs 
WHERE session_id = '$SESSION_ID';
"

echo "Cache statistics:"
run_query "$QUERY" | while IFS='|' read -r hits misses completed avg_time; do
    echo "  Cache hits: $hits"
    echo "  Cache misses: $misses"
    echo "  Completed evaluations: $completed"
    echo "  Average evaluation time: ${avg_time}s"
    
    if [ "$hits" -gt 0 ]; then
        hit_rate=$(echo "scale=2; $hits * 100 / ($hits + $misses)" | bc)
        echo -e "  ${GREEN}Cache hit rate: ${hit_rate}%${NC}"
    fi
done
echo ""

echo -e "${YELLOW}[7/7] Bottleneck Identification${NC}"
echo "-----------------------------------"

# Find slowest steps across all recent sessions
QUERY="
SELECT 
    step_name,
    COUNT(*) as occurrences,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_duration,
    MAX(EXTRACT(EPOCH FROM (updated_at - created_at))) as max_duration
FROM audit_logs 
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND step_name NOT IN ('pending', 'cache_hit')
GROUP BY step_name
HAVING AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) > 1
ORDER BY avg_duration DESC;
"

echo "Slowest operations (last 24 hours):"
run_query "$QUERY" | while IFS='|' read -r step count avg_dur max_dur; do
    if (( $(echo "$avg_dur > 30" | bc -l) )); then
        echo -e "${RED}  ⚠ $step${NC}"
    elif (( $(echo "$avg_dur > 10" | bc -l) )); then
        echo -e "${YELLOW}  ⚠ $step${NC}"
    else
        echo -e "  $step"
    fi
    echo "    Occurrences: $count"
    echo "    Average: ${avg_dur}s"
    echo "    Max: ${max_dur}s"
    echo ""
done

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Diagnostic Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Generate recommendations
echo -e "${YELLOW}Recommendations:${NC}"
echo ""

# Check if GPU is being used
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}1. GPU not detected - verify NVIDIA drivers are installed${NC}"
    echo "   Run: nvidia-smi"
    echo ""
fi

# Check for slow extraction
SLOW_EXTRACTION=$(run_query "SELECT COUNT(*) FROM audit_logs WHERE session_id = '$SESSION_ID' AND step_name LIKE '%extract%' AND EXTRACT(EPOCH FROM (updated_at - created_at)) > 30;")
if [ "$SLOW_EXTRACTION" -gt 0 ]; then
    echo -e "${RED}2. Evidence extraction is slow (>30s)${NC}"
    echo "   - Check Florence service GPU utilization"
    echo "   - Verify Florence is using CUDA (not CPU)"
    echo "   - Check: curl http://localhost:5000/health"
    echo ""
fi

# Check for slow LLM evaluation
SLOW_LLM=$(run_query "SELECT COUNT(*) FROM audit_logs WHERE session_id = '$SESSION_ID' AND step_name = 'completed' AND EXTRACT(EPOCH FROM (updated_at - created_at)) > 60;")
if [ "$SLOW_LLM" -gt 0 ]; then
    echo -e "${RED}3. LLM evaluation is slow (>60s)${NC}"
    echo "   - Check Ollama GPU utilization"
    echo "   - Verify Mistral Nemo is loaded: curl http://localhost:11434/api/tags"
    echo "   - Check model quantization (should be Q4_K_M)"
    echo ""
fi

# Check for RAG search issues
SLOW_RAG=$(run_query "SELECT COUNT(*) FROM audit_logs WHERE session_id = '$SESSION_ID' AND step_name LIKE '%rag%' AND EXTRACT(EPOCH FROM (updated_at - created_at)) > 10;")
if [ "$SLOW_RAG" -gt 0 ]; then
    echo -e "${YELLOW}4. RAG search is slow (>10s)${NC}"
    echo "   - Check Qdrant collection size"
    echo "   - Verify embedding service is responding"
    echo ""
fi

echo -e "${GREEN}Diagnostic complete!${NC}"
echo ""
echo "For more details, check:"
echo "  - n8n execution logs: python3 scripts/export_n8n_logs.py --list-recent"
echo "  - GPU monitoring: watch -n 1 nvidia-smi"
echo "  - Service logs: docker compose logs -f [service_name]"
