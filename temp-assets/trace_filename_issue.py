#!/usr/bin/env python3
"""
Trace Filename Issue in Workflow C2
Extracts specific node outputs to identify where original filenames are lost
"""

import json
import sys

def extract_node_data(execution_file, node_name):
    """Extract data from a specific node in the execution log"""
    with open(execution_file, 'r') as f:
        data = json.load(f)
    
    # Parse the execution_data field
    exec_data = data.get('execution_data')
    if isinstance(exec_data, str):
        exec_data = json.loads(exec_data)
    
    # Navigate to runData
    run_data = exec_data[4] if isinstance(exec_data, list) and len(exec_data) > 4 else {}
    
    if node_name in run_data:
        node_runs = run_data[node_name]
        return node_runs
    
    return None

def main():
    execution_file = 'execution_4988_detailed.json'
    
    # Key nodes to trace
    nodes_to_check = [
        'Split by Question',
        'Prepare Files for Extraction',
        'Call Workflow A: Extract',
        'Combine Extraction Results',
        'Consolidate Evidence Text',
        'Build AI Prompt',
        'Parse AI Response'
    ]
    
    print("=" * 80)
    print("TRACING FILENAME DATA FLOW - Execution 4988")
    print("=" * 80)
    
    for node_name in nodes_to_check:
        print(f"\n{'=' * 80}")
        print(f"NODE: {node_name}")
        print('=' * 80)
        
        node_data = extract_node_data(execution_file, node_name)
        
        if not node_data:
            print(f"❌ Node '{node_name}' not found in execution data")
            continue
        
        # Extract first run, first output item
        try:
            first_run = node_data[0]
            output_data = first_run.get('data', {}).get('main', [[]])[0]
            
            if not output_data:
                print(f"⚠️  No output data for '{node_name}'")
                continue
            
            first_item = output_data[0]
            json_data = first_item.get('json', {})
            
            # Extract relevant fields based on node
            if node_name == 'Split by Question':
                print(f"📋 fileMap structure:")
                file_map = json_data.get('fileMap', {})
                for key, value in file_map.items():
                    print(f"  {key}: {value}")
                print(f"\n📋 evidenceFiles:")
                evidence_files = json_data.get('evidenceFiles', [])
                for ef in evidence_files:
                    print(f"  {ef}")
            
            elif node_name == 'Prepare Files for Extraction':
                print(f"📋 filename: {json_data.get('filename')}")
                print(f"📋 hash: {json_data.get('hash')}")
                print(f"📋 sessionId: {json_data.get('sessionId')}")
            
            elif node_name == 'Call Workflow A: Extract':
                print(f"📋 originalFileName: {json_data.get('originalFileName')}")
                print(f"📋 filePrefix: {json_data.get('filePrefix')}")
                print(f"📋 totalPages: {json_data.get('totalPages')}")
            
            elif node_name == 'Combine Extraction Results':
                print(f"📋 filename: {json_data.get('filename')}")
                print(f"📋 fileHash: {json_data.get('fileHash')}")
                extracted_data = json_data.get('extractedData', {})
                print(f"📋 extractedData.originalFileName: {extracted_data.get('originalFileName')}")
            
            elif node_name == 'Consolidate Evidence Text':
                print(f"📋 sourceFiles:")
                source_files = json_data.get('sourceFiles', [])
                for sf in source_files:
                    print(f"  - filename: {sf.get('filename')}")
                    print(f"    hash: {sf.get('hash')}")
                    print(f"    pages: {sf.get('pages')}")
            
            elif node_name == 'Build AI Prompt':
                prompt_data = json_data.get('prompt', '')
                # Extract evidence summary section from prompt
                if 'Evidence files reviewed:' in prompt_data:
                    start = prompt_data.find('Evidence files reviewed:')
                    end = prompt_data.find('\n\n', start)
                    evidence_section = prompt_data[start:end] if end > start else prompt_data[start:start+200]
                    print(f"📋 Evidence section in prompt:")
                    print(f"  {evidence_section}")
                
                source_files = json_data.get('sourceFiles', [])
                print(f"\n📋 sourceFiles in promptData:")
                for sf in source_files:
                    print(f"  - filename: {sf.get('filename')}")
            
            elif node_name == 'Parse AI Response':
                evaluation = json_data.get('evaluation', {})
                evidence_summary = evaluation.get('evidence_summary', '')
                print(f"📋 evaluation.evidence_summary:")
                print(f"  {evidence_summary}")
                
                source_files = json_data.get('sourceFiles', [])
                print(f"\n📋 sourceFiles passed to Parse AI Response:")
                for sf in source_files:
                    print(f"  - filename: {sf.get('filename')}")
            
            # Print full JSON for debugging (truncated)
            print(f"\n📄 Full JSON output (first 500 chars):")
            json_str = json.dumps(json_data, indent=2)
            print(json_str[:500] + "..." if len(json_str) > 500 else json_str)
            
        except Exception as e:
            print(f"❌ Error extracting data from '{node_name}': {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("TRACE COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
