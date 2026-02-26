#!/usr/bin/env python3
"""
Debug C2 execution - trace filename data flow
"""

import json
import sys

def resolve_references(data, index_map=None):
    if index_map is None:
        if isinstance(data, list):
            index_map = {str(i): data[i] for i in range(len(data))}
        else:
            return data
    
    if isinstance(data, str) and data.isdigit():
        ref_data = index_map.get(data)
        if ref_data is not None:
            return resolve_references(ref_data, index_map)
        return data
    elif isinstance(data, list):
        return [resolve_references(item, index_map) for item in data]
    elif isinstance(data, dict):
        return {k: resolve_references(v, index_map) for k, v in data.items()}
    else:
        return data

# Load execution log
exec_file = sys.argv[1] if len(sys.argv) > 1 else 'execution_5852.json'
with open(exec_file, 'r') as f:
    execution = json.load(f)

# Parse execution_data
exec_data_str = execution.get('execution_data', '[]')
exec_data = json.loads(exec_data_str)

# Resolve all references
resolved_data = resolve_references(exec_data)

# Extract runData
run_data = resolved_data[2].get('runData', {}) if len(resolved_data) > 2 else {}

# Check specific nodes
nodes_to_check = [
    'Split by Question',
    'Combine Extraction Results', 
    'Consolidate Evidence Text',
    'Parse AI Response'
]

for node_name in nodes_to_check:
    if node_name in run_data:
        print("=" * 80)
        print(f"NODE: {node_name}")
        print("=" * 80)
        
        node_runs = run_data[node_name]
        if node_runs and len(node_runs) > 0:
            output = node_runs[0].get('data', {}).get('main', [[]])[0]
            
            if output:
                for idx, item in enumerate(output[:2]):  # First 2 items
                    json_data = item.get('json', {})
                    
                    print(f"\nItem {idx}:")
                    
                    if node_name == 'Split by Question':
                        print(f"  fileMap keys: {list(json_data.get('fileMap', {}).keys())}")
                        if json_data.get('fileMap'):
                            for key, val in list(json_data.get('fileMap', {}).items())[:2]:
                                print(f"    {key}:")
                                print(f"      fileName: {val.get('fileName')}")
                                print(f"      hash: {val.get('hash')}")
                    
                    elif node_name == 'Combine Extraction Results':
                        print(f"  filename: {json_data.get('filename')}")
                        print(f"  fileHash: {json_data.get('fileHash')}")
                        extracted = json_data.get('extractedData', {})
                        print(f"  extractedData.originalFileName: {extracted.get('originalFileName')}")
                        print(f"  extractedData keys: {list(extracted.keys())[:5]}")
                    
                    elif node_name == 'Consolidate Evidence Text':
                        source_files = json_data.get('sourceFiles', [])
                        print(f"  sourceFiles ({len(source_files)} files):")
                        for sf in source_files[:2]:
                            print(f"    - filename: {sf.get('filename')}")
                            print(f"      hash: {sf.get('hash')}")
                    
                    elif node_name == 'Parse AI Response':
                        evaluation = json_data.get('evaluation', {})
                        print(f"  evaluation.evidence_summary: {evaluation.get('evidence_summary')}")
                        source_files = json_data.get('sourceFiles', [])
                        print(f"  sourceFiles ({len(source_files)} files):")
                        for sf in source_files[:2]:
                            print(f"    - filename: {sf.get('filename')}")
