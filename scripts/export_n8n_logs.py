#!/usr/bin/env python3
"""
n8n Execution Logs Exporter
============================
Fetches execution logs from n8n PostgreSQL database by execution ID.
Based on official n8n database structure: https://docs.n8n.io/hosting/architecture/database-structure/

Usage:
    python export_n8n_logs.py <execution_id> [--format json|csv|text] [--output file.json]
    python export_n8n_logs.py --list-recent [--limit 10]
    python export_n8n_logs.py --list-failed [--limit 10]
    python export_n8n_logs.py --workflow <workflow_name> [--limit 10]
    python export_n8n_logs.py <execution_id> --metadata

Examples:
    # Export specific execution as JSON
    python export_n8n_logs.py 12345 --format json --output execution_12345.json
    
    # Export with custom metadata
    python export_n8n_logs.py 12345 --metadata --format json
    
    # Export as CSV
    python export_n8n_logs.py 12345 --format csv --output execution_12345.csv
    
    # List recent executions
    python export_n8n_logs.py --list-recent --limit 20
    
    # List failed executions for debugging
    python export_n8n_logs.py --list-failed --limit 10
    
    # Export all executions for a workflow
    python export_n8n_logs.py --workflow "Workflow C2 - Audit Worker" --limit 5

Environment Variables:
    DB_HOST       - Database host (default: localhost)
    DB_PORT       - Database port (default: 5432)
    DB_NAME       - Database name (default: compliance_db)
    DB_USER       - Database user (default: n8n)
    DB_PASSWORD   - Database password (default: ComplianceDB2026!)
"""

import argparse
import json
import csv
import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)


