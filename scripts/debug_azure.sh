#!/bin/bash
# Debug Azure Blob Storage connection

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

echo "=== Azure Blob Storage Diagnostics ==="
echo ""

# Parse credentials
read -r ACCOUNT_NAME ACCOUNT_KEY < <(python3 - "$ENV_FILE" << 'PYEOF'
import sys, re, os

env_file = sys.argv[1] if len(sys.argv) > 1 else ""
if env_file and os.path.isfile(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

conn = (os.environ.get('AZURE_STORAGE_CONNECTION_STRING') or
        os.environ.get('AZURE_BLOB_CONNECTION_STRING') or '')
if conn:
    m_name = re.search(r'AccountName=([^;]+)', conn)
    m_key  = re.search(r'AccountKey=([^;]+)', conn)
    if m_name and m_key:
        print(m_name.group(1), m_key.group(1))
        sys.exit(0)

name = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME', '')
key  = os.environ.get('AZURE_STORAGE_ACCOUNT_KEY', '')
print(name, key)
PYEOF
)

echo "1. Credentials Check:"
echo "   Account Name: ${ACCOUNT_NAME}"
echo "   Account Key: ${ACCOUNT_KEY:0:20}...${ACCOUNT_KEY: -10}"
echo ""

if [ -z "$ACCOUNT_KEY" ]; then 
    echo "ERROR: No Azure credentials found"
    exit 1
fi

echo "2. Testing SAS Token Generation:"
SAS=$(python3 "${SCRIPT_DIR}/_blob_sas.py" "$ACCOUNT_NAME" "$ACCOUNT_KEY" "s" "" "" "l" 2>&1)
SAS_EXIT=$?
echo "   Exit code: $SAS_EXIT"
if [ $SAS_EXIT -ne 0 ]; then
    echo "   ERROR: SAS generation failed"
    echo "   Output: $SAS"
    exit 1
fi
echo "   SAS Token: ${SAS:0:50}..."
echo ""

echo "3. Testing Azure Blob Service Endpoint:"
BASE_URL="https://${ACCOUNT_NAME}.blob.core.windows.net"
echo "   URL: ${BASE_URL}/?comp=list"
echo ""

echo "4. Making Request (with full error output):"
RESPONSE=$(curl -v "https://${ACCOUNT_NAME}.blob.core.windows.net/?comp=list&${SAS}" 2>&1)
CURL_EXIT=$?
echo "   Curl exit code: $CURL_EXIT"
echo ""
echo "5. Response:"
echo "$RESPONSE"
echo ""

# Try to parse if XML
if echo "$RESPONSE" | grep -q "<?xml"; then
    echo "6. Parsed Response:"
    echo "$RESPONSE" | python3 -c "
import sys, xml.etree.ElementTree as ET
try:
    root = ET.fromstring(sys.stdin.read())
    ns = root.tag.split('}')[0]+'}' if root.tag.startswith('{') else ''
    
    # Check for error
    code = root.find(f'{ns}Code')
    if code is not None:
        print(f'   ERROR CODE: {code.text}')
        msg = root.find(f'{ns}Message')
        if msg is not None:
            print(f'   ERROR MESSAGE: {msg.text}')
    else:
        # List containers
        containers = root.findall(f'.//{ns}Container')
        print(f'   Found {len(containers)} container(s)')
        for container in containers:
            name_elem = container.find(f'{ns}Name')
            if name_elem is not None:
                print(f'     - {name_elem.text}')
except Exception as e:
    print(f'   Parse error: {e}')
"
else
    echo "6. Response is not XML (authentication may have failed)"
fi
