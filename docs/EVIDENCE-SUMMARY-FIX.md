# Evidence Summary Fix

**Date:** 2026-02-26  
**Issue:** AI sometimes hallucinates filenames in `evidence_summary` field  
**Solution:** Override with actual uploaded filenames  
**Status:** ✅ Fixed

---

## Problem

The AI was instructed to populate the `evidence_summary` field with references to the evidence files. However, it sometimes:
- Hallucinated filenames that don't exist
- Referenced internal system paths
- Omitted files that were actually reviewed
- Made up file extensions

**Example of bad AI output:**
```json
{
  "evidence_summary": "Based on SecurityPolicy_final_v2.pdf and /tmp/n8n_processing/abc123/document.docx..."
}
```

**Actual files uploaded:**
- `SecurityPolicy.pdf`
- `ComplianceReport.xlsx`

---

## Solution

Override the `evidence_summary` field with the actual list of uploaded filenames from the current submission.

### Implementation

**Parse AI Response Node:**
```javascript
// Override evidence_summary with actual uploaded filenames
const actualFiles = promptData.sourceFiles || [];
if (actualFiles.length > 0) {
  const fileList = actualFiles.map(f => f.filename).join(', ');
  evaluation.evidence_summary = `Evidence files reviewed: ${fileList}`;
}
```

**Format Cached Response Node:**
```javascript
// Get actual filenames from the current submission
const actualFiles = questionData.evidenceFiles || [];
if (actualFiles.length > 0 && evaluation) {
  const fileList = actualFiles.map(f => {
    const fileData = questionData.fileMap[f.fieldName];
    return fileData ? fileData.fileName : f.fieldName;
  }).join(', ');
  
  evaluation.evidence_summary = `Evidence files reviewed: ${fileList}`;
}
```

---

## Result

**New output format:**
```json
{
  "evidence_summary": "Evidence files reviewed: SecurityPolicy.pdf, ComplianceReport.xlsx"
}
```

**Benefits:**
- ✅ Always accurate - uses actual uploaded filenames
- ✅ No hallucinations - no made-up files
- ✅ Consistent format - same structure every time
- ✅ Reliable - works for both cached and non-cached paths
- ✅ Simple - easy to parse and display

---

## Testing

### Test 1: Single File
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -F "questions=[{\"question_id\":\"<uuid>\",\"files\":[\"test.pdf\"]}]" \
  -F "test.pdf=@/path/to/test.pdf" \
  -F "domain=<domain_uuid>" \
  -H "X-API-Key: ${WEBHOOK_API_KEY}"
```

**Expected evidence_summary:**
```
Evidence files reviewed: test.pdf
```

### Test 2: Multiple Files
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -F "questions=[{\"question_id\":\"<uuid>\",\"files\":[\"doc1.pdf\",\"doc2.xlsx\"]}]" \
  -F "doc1.pdf=@/path/to/doc1.pdf" \
  -F "doc2.xlsx=@/path/to/doc2.xlsx" \
  -F "domain=<domain_uuid>" \
  -H "X-API-Key: ${WEBHOOK_API_KEY}"
```

**Expected evidence_summary:**
```
Evidence files reviewed: doc1.pdf, doc2.xlsx
```

### Test 3: Cached Evaluation
Submit the same request twice - the second submission should also have correct filenames in evidence_summary.

---

## Database Query

Check evidence_summary in completed evaluations:

```sql
SELECT 
  session_id,
  question_id,
  ai_response->>'evidence_summary' as evidence_summary,
  created_at
FROM audit_logs
WHERE step_name = 'completed'
  AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Files Modified

- `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`
  - Updated `Parse AI Response` node
  - Updated `Format Cached Response` node

---

## Notes

- The AI's original `evidence_summary` content is discarded
- We keep the AI's `findings`, `gaps`, and `recommendations` fields unchanged
- This only affects the `evidence_summary` field
- Works for both cache hit and cache miss scenarios

---

**Status:** ✅ Implemented and Ready for Testing  
**Impact:** Improves reliability of evidence tracking in audit results
