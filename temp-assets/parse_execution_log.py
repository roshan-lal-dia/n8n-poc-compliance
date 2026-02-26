#!/usr/bin/env python3
"""
Parse n8n execution log with proper JSON reference resolution
"""

import json

def resolve_references(data, index_map=None):
    """Recursively resolve string references to actual data"""
    if index_map is None:
        # Build index map on first call
        if isinstance(data, list):
            index_map = {str(i): data[i] for i in range(len(data))}
        else:
            return data
    
    if isinstance(data, str) and data.isdigit():
        # This is a reference, resolve it
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

def main():
    # Load execution log
    with open('execution_4988_detailed.json', 'r') as f:
        execution = json.load(f)
    
    # Parse execution_data
    exec_data_str = execution.get('execution_data', '[]')
    exec_data = json.loads(exec_data_str)
    
    # Resolve all references
    resolved_data = resolve_references(exec_data)
    
    # Extract runData (should be at index 4 based on structure)
    run_data = resolved_data[2].get('runData', {}) if len(resolved_data) > 2 else {}
    
    print("=" * 80)
    print("AVAILABLE NODES IN EXECUTION:")
    print("=" * 80)
    for node_name in run_data.keys():
        print(f"  - {node_name}")
    
    # Now extract specific nodes
    nodes_to_check = [
        'Parse Job (Exit if Empty)',
        'Split by Question',
        'Prepare Files for Extraction',
        'Call Workflow A: Extract',
        'Combine Extraction Results',
        'Consolidate Evidence Text',
        'Build AI Prompt',
        'Parse AI Response'
    ]
    
    for node_name in nodes_to_check:
        if node_name not in run_data:
            print(f"\n❌ Node '{node_name}' not found")
            continue
        
        print(f"\n{'=' * 80}")
        print(f"NODE: {node_name}")
        print('=' * 80)
        
        node_runs = run_data[node_name]
        if not node_runs or len(node_runs) == 0:
            print("No execution data")
            continue
        
        first_run = node_runs[0]
        output_data = first_run.get('data', {}).get('main', [[]])[0]
        
        if not output_data:
            print("No output items")
            continue
        
        # Print all items (in case there are multiple)
        for idx, item in enumerate(output_data):
            json_data = item.get('json', {})
            
            print(f"\n--- Item {idx} ---")
            
            if node_name == 'Parse Job (Exit if Empty)':
                print(f"fileMap: {json.dumps(json_data.get('fileMap', {}), indent=2)}")
                print(f"questions: {json.dumps(json_data.get('questions', []), indent=2)}")
            
            elif node_name == 'Split by Question':
                print(f"fileMap: {json.dumps(json_data.get('fileMap', {}), indent=2)}")
                print(f"evidenceFiles: {json_data.get('evidenceFiles', [])}")
            
            elif node_name == 'Prepare Files for Extraction':
                print(f"filename: {json_data.get('filename')}")
                print(f"hash: {json_data.get('hash')}")
            
            elif node_name == 'Call Workflow A: Extract':
                print(f"originalFileName: {json_data.get('originalFileName')}")
                print(f"filePrefix: {json_data.get('filePrefix')}")
            
            elif node_name == 'Combine Extraction Results':
                print(f"filename: {json_data.get('filename')}")
                extracted_data = json_data.get('extractedData', {})
                print(f"extractedData.originalFileName: {extracted_data.get('originalFileName')}")
            
            elif node_name == 'Consolidate Evidence Text':
                source_files = json_data.get('sourceFiles', [])
                print(f"sourceFiles ({len(source_files)} files):")
                for sf in source_files:
                    print(f"  - filename: {sf.get('filename')}")
                    print(f"    hash: {sf.get('hash')}")
            
            elif node_name == 'Build AI Prompt':
                source_files = json_data.get('sourceFiles', [])
                print(f"sourceFiles ({len(source_files)} files):")
                for sf in source_files:
                    print(f"  - filename: {sf.get('filename')}")
            
            elif node_name == 'Parse AI Response':
                evaluation = json_data.get('evaluation', {})
                evidence_summary = evaluation.get('evidence_summary', '')
                print(f"evaluation.evidence_summary:")
                print(f"  {evidence_summary}")
                
                source_files = json_data.get('sourceFiles', [])
                print(f"\nsourceFiles ({len(source_files)} files):")
                for sf in source_files:
                    print(f"  - filename: {sf.get('filename')}")

if __name__ == '__main__':
    main()
