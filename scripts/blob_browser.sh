#!/bin/bash
# Azure Blob Browser
# SAS: sv=2020-12-06, 16 fields, 15 \n, NO trailing newline
# Ref: https://learn.microsoft.com/rest/api/storageservices/create-service-sas

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

# Parse credentials via Python to safely handle ; = + in connection string
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

if [ -z "$ACCOUNT_KEY" ]; then echo "No Azure credentials. Set AZURE_STORAGE_CONNECTION_STRING in .env"; exit 1; fi
BASE_URL="https://${ACCOUNT_NAME}.blob.core.windows.net"

generate_sas() {
  python3 -W ignore "${SCRIPT_DIR}/_blob_sas.py" "$ACCOUNT_NAME" "$ACCOUNT_KEY" "$1" "$2" "$3" "$4"
}

cmd_help() {
  cat << HELP

  Azure Blob Browser  (account: ${ACCOUNT_NAME})

  Commands:
    ls     <container> [prefix]              List blobs
    tree   <container> [prefix]              Tree-style listing
    exists <container> <blob-path>           Check if a blob exists
    url    <container> <blob-path>           Generate 1-hour SAS download URL
    dl     <container> <blob-path> [dest]    Download a single blob
    dlall  <container> [prefix]   [dest]     Download all blobs (optionally filtered)

  Examples:
    ./scripts/blob_browser.sh ls compliance
    ./scripts/blob_browser.sh ls compliance compliance_assessment/
    ./scripts/blob_browser.sh tree compliance compliance_assessment/
    ./scripts/blob_browser.sh exists compliance compliance_assessment/.../dummy.pdf
    ./scripts/blob_browser.sh url    compliance compliance_assessment/.../dummy.pdf
    ./scripts/blob_browser.sh dl     compliance compliance_assessment/.../dummy.pdf ~/downloads
    ./scripts/blob_browser.sh dlall  compliance compliance_assessment/09318e2b-.../ ~/downloads

HELP
}

cmd_ls() {
  local CONTAINER="${1:?Usage: ls container [prefix]}"
  local PREFIX="${2:-}"
  local SAS; SAS=$(generate_sas "c" "$CONTAINER" "" "rl")
  local URL="${BASE_URL}/${CONTAINER}?restype=container&comp=list&maxresults=500"
  [ -n "$PREFIX" ] && URL="${URL}&prefix=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe='/'))" "$PREFIX")"
  URL="${URL}&${SAS}"
  echo "  ${CONTAINER}/${PREFIX:-}"
  echo ""
  curl -sf "$URL" | python3 ${SCRIPT_DIR}/_blob_parse.py ls
}

cmd_tree() {
  local CONTAINER="${1:?Usage: tree container [prefix]}"
  local PREFIX="${2:-}"
  local SAS; SAS=$(generate_sas "c" "$CONTAINER" "" "rl")
  local URL="${BASE_URL}/${CONTAINER}?restype=container&comp=list&maxresults=500"
  [ -n "$PREFIX" ] && URL="${URL}&prefix=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe='/'))" "$PREFIX")"
  URL="${URL}&${SAS}"
  echo "  ${CONTAINER}/${PREFIX:-}"
  echo ""
  curl -sf "$URL" | python3 ${SCRIPT_DIR}/_blob_parse.py tree
}

cmd_exists() {
  local CONTAINER="${1:?Usage: exists container blob-path}"
  local BLOB_PATH="${2:?Usage: exists container blob-path}"
  local SAS; SAS=$(generate_sas "b" "$CONTAINER" "$BLOB_PATH" "r")
  local CODE; CODE=$(curl -so /dev/null -w "%{http_code}" "${BASE_URL}/${CONTAINER}/${BLOB_PATH}?${SAS}")
  case "$CODE" in
    200) echo "EXISTS     ${CONTAINER}/${BLOB_PATH}" ;;
    404) echo "NOT FOUND  ${CONTAINER}/${BLOB_PATH}" ;;
    403) echo "FORBIDDEN  (wrong key or container?)" ;;
    *)   echo "HTTP ${CODE}   ${CONTAINER}/${BLOB_PATH}" ;;
  esac
}

cmd_url() {
  local CONTAINER="${1:?Usage: url container blob-path}"
  local BLOB_PATH="${2:?Usage: url container blob-path}"
  local SAS; SAS=$(generate_sas "b" "$CONTAINER" "$BLOB_PATH" "r")
  echo ""
  echo "${BASE_URL}/${CONTAINER}/${BLOB_PATH}?${SAS}"
}

