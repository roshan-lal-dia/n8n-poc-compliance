#!/bin/bash
# List all containers in Azure Storage Account

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

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

if [ -z "$ACCOUNT_KEY" ]; then 
    echo "ERROR: No Azure credentials found"
    exit 1
fi

echo "Storage Account: ${ACCOUNT_NAME}"
echo "Listing all containers..."
echo ""

# Generate account-level SAS token for listing
SAS=$(python3 "${SCRIPT_DIR}/_blob_sas.py" "$ACCOUNT_NAME" "$ACCOUNT_KEY" "" "" "" "l")

# List containers
curl -sf "https://${ACCOUNT_NAME}.blob.core.windows.net/?comp=list&${SAS}" | python3 -c "
import sys, xml.etree.ElementTree as ET

try:
    root = ET.fromstring(sys.stdin.read())
    ns = root.tag.split('}')[0]+'}' if root.tag.startswith('{') else ''
    
    containers = root.findall(f'.//{ns}Container')
    
    if not containers:
        print('  (no containers found)')
    else:
        print(f'  Found {len(containers)} container(s):')
        print('')
        for container in containers:
            name_elem = container.find(f'{ns}Name')
            if name_elem is not None:
                print(f'    - {name_elem.text}')
except Exception as e:
    print(f'ERROR parsing response: {e}')
    sys.exit(1)
"

echo ""
