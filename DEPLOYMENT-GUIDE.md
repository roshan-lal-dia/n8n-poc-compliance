# Multi-Question Audit System - Deployment Guide

**Version:** 2.0  
**Date:** February 10, 2026  
**Status:** Ready for Testing

---

## What's Been Implemented

### ✅ Core Features

1. **Multi-Question Support**: Submit multiple questions in a single API call
2. **Multi-Document Per Question**: Each question can have multiple evidence files
3. **Evidence Isolation**: Question 1's evidence never used for Question 2
4. **Deduplication**: Identical files extracted only once per session
5. **Background Processing**: Redis job queue, immediate API response (202 Accepted)
6. **Large File Support**: 500MB total limit, disk-based storage (no memory overflow)
7. **Granular Status Updates**: Real-time progress with percentages per question
8. **Score Aggregation**: Automatic averaging of multi-question scores

### ✅ Database Changes

- **Removed**: `file_registry` table (unused), GIN full-text index (unused), views (unused)
- **Modified**: `audit_evidence` unique constraint (session+q_id+hash)
- **Added**: `file_size_bytes`, `evidence_order`, `job_id` columns
- **Cleaned**: 1 unused column removed (`file_type`)

### ✅ New Workflows

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| **C1** - audit-entry | Accept uploads, validate, queue job | Webhook: POST /audit/submit |
| **C2** - audit-worker | Process jobs from queue | Cron: Every 10s |
| **C3** - status-poll | Real-time progress tracking | Webhook: GET /audit/status/:id |
| **C4** - results-retrieval | Fetch completed audit results | Webhook: GET /audit/results/:id |

### ✅ Documentation Created

- **[AUDIT-TRANSPARENCY-GUIDE.md](docs/AUDIT-TRANSPARENCY-GUIDE.md)**: Complete system internals (how everything works)
- **[FRONTEND-API-GUIDE.md](docs/FRONTEND-API-GUIDE.md)**: API integration guide for frontend developers
- **[monitor_queue.sh](scripts/monitor_queue.sh)**: Queue monitoring and health check script

### ✅ Infrastructure Added

- **Redis**: Job queue (compliance:jobs:pending)
- **Docker Compose**: Redis service added, environment variables updated

---

## Deployment Steps

### Step 1: Backup Current System

```bash
# Backup database
docker exec compliance-db pg_dump -U n8n compliance_db > backup_$(date +%Y%m%d).sql

# Backup current workflow
cp workflows/workflow-c-audit-orchestrator.json workflows/workflow-c-audit-orchestrator.json.backup

# Backup docker-compose
cp docker-compose.prod.yml docker-compose.prod.yml.backup
```

### Step 2: Apply Database Migration

```bash
# Migration already applied during development
# Verify it worked:
docker exec compliance-db psql -U n8n -d compliance_db -c "\dt" | grep file_registry
# Should return nothing (table dropped)

docker exec compliance-db psql -U n8n -d compliance_db -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='audit_evidence';" | grep file_size_bytes
# Should show: file_size_bytes
```

### Step 3: Start Redis Service

```bash
# Redis already added to docker-compose.prod.yml

# Start Redis (won't affect running services):
docker-compose -f docker-compose.prod.yml up -d redis

# Verify Redis is running:
docker ps | grep redis
# Should show: compliance-redis ... Up X minutes

# Test Redis:
docker exec compliance-redis redis-cli PING
# Should return: PONG
```

### Step 4: Import New Workflows to n8n

**Option A: Via n8n UI (Recommended)**

1. Open n8n: `http://172.206.67.83:5678`
2. Login with credentials (admin / ComplianceAdmin2026!)
3. For each workflow file:
   - Go to **Workflows** → **Import from File**
   - Upload:
     - `workflows/workflow-c1-audit-entry.json`
     - `workflows/workflow-c2-audit-worker.json`
     - `workflows/workflow-c3-status-poll.json`
     - `workflows/workflow-c4-results-retrieval.json`
   - Click **Import**
   - **Activate** the workflow (toggle in top-right)