class N8nLogExporter:
    def __init__(self):
        """Initialize database connection from environment variables."""
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'compliance_db'),
            'user': os.getenv('DB_USER', 'n8n'),
            'password': os.getenv('DB_PASSWORD', 'ComplianceDB2026!')
        }
        self.conn = None
    
    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.conn_params, cursor_factory=RealDictCursor)
            print(f"✓ Connected to {self.conn_params['database']} at {self.conn_params['host']}")
        except psycopg2.Error as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def get_execution_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch execution details by ID from execution_entity table.
        
        Based on n8n official database structure:
        https://docs.n8n.io/hosting/architecture/database-structure/
        
        execution_entity stores: id, finished, mode, retryOf, retrySuccessId,
        startedAt, stoppedAt, workflowId, waitTill, status (PostgreSQL)
        
        execution_data stores: executionId, workflowData, data
        """
        query = """
            SELECT 
                ee.id,
                ee."workflowId",
                ee.finished,
                ee.mode,
                ee."startedAt",
                ee."stoppedAt",
                ee."waitTill",
                ee.status,
                ee."retryOf",
                ee."retrySuccessId",
                ed.data as execution_data,
                ed."workflowData",
                w.name as workflow_name,
                w.active as workflow_active
            FROM execution_entity ee
            LEFT JOIN execution_data ed ON ee.id = ed."executionId"
            LEFT JOIN workflow_entity w ON ee."workflowId" = w.id
            WHERE ee.id = %s
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (execution_id,))
            result = cur.fetchone()
            return dict(result) if result else None

    
    def list_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent executions with summary info.
        Joins execution_entity with workflow_entity for workflow names.
        """
        query = """
            SELECT 
                e.id,
                w.name as workflow_name,
                w.id as workflow_id,
                e.mode,
                e."startedAt",
                e."stoppedAt",
                e.finished,
                e.status,
                e."retryOf",
                EXTRACT(EPOCH FROM (e."stoppedAt" - e."startedAt")) as duration_seconds
            FROM execution_entity e
            LEFT JOIN workflow_entity w ON e."workflowId" = w.id
            ORDER BY e."startedAt" DESC
            LIMIT %s
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (limit,))
            return [dict(row) for row in cur.fetchall()]
    
    def get_executions_by_workflow(self, workflow_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch executions for a specific workflow."""
        query = """
            SELECT 
                e.id,
                w.name as workflow_name,
                w.id as workflow_id,
                e.mode,
                e."startedAt",
                e."stoppedAt",
                e.finished,
                e.status,
                e."retryOf",
                EXTRACT(EPOCH FROM (e."stoppedAt" - e."startedAt")) as duration_seconds
            FROM execution_entity e
            INNER JOIN workflow_entity w ON e."workflowId" = w.id
            WHERE w.name ILIKE %s
            ORDER BY e."startedAt" DESC
            LIMIT %s
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (f"%{workflow_name}%", limit))
            return [dict(row) for row in cur.fetchall()]
    
    def get_execution_metadata(self, execution_id: str) -> List[Dict[str, Any]]:
        """
        Fetch custom execution metadata.
        execution_metadata table stores custom data saved via Execution Data node.
        """
        query = """
            SELECT 
                key,
                value,
                "executionId"
            FROM execution_metadata
            WHERE "executionId" = %s
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (execution_id,))
            return [dict(row) for row in cur.fetchall()]
    
    def get_failed_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent failed executions for debugging."""
        query = """
            SELECT 
                e.id,
                w.name as workflow_name,
                e.mode,
                e."startedAt",
                e."stoppedAt",
                e.status,
                EXTRACT(EPOCH FROM (e."stoppedAt" - e."startedAt")) as duration_seconds
            FROM execution_entity e
            LEFT JOIN workflow_entity w ON e."workflowId" = w.id
            WHERE e.finished = false OR e.status = 'error'
            ORDER BY e."startedAt" DESC
            LIMIT %s
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (limit,))
            return [dict(row) for row in cur.fetchall()]
    
    def export_to_json(self, data: Any, output_file: Optional[str] = None):
        """Export data as JSON."""
        json_str = json.dumps(data, indent=2, default=str)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_str)
            print(f"✓ Exported to {output_file}")
        else:
            print(json_str)
    
    def export_to_csv(self, execution: Dict[str, Any], output_file: str):
        """Export execution data as CSV (flattened)."""
        # Flatten the execution data
        flat_data = {
            'execution_id': execution['id'],
            'workflow_id': execution.get('workflowId'),
            'workflow_name': execution.get('workflow_name'),
            'mode': execution.get('mode'),
            'status': execution.get('status'),
            'finished': execution.get('finished'),
            'started_at': execution.get('startedAt'),
            'stopped_at': execution.get('stoppedAt'),
            'retry_of': execution.get('retryOf'),
            'retry_success_id': execution.get('retrySuccessId'),
        }
        
        # Extract node execution data if available from execution_data table
        if execution.get('execution_data'):
            data = execution['execution_data']
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass
            
            if isinstance(data, dict):
                flat_data['result_data'] = json.dumps(data.get('resultData', {}))
                flat_data['execution_data'] = json.dumps(data.get('executionData', {}))
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flat_data.keys())
            writer.writeheader()
            writer.writerow(flat_data)
        
        print(f"✓ Exported to {output_file}")
    
    def export_to_text(self, execution: Dict[str, Any], output_file: Optional[str] = None):
        """Export execution as human-readable text."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"n8n Execution Log - ID: {execution['id']}")
        lines.append("=" * 80)
        lines.append(f"Workflow: {execution.get('workflow_name', 'Unknown')}")
        lines.append(f"Workflow ID: {execution.get('workflowId')}")
        lines.append(f"Mode: {execution.get('mode')}")
        lines.append(f"Status: {execution.get('status')}")
        lines.append(f"Finished: {execution.get('finished')}")
        lines.append(f"Started: {execution.get('startedAt')}")
        lines.append(f"Stopped: {execution.get('stoppedAt')}")
        
        if execution.get('retryOf'):
            lines.append(f"Retry Of: {execution.get('retryOf')}")
        if execution.get('retrySuccessId'):
            lines.append(f"Retry Success ID: {execution.get('retrySuccessId')}")
        
        lines.append("")
        
        # Parse and display execution data from execution_data table
        if execution.get('execution_data'):
            data = execution['execution_data']
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass
            
            if isinstance(data, dict):
                lines.append("-" * 80)
                lines.append("EXECUTION DATA:")
                lines.append("-" * 80)
                lines.append(json.dumps(data, indent=2, default=str))
        
        # Parse and display workflow data
        if execution.get('workflowData'):
            workflow_data = execution['workflowData']
            if isinstance(workflow_data, str):
                try:
                    workflow_data = json.loads(workflow_data)
                except:
                    pass
            
            if isinstance(workflow_data, dict):
                lines.append("")
                lines.append("-" * 80)
                lines.append("WORKFLOW DATA:")
                lines.append("-" * 80)
                lines.append(f"Name: {workflow_data.get('name')}")
                lines.append(f"Active: {workflow_data.get('active')}")
                lines.append(f"Nodes: {len(workflow_data.get('nodes', []))}")
        
        lines.append("=" * 80)
        
        text = "\n".join(lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(text)
            print(f"✓ Exported to {output_file}")
        else:
            print(text)
    
    def print_execution_list(self, executions: List[Dict[str, Any]]):
        """Print execution list in table format."""
        if not executions:
            print("No executions found.")
            return
        
        print("\n" + "=" * 120)
        print(f"{'ID':<10} {'Workflow':<35} {'Mode':<10} {'Status':<10} {'Started':<20} {'Duration':<10}")
        print("=" * 120)
        
        for ex in executions:
            duration = f"{ex.get('duration_seconds', 0):.1f}s" if ex.get('duration_seconds') else "N/A"
            started = str(ex.get('startedAt', 'N/A'))[:19] if ex.get('startedAt') else 'N/A'
            workflow = (ex.get('workflow_name') or 'Unknown')[:34]
            
            print(f"{str(ex['id']):<10} {workflow:<35} {ex.get('mode', 'N/A'):<10} "
                  f"{ex.get('status', 'N/A'):<10} {started:<20} {duration:<10}")
        
        print("=" * 120 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Export n8n execution logs from PostgreSQL database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('execution_id', nargs='?', help='Execution ID to export')
    parser.add_argument('--format', choices=['json', 'csv', 'text'], default='json',
                        help='Output format (default: json)')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--list-recent', action='store_true',
                        help='List recent executions')
    parser.add_argument('--list-failed', action='store_true',
                        help='List recent failed executions')
    parser.add_argument('--workflow', '-w', help='Filter by workflow name')
    parser.add_argument('--metadata', '-m', action='store_true',
                        help='Include execution metadata (custom data)')
    parser.add_argument('--limit', '-l', type=int, default=10,
                        help='Limit number of results (default: 10)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.list_recent and not args.list_failed and not args.workflow and not args.execution_id:
        parser.error("Must provide execution_id, --list-recent, --list-failed, or --workflow")
    
    exporter = N8nLogExporter()
    exporter.connect()
    
    try:
        # List recent executions
        if args.list_recent:
            executions = exporter.list_recent_executions(args.limit)
            exporter.print_execution_list(executions)
        
        # List failed executions
        elif args.list_failed:
            executions = exporter.get_failed_executions(args.limit)
            print("\n🔴 Recent Failed Executions:")
            exporter.print_execution_list(executions)
        
        # List executions by workflow
        elif args.workflow:
            executions = exporter.get_executions_by_workflow(args.workflow, args.limit)
            exporter.print_execution_list(executions)
            
            if executions and args.output:
                exporter.export_to_json(executions, args.output)
        
        # Export specific execution
        elif args.execution_id:
            execution = exporter.get_execution_by_id(args.execution_id)
            
            if not execution:
                print(f"✗ Execution ID {args.execution_id} not found")
                sys.exit(1)
            
            # Optionally fetch metadata
            if args.metadata:
                metadata = exporter.get_execution_metadata(args.execution_id)
                if metadata:
                    execution['custom_metadata'] = metadata
                    print(f"✓ Found {len(metadata)} custom metadata entries")
            
            if args.format == 'json':
                exporter.export_to_json(execution, args.output)
            elif args.format == 'csv':
                if not args.output:
                    args.output = f"execution_{args.execution_id}.csv"
                exporter.export_to_csv(execution, args.output)
            elif args.format == 'text':
                exporter.export_to_text(execution, args.output)
    
    finally:
        exporter.close()


if __name__ == '__main__':
    main()
