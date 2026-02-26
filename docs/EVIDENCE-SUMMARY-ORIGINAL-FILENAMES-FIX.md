# Evidence Summary Original Filenames Fix

## Problem
The `evidence_summary` field in audit results was showing temporary file paths instead of original filenames from the API request:

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

## Root Cause Analysis

### Investigation Process
1. Used `scripts/export_n8n_logs.py` to export execution logs from PostgreSQL
2. Created `temp-assets/parse_execution_log.py` to trace data flow through nodes
3. Created `temp-assets/check_c1_webhook_data.py` to examine Workflow C1 data

### Root Cause
The issue occurred in **Workflow C1: Audit Entry** at the "Aggregate Files" node:

1. **Webhook** receives files with original names: `NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx`
2. **Parse & Validate Input** preserves original names in `fileData.fileName`
3. **Prepare File Writes** creates items with `fileName: fileData.fileName` (original name)
4. **Write Binary File** node **overwrites** `json.fileName` with the disk path (n8n standard behavior)
5. **Aggregate Files** reads `row.fileName` which now contains the temp path instead of original name
6. This temp path gets stored in `fileMap` and passed to Workflow C2 via Redis
7. Workflow C2 uses these temp paths in `evidence_summary`

## Solution

### Fix 1: Workflow C1 - Preserve Original Filenames

**File:** `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`

#### Node: "Prepare File Writes"
Added `originalFileName` field that won't be overwritten by the Write Binary File node:

```javascript
items.push({
  json: {
    sessionId,
    domain,
    fieldName,
    fileName: fileData.fileName,
    originalFileName: fileData.fileName,  // NEW: Preserve original - won't be overwritten
    mimeType: fileData.mimeType,
    fileSize: buffer.length,
    hash,
    filePath,
    questions
  },
  binary: {
    data: fileData
  }
});
```

#### Node: "Aggregate Files"
Updated to use `originalFileName` instead of `fileName`:

```javascript
for (const item of items) {
  const row = item.json;
  // Use originalFileName which wasn't overwritten by Write Binary File node
  const originalName = row.originalFileName || row.fileName;
  
  fileMap[row.fieldName] = {
    hash: row.hash,
    fileName: originalName,  // Original filename from API
    fileSize: row.fileSize,
    mimeType: row.mimeType,
    fieldName: row.fieldName,
    filePath: row.filePath  // Temp disk path
  };
}
```

### Fix 2: Workflow C2 - Use Original Filenames

**File:** `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`

#### Node: "Consolidate Evidence Text"
Look up original filenames from `fileMap` using file hash:

```javascript
// Find original filename from fileMap using hash
let originalFileName = null;
for (const [fieldName, fileInfo] of Object.entries(fileMap)) {
  if (fileInfo.hash === fileHash) {
    originalFileName = fileInfo.fileName;  // This is now the original filename from API
    break;
  }
}

if (!originalFileName) {
  originalFileName = data.filename || 'unknown';
}

consolidatedText += `\\n\\n=== File: ${originalFileName} ===\\n`;

sourceFiles.push({
  filename: originalFileName,  // Use original filename
  hash: fileHash,
  pages: extractedData.totalPages || 0,
  words: extractedData.totalWords || 0
});
```

#### Node: "Parse AI Response"
Use `sourceFiles` from `promptData` to build evidence summary:

```javascript
// Extract sourceFiles from promptData (which came from Consolidate Evidence Text)
const sourceFiles = promptData.sourceFiles || [];

// Build evidence summary using original filenames
const evidenceSummary = sourceFiles.length > 0
  ? `Evidence files reviewed: ${sourceFiles.map(f => f.filename).join(', ')}`
  : 'No evidence files provided';

// Override evidence_summary with original filenames
evaluation.evidence_summary = evidenceSummary;
```

## Testing

### Before Fix
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -H "X-API-Key: your-secret-key" \
  -F "domain=6ec7535e-6134-4010-9817-8c0849e8f59b" \
  -F 'questions=[{"question_id":"1daa7d40-a975-4026-b6a9-818b34c2f3c0","files":["null0","null1"]}]' \
  -F "null0=@NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" \
  -F "null1=@NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
```

**Result:**
```json
{
  "evidence_summary": "Evidence files reviewed: /tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx, /tmp/n8n_processing/.../0fed1cddfc600ffb6ad6f9d21cb1ffd3c8358e5d9f520c5339ab8cc4c2fa6b10.xlsx"
}
```

### After Fix
Same curl command, but now:

**Result:**
```json
{
  "evidence_summary": "Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx, NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
}
```

## Deployment Steps

1. **Re-import Workflow C1:**
   - Open n8n UI
   - Navigate to Workflows
   - Open "Workflow C1: Audit Entry (Job Submission)"
   - Click "..." menu → "Import from File"
   - Select `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
   - Click "Save"

2. **Re-import Workflow C2:**
   - Open "Workflow C2: Audit Worker (Background Processor)"
   - Click "..." menu → "Import from File"
   - Select `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`
   - Click "Save"

3. **Test:**
   - Submit a new audit request with the curl command above
   - Wait for completion
   - Check the results - `evidence_summary` should show original filenames

## Files Modified

- `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`
  - Node: "Prepare File Writes" - Added `originalFileName` field
  - Node: "Aggregate Files" - Use `originalFileName` instead of `fileName`

- `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`
  - Node: "Consolidate Evidence Text" - Look up original filenames from `fileMap`
  - Node: "Parse AI Response" - Use `sourceFiles` for evidence summary

## Scripts Created

- `temp-assets/fix_c1_aggregate_files.py` - Applied fix to Workflow C1
- `temp-assets/fix_c2_use_original_filenames.py` - Applied fix to Workflow C2
- `temp-assets/parse_execution_log.py` - Debug tool to trace data flow
- `temp-assets/check_c1_webhook_data.py` - Debug tool to examine C1 execution

## Key Learnings

1. **n8n Behavior:** The "Write Binary File" node overwrites `json.fileName` with the disk path
2. **Data Preservation:** Need to explicitly preserve original data in separate fields before nodes that modify it
3. **Debugging:** Execution logs from PostgreSQL are invaluable for tracing data flow issues
4. **Hash Lookup:** Using file hashes to look up original filenames from `fileMap` is reliable

## Related Documentation

- `docs/MASTER-CACHE-IMPLEMENTATION-SUMMARY.md` - Master cache implementation
- `docs/CURL-PLAYBOOK.md` - API testing examples
- `scripts/README-export-logs.md` - How to use the log export script
