#!/usr/bin/env python3
"""
Fix Aggregate Scores node to work with both cached and non-cached paths.
The issue: It references Parse AI Response which doesn't execute on cache hits.
Solution: Get data from the input (Log Evaluation Result) instead.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Fixing Aggregate Scores node...")

# Find the Aggregate Scores node and fix the code
fixed = False
for node in workflow['nodes']:
    if node['name'] == 'Aggregate Scores':
        # New code that gets data from input (Log Evaluation Result) instead of Parse AI Response
        node['parameters']['jsCode'] = """// After all questions complete, aggregate scores
// Get evaluation data from Log Evaluation Result (works for both cached and non-cached paths)
const allResults = $input.all();

// Safety check
if (!allResults || allResults.length === 0) {
  throw new Error('No question results to aggregate');
}

console.log('=== AGGREGATE SCORES DEBUG ===');
console.log('Total results:', allResults.length);

// Extract scores from the logged data
// The data structure comes from either Parse AI Response or Format Cached Response
const scores = [];
const questionResults = [];
let sessionId = null;

for (const result of allResults) {
  const data = result.json;
  
  // Get session ID from first result
  if (!sessionId && data.sessionId) {
    sessionId = data.sessionId;
  }
  
  // Extract evaluation data
  const evaluation = data.evaluation || {};
  const score = evaluation.score || 0;
  const compliant = evaluation.compliant || false;
  
  scores.push(score);
  questionResults.push({
    qId: data.qId,
    score: score,
    compliant: compliant,
    fromCache: data.fromMasterCache || false
  });
  
  console.log(`Question ${data.qId}: score=${score}, cached=${data.fromMasterCache || false}`);
}

// Calculate average score
const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;

if (!sessionId) {
  console.error('SessionId is undefined! First result:', JSON.stringify(allResults[0].json, null, 2));
  throw new Error('SessionId not found in evaluation results');
}

console.log(`Overall score: ${avgScore.toFixed(2)}`);
console.log(`Cache hits: ${questionResults.filter(q => q.fromCache).length}/${questionResults.length}`);

return [{
  json: {
    sessionId: sessionId,
    overallScore: Math.round(avgScore * 100) / 100,
    totalQuestions: allResults.length,
    questionResults: questionResults,
    cacheHits: questionResults.filter(q => q.fromCache).length,
    cacheMisses: questionResults.filter(q => !q.fromCache).length
  }
}];"""
        
        fixed = True
        print(f"   ✓ Fixed code in node: {node['name']} (id: {node['id']})")
        break

if not fixed:
    print("   ✗ Aggregate Scores node not found!")
else:
    # Write the modified workflow
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print("\n✓ Aggregate Scores fixed successfully!")
    print("\nChanges:")
    print("  - Now reads from $input.all() instead of $('Parse AI Response').all()")
    print("  - Works with both cached and non-cached evaluation paths")
    print("  - Adds cache hit/miss statistics to output")
    print("  - Includes fromCache flag in questionResults")
