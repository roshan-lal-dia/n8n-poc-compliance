#!/bin/bash
# Debug Redis Queue Script

echo "=== Redis Queue Debug =========================="
echo

echo "1. Queue Length:"
docker exec compliance-redis redis-cli llen audit_job_queue
echo

echo "2. View last 5 items (without popping):"
docker exec compliance-redis redis-cli lrange audit_job_queue -5 -1
echo

echo "3. All Redis keys matching 'audit*':"
docker exec compliance-redis redis-cli keys "audit*"
echo

echo "4. Redis database info:"
docker exec compliance-redis redis-cli info keyspace
echo

echo "=== To manually inspect Redis: ================="
echo "Run: docker exec -it compliance-redis redis-cli"
echo "Then use commands like:"
echo "  - LLEN audit_job_queue              (check queue length)"
echo "  - LRANGE audit_job_queue 0 -1       (view all items)"
echo "  - RPOP audit_job_queue              (pop from tail)"
echo "  - LPUSH audit_job_queue '{...}'     (push to head)"
echo

echo "=== Web Interfaces: ============================"
echo "n8n UI:     http://localhost:5678"
echo "            (or http://YOUR_VM_IP:5678)"
echo
echo "To add Redis Commander (optional web UI for Redis):"
echo "  Add to docker-compose.prod.yml:"
echo "    redis-commander:"
echo "      image: rediscommander/redis-commander:latest"
echo "      ports:"
echo "        - \"8081:8081\""
echo "      environment:"
echo "        - REDIS_HOSTS=local:compliance-redis:6379"
echo
