#!/usr/bin/env python3
"""
Comprehensive workflow fixes:
1. Fix cron trigger to use seconds (10s interval)
2. Verify all node connections are valid
3. Check for duplicate nodes
4. Verify master cache query has UNION ALL fallback
5. Ensure all node references in connections exist
"""

import json
import sys

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("=" * 60)
print("COMPREHENSIVE WORKFLOW VALIDATION & FIXES")
print("=" * 60)

# Issue 1: Fix Cron Trigger to use seconds
print("\n[1] Fixing Cron Trigger...")
cron_fixed = False
for node in workflow['nodes']:
    if node['name'] == 'Cron: Every 10s' and node['type'] == 'n8n-nodes-base.scheduleTrigger':
        # Change from minutes to seconds with 10 second interval
        node['parameters'] = {
            "rule": {
                "interval": [
                    {
                        "field": "seconds",
                        "secondsInterval": 10
                    }
                ]
            }
        }
        cron_fixed = True
        print("   ✓ Changed cron trigger from 'minutes' to 'seconds' (10s interval)")
        break

if not cron_fixed:
    print("   ⚠ Warning: Cron trigger node not found")

# Issue 2: Check for duplicate nodes
print("\n[2] Checking for duplicate nodes...")
node_names = {}
duplicates = []
for node in workflow['nodes']:
    name = node['name']
    if name in node_names:
        duplicates.append(name)
        print(f"   ⚠ Duplicate found: {name}")
    else:
        node_names[name] = node['id']

if not duplicates:
    print("   ✓ No duplicate nodes found")

# Issue 3: Verify master cache query
print("\n[3] Verifying Master Cache query...")
master_cache_ok = False
for node in workflow['nodes']:
    if node['name'] == 'Check Master Cache':
        query = node['parameters'].get('query', '')
        if 'UNION ALL' in query and 'WHERE NOT EXISTS' in query:
            master_cache_ok = True
            print("   ✓ Master cache query has UNION ALL fallback")
        else:
            print("   ✗ Master cache query missing UNION ALL fallback")
        break

if not master_cache_ok and 'Check Master Cache' in node_names:
    print("   ⚠ Master cache query needs fixing")

# Issue 4: Verify all connections reference existing nodes
print("\n[4] Validating node connections...")
connection_errors = []
for source_node, connections in workflow['connections'].items():
    if source_node not in node_names:
        connection_errors.append(f"Source node '{source_node}' in connections but not in nodes")
        continue
    
    for output_type, output_branches in connections.items():
        for branch_idx, branch_connections in enumerate(output_branches):
            for conn in branch_connections:
                target_node = conn.get('node')
                if target_node and target_node not in node_names:
                    connection_errors.append(
                        f"Connection from '{source_node}' references non-existent node '{target_node}'"
                    )

if connection_errors:
    print(f"   ✗ Found {len(connection_errors)} connection errors:")
    for error in connection_errors:
        print(f"      - {error}")
else:
    print("   ✓ All connections reference valid nodes")

# Issue 5: Verify critical path exists
print("\n[5] Verifying critical workflow paths...")
critical_nodes = [
    'Cron: Every 10s',
    'Dequeue Job from Redis',
    'Parse Job (Exit if Empty)',
    'Split by Question',
    'Log: Question Start',
    'Check Master Cache',
    'Is Cached?',
    'Format Cached Response',
    'Check Evidence Cache',
    'Log Evaluation Result',
    'Aggregate Scores',
    'Update Session: Completed'
]

missing_critical = []
for node_name in critical_nodes:
    if node_name not in node_names:
        missing_critical.append(node_name)

if missing_critical:
    print(f"   ✗ Missing critical nodes:")
    for node in missing_critical:
        print(f"      - {node}")
else:
    print("   ✓ All critical nodes present")

# Issue 6: Check for orphaned nodes (nodes with no incoming connections)
print("\n[6] Checking for orphaned nodes...")
nodes_with_incoming = set()
for source_node, connections in workflow['connections'].items():
    for output_type, output_branches in connections.items():
        for branch_connections in output_branches:
            for conn in branch_connections:
                target_node = conn.get('node')
                if target_node:
                    nodes_with_incoming.add(target_node)

# Trigger nodes don't need incoming connections
trigger_nodes = ['Cron: Every 10s']
orphaned = []
for node in workflow['nodes']:
    name = node['name']
    if name not in nodes_with_incoming and name not in trigger_nodes:
        orphaned.append(name)

if orphaned:
    print(f"   ⚠ Found {len(orphaned)} potentially orphaned nodes:")
    for node in orphaned:
        print(f"      - {node}")
else:
    print("   ✓ No orphaned nodes found")

# Issue 7: Verify Format Cached Response connects to Log Evaluation Result
print("\n[7] Verifying cache bypass path...")
cache_path_ok = False
if 'Format Cached Response' in workflow['connections']:
    targets = workflow['connections']['Format Cached Response']['main'][0]
    if any(conn['node'] == 'Log Evaluation Result' for conn in targets):
        cache_path_ok = True
        print("   ✓ Format Cached Response → Log Evaluation Result connected")
    else:
        print("   ✗ Format Cached Response not connected to Log Evaluation Result")
else:
    print("   ⚠ Format Cached Response has no outgoing connections")

# Issue 8: Verify Is Cached? has both TRUE and FALSE branches
print("\n[8] Verifying Is Cached? IF node branches...")
if 'Is Cached?' in workflow['connections']:
    branches = workflow['connections']['Is Cached?']['main']
    if len(branches) >= 2:
        true_branch = branches[0]
        false_branch = branches[1]
        
        true_target = true_branch[0]['node'] if true_branch else None
        false_target = false_branch[0]['node'] if false_branch else None
        
        print(f"   ✓ TRUE branch → {true_target}")
        print(f"   ✓ FALSE branch → {false_target}")
        
        if true_target != 'Format Cached Response':
            print(f"   ⚠ Warning: TRUE branch should go to 'Format Cached Response', not '{true_target}'")
        if false_target != 'Check Evidence Cache':
            print(f"   ⚠ Warning: FALSE branch should go to 'Check Evidence Cache', not '{false_target}'")
    else:
        print("   ✗ Is Cached? node missing TRUE or FALSE branch")
else:
    print("   ⚠ Is Cached? node has no connections")

# Write the fixed workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total nodes: {len(workflow['nodes'])}")
print(f"Total connections: {len(workflow['connections'])}")
print(f"Cron trigger: {'✓ Fixed to 10 seconds' if cron_fixed else '✗ Not fixed'}")
print(f"Duplicates: {'✗ Found ' + str(len(duplicates)) if duplicates else '✓ None'}")
print(f"Connection errors: {'✗ Found ' + str(len(connection_errors)) if connection_errors else '✓ None'}")
print(f"Critical nodes: {'✗ Missing ' + str(len(missing_critical)) if missing_critical else '✓ All present'}")
print(f"Master cache: {'✓ OK' if master_cache_ok else '✗ Needs fix'}")
print(f"Cache bypass path: {'✓ OK' if cache_path_ok else '✗ Needs fix'}")

if not connection_errors and not missing_critical and cron_fixed and master_cache_ok and cache_path_ok:
    print("\n✅ Workflow is ready for import!")
else:
    print("\n⚠️  Some issues detected - review above")

print("\n" + "=" * 60)
