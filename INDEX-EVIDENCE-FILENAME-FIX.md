# Evidence Summary Filename Fix - Documentation Index

## Quick Links

### For Deployment
- **Quick Reference**: `QUICK-FIX-REFERENCE.md` - Fast deployment guide
- **Deployment Checklist**: `DEPLOYMENT-CHECKLIST.md` - Step-by-step deployment

### For Understanding
- **Summary**: `EVIDENCE-FILENAME-FIX-SUMMARY.md` - Executive summary
- **Visual Diagram**: `docs/FILENAME-FIX-DIAGRAM.md` - Visual explanation of the fix
- **Session Summary**: `SESSION-SUMMARY.md` - Complete session overview

### For Technical Details
- **Complete Fix Documentation**: `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md` - Full technical details
- **Root Cause Analysis**: See "Root Cause Analysis" section in complete documentation

### For Using Log Exporter
- **Quick Start**: `docs/LOG-EXPORTER-QUICK-START.md` - 5-minute tutorial
- **Complete Guide**: `docs/HOW-TO-USE-LOG-EXPORTER.md` - Full documentation with examples
- **Script README**: `scripts/README-export-logs.md` - Script documentation

## Problem Statement

The `evidence_summary` field was showing temporary file paths instead of original filenames:

**Before:**
```
Evidence files reviewed: /tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx
```

**After:**
```
Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx
```

## Files Modified

### Workflows
- `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
- `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`

### Scripts Created
- `temp-assets/fix_c1_aggregate_files.py` - Apply fix to Workflow C1
- `temp-assets/fix_c2_use_original_filenames.py` - Apply fix to Workflow C2
- `temp-assets/validate_filename_fix.py` - Validate fixes
- `temp-assets/parse_execution_log.py` - Debug tool
- `temp-assets/check_c1_webhook_data.py` - Debug tool

## Documentation Structure

```
.
├── QUICK-FIX-REFERENCE.md                    # Start here for deployment
├── EVIDENCE-FILENAME-FIX-SUMMARY.md          # Executive summary
├── SESSION-SUMMARY.md                        # Complete session overview
├── DEPLOYMENT-CHECKLIST.md                   # Deployment steps
├── INDEX-EVIDENCE-FILENAME-FIX.md            # This file
│
├── docs/
│   ├── EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md  # Complete technical details
│   ├── FILENAME-FIX-DIAGRAM.md                     # Visual explanation
│   ├── HOW-TO-USE-LOG-EXPORTER.md                  # Log exporter guide
│   └── LOG-EXPORTER-QUICK-START.md                 # Log exporter tutorial
│
├── scripts/
│   ├── export_n8n_logs.py                    # Log exporter tool
│   └── README-export-logs.md                 # Script documentation
│
└── temp-assets/
    ├── fix_c1_aggregate_files.py             # Fix script for C1
    ├── fix_c2_use_original_filenames.py      # Fix script for C2
    ├── validate_filename_fix.py              # Validation script
    ├── parse_execution_log.py                # Debug tool
    └── check_c1_webhook_data.py              # Debug tool
```

## Quick Start

### 1. Understand the Problem
Read: `EVIDENCE-FILENAME-FIX-SUMMARY.md` or `docs/FILENAME-FIX-DIAGRAM.md`

### 2. Deploy the Fix
Follow: `QUICK-FIX-REFERENCE.md`

### 3. Validate
Run: `python3 temp-assets/validate_filename_fix.py`

### 4. Test
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -H "X-API-Key: your-secret-key" \
  -F "domain=6ec7535e-6134-4010-9817-8c0849e8f59b" \
  -F 'questions=[{"question_id":"1daa7d40-a975-4026-b6a9-818b34c2f3c0","files":["null0"]}]' \
  -F "null0=@MyDocument.pdf"
```

Verify `evidence_summary` shows "MyDocument.pdf" not "/tmp/n8n_processing/.../hash.pdf"

## Key Concepts

### The Problem
n8n's "Write Binary File" node overwrites `json.fileName` with the disk path. This is standard behavior.

### The Solution
1. **Workflow C1**: Preserve original filename in `originalFileName` field before it gets overwritten
2. **Workflow C2**: Look up original filenames from `fileMap` using file hash

### The Tools
- **Log Exporter**: Extract execution logs from PostgreSQL for debugging
- **Parser Scripts**: Analyze node outputs to trace data flow
- **Validation Script**: Confirm fixes are correctly applied

## Learning Resources

### For Developers
1. Read `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md` for complete technical details
2. Study `docs/FILENAME-FIX-DIAGRAM.md` for visual understanding
3. Review the fix scripts to see implementation

### For DevOps
1. Read `QUICK-FIX-REFERENCE.md` for deployment
2. Follow `DEPLOYMENT-CHECKLIST.md` for step-by-step process
3. Use `temp-assets/validate_filename_fix.py` to verify

### For Debugging
1. Read `docs/LOG-EXPORTER-QUICK-START.md` for quick tutorial
2. Study `docs/HOW-TO-USE-LOG-EXPORTER.md` for complete guide
3. Use `scripts/export_n8n_logs.py` to extract execution logs

## Related Work

### Previous Session: Master Cache Optimization
- **Date**: 2026-02-26
- **Feature**: Cross-session master cache for 99% performance improvement
- **Documentation**: `docs/MASTER-CACHE-IMPLEMENTATION-SUMMARY.md`

## Support

### Common Issues

**Issue**: Validation fails
- **Solution**: Check that workflows were re-imported correctly

**Issue**: Still seeing temp paths
- **Solution**: Ensure you're testing with a NEW audit submission (not cached results)

**Issue**: Can't connect to database
- **Solution**: Check database credentials in environment variables

### Getting Help

1. Check the relevant documentation file from this index
2. Review the visual diagram: `docs/FILENAME-FIX-DIAGRAM.md`
3. Run validation: `python3 temp-assets/validate_filename_fix.py`
4. Export logs for debugging: `python3 scripts/export_n8n_logs.py <execution_id>`

## Next Steps

1. ✅ Fix implemented and validated
2. ⏳ Deploy to n8n (re-import workflows)
3. ⏳ Test with real audit submission
4. ⏳ Monitor for issues
5. ⏳ Update team documentation

## Changelog

### 2026-02-26
- Initial implementation of evidence summary filename fix
- Created comprehensive documentation
- Developed log exporter usage guides
- Validated all changes
