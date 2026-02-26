#!/usr/bin/env python3
"""
Remove duplicate nodes from the workflow.
Keep the first occurrence of each node name.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Removing duplicate nodes...")
print(f"Total nodes before: {len(workflow['nodes'])}")

# Track seen node names and keep only first occurrence
seen_names = {}
unique_nodes = []
removed = []

for node in workflow['nodes']:
    name = node['name']
    if name not in seen_names:
        seen_names[name] = node['id']
        unique_nodes.append(node)
    else:
        removed.append(f"{name} (id: {node['id']})")
        print(f"  Removed duplicate: {name} (id: {node['id']})")

workflow['nodes'] = unique_nodes

print(f"\nTotal nodes after: {len(workflow['nodes'])}")
print(f"Removed {len(removed)} duplicate(s)")

# Write the fixed workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Duplicates removed successfully!")
