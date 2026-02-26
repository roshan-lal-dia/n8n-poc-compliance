#!/usr/bin/env python3
"""
Fix the Check Master Cache query to always return a row (even on cache miss).
This prevents n8n from stopping execution when no cache is found.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

# Find all "Check Master Cache" nodes and update their queries
fixed_count = 0
for node in workflow['nodes']:
    if node['name'] == 'Check Master Cache':
        # Update the query to always return a row
        node['parameters']['query'] = """-- Check if this exact question + file combination was evaluated before
WITH current_hashes AS (
  SELECT UNNEST(ARRAY[{{ $('Split by Question').first().json.evidenceFiles.map(f => "'" + f.hash + "'").join(',') }}]::text[]) AS hash
),
current_hash_count AS (
  SELECT COUNT(*) as cnt FROM current_hashes
),
matching_sessions AS (
  SELECT DISTINCT
    al.session_id,
    al.question_id,
    al.ai_response,
    al.created_at,
    COUNT(DISTINCT ae.file_hash) as file_count
  FROM audit_logs al
  JOIN audit_evidence ae ON ae.session_id = al.session_id AND ae.question_id = al.question_id
  WHERE al.question_id = '{{ $('Split by Question').first().json.qId }}'::uuid
    AND al.step_name = 'completed'
    AND al.status = 'success'
    AND al.ai_response IS NOT NULL
    AND ae.file_hash IN (SELECT hash FROM current_hashes)
  GROUP BY al.session_id, al.question_id, al.ai_response, al.created_at
  HAVING COUNT(DISTINCT ae.file_hash) = (SELECT cnt FROM current_hash_count)
)
SELECT
  session_id,
  question_id,
  ai_response,
  created_at
FROM matching_sessions
ORDER BY created_at DESC
LIMIT 1
UNION ALL
SELECT
  NULL::uuid as session_id,
  NULL::uuid as question_id,
  NULL::jsonb as ai_response,
  NULL::timestamp as created_at
WHERE NOT EXISTS (SELECT 1 FROM matching_sessions)
LIMIT 1;"""
        fixed_count += 1
        print(f"Fixed node: {node['name']} (id: {node['id']})")

# Remove duplicate nodes (keep only one Check Master Cache)
seen_names = {}
unique_nodes = []
for node in workflow['nodes']:
    name = node['name']
    if name == 'Check Master Cache':
        if name not in seen_names:
            seen_names[name] = True
            unique_nodes.append(node)
            print(f"Kept first occurrence of: {name}")
        else:
            print(f"Removed duplicate: {name} (id: {node['id']})")
    else:
        unique_nodes.append(node)

workflow['nodes'] = unique_nodes

# Write the modified workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print(f"\n✓ Fixed {fixed_count} Check Master Cache node(s)")
print(f"✓ Total nodes: {len(workflow['nodes'])}")
print("\nThe query now always returns a row:")
print("  - Cache HIT: Returns ai_response with data")
print("  - Cache MISS: Returns ai_response = NULL")
print("\nThe 'Is Cached?' IF node will route correctly in both cases.")
