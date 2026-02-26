#!/usr/bin/env python3
"""
Fix Combine Extraction Results to output individual items

The issue: The node returns ONE item with allEvidence array,
but Consolidate Evidence Text expects MULTIPLE items (one per file).

Solution: Return individual items for each evidence file.
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

# Find and fix Combine Extraction Results node
for node in workflow['nodes']:
    if node['name'] == 'Combine Extraction Results':
        print(f"✓ Found node: {node['name']}")
        
        # Fixed code that returns individual items
        new_code = """// Combine extracted results with cached evidence
const currentItems = $input.all();
const preparedItems = $('Prepare Files for Extraction').all();

// Check if this is the FALSE path (no extraction needed)
if (currentItems.length > 0 && currentItems[0].json.allEvidence !== undefined) {
  // Already has the complete structure, pass through
  return currentItems;
}

// This is the TRUE path (extraction happened)
// Get cached evidence from first prepared item
const cachedEvidence = preparedItems[0].json.cachedEvidence || [];
const firstPrepared = preparedItems[0].json;
const questionData = $('Split by Question').item.json;

const allEvidence = [...cachedEvidence];
const newExtractions = [];

// Process each extraction result
for (let i = 0; i < currentItems.length; i++) {
  const extractedData = currentItems[i].json;
  const preparedData = preparedItems[i].json;
  
  // Validate that extraction returned proper data
  if (!extractedData.fullDocument && !extractedData.text) {
    console.error('Extraction failed for file:', preparedData.filename);
    console.error('Got data:', JSON.stringify(extractedData));
    
    // Use empty extraction as fallback
    extractedData.fullDocument = `[Extraction failed for ${preparedData.filename}]`;
    extractedData.totalPages = 0;
    extractedData.totalWords = 0;
    extractedData.hasDiagrams = false;
  }
  
  // Get original filename from Workflow A response
  const originalFilename = extractedData.originalFileName || preparedData.filename;
  
  console.log(`File ${preparedData.hash}: using originalFileName="${originalFilename}"`);
  
  allEvidence.push({
    hash: preparedData.hash,
    filename: originalFilename,
    extractedData: extractedData,
    fileSize: preparedData.fileSize,
    fromCache: false
  });
  
  newExtractions.push({
    hash: preparedData.hash,
    filename: originalFilename,
    extractedData: extractedData,
    fileSize: preparedData.fileSize
  });
}

// CRITICAL FIX: Return individual items for each evidence file
// This allows Consolidate Evidence Text to process each file separately
const outputItems = [];

for (const evidence of allEvidence) {
  outputItems.push({
    json: {
      sessionId: firstPrepared.sessionId,
      qId: firstPrepared.qId,
      domain: firstPrepared.domain,
      filename: evidence.filename,
      fileHash: evidence.hash,
      fileSize: evidence.fileSize,
      extractedData: evidence.extractedData,
      fromCache: evidence.fromCache,
      questionIndex: questionData.questionIndex,
      totalQuestions: questionData.totalQuestions
    }
  });
}

return outputItems;"""
        
        node['parameters']['jsCode'] = new_code
        print(f"✓ Updated Combine Extraction Results to return individual items")
        break

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Workflow C2 fixed")
print("\nChanges:")
print("- Combine Extraction Results now returns individual items (one per file)")
print("- Each item has filename, fileHash, and extractedData")
print("- This allows Consolidate Evidence Text to process files correctly")
print("\nRe-import the workflow and test again.")
