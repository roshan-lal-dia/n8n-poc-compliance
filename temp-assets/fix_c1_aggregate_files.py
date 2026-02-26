#!/usr/bin/env python3
"""
Fix Workflow C1 Aggregate Files node to use filePath for temp paths
and preserve original fileName separately.

ROOT CAUSE: The "Write Binary File" node overwrites json.fileName with the 
disk path. We need to read from the binary metadata or preserve it earlier.

SOLUTION: In "Prepare File Writes", store originalFileName explicitly.
Then in "Aggregate Files", use originalFileName for the fileName field.
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'r') as f:
    workflow = json.load(f)

# Fix 1: Update "Prepare File Writes" to preserve originalFileName
for node in workflow['nodes']:
    if node['name'] == 'Prepare File Writes':
        print(f"✓ Found node: {node['name']}")
        
        old_code = node['parameters']['jsCode']
        
        # Add originalFileName field that won't be overwritten
        new_code = old_code.replace(
            '''items.push({
    json: {
      sessionId,
      domain,
      fieldName,
      fileName: fileData.fileName,
      mimeType: fileData.mimeType,
      fileSize: buffer.length,
      hash,
      filePath,
      questions
    },
    binary: {
      data: fileData
    }
  });''',
            '''items.push({
    json: {
      sessionId,
      domain,
      fieldName,
      fileName: fileData.fileName,
      originalFileName: fileData.fileName,  // Preserve original - won't be overwritten
      mimeType: fileData.mimeType,
      fileSize: buffer.length,
      hash,
      filePath,
      questions
    },
    binary: {
      data: fileData
    }
  });'''
        )
        
        if new_code != old_code:
            node['parameters']['jsCode'] = new_code
            print(f"✓ Updated Prepare File Writes to preserve originalFileName")
        else:
            print(f"⚠️  Could not update Prepare File Writes (pattern not found)")

# Fix 2: Update "Aggregate Files" to use originalFileName
for node in workflow['nodes']:
    if node['name'] == 'Aggregate Files':
        print(f"✓ Found node: {node['name']}")
        
        # Update to use originalFileName instead of fileName (which gets overwritten)
        new_code = """// Reconstruct fileMap and question structure
const items = $input.all();
const firstItem = items[0].json;
const sessionId = firstItem.sessionId;
const domain = firstItem.domain;
const questions = firstItem.questions;

const fileMap = {};

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

// Map questions to hashes
const questionsWithHashes = questions.map(q => ({
  question_id: q.question_id,
  evidence_files: q.files.map(fileName => {
    const fileInfo = fileMap[fileName];
    return {
      hash: fileInfo.hash,
      originalName: fileInfo.fileName,  // Use original filename
      fieldName: fileName
    };
  })
}));

return [{
  json: {
    sessionId,
    domain,
    questions: questionsWithHashes,
    fileMap,
    totalFiles: Object.keys(fileMap).length
  }
}];"""
        
        node['parameters']['jsCode'] = new_code
        print(f"✓ Updated Aggregate Files to use originalFileName")

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n" + "=" * 80)
print("✓ Workflow C1 fixed successfully!")
print("=" * 80)
print("\nChanges made:")
print("1. Prepare File Writes: Added originalFileName field to preserve API filename")
print("2. Aggregate Files: Use originalFileName instead of fileName (which gets overwritten)")
print("\nThis ensures original filenames flow through to Workflow C2 and appear in")
print("evidence_summary instead of temp paths.")
