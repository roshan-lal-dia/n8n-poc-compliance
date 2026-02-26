#!/usr/bin/env python3
"""
Check what data Workflow C1 receives from the webhook
"""

import json

def resolve_references(data, index_map=None):
    """Recursively resolve string references to actual data"""
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
with open('execution_c1_4986.json', 'r') as f:
    execution = json.load(f)

# Parse execution_data
exec_data_str = execution.get('execution_data', '[]')
exec_data = json.loads(exec_data_str)

# Resolve all references
resolved_data = resolve_references(exec_data)

# Extract runData
run_data = resolved_data[2].get('runData', {}) if len(resolved_data) > 2 else {}

# Check webhook node
if 'Webhook: Submit Audit' in run_data:
    print("=" * 80)
    print("WEBHOOK NODE OUTPUT")
    print("=" * 80)
    
    webhook_runs = run_data['Webhook: Submit Audit']
    if webhook_runs and len(webhook_runs) > 0:
        first_run = webhook_runs[0]
        output_data = first_run.get('data', {}).get('main', [[]])[0]
        
        if output_data and len(output_data) > 0:
            item = output_data[0]
            json_data = item.get('json', {})
            binary_data = item.get('binary', {})
            
            print("\nJSON fields:")
            for key in json_data.keys():
                print(f"  - {key}")
            
            print("\nBinary fields:")
            for field_name, binary_info in binary_data.items():
                print(f"  - {field_name}:")
                print(f"      fileName: {binary_info.get('fileName')}")
                print(f"      mimeType: {binary_info.get('mimeType')}")
                print(f"      fileSize: {binary_info.get('fileSize')}")

# Check Parse & Validate Input node
if 'Parse & Validate Input' in run_data:
    print("\n" + "=" * 80)
    print("PARSE & VALIDATE INPUT NODE OUTPUT")
    print("=" * 80)
    
    parse_runs = run_data['Parse & Validate Input']
    if parse_runs and len(parse_runs) > 0:
        first_run = parse_runs[0]
        output_data = first_run.get('data', {}).get('main', [[]])[0]
        
        if output_data and len(output_data) > 0:
            item = output_data[0]
            json_data = item.get('json', {})
            
            print("\nfiles metadata:")
            files = json_data.get('files', [])
            for f in files:
                print(f"  - fieldName: {f.get('fieldName')}")
                print(f"    fileName: {f.get('fileName')}")
                print(f"    fileSize: {f.get('fileSize')}")

# Check Prepare File Writes node
if 'Prepare File Writes' in run_data:
    print("\n" + "=" * 80)
    print("PREPARE FILE WRITES NODE OUTPUT")
    print("=" * 80)
    
    prepare_runs = run_data['Prepare File Writes']
    if prepare_runs and len(prepare_runs) > 0:
        first_run = prepare_runs[0]
        output_data = first_run.get('data', {}).get('main', [[]])[0]
        
        if output_data:
            print(f"\nTotal items: {len(output_data)}")
            for idx, item in enumerate(output_data):
                json_data = item.get('json', {})
                print(f"\n  Item {idx}:")
                print(f"    fieldName: {json_data.get('fieldName')}")
                print(f"    fileName: {json_data.get('fileName')}")
                print(f"    filePath: {json_data.get('filePath')}")
                print(f"    hash: {json_data.get('hash')}")

# Check Aggregate Files node
if 'Aggregate Files' in run_data:
    print("\n" + "=" * 80)
    print("AGGREGATE FILES NODE OUTPUT")
    print("=" * 80)
    
    agg_runs = run_data['Aggregate Files']
    if agg_runs and len(agg_runs) > 0:
        first_run = agg_runs[0]
        output_data = first_run.get('data', {}).get('main', [[]])[0]
        
        if output_data and len(output_data) > 0:
            item = output_data[0]
            json_data = item.get('json', {})
            file_map = json_data.get('fileMap', {})
            
            print("\nfileMap:")
            for field_name, file_info in file_map.items():
                print(f"  {field_name}:")
                print(f"    fileName: {file_info.get('fileName')}")
                print(f"    filePath: {file_info.get('filePath')}")
                print(f"    hash: {file_info.get('hash')}")
