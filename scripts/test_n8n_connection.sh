#!/bin/bash
# Quick test script for n8n database connection

echo "Testing n8n PostgreSQL connection..."
echo "======================================"

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set defaults
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-compliance_db}
DB_USER=${DB_USER:-n8n}

echo "Host: $DB_HOST"
echo "Port: $DB_PORT"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo ""

# Test connection
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
SELECT 
    'execution_entity' as table_name,
    COUNT(*) as record_count
FROM execution_entity
UNION ALL
SELECT 
    'workflow_entity' as table_name,
    COUNT(*) as record_count
FROM workflow_entity
ORDER BY table_name;
" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Connection successful!"
    echo ""
    echo "You can now use export_n8n_logs.py to export execution logs."
else
    echo ""
    echo "✗ Connection failed. Please check your credentials."
fi
