#!/bin/bash
#==========================================
# Compliance Audit System - Queue Monitor
# Purpose: Monitor Redis job queue and system health
#==========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REDIS_CONTAINER="compliance-redis"
DB_CONTAINER="compliance-db"
N8N_CONTAINER="compliance-n8n"

# Redis queue key (must match workflow-c1-audit-entry.json LPUSH and
# workflow-c2-audit-worker.json RPOP configuration)
QUEUE_KEY="audit_job_queue"

# Function: Print header
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Compliance Audit Queue Monitor       ║${NC}"
    echo -e "${BLUE}║  $(date '+%Y-%m-%d %H:%M:%S')                 ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

# Function: Check container health
check_container_health() {
    local container=$1
    local status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
    
    if [ "$status" == "healthy" ]; then
        echo -e "${GREEN}✓${NC} $container: healthy"
    elif [ "$status" == "unhealthy" ]; then
        echo -e "${RED}✗${NC} $container: unhealthy"
    elif [ "$status" == "none" ]; then
        local running=$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null || echo "false")
        if [ "$running" == "true" ]; then
            echo -e "${YELLOW}⚠${NC} $container: running (no healthcheck)"
        else
            echo -e "${RED}✗${NC} $container: not running"
        fi
    else
        echo -e "${YELLOW}⚠${NC} $container: $status"
    fi
}

# Function: Get Redis queue stats
get_queue_stats() {
    echo -e "\n${BLUE}━━━ Redis Queue Status ━━━${NC}"

    local pending=$(docker exec "$REDIS_CONTAINER" redis-cli LLEN "$QUEUE_KEY" 2>/dev/null || echo "ERROR")
    local processing=$(docker exec "$REDIS_CONTAINER" redis-cli LLEN compliance:jobs:processing 2>/dev/null || echo "0")
    local failed=$(docker exec "$REDIS_CONTAINER" redis-cli LLEN compliance:jobs:failed 2>/dev/null || echo "0")
    
    echo " Pending Jobs:    $pending"
    echo " Processing Jobs: $processing"
    echo " Failed Jobs:     $failed"
    
    if [ "$pending" != "ERROR" ] && [ "$pending" -gt 0 ]; then
        echo -e "\n${YELLOW}⚠ Warning: $pending jobs waiting in queue${NC}"
        
        # Show first pending job
        echo -e "\n${BLUE}Next Job in Queue:${NC}"
        docker exec "$REDIS_CONTAINER" redis-cli LRANGE "$QUEUE_KEY" -1 -1 | jq '.' 2>/dev/null || echo "(parsing failed)"
    fi
    
    if [ "$failed" != "0" ] && [ "$failed" -gt 0 ]; then
        echo -e "\n${RED}✗ Error: $failed failed jobs detected${NC}"
        echo "View failed jobs: docker exec $REDIS_CONTAINER redis-cli LRANGE compliance:jobs:failed 0 -1"
    fi
}

# Function: Get session statistics
get_session_stats() {
    echo -e "\n${BLUE}━━━ Session Statistics ━━━${NC}"
    
    local query="
    SELECT 
        status,
        COUNT(*) as count,
        ROUND(AVG(overall_compliance_score), 2) as avg_score
    FROM audit_sessions
    WHERE started_at > NOW() - INTERVAL '24 hours'
    GROUP BY status
    ORDER BY 
        CASE status
            WHEN 'completed' THEN 1
            WHEN 'processing' THEN 2
            WHEN 'queued' THEN 3
            WHEN 'failed' THEN 4
            ELSE 5
        END;
    "
    
    docker exec "$DB_CONTAINER" psql -U n8n -d compliance_db -t -c "$query" 2>/dev/null || echo "Database query failed"
    
    # Current processing sessions
    local processing_count=$(docker exec "$DB_CONTAINER" psql -U n8n -d compliance_db -t -c \
        "SELECT COUNT(*) FROM audit_sessions WHERE status = 'processing';" 2>/dev/null | tr -d ' ')
    
    if [ "$processing_count" -gt 0 ]; then
        echo -e "\n${YELLOW}Currently Processing:${NC}"
        docker exec "$DB_CONTAINER" psql -U n8n -d compliance_db -c \
            "SELECT session_id, domain, started_at, 
                    EXTRACT(EPOCH FROM (NOW() - started_at)) as elapsed_seconds
             FROM audit_sessions 
             WHERE status = 'processing' 
             ORDER BY started_at;" 2>/dev/null || echo "Query failed"
    fi
}