cmd_dl() {
  local CONTAINER="${1:?Usage: dl container blob-path [dest-dir]}"
  local BLOB_PATH="${2:?Usage: dl container blob-path [dest-dir]}"
  local DEST_DIR="${3:-$(pwd)}"
  mkdir -p "$DEST_DIR"
  local FILENAME; FILENAME=$(basename "$BLOB_PATH")
  local DEST="${DEST_DIR}/${FILENAME}"
  local SAS; SAS=$(generate_sas "b" "$CONTAINER" "$BLOB_PATH" "r" 2>/dev/null)
  local CODE; CODE=$(curl -sf -w "%{http_code}" -o "$DEST" "${BASE_URL}/${CONTAINER}/${BLOB_PATH}?${SAS}" 2>/dev/null; echo)
  # curl -w appends code after body; grab last 3 chars
  local HTTP_CODE; HTTP_CODE=$(tail -c 3 <<< "$CODE")
  # re-run cleanly with -w only
  HTTP_CODE=$(curl -s -o "$DEST" -w "%{http_code}" "${BASE_URL}/${CONTAINER}/${BLOB_PATH}?${SAS}")
  case "$HTTP_CODE" in
    200)
      local SIZE; SIZE=$(wc -c < "$DEST" | tr -d ' ')
      echo "OK   ${SIZE} B  ->  ${DEST}"
      ;;
    404) rm -f "$DEST"; echo "NOT FOUND  ${CONTAINER}/${BLOB_PATH}"; exit 1 ;;
    403) rm -f "$DEST"; echo "FORBIDDEN  (check credentials)"; exit 1 ;;
    *)   rm -f "$DEST"; echo "HTTP ${HTTP_CODE}  ${CONTAINER}/${BLOB_PATH}"; exit 1 ;;
  esac
}

cmd_dlall() {
  local CONTAINER="${1:?Usage: dlall container [prefix] [dest-dir]}"
  local PREFIX="${2:-}"
  local DEST_DIR="${3:-./blob-downloads}"
  mkdir -p "$DEST_DIR"

  local SAS; SAS=$(generate_sas "c" "$CONTAINER" "" "rl" 2>/dev/null)
  local LIST_URL="${BASE_URL}/${CONTAINER}?restype=container&comp=list&maxresults=500"
  [ -n "$PREFIX" ] && LIST_URL="${LIST_URL}&prefix=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe='/')" "$PREFIX")"
  LIST_URL="${LIST_URL}&${SAS}"

  # get all blob names
  local BLOBS; BLOBS=$(curl -sf "$LIST_URL" | python3 -c "
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
ns = root.tag.split('}')[0]+'}' if root.tag.startswith('{') else ''
for b in root.findall(f'.//{ns}Name'):
    print(b.text)
")

  if [ -z "$BLOBS" ]; then
    echo "No blobs found in ${CONTAINER}/${PREFIX:-}"
    exit 0
  fi

  local COUNT=0 FAIL=0
  echo "Downloading from: ${CONTAINER}/${PREFIX:-}  ->  ${DEST_DIR}"
  echo ""

  while IFS= read -r BLOB; do
    [ -z "$BLOB" ] && continue
    local FILENAME; FILENAME=$(basename "$BLOB")
    local DEST="${DEST_DIR}/${FILENAME}"
    # if duplicate filenames, prefix with parent folder
    if [ -f "$DEST" ]; then
      local PARENT; PARENT=$(basename "$(dirname "$BLOB")")
      DEST="${DEST_DIR}/${PARENT}_${FILENAME}"
    fi
    local BLOB_SAS; BLOB_SAS=$(generate_sas "b" "$CONTAINER" "$BLOB" "r" 2>/dev/null)
    local HTTP_CODE; HTTP_CODE=$(curl -s -o "$DEST" -w "%{http_code}" "${BASE_URL}/${CONTAINER}/${BLOB}?${BLOB_SAS}")
    if [ "$HTTP_CODE" = "200" ]; then
      local SIZE; SIZE=$(wc -c < "$DEST" | tr -d ' ')
      printf "  OK   %8s B  %s\n" "$SIZE" "$(basename "$DEST")"
      COUNT=$((COUNT+1))
    else
      rm -f "$DEST"
      printf "  FAIL HTTP %-3s  %s\n" "$HTTP_CODE" "$BLOB"
      FAIL=$((FAIL+1))
    fi
  done <<< "$BLOBS"

  echo ""
  echo "Done: ${COUNT} downloaded, ${FAIL} failed  ->  ${DEST_DIR}"
}

COMMAND="${1:-help}"; shift 2>/dev/null || true
case "$COMMAND" in
  ls|list)        cmd_ls "$@" ;;
  tree)           cmd_tree "$@" ;;
  exists|check)   cmd_exists "$@" ;;
  url|sas)        cmd_url "$@" ;;
  dl|download)    cmd_dl "$@" ;;
  dlall|download-all) cmd_dlall "$@" ;;
  help|--help|-h) cmd_help ;;
  *) echo "Unknown: $COMMAND"; cmd_help; exit 1 ;;
esac
