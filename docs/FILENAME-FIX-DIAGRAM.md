# Evidence Summary Filename Fix - Visual Diagram

## Data Flow - Before Fix

```
API Request
  │
  ├─ File: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx"
  └─ File: "NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Workflow C1: Audit Entry                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. Webhook                                                      │
│    fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 2. Parse & Validate Input                                      │
│    fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 3. Prepare File Writes                                         │
│    fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 4. Write Binary File  ⚠️  OVERWRITES fileName                  │
│    fileName: "/tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx" ❌
│                                                                 │
│ 5. Aggregate Files                                             │
│    fileMap[null0].fileName: "/tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx" ❌
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
  │
  │ Redis Queue (fileMap with temp paths)
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Workflow C2: Audit Worker                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. Parse Job                                                    │
│    fileMap[null0].fileName: "/tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx" ❌
│                                                                 │
│ 2. Consolidate Evidence Text                                   │
│    sourceFiles[0].filename: "/tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx" ❌
│                                                                 │
│ 3. Parse AI Response                                           │
│    evidence_summary: "Evidence files reviewed: /tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx" ❌
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
Final Result: Temp paths in evidence_summary ❌
```

## Data Flow - After Fix

```
API Request
  │
  ├─ File: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx"
  └─ File: "NPC_DGO_QDKC_General_Data Management Domain Plan Template_V2.xlsx"
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Workflow C1: Audit Entry (FIXED)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. Webhook                                                      │
│    fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 2. Parse & Validate Input                                      │
│    fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 3. Prepare File Writes (FIXED)                                 │
│    fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│    originalFileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓ NEW!
│                                                                 │
│ 4. Write Binary File  ⚠️  OVERWRITES fileName (but not originalFileName)
│    fileName: "/tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx"
│    originalFileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓ PRESERVED!
│                                                                 │
│ 5. Aggregate Files (FIXED)                                     │
│    Uses originalFileName instead of fileName                    │
│    fileMap[null0].fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
  │
  │ Redis Queue (fileMap with original filenames)
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Workflow C2: Audit Worker (FIXED)                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. Parse Job                                                    │
│    fileMap[null0].fileName: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 2. Consolidate Evidence Text (FIXED)                           │
│    Looks up original filename from fileMap using hash           │
│    sourceFiles[0].filename: "NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
│ 3. Parse AI Response (FIXED)                                   │
│    Uses sourceFiles from promptData                             │
│    evidence_summary: "Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx" ✓
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
Final Result: Original filenames in evidence_summary ✓
```

## Key Changes

### Workflow C1

#### Before:
```javascript
// Prepare File Writes
items.push({
  json: {
    fileName: fileData.fileName,  // Gets overwritten by Write Binary File
    ...
  }
});

// Aggregate Files
fileMap[row.fieldName] = {
  fileName: row.fileName,  // This is now the temp path!
  ...
};
```

#### After:
```javascript
// Prepare File Writes
items.push({
  json: {
    fileName: fileData.fileName,
    originalFileName: fileData.fileName,  // NEW: Won't be overwritten
    ...
  }
});

// Aggregate Files
const originalName = row.originalFileName || row.fileName;  // NEW: Use preserved name
fileMap[row.fieldName] = {
  fileName: originalName,  // Now contains original filename!
  ...
};
```

### Workflow C2

#### Before:
```javascript
// Consolidate Evidence Text
consolidatedText += `\n\n=== File: ${data.filename} ===\n`;  // Uses temp path

sourceFiles.push({
  filename: data.filename,  // Temp path
  ...
});

// Parse AI Response
// AI generates evidence_summary with temp paths
```

#### After:
```javascript
// Consolidate Evidence Text
// Look up original filename from fileMap using hash
let originalFileName = null;
for (const [fieldName, fileInfo] of Object.entries(fileMap)) {
  if (fileInfo.hash === fileHash) {
    originalFileName = fileInfo.fileName;  // Original filename!
    break;
  }
}

consolidatedText += `\n\n=== File: ${originalFileName} ===\n`;

sourceFiles.push({
  filename: originalFileName,  // Original filename!
  ...
});

// Parse AI Response
const evidenceSummary = sourceFiles.length > 0
  ? `Evidence files reviewed: ${sourceFiles.map(f => f.filename).join(', ')}`
  : 'No evidence files provided';

evaluation.evidence_summary = evidenceSummary;  // Original filenames!
```

## The Problem: n8n's Write Binary File Behavior

```
┌─────────────────────────────────────────────────────────────┐
│ Write Binary File Node                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Input:                                                      │
│   json.fileName = "MyDocument.pdf"                          │
│   json.filePath = "/tmp/session/hash.pdf"                  │
│                                                             │
│ Action: Writes binary data to disk at filePath             │
│                                                             │
│ Output:                                                     │
│   json.fileName = "/tmp/session/hash.pdf"  ⚠️  OVERWRITTEN!│
│   json.filePath = "/tmp/session/hash.pdf"                  │
│                                                             │
│ This is standard n8n behavior!                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## The Solution: Preserve Before Overwrite

```
┌─────────────────────────────────────────────────────────────┐
│ Our Fix: Add originalFileName Field                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Before Write Binary File:                                   │
│   json.fileName = "MyDocument.pdf"                          │
│   json.originalFileName = "MyDocument.pdf"  ✓ NEW!         │
│   json.filePath = "/tmp/session/hash.pdf"                  │
│                                                             │
│ After Write Binary File:                                    │
│   json.fileName = "/tmp/session/hash.pdf"  (overwritten)   │
│   json.originalFileName = "MyDocument.pdf"  ✓ PRESERVED!   │
│   json.filePath = "/tmp/session/hash.pdf"                  │
│                                                             │
│ Then use originalFileName in downstream nodes!              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Debugging Process

```
1. User reports issue
   └─> evidence_summary shows temp paths

2. Export execution logs
   └─> python3 scripts/export_n8n_logs.py 4988 --format json

3. Create parser script
   └─> temp-assets/parse_execution_log.py

4. Trace data through nodes
   └─> Found: Write Binary File overwrites fileName

5. Check Workflow C1 execution
   └─> Confirmed: fileMap already has temp paths

6. Identify root cause
   └─> Aggregate Files reads overwritten fileName

7. Create fix scripts
   ├─> temp-assets/fix_c1_aggregate_files.py
   └─> temp-assets/fix_c2_use_original_filenames.py

8. Apply fixes
   └─> Both workflows updated

9. Validate
   └─> python3 temp-assets/validate_filename_fix.py
   └─> ✅ ALL VALIDATIONS PASSED

10. Document
    └─> Created comprehensive documentation
```

## Testing the Fix

### Before Fix:
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -F "null0=@MyDocument.pdf"

# Result:
{
  "evidence_summary": "Evidence files reviewed: /tmp/n8n_processing/.../abc123.pdf"
}
```

### After Fix:
```bash
curl -X POST http://localhost:5678/webhook/audit/submit \
  -F "null0=@MyDocument.pdf"

# Result:
{
  "evidence_summary": "Evidence files reviewed: MyDocument.pdf"
}
```

## Summary

The fix ensures original filenames from the API request are preserved throughout the workflow and appear in the final `evidence_summary` field, making audit results more readable and useful for compliance reporting.
