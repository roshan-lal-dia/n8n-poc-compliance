#!/usr/bin/env python3
"""
Fix workflow connections so data flows correctly to Aggregate Scores.

Issue: Log Evaluation Result is a Postgres INSERT node - it doesn't pass data through.
Solution: Both Parse AI Response and Format Cached Response should connect to BOTH:
  1. Log Evaluation Result (for logging)
  2. Aggregate Scores (for aggregation)
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing workflow connections...")

# Fix 1: Parse AI Response should connect to both Log Evaluation Result AND Aggregate Scores
if 'Parse AI Response' in workflow['connections']:
    workflow['connections']['Parse AI Response'] = {
        "main": [[
            {"node": "Log Evaluation Result", "type": "main", "index": 0},
            {"node": "Aggregate Scores", "type": "main", "index": 0}
        ]]
    }
    print("   ✓ Parse AI Response → Log Evaluation Result + Aggregate Scores")

# Fix 2: Format Cached Response should connect to both Log Evaluation Result AND Aggregate Scores
if 'Format Cached Response' in workflow['connections']:
    workflow['connections']['Format Cached Response'] = {
        "main": [[
            {"node": "Log Evaluation Result", "type": "main", "index": 0},
            {"node": "Aggregate Scores", "type": "main", "index": 0}
        ]]
    }
    print("   ✓ Format Cached Response → Log Evaluation Result + Aggregate Scores")

# Fix 3: Log Evaluation Result should NOT connect to Aggregate Scores
# (it's just for logging, data comes directly from Parse AI Response / Format Cached Response)
if 'Log Evaluation Result' in workflow['connections']:
    # Remove connection to Aggregate Scores if it exists
    workflow['connections']['Log Evaluation Result'] = {"main": [[]]}
    print("   ✓ Log Evaluation Result → [no connections] (just logs)")

# Write the modified workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Connections fixed successfully!")
print("\nNew flow:")
print("  Cache Hit:  Format Cached Response → [Log Evaluation Result, Aggregate Scores]")
print("  Cache Miss: Parse AI Response → [Log Evaluation Result, Aggregate Scores]")
print("  Both paths now feed data directly to Aggregate Scores")