4. **Setup Credentials** (if not already configured):
   - Go to **Credentials** → **Add Credential**
   - Add:
     - **Postgres** (ID: `postgres-compliance`):
       - Host: postgres
       - Port: 5432
       - Database: compliance_db
       - User: n8n
       - Password: ComplianceDB2026!
     - **Redis** (ID: `redis-compliance`):
       - Host: redis
       - Port: 6379
       - Database: 0

**Option B: Via Docker Volume Mount (Alternative)**

```bash
# Copy workflows to n8n data directory
docker cp workflows/workflow-c1-audit-entry.json compliance-n8n:/home/node/.n8n/workflows/
docker cp workflows/workflow-c2-audit-worker.json compliance-n8n:/home/node/.n8n/workflows/
docker cp workflows/workflow-c3-status-poll.json compliance-n8n:/home/node/.n8n/workflows/
docker cp workflows/workflow-c4-results-retrieval.json compliance-n8n:/home/node/.n8n/workflows/

# Restart n8n to load workflows
docker restart compliance-n8n
```

### Step 5: Verify Workflows are Active

```bash
# Check workflow status in n8n UI
# All 4 workflows should show as "Active" with green toggle

# Or check via logs:
docker logs compliance-n8n --tail 50 | grep "Workflow"
# Should show workflow execution startup messages
```

### Step 6: Test End-to-End

**Test 1: Simple Single-Question Audit**

```bash
# Create test file
echo "Sample compliance document content..." > test_evidence.txt

# Submit audit
curl -X POST http://172.206.67.83:5678/webhook/audit/submit \
  -F 'questions=[{"q_id":"data_arch_q1","files":["test_evidence.txt"]}]' \
  -F 'test_evidence.txt=@test_evidence.txt' \
  -F 'domain=Data Architecture'

# Expected response (202):
# {
#   "sessionId": "abc-123-...",
#   "status": "queued",
#   ...
# }

# Save session ID
SESSION_ID="<paste_session_id_here>"

# Poll status (repeat every 3-5 seconds):
curl http://172.206.67.83:5678/webhook/audit/status/$SESSION_ID

# Wait for status = "completed"

# Get results:
curl http://172.206.67.83:5678/webhook/audit/results/$SESSION_ID
```

**Test 2: Multi-Question Audit**

```bash
# Submit 2 questions, 3 files:
curl -X POST http://172.206.67.83:5678/webhook/audit/submit \
  -F 'questions=[{"q_id":"privacy_q1","files":["file1.txt","file2.txt"]},{"q_id":"privacy_q2","files":["file3.txt"]}]' \
  -F 'file1.txt=@test1.txt' \
  -F 'file2.txt=@test2.txt' \
  -F 'file3.txt=@test3.txt' \
  -F 'domain=Privacy'

# Monitor via queue script:
./scripts/monitor_queue.sh --watch
```

**Test 3: Large File (100MB+)**

```bash
# Create large test file:
dd if=/dev/urandom of=large_file.bin bs=1M count=100

# Submit:
curl -X POST http://172.206.67.83:5678/webhook/audit/submit \
  -F 'questions=[{"q_id":"security_q1","files":["large_file.bin"]}]' \
  -F 'large_file.bin=@large_file.bin'

# Monitor disk usage:
./scripts/monitor_queue.sh --cleanup
```

### Step 7: Configure Queue Monitoring Cron (Optional)

```bash
# Add to crontab for automated cleanup:
crontab -e

# Add line:
0 2 * * * /home/azureuser/n8n-poc-compliance/scripts/monitor_queue.sh --cleanup >> /var/log/compliance_cleanup.log 2>&1

# Runs daily at 2 AM
```

---

## Verification Checklist

### ✅ Database

```bash
# Check schema changes applied:
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE 'audit%';
"
# Should NOT include: file_registry
# Should include: audit_sessions, audit_logs, audit_evidence, audit_questions

# Check unique constraint:
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT constraint_name FROM information_schema.table_constraints 
WHERE table_name = 'audit_evidence' AND constraint_type = 'UNIQUE';
"
# Should show: unique_evidence_per_session
```

### ✅ Redis

