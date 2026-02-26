#!/usr/bin/env python3
"""
Debug execution 5721 error - check input data to Prepare File Writes
"""

import json

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
with open('execution_5721_error.json', 'r') as f:
    execution = json.load(f)

# Parse execution_data
exec_data_str = execution.get('execution_data', '[]')
exec_data = json.loads(exec_data_str)

# Resolve all references
resolved_data = resolve_references(exec_data)

# Extract runData
run_data = resolved_data[2].get('runData', {}) if len(resolved_data) > 2 else {}

# Check Parse & Validate Input output
if 'Parse & Validate Input' in run_data:
    print("=" * 80)
    print("PARSE & VALIDATE INPUT OUTPUT")
    print("=" * 80)
    
    node_runs = run_data['Parse & Validate Input']
    if node_runs and len(node_runs) > 0:
        output = node_runs[0].get('data', {}).get('main', [[]])[0]
        if output and len(output) > 0:
            item = output[0]
            json_data = item.get('json', {})
            binary_data = item.get('binary', {})
            
            print("\nJSON keys:", list(json_data.keys()))
            print("\nBinary keys:", list(binary_data.keys()))
            
            if binary_data:
                print("\nBinary data details:")
                for key, val in binary_data.items():
                    print(f"  {key}:")
                    if isinstance(val, dict):
                        print(f"    fileName: {val.get('fileName')}")
                        print(f"    mimeType: {val.get('mimeType')}")
                        print(f"    fileSize: {val.get('fileSize')}")
                    else:
                        print(f"    Type: {type(val)}")

# Check Create Audit Session output
if 'Create Audit Session' in run_data:
    print("\n" + "=" * 80)
    print("CREATE AUDIT SESSION OUTPUT")
    print("=" * 80)
    
    node_runs = run_data['Create Audit Session']
    if node_runs and len(node_runs) > 0:
        output = node_runs[0].get('data', {}).get('main', [[]])[0]
        if output and len(output) > 0:
            item = output[0]
            json_data = item.get('json', {})
            
            print("\nJSON data:")
            print(json.dumps(json_data, indent=2))

# Check Prepare File Writes error details
if 'Prepare File Writes' in run_data:
    print("\n" + "=" * 80)
    print("PREPARE FILE WRITES ERROR DETAILS")
    print("=" * 80)
    
    node_runs = run_data['Prepare File Writes']
    if node_runs and len(node_runs) > 0:
        first_run = node_runs[0]
        error = first_run.get('error', {})
        
        print("\nError message:", error.get('message'))
        print("\nFull error:")
        print(json.dumps(error, indent=2))
