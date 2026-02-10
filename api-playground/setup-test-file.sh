#!/bin/bash
# Setup test file for Yaak API requests

echo "===================================="
echo "Yaak API Test File Setup"
echo "===================================="
echo ""

# Check if file already exists
if [ -f "/tmp/sql_and_dba_advanced_concepts.pdf" ]; then
    echo "✓ Test file already exists at /tmp/sql_and_dba_advanced_concepts.pdf"
    ls -lh /tmp/sql_and_dba_advanced_concepts.pdf
    echo ""
    read -p "Do you want to replace it? (y/N): " replace
    if [[ ! $replace =~ ^[Yy]$ ]]; then
        echo "Using existing file."
        exit 0
    fi
fi

echo "Please provide the path to your test PDF file."
echo "Example: /home/azureuser/downloads/sql_and_dba_advanced_concepts.pdf"
echo ""
read -p "File path: " source_file

# Validate file exists
if [ ! -f "$source_file" ]; then
    echo "❌ Error: File not found at: $source_file"
    echo ""
    echo "Options:"
    echo "1. Transfer from Windows: Use WinSCP or scp"
    echo "2. Download from URL: wget <url> -O /tmp/sql_and_dba_advanced_concepts.pdf"
    echo "3. Use existing file in workspace"
    exit 1
fi

# Copy to /tmp
cp "$source_file" /tmp/sql_and_dba_advanced_concepts.pdf

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ File copied successfully!"
    echo ""
    ls -lh /tmp/sql_and_dba_advanced_concepts.pdf
    echo ""
    echo "===================================="
    echo "Next Steps:"
    echo "===================================="
    echo "1. Open Yaak (https://yaak.app)"
    echo "2. Import workspace: api-playground/yaak.wk_fyV8LrMfV8.yaml"
    echo "3. Import requests: api-playground/yaak.rq_*.yaml"
    echo "4. Start testing!"
    echo ""
    echo "Test order:"
    echo "  1. Extract Text Only (optional)"
    echo "  2. Submit Audit"
    echo "  3. Get Status (poll every 3s)"
    echo "  4. Get Results"
    echo ""
else
    echo "❌ Error copying file"
    exit 1
fi
