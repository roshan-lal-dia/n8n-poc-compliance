#!/usr/bin/env python3
"""
Optimize the Check Master Cache query to avoid repetition.
Use a single CTE and LEFT JOIN to ensure we always get a row.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Optimizing Check Master Cache query...")

# Find the Check Master Cache node and optimize the query
fixed = False
for node in workflow['nodes']:
    if node['name'] == 'Check Master Cache':
        # Optimized query using LEFT JOIN approach
        node['parameters']['query'] = """-- Check if this exact question + file combination was evaluated before
-- Always returns 1 row: cached data if found, NULLs if not found
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
    al.created_at
  FROM audit_logs al
  JOIN audit_evidence ae ON ae.session_id = al.session_id AND ae.question_id = al.question_id
  WHERE al.question_id = '{{ $('Split by Question').first().json.qId }}'::uuid
    AND al.step_name = 'completed'
    AND al.status = 'success'
    AND al.ai_response IS NOT NULL
    AND ae.file_hash IN (SELECT hash FROM current_hashes)
  GROUP BY al.session_id, al.question_id, al.ai_response, al.created_at
  HAVING COUNT(DISTINCT ae.file_hash) = (SELECT cnt FROM current_hash_count)
  ORDER BY al.created_at DESC
  LIMIT 1
)
SELECT 
  COALESCE(ms.ai_response, NULL::jsonb) as ai_response,
  COALESCE(ms.session_id, NULL::uuid) as cached_session_id,
  COALESCE(ms.created_at, NULL::timestamp) as cached_at
FROM (SELECT 1) as dummy
LEFT JOIN matching_sessions ms ON true;"""
        
        fixed = True
        print(f"   ✓ Optimized query in node: {node['name']} (id: {node['id']})")
        break

if not fixed:
    print("   ✗ Check Master Cache node not found!")
else:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Query optimized successfully!")
    print("\nOptimized approach:")
    print("  - Single CTE execution (no repetition)")
    print("  - LEFT JOIN with dummy table ensures 1 row always returned")
    print("  - Returns NULL values when no cache match found")
    print("  - Much more efficient than previous version")
    print("  - PostgreSQL compatible syntax")
