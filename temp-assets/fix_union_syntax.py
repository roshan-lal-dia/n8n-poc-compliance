#!/usr/bin/env python3
"""
Fix the UNION ALL syntax error in Check Master Cache query.
The issue is that UNION ALL after a CTE with LIMIT doesn't work in PostgreSQL.
We need to restructure using a subquery approach.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing UNION ALL syntax error in Check Master Cache query...")

# Find the Check Master Cache node and fix the query
fixed = False
for node in workflow['nodes']:
    if node['name'] == 'Check Master Cache':
        # New query structure that always returns a row
        node['parameters']['query'] = """-- Check if this exact question + file combination was evaluated before
-- Returns cached ai_response if found, NULL if not found (always returns 1 row)
SELECT 
  COALESCE(
    (
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
      SELECT ai_response FROM matching_sessions
    ),
    NULL::jsonb
  ) as ai_response,
  COALESCE(
    (
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
      SELECT session_id FROM matching_sessions
    ),
    NULL::uuid
  ) as cached_session_id,
  COALESCE(
    (
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
      SELECT created_at FROM matching_sessions
    ),
    NULL::timestamp
  ) as cached_at;"""
        
        fixed = True
        print(f"   ✓ Fixed query in node: {node['name']} (id: {node['id']})")
        break

if not fixed:
    print("   ✗ Check Master Cache node not found!")
else:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Query fixed successfully!")
    print("\nNew approach:")
    print("  - Uses COALESCE with subqueries instead of UNION ALL")
    print("  - Always returns exactly 1 row")
    print("  - Returns NULL values when no cache match found")
    print("  - PostgreSQL compatible syntax")