# Function: Get worker status
get_worker_status() {
    echo -e "\n${BLUE}━━━ Worker Status (Workflow C2) ━━━${NC}"
    
    # Check last cron execution
    local last_exec=$(docker exec "$DB_CONTAINER" psql -U n8n -d compliance_db -t -c \
        "SELECT MAX(created_at) FROM audit_logs WHERE step_name = 'processing';" 2>/dev/null | tr -d ' ')
    
    if [ -n "$last_exec" ] && [ "$last_exec" != "" ]; then
        echo " Last Worker Execution: $last_exec"
        
        # Calculate time since last execution
        local now=$(date +%s)
        local last_timestamp=$(date -d "$last_exec" +%s 2>/dev/null || echo "$now")
        local diff=$((now - last_timestamp))
        
        if [ "$diff" -gt 60 ]; then
            echo -e " ${RED}⚠ Warning: No worker activity for $diff seconds${NC}"
            echo "   Check n8n logs: docker logs $N8N_CONTAINER --tail 100"
        else
            echo -e " ${GREEN}✓ Worker active (last run: ${diff}s ago)${NC}"
        fi
    else
        echo " No recent worker activity detected"
    fi
}

# Function: Get disk space usage
get_disk_usage() {
    echo -e "\n${BLUE}━━━ Disk Usage ━━━${NC}"
    
    # Check temp directory
    if [ -d "/tmp/n8n_processing/sessions" ]; then
        local session_count=$(find /tmp/n8n_processing/sessions -maxdepth 1 -type d | wc -l)
        local total_size=$(du -sh /tmp/n8n_processing/sessions 2>/dev/null | cut -f1 || echo "N/A")
        
        echo " Active Sessions: $((session_count - 1))"
        echo " Temp Files Size: $total_size"
        
        if [ "$session_count" -gt 50 ]; then
            echo -e " ${YELLOW}⚠ Warning: Many session directories (possible cleanup needed)${NC}"
        fi
    else
        echo " No session directories found"
    fi
    
    # Check Docker volumes
    echo -e "\n Docker Volume Sizes:"
    docker volume ls | grep compliance | while read -r driver name; do
        local size=$(docker run --rm -v ${name}:/data alpine du -sh /data 2>/dev/null | cut -f1 || echo "N/A")
        echo "  - $name: $size"
    done
}

# Function: Get performance metrics
get_performance_metrics() {
    echo -e "\n${BLUE}━━━ Performance Metrics (Last 24h) ━━━${NC}"
    
    local query="
    SELECT 
        TO_CHAR(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 'FM999999990.00') || 's' as avg_duration,
        TO_CHAR(MIN(EXTRACT(EPOCH FROM (completed_at - started_at))), 'FM999999990.00') || 's' as min_duration,
        TO_CHAR(MAX(EXTRACT(EPOCH FROM (completed_at - started_at))), 'FM999999990.00') || 's' as max_duration,
        COUNT(*) as completed_count
    FROM audit_sessions
    WHERE completed_at > NOW() - INTERVAL '24 hours'
      AND status = 'completed';
    "
    
    docker exec "$DB_CONTAINER" psql -U n8n -d compliance_db -t -c "$query" 2>/dev/null || echo "Query failed"
}

# Function: Show help
show_help() {
    cat << EOF
Usage: $0 [OPTION]

Monitor the Compliance Audit System job queue and health.

Options:
  -h, --help        Show this help message
  -w, --watch       Continuous monitoring (refresh every 10s)
  --queue           Show only queue statistics
  --sessions        Show only session statistics
  --health          Show only health checks
  --cleanup         Remove old temp files (>24h)
  --failed          Show details of failed jobs
  --raw             Raw Redis inspection (queue lengths, keys, last 5 jobs)

Examples:
  $0                    # Run once, show all stats
  $0 --watch            # Continuous live monitoring
  $0 --queue            # Quick queue check
  $0 --cleanup          # Clean up old files
  $0 --raw              # Direct Redis key inspection
EOF
}

