# Evidence Summary Filename Fix - Summary

## Problem Statement
The `evidence_summary` field in audit evaluation results was displaying temporary file paths instead of the original filenames submitted via the API.

**Before:**
```json
"evidence_summary": "Evidence files reviewed: /tmp/n8n_processing/822d2327-b1c6-4d7e-8bff-eeea4f89717f/fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx, ..."
```

**After:**
```json
"evidence_summary": "Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx, NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
```

## Root Cause
The n8n "Write Binary File" node overwrites the `json.fileName` field with the disk path where it writes the file. This is standard n8n behavior. The "Aggregate Files" node in Workflow C1 was reading this overwritten value and storing it in the `fileMap`, which then propagated through to Workflow C2 and into the final `evidence_summary`.

## Solution Overview

### Workflow C1 Changes
1. **Prepare File Writes** node: Added `originalFileName` field to preserve the API filename before it gets overwritten
2. **Aggregate Files** node: Use `originalFileName` instead of `fileName` when building the `fileMap`

### Workflow C2 Changes
1. **Consolidate Evidence Text** node: Look up original filenames from `fileMap` using file hash
2. **Parse AI Response** node: Use `sourceFiles` from `promptData` to build evidence summary with original filenames

## Files Modified
- `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
- `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`

## Deployment
1. Re-import Workflow C1 in n8n UI
2. Re-import Workflow C2 in n8n UI
3. Test with a new audit submission
4. Verify `evidence_summary` contains original filenames

## Documentation
- **Complete Details:** `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md`
- **Deployment Steps:** `DEPLOYMENT-CHECKLIST.md`

## Scripts Used for Debugging
- `scripts/export_n8n_logs.py` - Export execution logs from PostgreSQL
- `temp-assets/parse_execution_log.py` - Trace data flow through workflow nodes
- `temp-assets/check_c1_webhook_data.py` - Examine Workflow C1 execution data
- `temp-assets/fix_c1_aggregate_files.py` - Apply fix to Workflow C1
- `temp-assets/fix_c2_use_original_filenames.py` - Apply fix to Workflow C2

## Impact
- Users will now see meaningful filenames in audit results
- Evidence summary is more readable and useful for compliance reporting
- No breaking changes to API or data structures
- Backward compatible (falls back to `fileName` if `originalFileName` not present)
