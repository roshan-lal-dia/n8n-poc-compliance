#!/usr/bin/env python3
"""
Fix Prepare Evidence Inserts to work with individual items

The issue: The node expects data.newExtractions array,
but Combine Extraction Results now returns individual items.

Solution: Process all input items and only insert non-cached evidence.
"""

import json

# Load workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

# Find and fix Prepare Evidence Inserts node
for node in workflow['nodes']:
    if node['name'] == 'Prepare Evidence Inserts':
        print(f"✓ Found node: {node['name']}")
        
        # Fixed code that works with individual items
        new_code = """// Store newly extracted evidence to database
const allItems = $input.all();
const insertStatements = [];

// Process each evidence item
let order = 1;
for (const item of allItems) {
  const data = item.json;
  
  // Only insert if not from cache
  if (data.fromCache === false) {
    insertStatements.push({
      sessionId: data.sessionId,
      qId: data.qId,
      domain: data.domain,
      filename: data.filename,
      fileHash: data.fileHash,
      fileSize: data.fileSize,
      extractedData: JSON.stringify(data.extractedData),
      evidenceOrder: order++
    });
  }
}

// If nothing to insert, return empty array to skip DB insert
if (insertStatements.length === 0) {
  return [];
}

return insertStatements.map(s => ({ json: s }));"""
        
        node['parameters']['jsCode'] = new_code
        print(f"✓ Updated Prepare Evidence Inserts to work with individual items")
        break

# Save workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Workflow C2 fixed")
print("\nChanges:")
print("- Prepare Evidence Inserts now processes individual items")
print("- Only inserts evidence where fromCache === false")
print("- Works with the new Combine Extraction Results structure")
print("\nRe-import the workflow and test again.")
