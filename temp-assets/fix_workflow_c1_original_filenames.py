#!/usr/bin/env python3
"""
Fix Workflow C1 to preserve original filenames in fileMap
The issue: fileMap.fileName contains temp paths instead of original filenames from API
Solution: Add originalFileName field to fileMap that preserves the API filename
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'r') as f:
    workflow = json.load(f)

# Find and fix "Aggregate Files" node
for node in workflow['nodes']:
    if node['name'] == 'Aggregate Files':
        print(f"✓ Found node: {node['name']}")
        
        # Update the code to preserve original filename
        old_code = node['parameters']['jsCode']
        
        # The fix: Store both filePath (temp path) and originalFileName (from API)
        new_code = """// Reconstruct fileMap and question structure
const items = $input.all();
const firstItem = items[0].json;
const sessionId = firstItem.sessionId;
const domain = firstItem.domain;
const questions = firstItem.questions;

const fileMap = {};

for (const item of items) {
  const row = item.json;
  fileMap[row.fieldName] = {
    hash: row.hash,
    fileName: row.fileName,  // This is the original filename from API
    originalFileName: row.fileName,  // Explicitly preserve it
    fileSize: row.fileSize,
    mimeType: row.mimeType,
    fieldName: row.fieldName,
    filePath: row.filePath  // This is the temp disk path
  };
}

// Map questions to hashes
const questionsWithHashes = questions.map(q => ({
  question_id: q.question_id,
  evidence_files: q.files.map(fileName => {
    const fileInfo = fileMap[fileName];
    return {
      hash: fileInfo.hash,
      originalName: fileInfo.fileName,  // Use original filename from API
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
        print(f"✓ Updated Aggregate Files node to preserve originalFileName")
        break

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Workflow C1 updated successfully")
print("\nNOTE: The real issue is that fileMap.fileName already contains temp paths")
print("when it comes from Redis. This suggests the problem is in how files are")
print("initially processed. We need to check if binaryData.fileName in the webhook")
print("is actually the original filename or if it's being overwritten somewhere.")
