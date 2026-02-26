#!/usr/bin/env python3
"""
Final validation: Check workflow logic and data flow
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("=" * 70)
print("FINAL WORKFLOW VALIDATION - LOGIC & DATA FLOW")
print("=" * 70)

# Build node lookup
nodes_by_name = {node['name']: node for node in workflow['nodes']}
nodes_by_id = {node['id']: node for node in workflow['nodes']}

# Test 1: Verify cron trigger configuration
print("\n[TEST 1] Cron Trigger Configuration")
cron = nodes_by_name.get('Cron: Every 10s')
if cron:
    params = cron['parameters']
    interval = params.get('rule', {}).get('interval', [{}])[0]
    field = interval.get('field')
    seconds = interval.get('secondsInterval')
    
    if field == 'seconds' and seconds == 10:
        print("   ✓ Cron trigger: Every 10 seconds")
    else:
        print(f"   ✗ Cron trigger misconfigured: field={field}, interval={seconds}")
else:
    print("   ✗ Cron trigger node not found")

# Test 2: Verify master cache flow
print("\n[TEST 2] Master Cache Flow")
print("   Expected: Log: Question Start → Check Master Cache → Is Cached?")

log_start_conn = workflow['connections'].get('Log: Question Start', {}).get('main', [[]])[0]
if log_start_conn and log_start_conn[0]['node'] == 'Check Master Cache':
    print("   ✓ Log: Question Start → Check Master Cache")
else:
    print("   ✗ Log: Question Start not connected to Check Master Cache")

cache_check_conn = workflow['connections'].get('Check Master Cache', {}).get('main', [[]])[0]
if cache_check_conn and cache_check_conn[0]['node'] == 'Is Cached?':
    print("   ✓ Check Master Cache → Is Cached?")
else:
    print("   ✗ Check Master Cache not connected to Is Cached?")

# Test 3: Verify Is Cached? branches
print("\n[TEST 3] Is Cached? Branch Logic")
is_cached_branches = workflow['connections'].get('Is Cached?', {}).get('main', [[], []])

if len(is_cached_branches) >= 2:
    true_branch = is_cached_branches[0]
    false_branch = is_cached_branches[1]
    
    true_target = true_branch[0]['node'] if true_branch else None
    false_target = false_branch[0]['node'] if false_branch else None
    
    if true_target == 'Format Cached Response':
        print("   ✓ TRUE branch (cache hit) → Format Cached Response")
    else:
        print(f"   ✗ TRUE branch goes to '{true_target}' instead of 'Format Cached Response'")
    
    if false_target == 'Check Evidence Cache':
        print("   ✓ FALSE branch (cache miss) → Check Evidence Cache")
    else:
        print(f"   ✗ FALSE branch goes to '{false_target}' instead of 'Check Evidence Cache'")
else:
    print("   ✗ Is Cached? missing branches")

# Test 4: Verify cache bypass to Log Evaluation Result
print("\n[TEST 4] Cache Bypass Path")
format_cached_conn = workflow['connections'].get('Format Cached Response', {}).get('main', [[]])[0]
if format_cached_conn and format_cached_conn[0]['node'] == 'Log Evaluation Result':
    print("   ✓ Format Cached Response → Log Evaluation Result (bypasses extraction & RAG)")
else:
    print("   ✗ Format Cached Response not properly connected")

# Test 5: Verify normal flow still works
print("\n[TEST 5] Normal Flow (Cache Miss Path)")
normal_flow = [
    ('Check Evidence Cache', 'Prepare Files for Extraction'),
    ('Prepare Files for Extraction', 'Check if Extraction Needed'),
    ('Consolidate Evidence Text', 'Load Question'),
    ('Parse AI Response', 'Log Evaluation Result'),
    ('Log Evaluation Result', 'Aggregate Scores'),
    ('Aggregate Scores', 'Update Session: Completed')
]

all_ok = True
for source, target in normal_flow:
    source_conn = workflow['connections'].get(source, {}).get('main', [[]])[0]
    if source_conn:
        targets = [conn['node'] for conn in source_conn]
        if target in targets:
            print(f"   ✓ {source} → {target}")
        else:
            print(f"   ✗ {source} not connected to {target}")
            all_ok = False
    else:
        print(f"   ✗ {source} has no connections")
        all_ok = False

# Test 6: Verify Cleanup: Evidence DB is removed
print("\n[TEST 6] Evidence Persistence")
if 'Cleanup: Evidence DB' in nodes_by_name:
    print("   ✗ 'Cleanup: Evidence DB' node still exists (should be removed)")
else:
    print("   ✓ 'Cleanup: Evidence DB' node removed (evidence persists)")

# Test 7: Check master cache query structure
print("\n[TEST 7] Master Cache Query Structure")
cache_node = nodes_by_name.get('Check Master Cache')
if cache_node:
    query = cache_node['parameters'].get('query', '')
    
    checks = [
        ('WITH current_hashes', 'CTE for current file hashes'),
        ('matching_sessions', 'CTE for matching sessions'),
        ('UNION ALL', 'Fallback for cache miss'),
        ('WHERE NOT EXISTS', 'Ensures fallback only when no match'),
        ('NULL::jsonb as ai_response', 'Returns NULL on cache miss')
    ]
    
    for pattern, description in checks:
        if pattern in query:
            print(f"   ✓ {description}")
        else:
            print(f"   ✗ Missing: {description}")
else:
    print("   ✗ Check Master Cache node not found")

# Test 8: Verify Format Cached Response code
print("\n[TEST 8] Format Cached Response Logic")
format_node = nodes_by_name.get('Format Cached Response')
if format_node:
    code = format_node['parameters'].get('jsCode', '')
    
    checks = [
        ('$input.first().json', 'Reads cached data'),
        ("$('Split by Question').item.json", 'Gets question context'),
        ('fromMasterCache: true', 'Marks as cached'),
        ('evaluation:', 'Includes evaluation object'),
        ('questionIndex:', 'Preserves question index'),
        ('totalQuestions:', 'Preserves total questions')
    ]
    
    for pattern, description in checks:
        if pattern in code:
            print(f"   ✓ {description}")
        else:
            print(f"   ✗ Missing: {description}")
else:
    print("   ✗ Format Cached Response node not found")

# Final summary
print("\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)
print(f"\nTotal nodes: {len(workflow['nodes'])}")
print(f"Total connections: {len(workflow['connections'])}")
print("\nWorkflow is ready for:")
print("  1. Import into n8n UI")
print("  2. Testing with duplicate submissions")
print("  3. Monitoring cache hit rates")
print("\n" + "=" * 70)
