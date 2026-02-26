#!/usr/bin/env python3
"""
Fix Workflow C1 connections issue

PROBLEM: Prepare File Writes receives input from Create Audit Session,
but needs binary data from Parse & Validate Input. Binary data doesn't
flow through database nodes.

SOLUTION: Change Prepare File Writes to receive input from Parse & Validate Input
instead, and access session data from Create Audit Session using $('Create Audit Session')
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'r') as f:
    workflow = json.load(f)

print("=" * 80)
print("FIXING WORKFLOW C1 CONNECTIONS")
print("=" * 80)

# Step 1: Change connection - Prepare File Writes should receive from Parse & Validate Input
print("\n1. Updating connections...")

# Remove old connection from Create Audit Session to Prepare File Writes
if 'Create Audit Session' in workflow['connections']:
    old_conns = workflow['connections']['Create Audit Session']['main'][0]
    workflow['connections']['Create Audit Session']['main'][0] = [
        conn for conn in old_conns if conn['node'] != 'Prepare File Writes'
    ]
    print("   ✓ Removed connection: Create Audit Session -> Prepare File Writes")

# Add new connection from Parse & Validate Input to Prepare File Writes
if 'Parse & Validate Input' not in workflow['connections']:
    workflow['connections']['Parse & Validate Input'] = {'main': [[]]}

# Check if connection already exists
existing = workflow['connections']['Parse & Validate Input']['main'][0]
if not any(conn['node'] == 'Prepare File Writes' for conn in existing):
    workflow['connections']['Parse & Validate Input']['main'][0].append({
        'node': 'Prepare File Writes',
        'type': 'main',
        'index': 0
    })
    print("   ✓ Added connection: Parse & Validate Input -> Prepare File Writes")

# Step 2: Update Prepare File Writes code to get session data from Create Audit Session
print("\n2. Updating Prepare File Writes code...")

for node in workflow['nodes']:
    if node['name'] == 'Prepare File Writes':
        new_code = """// Calculate hashes and prepare items for writing
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Get session data from Create Audit Session node
const sessionData = $('Create Audit Session').first().json;
const sessionId = sessionData.session_id;
const domain = sessionData.domain_id;

// Get questions and binary data from current input (Parse & Validate Input)
const inputData = $input.first();
const questions = inputData.json.questions;
const binaryData = inputData.binary;

if (!binaryData || Object.keys(binaryData).length === 0) {
  throw new Error('No binary data found in input');
}

const binaryKeys = Object.keys(binaryData);

// Create session directory
const sessionDir = `/tmp/n8n_processing/${sessionId}`;
if (!fs.existsSync(sessionDir)) {
  fs.mkdirSync(sessionDir, { recursive: true });
}

console.log(`Created session directory: ${sessionDir}`);

const items = [];

// Process each binary file
for (let ki = 0; ki < binaryKeys.length; ki++) {
  const fieldName = binaryKeys[ki];
  const fileData = binaryData[fieldName];
  if (!fileData) continue;

  // Get binary buffer
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
  throw new Error('No files processed');
}

return items;"""
        
        node['parameters']['jsCode'] = new_code
        print("   ✓ Updated Prepare File Writes code")
        print("     - Now receives input from Parse & Validate Input")
        print("     - Gets session data from Create Audit Session using $()")
        break

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n" + "=" * 80)
print("✓ WORKFLOW C1 FIXED")
print("=" * 80)
print("\nChanges:")
print("1. Connection changed: Parse & Validate Input -> Prepare File Writes")
print("2. Prepare File Writes now:")
print("   - Receives binary data from $input (Parse & Validate Input)")
print("   - Gets session_id from $('Create Audit Session')")
print("\nThis ensures binary data flows correctly to Prepare File Writes.")
print("\nNext: Re-import the workflow in n8n UI")
