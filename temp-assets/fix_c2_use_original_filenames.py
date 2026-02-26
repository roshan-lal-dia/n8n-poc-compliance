#!/usr/bin/env python3
"""
Fix Workflow C2 to use original filenames from fileMap in evidence_summary

Now that Workflow C1 preserves originalFileName in fileMap, we need to:
1. Use fileMap[].fileName (which now contains original names) in Consolidate Evidence Text
2. Ensure these flow through to Parse AI Response for evidence_summary
"""

import json
import re

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

# Fix "Consolidate Evidence Text" node to use original filenames from fileMap
for node in workflow['nodes']:
    if node['name'] == 'Consolidate Evidence Text':
        print(f"✓ Found node: {node['name']}")
        
        new_code = """// Consolidate all evidence text and track source files
const allEvidence = $input.all();
const questionData = $('Split by Question').first().json;
const fileMap = questionData.fileMap;

let consolidatedText = '';
const sourceFiles = [];

for (const item of allEvidence) {
  const data = item.json;
  const extractedData = data.extractedData;
  const fileHash = data.fileHash;
  
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
  consolidatedText += extractedData.fullDocument || '';
  
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
        print(f"✓ Updated Consolidate Evidence Text to use original filenames from fileMap")

# Fix "Parse AI Response" node to use sourceFiles from promptData
for node in workflow['nodes']:
    if node['name'] == 'Parse AI Response':
        print(f"✓ Found node: {node['name']}")
        
        new_code = """// Parse AI response and construct evaluation object
const aiResponse = $('Ollama: Evaluate Compliance').first().json.response;
const promptData = $('Build AI Prompt').first().json;

// Extract sourceFiles from promptData (which came from Consolidate Evidence Text)
const sourceFiles = promptData.sourceFiles || [];

// Build evidence summary using original filenames
const evidenceSummary = sourceFiles.length > 0
  ? `Evidence files reviewed: ${sourceFiles.map(f => f.filename).join(', ')}`
  : 'No evidence files provided';

let evaluation;
try {
  // Try to parse as JSON first
  const jsonMatch = aiResponse.match(/\\{[\\s\\S]*\\}/);
  if (jsonMatch) {
    evaluation = JSON.parse(jsonMatch[0]);
  } else {
    throw new Error('No JSON found in response');
  }
} catch (e) {
  // Fallback: extract fields using regex
  evaluation = {
    score: parseInt(aiResponse.match(/score[\"']?\\s*:\\s*(\\d+)/i)?.[1] || '0'),
    compliant: /compliant[\"']?\\s*:\\s*true/i.test(aiResponse),
    confidence: parseInt(aiResponse.match(/confidence[\"']?\\s*:\\s*(\\d+)/i)?.[1] || '0'),
    findings: aiResponse.match(/findings[\"']?\\s*:\\s*[\"']([^\"']+)[\"']/i)?.[1] || 'Unable to parse findings',
    gaps: [],
    recommendations: []
  };
}

// Override evidence_summary with original filenames
evaluation.evidence_summary = evidenceSummary;

return [{
  json: {
    sessionId: promptData.sessionId,
    qId: promptData.qId,
    evaluation: evaluation,
    rawResponse: aiResponse,
    ragSources: promptData.ragSources || [],
    sourceFiles: sourceFiles,  // Pass through for downstream nodes
    promptLength: promptData.promptLength,
    questionIndex: promptData.questionIndex,
    totalQuestions: promptData.totalQuestions
  }
}];"""
        
        node['parameters']['jsCode'] = new_code
        print(f"✓ Updated Parse AI Response to use original filenames in evidence_summary")

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n" + "=" * 80)
print("✓ Workflow C2 fixed successfully!")
print("=" * 80)
print("\nChanges made:")
print("1. Consolidate Evidence Text: Look up original filenames from fileMap using hash")
print("2. Parse AI Response: Use sourceFiles from promptData for evidence_summary")
print("\nNow evidence_summary will show:")
print("  'Evidence files reviewed: NPC_DGO_QDKC_General_Initiative Card Template_V2.pptx, ...'")
print("\nInstead of:")
print("  'Evidence files reviewed: /tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx, ...'")
