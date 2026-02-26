#!/usr/bin/env python3
"""
Fix Parse AI Response to get original filenames from Build AI Prompt node
instead of Split by Question (which causes paired item error).
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing Parse AI Response to avoid paired item error...")

# Find the Parse AI Response node and fix it
fixed = False
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
  
  // Override evidence_summary with ORIGINAL filenames from sourceFiles
  // sourceFiles comes from Build AI Prompt which has the original filenames
  const sourceFiles = promptData.sourceFiles || [];
  
  if (sourceFiles.length > 0) {
    // Extract original filenames
    const fileList = sourceFiles.map(f => f.filename).join(', ');
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
        
        fixed = True
        print(f"   ✓ Fixed Parse AI Response node")
        break

if fixed:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Parse AI Response fixed successfully!")
    print("\nChanges:")
    print("  - Now uses promptData.sourceFiles (from Build AI Prompt)")
    print("  - Avoids paired item error from Split by Question")
    print("  - sourceFiles already contains original filenames")
else:
    print("\n✗ Parse AI Response node not found!")
