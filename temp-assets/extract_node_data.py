#!/usr/bin/env python3
"""
Extract specific node execution data from n8n execution log
"""

import json
import sys

# Read the execution log
with open('execution_4988_full.json', 'r') as f:
    data = json.load(f)

# Nodes we want to inspect
target_nodes = [
    'Split by Question',
    'Prepare Files for Extraction', 
    'Call Workflow A: Extract',
    'Combine Extraction Results',
    'Consolidate Evidence Text',
    'Build AI Prompt',
    'Parse AI Response'
]

print("=== EXECUTION DATA ANALYSIS ===\n")

# Try to find node execution data
if 'data' in data and 'resultData' in data['data']:
    result_data = data['data']['resultData']
    
    if 'runData' in result_data:
        run_data = result_data['runData']
        
        for node_name in target_nodes:
            if node_name in run_data:
                print(f"\n{'='*60}")
                print(f"NODE: {node_name}")
                print(f"{'='*60}")
                
                node_data = run_data[node_name]
                if isinstance(node_data, list) and len(node_data) > 0:
                    first_run = node_data[0]
                    
                    if 'data' in first_run and 'main' in first_run['data']:
                        main_data = first_run['data']['main']
                        
                        if isinstance(main_data, list) and len(main_data) > 0:
                            items = main_data[0]
                            
                            print(f"\nNumber of items: {len(items)}")
                            
                            # Print first item's JSON (truncated)
                            if len(items) > 0:
                                first_item = items[0]
                                if 'json' in first_item:
                                    json_str = json.dumps(first_item['json'], indent=2)
                                    
                                    # Truncate long strings
                                    if len(json_str) > 2000:
                                        print(f"\nFirst item JSON (truncated):")
                                        print(json_str[:2000])
                                        print("\n... (truncated)")
                                    else:
                                        print(f"\nFirst item JSON:")
                                        print(json_str)
                                        
                                # Check for specific fields we care about
                                if node_name == 'Split by Question':
                                    if 'fileMap' in first_item['json']:
                                        print("\n--- fileMap structure ---")
                                        for key, val in first_item['json']['fileMap'].items():
                                            print(f"  {key}: fileName={val.get('fileName', 'N/A')}")
                                            
                                elif node_name == 'Call Workflow A: Extract':
                                    if 'originalFileName' in first_item['json']:
                                        print(f"\n--- originalFileName: {first_item['json']['originalFileName']}")
                                        
                                elif node_name == 'Consolidate Evidence Text':
                                    if 'sourceFiles' in first_item['json']:
                                        print("\n--- sourceFiles ---")
                                        for sf in first_item['json']['sourceFiles']:
                                            print(f"  filename: {sf.get('filename', 'N/A')}")
                                            
                                elif node_name == 'Parse AI Response':
                                    if 'evaluation' in first_item['json']:
                                        eval_data = first_item['json']['evaluation']
                                        if 'evidence_summary' in eval_data:
                                            print(f"\n--- evidence_summary ---")
                                            print(eval_data['evidence_summary'])
            else:
                print(f"\n{'='*60}")
                print(f"NODE: {node_name} - NOT FOUND IN EXECUTION")
                print(f"{'='*60}")
else:
    print("Could not find execution data in the log file")
    print(f"Available keys: {list(data.keys())}")
