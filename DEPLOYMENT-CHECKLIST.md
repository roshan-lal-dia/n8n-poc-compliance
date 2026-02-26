# Workflow C2 Master Cache - Deployment Checklist

**Date:** 2026-02-26  
**Feature:** Master Cache Optimization  
**Status:** Ready for Deployment

---

## Pre-Deployment Validation ✅

- [x] Workflow file validated (35 nodes, 34 connections)
- [x] No duplicate nodes
- [x] All connections reference valid nodes
- [x] Cron trigger set to 10 seconds
- [x] Master cache query has UNION ALL fallback
- [x] Cache bypass path verified
- [x] Evidence cleanup removed
- [x] All critical nodes present
- [x] No orphaned nodes

---

## Deployment Steps

### Step 1: Backup Current Workflow
```bash
# Create backup of current workflow
docker exec compliance-n8n n8n export:workflow --id=<workflow-c2-id> --output=/tmp/workflow-c2-backup.json

# Or manually export via UI
# n8n UI → Workflows → Workflow C2 → ... → Download
```

**Status:** [ ] Complete

---

### Step 2: Import Updated Workflow
```bash
# Option A: Via n8n UI (Recommended)
# 1. Open n8n: http://localhost:5678
# 2. Go to: Workflows → Import from File
# 3. Select: workflows/unifi-npc-compliance/workflow-c2-audit-worker.json
# 4. Confirm import (will replace existing)

# Option B: Via CLI
docker cp workflows/unifi-npc-compliance/workflow-c2-audit-worker.json compliance-n8n:/tmp/
docker exec compliance-n8n n8n import:workflow --input=/tmp/workflow-c2-audit-worker.json
```

**Status:** [ ] Complete

---

### Step 3: Verify Workflow Configuration
```bash
# Check in n8n UI:
# 1. Workflow is activated (toggle in top-right)
# 2. Cron trigger shows "Every 10 seconds"
# 3. All nodes are connected (no red error indicators)
# 4. Credentials are properly linked (postgres, redis)
```

**Checklist:**
- [ ] Workflow activated
- [ ] Cron trigger: 10 seconds
- [ ] No connection errors
- [ ] Postgres credentials linked
- [ ] Redis credentials linked

---

### Step 4: Test Cache Miss (First Submission)
```bash
# Submit a test audit
curl -X POST http://localhost:5678/webhook/audit/submit \
  -F "domain=a14d13d9-81eb-46da-ab4f-8476c6469dd3" \
  -F "questions[0][question_id]=<test_question_uuid>" \
  -F "questions[0][evidence_files][0]=@test_document.pdf" \
  -H "X-API-Key: ${WEBHOOK_API_KEY}"

# Expected: Full workflow execution (12-40 seconds)
```

**Verification:**
- [ ] Request accepted (202 response)
- [ ] Session created in `audit_sessions`
- [ ] Evidence stored in `audit_evidence`
- [ ] Evaluation logged in `audit_logs`
- [ ] No "MASTER CACHE HIT" in logs

**Session ID:** ___________________________

---

### Step 5: Test Cache Hit (Repeat Submission)
```bash
# Submit EXACT same request again
curl -X POST http://localhost:5678/webhook/audit/submit \
  -F "domain=a14d13d9-81eb-46da-ab4f-8476c6469dd3" \
  -F "questions[0][question_id]=<test_question_uuid>" \
  -F "questions[0][evidence_files][0]=@test_document.pdf" \
  -H "X-API-Key: ${WEBHOOK_API_KEY}"

# Expected: Near-instant completion (~100ms)
```

**Verification:**
- [ ] Request accepted (202 response)
- [ ] Completed in < 1 second
- [ ] "MASTER CACHE HIT" in n8n logs
- [ ] Identical evaluation scores
- [ ] No new `audit_evidence` rows

**Session ID:** ___________________________

---

### Step 6: Verify Cache Hit in Database
```sql
-- Check that cache hit was logged
SELECT 
  session_id,
  question_id,
  ai_response->>'fromMasterCache' as is_cached,
  ai_response->>'cachedFromSession' as original_session,
  ai_response->'evaluation'->>'score' as score,
  created_at
FROM audit_logs
WHERE session_id = '<session_id_from_step_5>'
  AND step_name = 'completed';
```

**Expected Results:**
- [ ] `is_cached` = "true"
- [ ] `original_session` = session ID from Step 4
- [ ] `score` matches Step 4 evaluation

---

### Step 7: Monitor Worker Activity
```bash
# Check worker is polling queue
./scripts/monitor_queue.sh --watch

# Or check logs
docker logs compliance-n8n --tail 50 -f
```

**Verification:**
- [ ] Worker polling every 10 seconds
- [ ] No errors in logs
- [ ] Queue processing normally

---

### Step 8: Check Evidence Persistence
```sql
-- Verify evidence from Step 4 still exists
SELECT 
  session_id,
  question_id,
  filename,
  file_hash,
  created_at
FROM audit_evidence
WHERE session_id = '<session_id_from_step_4>';
```

**Expected:**
- [ ] Evidence rows still exist (not deleted)
- [ ] File hashes match uploaded files

---

## Post-Deployment Monitoring

