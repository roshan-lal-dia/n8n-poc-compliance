#!/usr/bin/env python3
"""
Validate that the filename fix has been properly applied to both workflows
"""

import json
import sys

def validate_workflow_c1():
    """Validate Workflow C1 has the originalFileName fix"""
    print("=" * 80)
    print("VALIDATING WORKFLOW C1")
    print("=" * 80)
    
    with open('workflows/unifi-npc-compliance/workflow-c1-audit-entry.json', 'r') as f:
        workflow = json.load(f)
    
    issues = []
    
    # Check "Prepare File Writes" node
    prepare_node = None
    for node in workflow['nodes']:
        if node['name'] == 'Prepare File Writes':
            prepare_node = node
            break
    
    if not prepare_node:
        issues.append("❌ 'Prepare File Writes' node not found")
    else:
        code = prepare_node['parameters']['jsCode']
        if 'originalFileName: fileData.fileName' in code:
            print("✓ 'Prepare File Writes' preserves originalFileName")
        else:
            issues.append("❌ 'Prepare File Writes' does not preserve originalFileName")
    
    # Check "Aggregate Files" node
    aggregate_node = None
    for node in workflow['nodes']:
        if node['name'] == 'Aggregate Files':
            aggregate_node = node
            break
    
    if not aggregate_node:
        issues.append("❌ 'Aggregate Files' node not found")
    else:
        code = aggregate_node['parameters']['jsCode']
        if 'row.originalFileName' in code and 'fileName: originalName' in code:
            print("✓ 'Aggregate Files' uses originalFileName")
        else:
            issues.append("❌ 'Aggregate Files' does not use originalFileName")
    
    return issues

def validate_workflow_c2():
    """Validate Workflow C2 uses original filenames"""
    print("\n" + "=" * 80)
    print("VALIDATING WORKFLOW C2")
    print("=" * 80)
    
    with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
        workflow = json.load(f)
    
    issues = []
    
    # Check "Consolidate Evidence Text" node
    consolidate_node = None
    for node in workflow['nodes']:
        if node['name'] == 'Consolidate Evidence Text':
            consolidate_node = node
            break
    
    if not consolidate_node:
        issues.append("❌ 'Consolidate Evidence Text' node not found")
    else:
        code = consolidate_node['parameters']['jsCode']
        if 'Find original filename from fileMap' in code and 'fileInfo.fileName' in code:
            print("✓ 'Consolidate Evidence Text' looks up original filenames from fileMap")
        else:
            issues.append("❌ 'Consolidate Evidence Text' does not look up original filenames")
    
    # Check "Parse AI Response" node
    parse_node = None
    for node in workflow['nodes']:
        if node['name'] == 'Parse AI Response':
            parse_node = node
            break
    
    if not parse_node:
        issues.append("❌ 'Parse AI Response' node not found")
    else:
        code = parse_node['parameters']['jsCode']
        if 'Build evidence summary using original filenames' in code and 'sourceFiles.map(f => f.filename)' in code:
            print("✓ 'Parse AI Response' builds evidence summary with original filenames")
        else:
            issues.append("❌ 'Parse AI Response' does not build evidence summary correctly")
    
    return issues

def main():
    print("\n" + "=" * 80)
    print("FILENAME FIX VALIDATION")
    print("=" * 80 + "\n")
    
    c1_issues = validate_workflow_c1()
    c2_issues = validate_workflow_c2()
    
    all_issues = c1_issues + c2_issues
    
    print("\n" + "=" * 80)
    if not all_issues:
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 80)
        print("\nBoth workflows have been correctly updated to use original filenames.")
        print("\nNext steps:")
        print("1. Re-import Workflow C1 in n8n UI")
        print("2. Re-import Workflow C2 in n8n UI")
        print("3. Test with a new audit submission")
        print("4. Verify evidence_summary shows original filenames")
        return 0
    else:
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        print("\nIssues found:")
        for issue in all_issues:
            print(f"  {issue}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
