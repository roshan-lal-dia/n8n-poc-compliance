# Session Summary - Evidence Summary Filename Fix

## Date
2026-02-26

## Problem
The `evidence_summary` field in audit evaluation results was displaying temporary file paths instead of the original filenames submitted via the API.

**Example of the issue:**
```json
{
  "evidence_summary": "Evidence files reviewed: /tmp/n8n_processing/822d2327-b1c6-4d7e-8bff-eeea4f89717f/fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx, /tmp/n8n_processing/822d2327-b1c6-4d7e-8bff-eeea4f89717f/0fed1cddfc600ffb6ad6f9d21cb1ffd3c8358e5d9f520c5339ab8cc4c2fa6b10.xlsx"
}
```

**Expected:**
```json
{
  "evidence_summary": "Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx, NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
}
```

## Investigation Process

### 1. Used Log Exporter Tool
```bash
# Exported execution logs from PostgreSQL
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json
python3 scripts/export_n8n_logs.py 4986 --format json --output execution_c1_4986.json
```

### 2. Created Parser Scripts
- `temp-assets/parse_execution_log.py` - Trace data flow through workflow nodes
- `temp-assets/check_c1_webhook_data.py` - Examine Workflow C1 execution data

### 3. Traced Data Flow
Analyzed each node's output to find where original filenames were lost:
- **Webhook**: Receives original filenames ✓
- **Parse & Validate Input**: Preserves original filenames ✓
- **Prepare File Writes**: Has original filenames ✓
- **Write Binary File**: **Overwrites `fileName` with disk path** ❌
- **Aggregate Files**: Reads overwritten `fileName` ❌
- **Workflow C2**: Uses temp paths from `fileMap` ❌

## Root Cause
The n8n "Write Binary File" node overwrites the `json.fileName` field with the disk path where it writes the file. This is standard n8n behavior. The "Aggregate Files" node was reading this overwritten value and storing it in the `fileMap`, which then propagated to Workflow C2.

## Solution Implemented

### Workflow C1 Changes
**File:** `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`

1. **Prepare File Writes** node:
   - Added `originalFileName` field to preserve API filename before it gets overwritten
   
2. **Aggregate Files** node:
   - Use `originalFileName` instead of `fileName` when building `fileMap`

### Workflow C2 Changes
**File:** `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`

1. **Consolidate Evidence Text** node:
   - Look up original filenames from `fileMap` using file hash
   
2. **Parse AI Response** node:
   - Use `sourceFiles` from `promptData` to build evidence summary with original filenames

## Scripts Created

### Fix Scripts
- `temp-assets/fix_c1_aggregate_files.py` - Applied fix to Workflow C1
- `temp-assets/fix_c2_use_original_filenames.py` - Applied fix to Workflow C2

### Debug Scripts
- `temp-assets/parse_execution_log.py` - Parse and display node outputs
- `temp-assets/check_c1_webhook_data.py` - Examine Workflow C1 data flow
- `temp-assets/trace_filename_issue.py` - Trace filename transformations

### Validation Script
- `temp-assets/validate_filename_fix.py` - Validate both workflows have correct fixes

## Documentation Created

### Main Documentation
- `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md` - Complete technical details
- `EVIDENCE-FILENAME-FIX-SUMMARY.md` - Executive summary
- `QUICK-FIX-REFERENCE.md` - Quick deployment guide

### Log Exporter Documentation
- `docs/HOW-TO-USE-LOG-EXPORTER.md` - Complete guide with examples
- `docs/LOG-EXPORTER-QUICK-START.md` - 5-minute tutorial
- Updated `scripts/README-export-logs.md` - Added quick start section

### Updated Files
- `DEPLOYMENT-CHECKLIST.md` - Added evidence summary fix section

## Validation Results

```bash
$ python3 temp-assets/validate_filename_fix.py

================================================================================
✅ ALL VALIDATIONS PASSED
================================================================================

Both workflows have been correctly updated to use original filenames.
```

## Deployment Steps

1. **Re-import Workflow C1:**
   - Open n8n UI
   - Navigate to "Workflow C1: Audit Entry (Job Submission)"
   - Import from `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
   - Save

2. **Re-import Workflow C2:**
   - Open "Workflow C2: Audit Worker (Background Processor)"
   - Import from `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`
   - Save

3. **Test:**
   ```bash
   curl -X POST http://localhost:5678/webhook/audit/submit \
     -H "X-API-Key: your-secret-key" \
     -F "domain=6ec7535e-6134-4010-9817-8c0849e8f59b" \
     -F 'questions=[{"question_id":"1daa7d40-a975-4026-b6a9-818b34c2f3c0","files":["null0","null1"]}]' \
     -F "null0=@NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" \
     -F "null1=@NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
   ```

4. **Verify:**
   - Check results endpoint
   - Confirm `evidence_summary` shows original filenames

## Key Learnings

1. **n8n Behavior**: The "Write Binary File" node overwrites `json.fileName` with the disk path
2. **Data Preservation**: Need to explicitly preserve original data in separate fields before nodes that modify it
3. **Debugging with Logs**: Execution logs from PostgreSQL are invaluable for tracing data flow issues
4. **Hash Lookup**: Using file hashes to look up original filenames from `fileMap` is reliable
5. **Log Exporter Tool**: Essential for debugging complex workflow issues

## Impact

- Users now see meaningful filenames in audit results
- Evidence summary is more readable and useful for compliance reporting
- No breaking changes to API or data structures
- Backward compatible (falls back to `fileName` if `originalFileName` not present)

## Files Modified

### Workflows
- `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
- `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`

### Documentation
- `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md` (new)
- `docs/HOW-TO-USE-LOG-EXPORTER.md` (new)
- `docs/LOG-EXPORTER-QUICK-START.md` (new)
- `EVIDENCE-FILENAME-FIX-SUMMARY.md` (new)
- `QUICK-FIX-REFERENCE.md` (new)
- `SESSION-SUMMARY.md` (new)
- `DEPLOYMENT-CHECKLIST.md` (updated)
- `scripts/README-export-logs.md` (updated)

### Scripts
- `temp-assets/fix_c1_aggregate_files.py` (new)
- `temp-assets/fix_c2_use_original_filenames.py` (new)
- `temp-assets/parse_execution_log.py` (new)
- `temp-assets/check_c1_webhook_data.py` (new)
- `temp-assets/trace_filename_issue.py` (new)
- `temp-assets/validate_filename_fix.py` (new)

## Next Steps

1. Deploy the workflow changes to n8n
2. Test with a real audit submission
3. Monitor for any issues
4. Update team on the fix

## Related Work

- **Previous Session**: Master Cache Optimization (2026-02-26)
  - Implemented cross-session caching for 99% performance improvement
  - Documentation: `docs/MASTER-CACHE-IMPLEMENTATION-SUMMARY.md`
