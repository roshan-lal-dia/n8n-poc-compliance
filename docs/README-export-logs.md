# n8n Execution Logs Exporter

Export and analyze n8n workflow execution logs from PostgreSQL database.

## Quick Start

```bash
# List recent executions
python3 scripts/export_n8n_logs.py --list-recent

# Export specific execution
python3 scripts/export_n8n_logs.py 4988 --format json --output execution_4988.json

# View as text
python3 scripts/export_n8n_logs.py 4988 --format text
```

## Documentation

- **Quick Start Guide**: `docs/LOG-EXPORTER-QUICK-START.md` - 5-minute tutorial with examples
- **Complete Guide**: `docs/HOW-TO-USE-LOG-EXPORTER.md` - Full documentation with debugging workflows
- **Script Help**: Run `python3 scripts/export_n8n_logs.py --help`

## Features

- Export execution logs by ID in JSON, CSV, or text format
- List recent executions with summary information
- Filter executions by workflow name
- View failed executions for debugging
- Include custom execution metadata
- Based on official n8n database structure

## Installation

```bash
pip install -r requirements-logs.txt
```

Or install directly:
```bash
pip install psycopg2-binary
```

## Configuration

Set environment variables for database connection:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=compliance_db
export DB_USER=n8n
export DB_PASSWORD=ComplianceDB2026!
```

Or use the defaults from your `.env` file.

## Usage

### List Recent Executions

```bash
python export_n8n_logs.py --list-recent --limit 20
```

### List Failed Executions

```bash
python export_n8n_logs.py --list-failed --limit 10
```

### Filter by Workflow Name

```bash
python export_n8n_logs.py --workflow "Audit Worker" --limit 5
```

### Export Specific Execution

Export as JSON:
```bash
python export_n8n_logs.py 12345 --format json --output execution_12345.json
```

Export as CSV:
```bash
python export_n8n_logs.py 12345 --format csv --output execution_12345.csv
```

Export as human-readable text:
```bash
python export_n8n_logs.py 12345 --format text --output execution_12345.txt
```

### Include Custom Metadata

```bash
python export_n8n_logs.py 12345 --metadata --format json
```

## Database Schema

The script queries the following n8n tables:

- `execution_entity` - Main execution records (id, status, timestamps, etc.)
- `execution_data` - Detailed execution data and workflow snapshots
- `execution_metadata` - Custom metadata saved via Execution Data node
- `workflow_entity` - Workflow information (name, active status)

Reference: [n8n Database Structure](https://docs.n8n.io/hosting/architecture/database-structure/)

## Output Formats

### JSON
Complete execution data including all fields and nested structures.

### CSV
Flattened execution data suitable for spreadsheet analysis.

### Text
Human-readable format with formatted sections for quick review.

## Examples

```bash
# Quick check of recent activity
python export_n8n_logs.py --list-recent

# Debug failed workflows
python export_n8n_logs.py --list-failed

# Export all executions for a specific workflow
python export_n8n_logs.py --workflow "C2" --limit 10 --output c2_executions.json

# Full export with metadata
python export_n8n_logs.py 12345 --metadata --format json --output full_execution.json
```

## Troubleshooting

### Connection Issues

If you get connection errors, verify:
1. PostgreSQL is running
2. Database credentials are correct
3. Network access is allowed (check firewall/security groups)

### Missing Executions

n8n only saves executions based on workflow settings. Check:
- Workflow execution settings (Save Data on Success/Error)
- Execution pruning settings (may have deleted old executions)

### Large Data

For executions with large binary data, use JSON format and consider:
- Filtering specific fields
- Using pagination with `--limit`
- Exporting to file instead of stdout