```bash
# Check Redis is accessible:
docker exec compliance-redis redis-cli PING
# Expected: PONG

# Check queue exists (should be empty initially):
docker exec compliance-redis redis-cli LLEN compliance:jobs:pending
# Expected: (integer) 0

# Check Redis persistence:
docker exec compliance-redis redis-cli INFO persistence | grep aof_enabled
# Expected: aof_enabled:1
```

### ✅ Workflows

```bash
# Check all 4 workflows are active in n8n UI:
# - Workflow C1: Audit Entry (webhook active)
# - Workflow C2: Audit Worker (cron running)
# - Workflow C3: Status Polling (webhook active)
# - Workflow C4: Results Retrieval (webhook active)

# Test webhook endpoints:
curl -I http://172.206.67.83:5678/webhook/audit/submit
# Expected: 400 or 405 (not 404)

curl http://172.206.67.83:5678/webhook/audit/status/test
# Expected: 404 (session not found) - confirms endpoint works
```

### ✅ Monitoring

```bash
# Run queue monitor:
./scripts/monitor_queue.sh

# Expected output:
# - All containers: healthy or running
# - Pending Jobs: 0
# - Failed Jobs: 0
# - Session Statistics: (shows 24h activity)
```

---

## Rollback Procedure (If Needed)

### If Issues Occur

```bash
# Stop new workflows:
# In n8n UI, deactivate workflows C1, C2, C3, C4

# Restore old workflow:
# Re-activate old "Workflow C: Audit Orchestrator (All-in-One)"

# Restore database (if needed):
docker exec -i compliance-db psql -U n8n -d compliance_db < backup_$(date +%Y%m%d).sql

# Remove Redis (if needed):
docker-compose -f docker-compose.prod.yml stop redis
docker-compose -f docker-compose.prod.yml rm -f redis

# Restore docker-compose:
cp docker-compose.prod.yml.backup docker-compose.prod.yml
```

---

## Performance Tuning

### Adjust Worker Poll Frequency

**Default:** Every 10 seconds

**For Higher Load:**
```json
// In Workflow C2, edit Cron trigger node:
"interval": [{"field": "seconds", "secondsInterval": 5}]  // Poll every 5s
```

**For Lower Load:**
```json
"interval": [{"field": "seconds", "secondsInterval": 30}]  // Poll every 30s
```

### Adjust File Size Limits

**Current:** 500MB total

**To Increase:**

Edit `workflow-c1-audit-entry.json`:
```javascript
// In "Parse & Validate Input" node:
if (totalSize > 1000 * 1024 * 1024) {  // Change to 1GB
```

**To Decrease:**
```javascript
if (totalSize > 200 * 1024 * 1024) {  // Change to 200MB
```

### Redis Memory Limit

**Current:** 512MB (in docker-compose.prod.yml)

**To Increase:**
```yaml
redis:
  command: redis-server --appendonly yes --maxmemory 1024mb --maxmemory-policy allkeys-lru
```

---

## Monitoring & Maintenance

### Daily Checks

```bash
# Run monitoring script:
./scripts/monitor_queue.sh

# Check for:
# - Failed jobs > 0 (investigate failures)
# - Pending jobs > 10 (possible worker issue)
# - Temp file size > 10GB (cleanup needed)
```

### Weekly Checks

```bash
# Check database size:
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT pg_size_pretty(pg_database_size('compliance_db'));
"

# Check old sessions:
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT COUNT(*)FROM audit_sessions WHERE completed_at < NOW() - INTERVAL '30 days';
"

# Clean up old sessions (if needed):
docker exec compliance-db psql -U n8n -d compliance_db -c "
DELETE FROM audit_sessions WHERE completed_at < NOW() - INTERVAL '90 days';
"
```

### Logs to Monitor

```bash
# n8n execution logs:
docker logs -f compliance-n8n --tail 100

# Redis logs:
docker logs -f compliance-redis --tail 50

# Database logs:
docker logs -f compliance-db --tail 50

# Worker-specific logs (Workflow C2 executions):
# View in n8n UI: Executions → Filter by "Workflow C2"
```

---

## Troubleshooting

### Issue: Jobs Not Processing

**Symptoms:** Status stuck at "queued", queue depth increasing

