# Log Exporter Quick Start Guide

## 5-Minute Tutorial

### Step 1: Find the Execution ID
In n8n UI, when you see an issue, note the execution number (e.g., #4988)

### Step 2: Export the Log
```bash
source venv/bin/activate
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json
```

### Step 3: Analyze the Data
```bash
# Quick view
python3 scripts/export_n8n_logs.py 4988 --format text

# Or use a parser script
python3 temp-assets/parse_execution_log.py
```

## Common Commands Cheat Sheet

### List Commands
```bash
# Last 10 executions
python3 scripts/export_n8n_logs.py --list-recent

# Last 20 executions
python3 scripts/export_n8n_logs.py --list-recent --limit 20

# Failed executions only
python3 scripts/export_n8n_logs.py --list-failed

# Specific workflow
python3 scripts/export_n8n_logs.py --workflow "Workflow C2"
```

### Export Commands
```bash
# Export as JSON (detailed)
python3 scripts/export_n8n_logs.py 4988 --format json --output execution.json

# Export as text (readable)
python3 scripts/export_n8n_logs.py 4988 --format text --output execution.txt

# Export as CSV (summary)
python3 scripts/export_n8n_logs.py 4988 --format csv --output execution.csv

# Print to console
python3 scripts/export_n8n_logs.py 4988 --format text
```

## Real Example: Debugging the Filename Issue

### What We Did
```bash
# 1. User reported temp paths in evidence_summary
# Execution ID: 4988

# 2. Export the execution
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json

# 3. Also export Workflow C1 execution
python3 scripts/export_n8n_logs.py 4986 --format json --output execution_c1_4986.json

# 4. Create parser to trace data flow
cat > temp-assets/parse_execution_log.py << 'EOF'
# ... parser code ...
EOF

# 5. Run parser to see node outputs
python3 temp-assets/parse_execution_log.py

# 6. Found the issue: "Write Binary File" overwrites fileName
# 7. Created fix scripts and applied them
python3 temp-assets/fix_c1_aggregate_files.py
python3 temp-assets/fix_c2_use_original_filenames.py

# 8. Validated the fix
python3 temp-assets/validate_filename_fix.py
```

### Output from Parser
```
NODE: Split by Question
--- Item 0 ---
fileMap: {
  "null0": {
    "fileName": "/tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx"
  }
}

NODE: Parse AI Response
--- Item 0 ---
evaluation.evidence_summary:
  Evidence files reviewed: /tmp/n8n_processing/.../fcd1abb359d572c8b8a932ee1ccc5738c5a817d6543ab12c48621d3c918d4119.pptx
```

This showed us exactly where the temp paths were coming from!

## Parser Script Template

Save this as `temp-assets/my_parser.py`:

```python
#!/usr/bin/env python3
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
with open('execution_4988.json', 'r') as f:
    execution = json.load(f)

# Parse execution_data
exec_data = json.loads(execution.get('execution_data', '[]'))
resolved_data = resolve_references(exec_data)
run_data = resolved_data[2].get('runData', {}) if len(resolved_data) > 2 else {}

# Extract data from specific node
node_name = 'Parse AI Response'
if node_name in run_data:
    node_runs = run_data[node_name]
    if node_runs and len(node_runs) > 0:
        output = node_runs[0].get('data', {}).get('main', [[]])[0]
        if output:
            item = output[0]
            json_data = item.get('json', {})
            
            # Print what you need
            print(f"Node: {node_name}")
            print(json.dumps(json_data, indent=2))
```

Run it:
```bash
python3 temp-assets/my_parser.py
```

## Tips

1. **Always export before making changes** - You'll want to compare before/after
2. **Use descriptive filenames** - `execution_4988_before_fix.json` is better than `log.json`
3. **Create reusable parsers** - Save time on recurring debugging tasks
4. **Check execution times** - Identify performance bottlenecks
5. **Compare executions** - Use diff to see what changed

## Next Steps

- Read full documentation: `docs/HOW-TO-USE-LOG-EXPORTER.md`
- Check script help: `python3 scripts/export_n8n_logs.py --help`
- See example parsers in `temp-assets/`

## Need Help?

Common issues:
- **Connection failed**: Check database is running and credentials are correct
- **Execution not found**: Use `--list-recent` to find valid execution IDs
- **Permission denied**: Check DB_PASSWORD environment variable
