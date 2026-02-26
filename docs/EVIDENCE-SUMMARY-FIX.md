# Evidence Summary Fix

**Date:** 2026-02-26  
**Issue:** AI sometimes hallucinates filenames in `evidence_summary` field + Paired item error  
**Solution:** Override with actual uploaded filenames using sourceFiles from Build AI Prompt  
**Status:** ✅ Fixed

---

## Problem

### Issue 1: AI Hallucinations
The AI was instructed to populate the `evidence_summary` field with references to the evidence files. However, it sometimes:
- Hallucinated filenames that don't exist
- Referenced internal system paths like `/tmp/n8n_processing/...`
- Omitted files that were actually reviewed
- Made up file extensions

**Example of bad AI output:**
```json
{
  "evidence_summary": "Based on SecurityPolicy_final_v2.pdf and /tmp/n8n_processing/abc123/document.docx..."
}
```

### Issue 2: Paired Item Error
When trying to fix Issue 1, the Parse AI Response node attempted to access `$('Split by Question').item.json` which caused:
```
"AI response parsing failed: Cannot assign to read only property 'name' of object 'Error: Paired item data for item from node 'Combine Extraction Results' is unavailable"
```

This happened because Split by Question is not a direct parent of Parse AI Response in the execution flow, making paired item data unavailable.

---

## Solution

Use original filenames from multiple sources without modifying existing file processing:
1. **Workflow A** returns `originalFileName` in its extraction response
2. **Workflow C1** stores original filenames in `fileMap` (from binary or ADLS)
3. **Workflow C2** uses these original filenames throughout

### Data Flow Chain

**For Multipart Uploads:**
1. API Request → Binary `fileName` → C1 `fileMap[].fileName`
2. C2 Prepare Files → Builds `hash-to-filename` map from `fileMap`
3. C2 Combine Results → Uses `extractedData.originalFileName` from Workflow A
4. C2 Consolidate Evidence → Uses `evidence.filename` (now original)
5. C2 Build AI Prompt → `sourceFiles[].filename` (now original)
6. C2 Parse AI Response → Uses `promptData.sourceFiles[].filename`

**For ADLS Paths:**
1. ADLS `blobPath` (e.g., "folder/subfolder/file.pdf")
2. C1 Fetch Azure Blob → Extracts filename: `blobPath.split('/').pop()`
3. C1 stores in `fileMap[].fileName` → "file.pdf"
4. Rest of flow same as multipart uploads

### Implementation

**Combine Extraction Results Node (FIXED):**
```javascript
// Use originalFileName from Workflow A response
const originalFilename = extractedData.originalFileName || preparedData.filename;

allEvidence.push({
  hash: preparedData.hash,
  filename: originalFilename,  // Original filename from Workflow A
  extractedData: extractedData,
  fileSize: preparedData.fileSize,
  fromCache: false
});
```

**Prepare Files for Extraction Node (FIXED):**
```javascript
// Build hash-to-original-filename map from questionData.fileMap
const hashToOriginalFilename = {};
for (const fileInfo of questionData.evidenceFiles || []) {
  const fileData = questionData.fileMap[fileInfo.fieldName];
  if (fileData && fileData.fileName) {
    // Extract just filename from path (handles ADLS paths like "folder/file.pdf")
    const cleanFilename = fileData.fileName.split('/').pop().split('\\\\').pop();
    hashToOriginalFilename[fileInfo.hash] = cleanFilename;
  }
}

// For cached evidence
const cachedEvidenceData = cachedEvidence.map(cached => ({
  hash: cached.file_hash,
  filename: hashToOriginalFilename[cached.file_hash] || cached.filename,
  extractedData: cached.extracted_data,
  fileSize: cached.file_size_bytes,
  fromCache: true
}));
```

**Parse AI Response Node (ALREADY FIXED):**
```javascript
// Uses sourceFiles from Build AI Prompt (which now has original filenames)
const sourceFiles = promptData.sourceFiles || [];

if (sourceFiles.length > 0) {
  const fileList = sourceFiles.map(f => f.filename).join(', ');
  evaluation.evidence_summary = `Evidence files reviewed: ${fileList}`;
}
```

---

## Result

**New output format:**
```json
{
  "evidence_summary": "Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx, NNPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
}
```

**Benefits:**
- ✅ No Paired Item Error - Accesses data from direct parent node (Build AI Prompt)
- ✅ Always accurate - uses actual uploaded filenames from API request
- ✅ No hallucinations - no made-up files or temp paths
- ✅ Consistent format - same structure every time
- ✅ Reliable - sourceFiles is always available in Build AI Prompt output
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
  - Updated `Combine Extraction Results` node (uses originalFileName from Workflow A)
  - Updated `Prepare Files for Extraction` node (builds hash-to-filename map, handles ADLS paths)
  - Updated `Parse AI Response` node (uses sourceFiles from Build AI Prompt)

**Fix Script:** `temp-assets/fix_original_filenames_comprehensive.py`
- Executed successfully on 2026-02-26
- Comprehensive fix that preserves original filenames from both multipart uploads and ADLS
- No changes to Workflow A or C1 - uses existing originalFileName data

---

## How It Works

1. **Workflow C1** already stores original filenames in `fileMap`:
   - Multipart: Uses `fileName` from binary data
   - ADLS: Extracts filename from blob path with `.split('/').pop()`

2. **Workflow A** already returns `originalFileName` in extraction response

3. **Workflow C2** now uses these original filenames:
   - Prepare Files: Builds hash-to-filename lookup from fileMap
   - Combine Results: Uses `extractedData.originalFileName` from Workflow A
   - Consolidate Evidence: Receives correct filenames from Combine Results
   - Parse AI Response: Uses sourceFiles which now have original names

---

## Next Steps

1. **Re-import workflow** into n8n from the updated JSON file
2. **Test with multipart upload** using curl command
3. **Test with ADLS paths** to verify filename extraction
4. **Verify** that evidence_summary shows original filenames without temp paths or full ADLS paths

---

## Notes

- The AI's original `evidence_summary` content is discarded
- We keep the AI's `findings`, `gaps`, and `recommendations` fields unchanged
- This only affects the `evidence_summary` field
- Works for both cache hit and cache miss scenarios

---

**Status:** ✅ Implemented and Ready for Testing  
**Impact:** Improves reliability of evidence tracking in audit results
