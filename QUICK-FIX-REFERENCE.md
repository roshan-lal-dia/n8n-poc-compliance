# Quick Fix Reference - Evidence Summary Original Filenames

## What Was Fixed
The `evidence_summary` field now shows original filenames from the API instead of temporary file paths.

## Files Changed
- `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
- `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`

## How to Deploy

### 1. Re-import Workflow C1
```
1. Open n8n UI (http://localhost:5678)
2. Navigate to Workflows
3. Open "Workflow C1: Audit Entry (Job Submission)"
4. Click "..." menu → "Import from File"
5. Select: workflows/unifi-npc-compliance/workflow-c1-audit-entry.json
6. Click "Save"
```

### 2. Re-import Workflow C2
```
1. Open "Workflow C2: Audit Worker (Background Processor)"
2. Click "..." menu → "Import from File"
3. Select: workflows/unifi-npc-compliance/workflow-c2-audit-worker.json
4. Click "Save"
```

### 3. Test
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -H "X-API-Key: your-secret-key" \
  -F "domain=6ec7535e-6134-4010-9817-8c0849e8f59b" \
  -F 'questions=[{"question_id":"1daa7d40-a975-4026-b6a9-818b34c2f3c0","files":["null0","null1"]}]' \
  -F "null0=@NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" \
  -F "null1=@NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
```

### 4. Verify
Check the results endpoint - `evidence_summary` should show:
```
"Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx, NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
```

NOT:
```
"Evidence files reviewed: /tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx, ..."
```

## Validation
Run the validation script to confirm fixes are in place:
```bash
source venv/bin/activate
python3 temp-assets/validate_filename_fix.py
```

Should output: `✅ ALL VALIDATIONS PASSED`

## Documentation
- **Complete Details:** `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md`
- **Summary:** `EVIDENCE-FILENAME-FIX-SUMMARY.md`
- **Deployment Checklist:** `DEPLOYMENT-CHECKLIST.md`

## Rollback
If issues occur, re-import the backup workflows from before this change.