**Checks:**
```bash
# Is worker workflow active?
# n8n UI → Workflows → C2 Audit Worker → Check toggle is ON

# Is worker executing?
docker logs compliance-n8n --tail 50 | grep "Cron: Every 10s"
# Should show executions every 10 seconds

# Check Redis connectivity:
docker exec compliance-n8n nc -zv redis 6379
# Expected: succeeded
```

**Fix:**
```bash
# Restart n8n:
docker restart compliance-n8n

# Check workflow C2 is activated after restart
```

### Issue: Evidence Not Found

**Symptoms:** "No evidence found for question" errors

**Checks:**
```bash
# Check session directory exists:
ls -la /tmp/n8n_processing/sessions/

# Check database:
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT COUNT(*) FROM audit_evidence WHERE session_id = '<SESSION_ID>';
"
```

**Fix:**
- Evidence deleted prematurely (check cleanup timing)
- File extraction failed (check Workflow A logs)

### Issue: High Memory Usage

**Symptoms:** Docker containers being OOM killed

**Checks:**
```bash
# Check memory usage:
docker stats --no-stream

# Check specific services:
docker stats compliance-ollama --no-stream
# Ollama typically uses 4-6GB during inference
```

**Fix:**
- Reduce concurrent processing (slow down worker poll)
- Add Docker memory limits (see docker-compose adjustments)
- Reduce evidence size limits

---

## Next Steps

### Phase 1: Testing (Current)

- [ ] Deploy to development environment
- [ ] Run end-to-end tests with real documents
- [ ] Load test with 10+ concurrent audits
- [ ] Verify transparency guide accuracy
- [ ] Frontend integration testing

### Phase 2: Optimization (Future)

- [ ] Add batch processing for similar questions
- [ ] Implement async Workflow A calls (parallel extraction)
- [ ] Add Redis cluster for high availability
- [ ] Implement evidence caching across sessions
- [ ] Add Grafana dashboard for monitoring

### Phase 3: Production (Future)

- [ ] Setup SSL/TLS for all endpoints
- [ ] Configure proper authentication (OAuth2/JWT)
- [ ] Add rate limiting per client
- [ ] Setup backup/restore automation
- [ ] Configure log aggregation (ELK stack)

---

## Files Created/Modified

### New Files

```
workflows/
  ├── workflow-c1-audit-entry.json          (NEW)
  ├── workflow-c2-audit-worker.json         (NEW)
  ├── workflow-c3-status-poll.json          (NEW)
  └── workflow-c4-results-retrieval.json    (NEW)

docs/
  ├── AUDIT-TRANSPARENCY-GUIDE.md           (NEW)
  └── FRONTEND-API-GUIDE.md                 (NEW)

scripts/
  └── monitor_queue.sh                      (NEW)

migrations/
  └── 001_cleanup_and_enhance.sql           (NEW)
```

### Modified Files

```
docker-compose.prod.yml                     (MODIFIED - added Redis)
workflows/workflow-c-audit-orchestrator.json (REPLACED by C1-C4)
```

---

## Contact & Support

**Documentation:**
- Transparency Guide: `docs/AUDIT-TRANSPARENCY-GUIDE.md`
- API Guide: `docs/FRONTEND-API-GUIDE.md`
- Workflow Details: `workflows/WORKFLOW-GUIDE.md`

**Logs:**
```bash
docker logs compliance-n8n        # Workflow execution
docker logs compliance-redis      # Queue operations
docker logs compliance-db         # Database queries
```

**Monitoring:**
```bash
./scripts/monitor_queue.sh --watch    # Live monitoring
./scripts/monitor_queue.sh --failed   # Check failures
```

**Database Queries:**
```bash
# Active sessions:
docker exec compliance-db psql -U n8n -d compliance_db -c \
  "SELECT * FROM audit_sessions WHERE status != 'completed' ORDER BY started_at DESC;"

# Recent evaluations:
docker exec compliance-db psql -U n8n -d compliance_db -c \
  "SELECT session_id, q_id, ai_response->>'score' as score, created_at 
   FROM audit_logs 
   WHERE step_name = 'completed' 
   ORDER BY created_at DESC LIMIT 10;"
```

---

**Deployment Status:** ✅ Ready for Testing  
**Last Updated:** February 10, 2026  
**Version:** 2.0.0
