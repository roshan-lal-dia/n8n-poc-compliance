#!/usr/bin/env python3
"""
Fix Parse AI Response to override evidence_summary with actual uploaded filenames.
The AI sometimes hallucinates filenames, so we replace it with the real list.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing Parse AI Response to use actual filenames for evidence_summary...")

# Find the Parse AI Response node and update the code
fixed = False
for node in workflow['nodes']:
    if node['name'] == 'Parse AI Response':
        # Updated code that overrides evidence_summary with actual filenames
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
  
  // Override evidence_summary with actual uploaded filenames
  // The AI sometimes hallucinates filenames, so we use the real list
  const actualFiles = promptData.sourceFiles || [];
  if (actualFiles.length > 0) {
    const fileList = actualFiles.map(f => f.filename).join(', ');
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
        print(f"   ✓ Fixed code in node: {node['name']} (id: {node['id']})")
        break

if not fixed:
    print("   ✗ Parse AI Response node not found!")
else:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Parse AI Response fixed successfully!")
    print("\nChanges:")
    print("  - evidence_summary now populated with actual uploaded filenames")
    print("  - Format: 'Evidence files reviewed: file1.pdf, file2.docx'")
    print("  - No more AI hallucinated filenames")
    print("  - Reliable and consistent evidence tracking")
