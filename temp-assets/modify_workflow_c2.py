#!/usr/bin/env python3
"""
Modify workflow-c2-audit-worker.json to add master cache optimization.

Changes:
1. Delete "Cleanup: Evidence DB" node
2. Add "Check Master Cache" node after "Log: Question Start"
3. Add "Is Cached?" IF node
4. Add "Format Cached Response" node
5. Update connections for cache bypass flow
"""

import json
import sys

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

# Step 1: Remove "Cleanup: Evidence DB" node
nodes_to_keep = [n for n in workflow['nodes'] if n['name'] != 'Cleanup: Evidence DB']
print(f"Removed 'Cleanup: Evidence DB' node. Nodes before: {len(workflow['nodes'])}, after: {len(nodes_to_keep)}")

# Step 2: Add new nodes for master cache
new_nodes = [
    # Check Master Cache - queries for previous evaluation with same question_id and file hashes
    {
        "parameters": {
            "operation": "executeQuery",
            "query": """-- Check if this exact question + file combination was evaluated before
WITH current_hashes AS (
  SELECT UNNEST(ARRAY[{{ $('Split by Question').first().json.evidenceFiles.map(f => \"'\" + f.hash + \"'\").join(',') }}]::text[]) AS hash
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
LIMIT 1;""",
            "options": {}
        },
        "id": "master-cache-check-node-id",
        "name": "Check Master Cache",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": [43536, 944],
        "credentials": {
            "postgres": {
                "id": "3ME8TvhWnolXkgqg",
                "name": "postgres-compliance"
            }
        }
    },
    # Is Cached? - IF node to check if master cache returned a result
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict"
                },
                "conditions": [
                    {
                        "id": "has-cached-result",
                        "leftValue": "={{ $json.ai_response !== undefined && $json.ai_response !== null }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": "is-cached-if-node-id",
        "name": "Is Cached?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [43760, 944]
    },
    # Format Cached Response - mocks Parse AI Response output with cached data
    {
        "parameters": {
            "jsCode": """// Reuse cached AI evaluation from previous session
const cachedResult = $input.first().json;
const questionData = $('Split by Question').item.json;

console.log('=== MASTER CACHE HIT ===');
console.log('Reusing evaluation from session:', cachedResult.session_id);
console.log('Original evaluation date:', cachedResult.created_at);

// Extract the cached evaluation
const evaluation = cachedResult.ai_response;

// Mock the output format of Parse AI Response
return [{
  json: {
    sessionId: questionData.sessionId,
    qId: questionData.qId,
    evaluation: evaluation,
    rawResponse: JSON.stringify(evaluation),
    ragSources: [],
    sourceFiles: [],
    promptLength: 0,
    questionIndex: questionData.questionIndex,
    totalQuestions: questionData.totalQuestions,
    fromMasterCache: true,
    cachedFromSession: cachedResult.session_id,
    cachedAt: cachedResult.created_at
  }
}];"""
        },
        "id": "format-cached-response-node-id",
        "name": "Format Cached Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [43984, 1144]
    }
]

# Add new nodes to the workflow
nodes_to_keep.extend(new_nodes)
workflow['nodes'] = nodes_to_keep

# Step 3: Update connections
# Remove old connection from "Cleanup: Temp Files" to "Cleanup: Evidence DB"
if 'Cleanup: Temp Files' in workflow['connections']:
    workflow['connections']['Cleanup: Temp Files'] = {"main": [[]]}

# Update "Log: Question Start" to connect to "Check Master Cache" instead of "Check Evidence Cache"
workflow['connections']['Log: Question Start'] = {
    "main": [[{"node": "Check Master Cache", "type": "main", "index": 0}]]
}

# Add "Check Master Cache" connections to "Is Cached?"
workflow['connections']['Check Master Cache'] = {
    "main": [[{"node": "Is Cached?", "type": "main", "index": 0}]]
}

# Add "Is Cached?" connections
# TRUE branch (cached) -> Format Cached Response
# FALSE branch (not cached) -> Check Evidence Cache (existing flow)
workflow['connections']['Is Cached?'] = {
    "main": [
        [{"node": "Format Cached Response", "type": "main", "index": 0}],
        [{"node": "Check Evidence Cache", "type": "main", "index": 0}]
    ]
}

# Add "Format Cached Response" connection to "Log Evaluation Result"
workflow['connections']['Format Cached Response'] = {
    "main": [[{"node": "Log Evaluation Result", "type": "main", "index": 0}]]
}

# Write the modified workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Workflow modified successfully!")
print("\nChanges made:")
print("1. Removed 'Cleanup: Evidence DB' node (evidence now persists)")
print("2. Added 'Check Master Cache' node after 'Log: Question Start'")
print("3. Added 'Is Cached?' IF node")
print("4. Added 'Format Cached Response' node")
print("5. Updated connections for cache bypass flow")
print("\nCache flow: Log: Question Start -> Check Master Cache -> Is Cached?")
print("  - TRUE: Format Cached Response -> Log Evaluation Result (BYPASS extraction & RAG)")
print("  - FALSE: Check Evidence Cache -> ... (existing flow)")
