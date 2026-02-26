# How to Use the n8n Log Exporter for Debugging

## Overview
The `scripts/export_n8n_logs.py` tool extracts execution logs from the n8n PostgreSQL database, allowing you to analyze workflow execution data, trace data flow, and debug issues.

## Prerequisites

### 1. Install Dependencies
```bash
source venv/bin/activate
pip install psycopg2-binary
```

### 2. Database Connection
The script uses these environment variables (with defaults):
- `DB_HOST` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5432)
- `DB_NAME` - Database name (default: compliance_db)
- `DB_USER` - Database user (default: n8n)
- `DB_PASSWORD` - Database password (default: ComplianceDB2026!)

If your setup differs, export the variables:
```bash
export DB_HOST=your-host
export DB_PASSWORD=your-password
```

## Basic Usage

### 1. List Recent Executions
See the last 10 workflow executions:
```bash
python3 scripts/export_n8n_logs.py --list-recent
```

Output:
```
================================================================================
ID         Workflow                            Mode       Status     Started              Duration  
================================================================================
4988       Workflow C2: Audit Worker           trigger    success    2026-02-26 12:42:50  543.7s    
4986       Workflow C1: Audit Entry            webhook    success    2026-02-26 12:42:46  0.5s      
================================================================================
```

Increase limit:
```bash
python3 scripts/export_n8n_logs.py --list-recent --limit 20
```

### 2. List Failed Executions
Find executions that failed for debugging:
```bash
python3 scripts/export_n8n_logs.py --list-failed --limit 10
```

### 3. Filter by Workflow Name
Get executions for a specific workflow:
```bash
python3 scripts/export_n8n_logs.py --workflow "Workflow C2" --limit 5
```

Partial name matching works:
```bash
python3 scripts/export_n8n_logs.py --workflow "Audit Worker"
```

### 4. Export Specific Execution
Export a single execution by ID:
```bash
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json
```

## Export Formats

### JSON Format (Default)
Complete execution data with all node outputs:
```bash
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json
```

**Use case:** Programmatic analysis, detailed debugging

### CSV Format
Flattened execution summary:
```bash
python3 scripts/export_n8n_logs.py 4988 --format csv --output execution_4988.csv
```

**Use case:** Quick overview, spreadsheet analysis

### Text Format
Human-readable execution summary:
```bash
python3 scripts/export_n8n_logs.py 4988 --format text --output execution_4988.txt
```

Or print to console:
```bash
python3 scripts/export_n8n_logs.py 4988 --format text
```

**Use case:** Quick inspection, sharing with team

## Advanced Usage

### Include Custom Metadata
If you're using the Execution Data node to store custom metadata:
```bash
python3 scripts/export_n8n_logs.py 4988 --metadata --format json --output execution_4988_full.json
```

### Export Multiple Executions
Export all executions for a workflow:
```bash
python3 scripts/export_n8n_logs.py --workflow "Workflow C2" --limit 10 --format json --output c2_executions.json
```

## Analyzing Exported Logs

### Understanding the JSON Structure
The exported JSON contains:
```json
{
  "id": 4988,
  "workflowId": "Noo1o2CwElfpL0h8FlSw2",
  "workflow_name": "Workflow C2: Audit Worker",
  "status": "success",
  "startedAt": "2026-02-26 12:42:50.008000+00:00",
  "stoppedAt": "2026-02-26 12:51:53.694000+00:00",
  "execution_data": "[...]"  // Compressed JSON with node execution data
}
```

The `execution_data` field contains a compressed JSON array with references. To parse it:

### Create a Parser Script
```python
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
with open('execution_4988.json', 'r') as f:
    execution = json.load(f)

# Parse execution_data
exec_data_str = execution.get('execution_data', '[]')
exec_data = json.loads(exec_data_str)

# Resolve all references
resolved_data = resolve_references(exec_data)

# Extract runData (node execution data)
run_data = resolved_data[2].get('runData', {}) if len(resolved_data) > 2 else {}

# Now you can access node outputs
for node_name, node_runs in run_data.items():
    print(f"Node: {node_name}")
    if node_runs and len(node_runs) > 0:
        first_run = node_runs[0]
        output_data = first_run.get('data', {}).get('main', [[]])[0]
        if output_data:
            print(f"  Output items: {len(output_data)}")
```

## Real-World Debugging Examples

### Example 1: Trace Data Flow Through Nodes
**Problem:** Need to see how data transforms through multiple nodes

**Solution:**
```bash
# 1. Export the execution
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json

# 2. Use the parser script (see temp-assets/parse_execution_log.py)
python3 temp-assets/parse_execution_log.py
```

This shows output from each node, helping you identify where data gets lost or transformed incorrectly.

### Example 2: Find Where Original Filenames Are Lost
**Problem:** Evidence summary shows temp paths instead of original filenames

**Solution:**
```bash
# 1. Export both C1 and C2 executions
python3 scripts/export_n8n_logs.py 4986 --format json --output execution_c1.json
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_c2.json

# 2. Create a custom parser to check specific fields
python3 temp-assets/check_c1_webhook_data.py
```

This revealed that the "Write Binary File" node was overwriting `fileName` with the disk path.

