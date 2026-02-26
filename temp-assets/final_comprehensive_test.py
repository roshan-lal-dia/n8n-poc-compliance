#!/usr/bin/env python3
"""
Final comprehensive test of the workflow structure.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("=" * 70)
print("FINAL COMPREHENSIVE WORKFLOW TEST")
print("=" * 70)

# Build lookups
nodes_by_name = {node['name']: node for node in workflow['nodes']}
connections = workflow['connections']

all_tests_passed = True

# Test 1: Verify both paths feed Aggregate Scores
print("\n[TEST 1] Data Flow to Aggregate Scores")
parse_ai_targets = connections.get('Parse AI Response', {}).get('main', [[]])[0]
format_cached_targets = connections.get('Format Cached Response', {}).get('main', [[]])[0]

parse_ai_has_aggregate = any(t['node'] == 'Aggregate Scores' for t in parse_ai_targets)
format_cached_has_aggregate = any(t['node'] == 'Aggregate Scores' for t in format_cached_targets)

if parse_ai_has_aggregate:
    print("   ✓ Parse AI Response → Aggregate Scores")
else:
    print("   ✗ Parse AI Response does NOT connect to Aggregate Scores")
    all_tests_passed = False

if format_cached_has_aggregate:
    print("   ✓ Format Cached Response → Aggregate Scores")
else:
    print("   ✗ Format Cached Response does NOT connect to Aggregate Scores")
    all_tests_passed = False

# Test 2: Verify Aggregate Scores uses $input.all()
print("\n[TEST 2] Aggregate Scores Code")
aggregate_node = nodes_by_name.get('Aggregate Scores')
if aggregate_node:
    code = aggregate_node['parameters'].get('jsCode', '')
    
    if '$input.all()' in code:
        print("   ✓ Uses $input.all() (works with both paths)")
    else:
        print("   ✗ Does NOT use $input.all()")
        all_tests_passed = False
    
    if "$('Parse AI Response')" not in code:
        print("   ✓ Does NOT reference Parse AI Response directly")
    else:
        print("   ✗ Still references Parse AI Response (will fail on cache hit)")
        all_tests_passed = False
else:
    print("   ✗ Aggregate Scores node not found")
    all_tests_passed = False

# Test 3: Verify cache query structure
print("\n[TEST 3] Master Cache Query")
cache_node = nodes_by_name.get('Check Master Cache')
if cache_node:
    query = cache_node['parameters'].get('query', '')
    
    if 'LEFT JOIN' in query and 'COALESCE' in query:
        print("   ✓ Uses LEFT JOIN with COALESCE (always returns 1 row)")
    else:
        print("   ✗ Query structure incorrect")
        all_tests_passed = False
    
    if 'FROM (SELECT 1) as dummy' in query:
        print("   ✓ Has dummy table for guaranteed row")
    else:
        print("   ✗ Missing dummy table")
        all_tests_passed = False
else:
    print("   ✗ Check Master Cache node not found")
    all_tests_passed = False

# Test 4: Verify both paths log results
print("\n[TEST 4] Logging Path")
parse_ai_has_log = any(t['node'] == 'Log Evaluation Result' for t in parse_ai_targets)
format_cached_has_log = any(t['node'] == 'Log Evaluation Result' for t in format_cached_targets)

if parse_ai_has_log:
    print("   ✓ Parse AI Response → Log Evaluation Result")
else:
    print("   ✗ Parse AI Response does NOT log results")
    all_tests_passed = False

if format_cached_has_log:
    print("   ✓ Format Cached Response → Log Evaluation Result")
else:
    print("   ✗ Format Cached Response does NOT log results")
    all_tests_passed = False

# Test 5: Verify Format Cached Response structure
print("\n[TEST 5] Format Cached Response Output")
format_node = nodes_by_name.get('Format Cached Response')
if format_node:
    code = format_node['parameters'].get('jsCode', '')
    
    required_fields = [
        'sessionId',
        'qId',
        'evaluation',
        'questionIndex',
        'totalQuestions',
        'fromMasterCache'
    ]
    
    all_fields_present = all(field in code for field in required_fields)
    
    if all_fields_present:
        print("   ✓ All required fields present in output")
    else:
        missing = [f for f in required_fields if f not in code]
        print(f"   ✗ Missing fields: {', '.join(missing)}")
        all_tests_passed = False
else:
    print("   ✗ Format Cached Response node not found")
    all_tests_passed = False

# Test 6: Verify Is Cached? condition
print("\n[TEST 6] Is Cached? Condition")
is_cached_node = nodes_by_name.get('Is Cached?')
if is_cached_node:
    conditions = is_cached_node['parameters'].get('conditions', {}).get('conditions', [])
    
    if conditions:
        condition = conditions[0]
        left_value = condition.get('leftValue', '')
        
        if 'ai_response' in left_value and 'null' in left_value.lower():
            print("   ✓ Checks if ai_response is not null")
        else:
            print(f"   ✗ Condition incorrect: {left_value}")
            all_tests_passed = False
    else:
        print("   ✗ No conditions defined")
        all_tests_passed = False
else:
    print("   ✗ Is Cached? node not found")
    all_tests_passed = False

# Final summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Total nodes: {len(workflow['nodes'])}")
print(f"Total connections: {len(workflow['connections'])}")

if all_tests_passed:
    print("\n✅ ALL TESTS PASSED - Workflow is ready!")
    print("\nThe workflow will now:")
    print("  1. Check master cache on every question")
    print("  2. On cache hit: Format Cached Response → [Log, Aggregate]")
    print("  3. On cache miss: Parse AI Response → [Log, Aggregate]")
    print("  4. Aggregate Scores receives data from both paths")
    print("  5. No more 'Parse AI Response hasn't been executed' errors")
else:
    print("\n⚠️  SOME TESTS FAILED - Review above")

print("\n" + "=" * 70)