# Function: Cleanup old temp files
cleanup_temp_files() {
    echo -e "${YELLOW}Cleaning up temp files older than 24 hours...${NC}"
    
    if [ -d "/tmp/n8n_processing/sessions" ]; then
        local count_before=$(find /tmp/n8n_processing/sessions -maxdepth 1 -type d | wc -l)
        
        find /tmp/n8n_processing/sessions -maxdepth 1 -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true
        
        local count_after=$(find /tmp/n8n_processing/sessions -maxdepth 1 -type d | wc -l)
        local removed=$((count_before - count_after))
        
        echo -e "${GREEN}✓ Removed $removed old session directories${NC}"
    else
        echo "No temp directory found"
    fi
}

# Function: Show failed jobs
show_failed_jobs() {
    echo -e "${BLUE}━━━ Failed Jobs ━━━${NC}\n"
    
    local failed_count=$(docker exec "$REDIS_CONTAINER" redis-cli LLEN compliance:jobs:failed 2>/dev/null || echo "0")
    
    if [ "$failed_count" == "0" ]; then
        echo -e "${GREEN}✓ No failed jobs${NC}"
        return
    fi
    
    echo -e "${RED}Found $failed_count failed job(s):${NC}\n"
    
    docker exec "$REDIS_CONTAINER" redis-cli LRANGE compliance:jobs:failed 0 -1 | while read -r job; do
        echo "$job" | jq -r '. | "Session: \(.sessionId)\nError: \(.error)\nFailed At: \(.failedAt)\n---"' 2>/dev/null || echo "$job"
    done
}

# Main monitoring function
run_monitor() {
    clear
    print_header
    
    echo -e "${BLUE}━━━ Container Health ━━━${NC}"
    check_container_health "$REDIS_CONTAINER"
    check_container_health "$DB_CONTAINER"
    check_container_health "$N8N_CONTAINER"
    check_container_health "compliance-qdrant"
    check_container_health "compliance-ollama"
    check_container_health "compliance-florence"
    
    get_queue_stats
    get_session_stats
    get_worker_status
    get_disk_usage
    get_performance_metrics
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "Tip: Run with ${YELLOW}--watch${NC} for continuous monitoring"
    echo -e "     Run with ${YELLOW}--help${NC} for more options"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -w|--watch)
        while true; do
            run_monitor
            sleep 10
        done
        ;;
    --queue)
        print_header
        get_queue_stats
        ;;
    --sessions)
        print_header
        get_session_stats
        ;;
    --health)
        print_header
        echo -e "${BLUE}━━━ Container Health ━━━${NC}"
        check_container_health "$REDIS_CONTAINER"
        check_container_health "$DB_CONTAINER"
        check_container_health "$N8N_CONTAINER"
        check_container_health "compliance-qdrant"
        check_container_health "compliance-ollama"
        check_container_health "compliance-florence"
        ;;
    --cleanup)
        print_header
        cleanup_temp_files
        ;;
    --failed)
        print_header
        show_failed_jobs
        ;;
    --raw)
        # Raw Redis inspection of the actual queue key used by workflows
        echo -e "${BLUE}━━━ Raw Redis Inspection (queue: $QUEUE_KEY) ━━━${NC}"
        echo -e "\nQueue length:"
        docker exec "$REDIS_CONTAINER" redis-cli LLEN "$QUEUE_KEY"
        echo -e "\nLast 5 items (WITHOUT popping):"
        docker exec "$REDIS_CONTAINER" redis-cli LRANGE "$QUEUE_KEY" -5 -1
        echo -e "\nAll Redis keys matching 'audit*':"
        docker exec "$REDIS_CONTAINER" redis-cli KEYS "audit*"
        echo -e "\nRedis database info:"
        docker exec "$REDIS_CONTAINER" redis-cli INFO keyspace
        ;;
    "")
        run_monitor
        ;;
    *)
        echo "Unknown option: $1"
        echo "Run '$0 --help' for usage information"
        exit 1
        ;;
esac