### Example 3: Debug Failed Executions
**Problem:** Workflow fails intermittently

**Solution:**
```bash
# 1. List recent failures
python3 scripts/export_n8n_logs.py --list-failed --limit 10

# 2. Export the failed execution
python3 scripts/export_n8n_logs.py 4985 --format text

# 3. Check error messages and node outputs
python3 scripts/export_n8n_logs.py 4985 --format json --output failed_execution.json
```

### Example 4: Performance Analysis
**Problem:** Need to identify slow nodes

**Solution:**
```bash
# Export execution and check node execution times
python3 scripts/export_n8n_logs.py 4988 --format json --output execution.json
```

Then parse the `executionTime` field for each node:
```python
for node_name, node_runs in run_data.items():
    if node_runs and len(node_runs) > 0:
        exec_time = node_runs[0].get('executionTime', 0)
        print(f"{node_name}: {exec_time}ms")
```

## Common Patterns

### Pattern 1: Compare Two Executions
```bash
# Export both
python3 scripts/export_n8n_logs.py 4986 --format json --output exec_before.json
python3 scripts/export_n8n_logs.py 4988 --format json --output exec_after.json

# Compare specific node outputs
diff <(jq '.execution_data' exec_before.json) <(jq '.execution_data' exec_after.json)
```

### Pattern 2: Extract Specific Node Output
```python
# Get output from "Parse AI Response" node
node_runs = run_data.get('Parse AI Response', [])
if node_runs:
    output = node_runs[0].get('data', {}).get('main', [[]])[0]
    if output:
        evaluation = output[0].get('json', {}).get('evaluation', {})
        print(f"Evidence Summary: {evaluation.get('evidence_summary')}")
```

### Pattern 3: Audit Trail
```bash
# Export all executions for a session
python3 scripts/export_n8n_logs.py --workflow "Workflow C2" --limit 50 --format json --output audit_trail.json
```

## Tips and Best Practices

### 1. Use Descriptive Output Filenames
```bash
# Good
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988_c2_audit_worker_2026-02-26.json

# Not as good
python3 scripts/export_n8n_logs.py 4988 --format json --output log.json
```

### 2. Keep Execution IDs Handy
When you see an issue in the UI, note the execution ID immediately:
```bash
# From n8n UI: Execution #4988 failed
python3 scripts/export_n8n_logs.py 4988 --format text
```

### 3. Create Custom Parser Scripts
For recurring debugging tasks, create reusable parser scripts:
```bash
# Save to temp-assets/debug_evidence_summary.py
python3 temp-assets/debug_evidence_summary.py execution_4988.json
```

### 4. Use with Version Control
Export logs before and after changes:
```bash
# Before fix
python3 scripts/export_n8n_logs.py 4988 --format json --output logs/before_fix_4988.json

# After fix
python3 scripts/export_n8n_logs.py 4990 --format json --output logs/after_fix_4990.json

# Commit both for reference
git add logs/
git commit -m "Evidence summary fix - before/after logs"
```

## Troubleshooting

### Connection Failed
```
✗ Database connection failed: could not connect to server
```

**Solution:** Check database is running and credentials are correct:
```bash
docker ps | grep postgres
export DB_PASSWORD=your-actual-password
```

### Execution Not Found
```
✗ Execution ID 9999 not found
```

**Solution:** Verify the execution ID exists:
```bash
python3 scripts/export_n8n_logs.py --list-recent --limit 20
```

### Permission Denied
```
psycopg2.OperationalError: FATAL: password authentication failed
```

**Solution:** Check database credentials in environment variables or `.env` file.

## Integration with Other Tools

### With jq (JSON Query)
```bash
# Extract just the workflow name and status
python3 scripts/export_n8n_logs.py 4988 --format json | jq '{workflow: .workflow_name, status: .status}'
```

### With grep
```bash
# Search for specific text in execution data
python3 scripts/export_n8n_logs.py 4988 --format text | grep "evidence_summary"
```

### With Python Analysis
```python
import json
import pandas as pd

# Load multiple executions
executions = []
for exec_id in range(4980, 4990):
    try:
        with open(f'execution_{exec_id}.json', 'r') as f:
            executions.append(json.load(f))
    except FileNotFoundError:
        pass

# Create DataFrame for analysis
df = pd.DataFrame([{
    'id': e['id'],
    'workflow': e['workflow_name'],
    'duration': (pd.to_datetime(e['stoppedAt']) - pd.to_datetime(e['startedAt'])).total_seconds(),
    'status': e['status']
} for e in executions])

print(df.describe())
```

## Related Scripts

- `temp-assets/parse_execution_log.py` - Parse and display node outputs
- `temp-assets/check_c1_webhook_data.py` - Analyze Workflow C1 data flow
- `temp-assets/trace_filename_issue.py` - Trace filename transformations
- `temp-assets/validate_filename_fix.py` - Validate workflow fixes

## See Also

- `scripts/README-export-logs.md` - Script documentation
- `docs/EVIDENCE-SUMMARY-ORIGINAL-FILENAMES-FIX.md` - Example of using logs for debugging
- n8n Database Structure: https://docs.n8n.io/hosting/architecture/database-structure/
