#!/usr/bin/env python3
"""
Fix Format Cached Response to also override evidence_summary with actual filenames.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing Format Cached Response to use actual filenames for evidence_summary...")

# Find the Format Cached Response node and update the code
fixed = False
for node in workflow['nodes']:
    if node['name'] == 'Format Cached Response':
        # Updated code that overrides evidence_summary with actual filenames
        node['parameters']['jsCode'] = """// Format cached AI response to match Parse AI Response output
const cachedData = $input.first().json;
const questionData = $('Split by Question').item.json;

// Extract the cached evaluation
const evaluation = cachedData.ai_response;

console.log('=== MASTER CACHE HIT ===');
console.log('Using cached evaluation from session:', cachedData.cached_session_id);
console.log('Question:', questionData.qId);

// Get actual filenames from the current submission
const actualFiles = questionData.evidenceFiles || [];
if (actualFiles.length > 0 && evaluation) {
  // Override evidence_summary with actual uploaded filenames
  const fileList = actualFiles.map(f => {
    // Get filename from fileMap
    const fileData = questionData.fileMap[f.fieldName];
    return fileData ? fileData.fileName : f.fieldName;
  }).join(', ');
  
  evaluation.evidence_summary = `Evidence files reviewed: ${fileList}`;
  console.log('Updated evidence_summary with actual files:', fileList);
}

return [{
  json: {
    sessionId: questionData.sessionId,
    qId: questionData.qId,
    evaluation: evaluation,
    rawResponse: JSON.stringify(evaluation),
    ragSources: [],
    sourceFiles: actualFiles.map(f => {
      const fileData = questionData.fileMap[f.fieldName];
      return {
        filename: fileData ? fileData.fileName : f.fieldName,
        hash: f.hash
      };
    }),
    promptLength: 0,
    questionIndex: questionData.questionIndex,
    totalQuestions: questionData.totalQuestions,
    fromMasterCache: true,
    cachedFromSession: cachedData.cached_session_id
  }
}];"""
        
        fixed = True
        print(f"   ✓ Fixed code in node: {node['name']} (id: {node['id']})")
        break

if not fixed:
    print("   ✗ Format Cached Response node not found!")
else:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Format Cached Response fixed successfully!")
    print("\nChanges:")
    print("  - evidence_summary now populated with actual uploaded filenames (cached path)")
    print("  - sourceFiles array populated with current submission files")
    print("  - Consistent behavior between cached and non-cached paths")
