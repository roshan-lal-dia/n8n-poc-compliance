#!/usr/bin/env python3
"""
Fix the Prepare File Writes node error

The issue: The node receives input from Create Audit Session but tries to access
binary data from Parse & Validate Input. The binary data is not passed through
Create Audit Session, so we need to ensure the code properly accesses it.

Actually, looking at the original code, it should work because it uses:
  $('Parse & Validate Input').first().binary

This explicitly references the Parse & Validate Input node, not $input.

The error might be that Parse & Validate Input didn't execute or there's no binary data.
Let me check if there's a syntax error or if the code has an issue.
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'r') as f:
    workflow = json.load(f)

# Find Prepare File Writes node
for node in workflow['nodes']:
    if node['name'] == 'Prepare File Writes':
        print(f"Found node: {node['name']}")
        
        code = node['parameters']['jsCode']
        
        # Check for potential issues
        print("\nChecking code for issues...")
        
        # The code looks correct, but let's add better error handling
        new_code = """// Calculate hashes and prepare items for writing
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const sessionData = $input.first().json;
const sessionId = sessionData.session_id;
const domain = sessionData.domain;

// Get data from Parse & Validate Input node
const parseNode = $('Parse & Validate Input').first();
if (!parseNode) {
  throw new Error('Parse & Validate Input node did not execute');
}

const questions = parseNode.json.questions;
const binaryData = parseNode.binary;

if (!binaryData) {
  throw new Error('No binary data found from Parse & Validate Input');
}

const binaryKeys = Object.keys(binaryData);

if (binaryKeys.length === 0) {
  throw new Error('No binary files found in Parse & Validate Input');
}

// Create session directory
const sessionDir = `/tmp/n8n_processing/${sessionId}`;
if (!fs.existsSync(sessionDir)) {
  fs.mkdirSync(sessionDir, { recursive: true });
}

console.log(`Created session directory: ${sessionDir}`);

const items = [];

// NOTE: getBinaryDataBuffer(itemIndex, propertyName) — itemIndex 0 because
// Parse & Validate Input is a single-item node (all files on firstItem).
for (let ki = 0; ki < binaryKeys.length; ki++) {
  const fieldName = binaryKeys[ki];
  const fileData = binaryData[fieldName];
  if (!fileData) continue;

  // Correct signature: getBinaryDataBuffer(itemIndex, binaryPropertyName)
  const buffer = await this.helpers.getBinaryDataBuffer(0, fieldName);
  const hash = crypto.createHash('sha256').update(buffer).digest('hex');
  const ext = path.extname(fileData.fileName) || '.bin';
  const diskFileName = `${hash}${ext}`;
  const filePath = path.join(sessionDir, diskFileName);

  items.push({
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
  });
}

if (items.length === 0) {
  throw new Error('No items created - no valid binary files processed');
}

return items;"""
        
        node['parameters']['jsCode'] = new_code
        print("✓ Updated Prepare File Writes with better error handling")
        break

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Workflow C1 updated with better error handling")
print("\nThe new code adds explicit error messages to help identify the issue.")