### Day 1: Initial Monitoring
```bash
# Check cache hit rate
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT 
  COUNT(*) FILTER (WHERE ai_response::text LIKE '%fromMasterCache%') as cache_hits,
  COUNT(*) as total_evaluations,
  ROUND(100.0 * COUNT(*) FILTER (WHERE ai_response::text LIKE '%fromMasterCache%') / COUNT(*), 2) as hit_rate_pct
FROM audit_logs
WHERE step_name = 'completed'
  AND created_at > NOW() - INTERVAL '24 hours';
"
```

**Metrics:**
- Cache hits: _______
- Total evaluations: _______
- Hit rate: _______%

---

### Week 1: Performance Review
```bash
# Check evidence table size
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT 
  COUNT(*) as total_rows,
  COUNT(DISTINCT session_id) as unique_sessions,
  COUNT(DISTINCT file_hash) as unique_files,
  pg_size_pretty(pg_total_relation_size('audit_evidence')) as table_size
FROM audit_evidence;
"
```

**Metrics:**
- Total evidence rows: _______
- Unique files: _______
- Table size: _______

---

### Month 1: Cleanup Planning
```bash
# Check oldest evidence
docker exec compliance-db psql -U n8n -d compliance_db -c "
SELECT 
  MIN(created_at) as oldest_evidence,
  MAX(created_at) as newest_evidence,
  COUNT(*) as total_rows
FROM audit_evidence;
"
```

**Decision:**
- [ ] No cleanup needed yet
- [ ] Schedule cleanup for evidence > 90 days
- [ ] Implement automated cleanup job

---

## Rollback Procedure (If Needed)

### Step 1: Restore Backup
```bash
# Via n8n UI
# 1. Workflows → Import from File
# 2. Select backup file
# 3. Confirm import

# Via CLI
docker exec compliance-n8n n8n import:workflow --input=/tmp/workflow-c2-backup.json
```

### Step 2: Verify Rollback
- [ ] Old workflow imported
- [ ] Workflow activated
- [ ] Test submission works

### Step 3: Optional Cleanup
```sql
-- Remove evidence from test period
DELETE FROM audit_evidence 
WHERE created_at > '<deployment_timestamp>';
```

---

## Known Issues & Mitigations

### Issue 1: Evidence Table Growth
**Symptom:** `audit_evidence` table grows continuously  
**Mitigation:** Implement periodic cleanup (see Month 1 checklist)  
**Status:** [ ] Monitoring [ ] Cleanup scheduled

### Issue 2: Cache Invalidation
**Symptom:** Cached evaluations may become stale if standards are updated  
**Mitigation:** Manual cleanup after standard updates  
**Status:** [ ] Documented [ ] Process established

---

## Success Criteria

- [x] Workflow imports without errors
- [ ] Cache miss path works (first submission)
- [ ] Cache hit path works (repeat submission)
- [ ] Cache hit rate > 0% after 24 hours
- [ ] No workflow execution errors
- [ ] Evidence persists across sessions
- [ ] Performance improvement visible (< 1s for cache hits)

---

## Sign-Off

**Deployed By:** ___________________________  
**Date:** ___________________________  
**Time:** ___________________________  

**Verified By:** ___________________________  
**Date:** ___________________________  

**Notes:**
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________

---

## Support Contacts

**Technical Issues:**
- Check logs: `docker logs compliance-n8n --tail 100`
- Monitor queue: `./scripts/monitor_queue.sh`
- Database queries: See `docs/WORKFLOW-C2-CHANGES-SUMMARY.md`

**Documentation:**
- `docs/MASTER-CACHE-OPTIMIZATION.md` - Technical details
- `docs/WORKFLOW-C2-CHANGES-SUMMARY.md` - Changes summary
- `docs/WORKFLOW-C2-DEEP-DIVE.md` - Original workflow documentation

---

**Status:** Ready for Deployment ✅


---

## Update 2026-02-26: Evidence Summary Original Filenames Fix

### Issue
The `evidence_summary` field was showing temporary file paths instead of original filenames from the API request.

### Changes Made
1. **Workflow C1** (`workflow-c1-audit-entry.json`):
   - "Prepare File Writes" node: Added `originalFileName` field to preserve API filename
   - "Aggregate Files" node: Use `originalFileName` instead of `fileName` (which gets overwritten)

2. **Workflow C2** (`workflow-c2-audit-worker.json`):
   - "Consolidate Evidence Text" node: Look up original filenames from `fileMap` using hash
   - "Parse AI Response" node: Use `sourceFiles` from `promptData` for evidence summary

### Deployment Steps
1. Re-import Workflow C1 from `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
2. Re-import Workflow C2 from `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`
3. Test with a new audit submission
4. Verify `evidence_summary` shows original filenames

### Documentation
See `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md` for complete details.

### Testing
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -H "X-API-Key: your-secret-key" \
  -F "domain=6ec7535e-6134-4010-9817-8c0849e8f59b" \
  -F 'questions=[{"question_id":"1daa7d40-a975-4026-b6a9-818b34c2f3c0","files":["null0","null1"]}]' \
  -F "null0=@NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" \
  -F "null1=@NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
```

Expected result: `evidence_summary` should show original filenames, not temp paths.
