#!/usr/bin/env python3
"""
Fix evidence_summary to use original filenames from the API request,
not the temp file paths.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing evidence_summary to use original filenames from API request...")

# Fix 1: Parse AI Response node
fixed_parse = False
for node in workflow['nodes']:
    if node['name'] == 'Parse AI Response':
        node['parameters']['jsCode'] = """// Parse and validate AI response
const aiResponse = $input.first().json;
const promptData = $('Build AI Prompt').first().json;

const rawResponse = aiResponse.response;
let evaluation;

try {
  evaluation = JSON.parse(rawResponse);
  
  // Validate required fields
  if (!evaluation.hasOwnProperty('compliant')) evaluation.compliant = false;
  if (!evaluation.hasOwnProperty('score')) evaluation.score = 0;
  if (!evaluation.hasOwnProperty('confidence')) evaluation.confidence = 0;
  if (!evaluation.findings) evaluation.findings = 'No findings provided';
  if (!evaluation.gaps) evaluation.gaps = [];
  if (!evaluation.recommendations) evaluation.recommendations = [];
  
  // Override evidence_summary with ORIGINAL filenames from API request
  // Get the original filenames from Split by Question node
  const questionData = $('Split by Question').item.json;
  const evidenceFiles = questionData.evidenceFiles || [];
  
  if (evidenceFiles.length > 0) {
    // Extract original filenames from the fileMap
    const originalFilenames = evidenceFiles.map(f => {
      const fileData = questionData.fileMap[f.fieldName];
      return fileData ? fileData.fileName : f.fieldName;
    });
    
    const fileList = originalFilenames.join(', ');
    evaluation.evidence_summary = `Evidence files reviewed: ${fileList}`;
  } else {
    evaluation.evidence_summary = evaluation.evidence_summary || 'No evidence files provided';
  }
  
} catch (e) {
  // Fallback on parse failure
  evaluation = {
    compliant: false,
    score: 0,
    confidence: 0,
    findings: 'AI response parsing failed: ' + e.message,
    evidence_summary: 'Unable to parse AI response',
    gaps: ['Unable to evaluate due to response format error'],
    recommendations: ['Review question prompt and try again']
  };
}

return [{
  json: {
    sessionId: promptData.sessionId,
    qId: promptData.qId,
    evaluation: evaluation,
    rawResponse: rawResponse,
    ragSources: promptData.ragSources,
    sourceFiles: promptData.sourceFiles,
    promptLength: promptData.promptLength,
    questionIndex: promptData.questionIndex,
    totalQuestions: promptData.totalQuestions
  }
}];"""
        
        fixed_parse = True
        print(f"   ✓ Fixed Parse AI Response node")
        break

# Fix 2: Format Cached Response node (already correct from previous fix)
fixed_cached = False
for node in workflow['nodes']:
    if node['name'] == 'Format Cached Response':
        # This one is already correct - it uses questionData.fileMap
        fixed_cached = True
        print(f"   ✓ Format Cached Response already uses original filenames")
        break

if fixed_parse and fixed_cached:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Evidence summary fixed successfully!")
    print("\nNow uses original filenames from API request:")
    print("  Before: /tmp/n8n_processing/.../abc123.pdf")
    print("  After:  MyDocument.pdf")
else:
    print("\n✗ Some nodes not found!")
