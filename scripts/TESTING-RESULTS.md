# n8n Log Exporter - Testing Results

## Test Date: 2026-02-26

### Environment Setup
- Python 3.12.3
- Virtual environment created at `./venv`
- Dependencies installed: `psycopg2-binary`

### Tests Performed

#### 1. List Recent Executions ✅
```bash
python scripts/export_n8n_logs.py --list-recent --limit 5
```
**Result:** Successfully listed 5 most recent executions with workflow names, status, and duration.

#### 2. Export Specific Execution (Text Format) ✅
```bash
python scripts/export_n8n_logs.py 4988 --format text
```
**Result:** Successfully exported execution 4988 details:
- Execution ID: 4988
- Workflow: Workflow C2: Audit Worker (Background Processor)
- Status: success
- Duration: ~9 minutes (12:42:50 - 12:51:53)
- Nodes: 35

#### 3. Export with Metadata (JSON) ✅
```bash
python scripts/export_n8n_logs.py 4988 --metadata --format json --output execution_4988_full.json
```
**Result:** Successfully exported full execution data
- File size: 9.3 MB
- Lines: 1,156
- Contains complete execution data and workflow snapshot

#### 4. Export to CSV ✅
```bash
python scripts/export_n8n_logs.py 4988 --format csv --output execution_4988.csv
```
**Result:** Successfully created CSV with flattened execution data
- File size: 275 bytes
- Contains: execution_id, workflow_id, workflow_name, mode, status, timestamps

#### 5. List Failed Executions ✅
```bash
python scripts/export_n8n_logs.py --list-failed --limit 5
```
**Result:** Successfully listed 5 recent failed executions for debugging
- Identified execution 4969 with error status (duration: 1060.5s)
- Multiple C3 workflow errors detected

#### 6. Filter by Workflow Name ✅
```bash
python scripts/export_n8n_logs.py --workflow "C2" --limit 3
```
**Result:** Successfully filtered executions for workflows containing "C2"
- Found 3 recent C2 Audit Worker executions
- All with success status

### Database Schema Validation ✅

The script correctly queries the official n8n database tables:
- `execution_entity` - Main execution records
- `execution_data` - Detailed execution data
- `execution_metadata` - Custom metadata
- `workflow_entity` - Workflow information

Reference: [n8n Database Structure](https://docs.n8n.io/hosting/architecture/database-structure/)

### Files Generated

1. `execution_4988.csv` - CSV export (275 bytes)
2. `execution_4988_full.json` - Full JSON export (9.3 MB)
3. `/tmp/execution_4988.json` - JSON export without metadata

### Performance

- Connection time: < 1 second
- Query execution: < 1 second for list operations
- Export time: < 2 seconds for large JSON files

### Conclusion

All features working as expected. The script successfully:
- Connects to n8n PostgreSQL database
- Queries execution data using correct schema
- Exports in multiple formats (JSON, CSV, text)
- Filters by workflow name
- Lists recent and failed executions
- Includes custom metadata when requested

## Usage Recommendations

For daily operations:
```bash
# Quick status check
python scripts/export_n8n_logs.py --list-recent

# Debug failures
python scripts/export_n8n_logs.py --list-failed

# Full audit export
python scripts/export_n8n_logs.py <execution_id> --metadata --format json
```
