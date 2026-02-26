#!/usr/bin/env python3
"""
Fix Consolidate Evidence Text node in Workflow C2

The issue: extractedData is undefined because the data structure
from Combine Extraction Results is different than expected.

Need to check the actual structure and handle it properly.
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

# Find and fix Consolidate Evidence Text node
for node in workflow['nodes']:
    if node['name'] == 'Consolidate Evidence Text':
        print(f"✓ Found node: {node['name']}")
        
        # Fixed code with proper null checks
        new_code = """// Consolidate all evidence text and track source files
const allEvidence = $input.all();
const questionData = $('Split by Question').first().json;
const fileMap = questionData.fileMap;

let consolidatedText = '';
const sourceFiles = [];

for (const item of allEvidence) {
  const data = item.json;
  
  // Handle both extractedData and direct data structure
  const extractedData = data.extractedData || data;
  const fileHash = data.fileHash || data.hash;
  
  // Find original filename from fileMap using hash
  let originalFileName = null;
  if (fileMap) {
    for (const [fieldName, fileInfo] of Object.entries(fileMap)) {
      if (fileInfo.hash === fileHash) {
        originalFileName = fileInfo.fileName;  // This is now the original filename from API
        break;
      }
    }
  }
  
  if (!originalFileName) {
    originalFileName = data.filename || extractedData.originalFileName || 'unknown';
  }
  
  // Get document text
  const docText = extractedData.fullDocument || extractedData.text || '';
  
  consolidatedText += `\\n\\n=== File: ${originalFileName} ===\\n`;
  consolidatedText += docText;
  
  sourceFiles.push({
    filename: originalFileName,  // Use original filename
    hash: fileHash,
    pages: extractedData.totalPages || 0,
    words: extractedData.totalWords || 0
  });
}

return [{
  json: {
    sessionId: questionData.sessionId,
    qId: questionData.qId,
    domain: questionData.domain,
    evidenceText: consolidatedText.trim(),
    evidenceLength: consolidatedText.length,
    sourceFiles: sourceFiles,
    totalPages: sourceFiles.reduce((sum, f) => sum + f.pages, 0),
    totalWords: sourceFiles.reduce((sum, f) => sum + f.words, 0),
    questionIndex: questionData.questionIndex,
    totalQuestions: questionData.totalQuestions
  }
}];"""
        
        node['parameters']['jsCode'] = new_code
        print(f"✓ Updated Consolidate Evidence Text with null checks")
        break

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Workflow C2 fixed")
print("\nChanges:")
print("- Added null checks for extractedData")
print("- Handle both extractedData and direct data structure")
print("- Fallback to originalFileName if fileMap lookup fails")
print("\nRe-import the workflow and test again.")
