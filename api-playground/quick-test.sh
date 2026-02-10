#!/bin/bash
# Quick test script for Compliance Audit API
# Alternative to Yaak - uses cURL commands

set -e  # Exit on error

API_BASE="http://172.206.67.83:5678"
TEST_FILE="/tmp/sql_and_dba_advanced_concepts.pdf"
QUESTION_ID="privacy_q1"
DOMAIN="Data Quality Management"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Compliance Audit API - Quick Test Script${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ jq not found. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y jq
fi

if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}✗ Test file not found: $TEST_FILE${NC}"
    echo ""
    echo "Please run: ./setup-test-file.sh"
    exit 1
fi

echo -e "${GREEN}✓ Test file exists: $TEST_FILE${NC}"
echo -e "${GREEN}✓ File size: $(du -h "$TEST_FILE" | cut -f1)${NC}"
echo ""

# Optional: Test extraction first
read -p "Test file extraction first? (y/N): " test_extract
if [[ $test_extract =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}STEP 0: Testing Text Extraction${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
    
    echo "Endpoint: POST $API_BASE/webhook/extract"
    echo "This may take 30-60 seconds..."
    echo ""
    
    EXTRACT_RESPONSE=$(curl -s -X POST "$API_BASE/webhook/extract?domain=$DOMAIN" \
        -F "data=@$TEST_FILE")
    
    if echo "$EXTRACT_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Extraction successful!${NC}"
        echo ""
        echo "$EXTRACT_RESPONSE" | jq '{
            success: .success,
            fileType: .fileType,
            pageCount: .pageCount,
            textLength: (.extractedText | length)
        }'
        echo ""
        echo -e "${GREEN}First 500 characters of extracted text:${NC}"
        echo "$EXTRACT_RESPONSE" | jq -r '.extractedText' | head -c 500
        echo ""
        echo "..."
    else
        echo -e "${RED}✗ Extraction failed${NC}"
        echo "$EXTRACT_RESPONSE" | jq .
        exit 1
    fi
    
    echo ""
    read -p "Continue with full audit? (Y/n): " continue_audit
    if [[ $continue_audit =~ ^[Nn]$ ]]; then
        exit 0
    fi
fi

# Step 1: Submit Audit
echo ""
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo -e "${BLUE}STEP 1: Submitting Audit Request${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"

echo "Endpoint: POST $API_BASE/webhook/audit/submit"
echo "Question: $QUESTION_ID"
echo "Domain: $DOMAIN"
echo ""

SUBMIT_RESPONSE=$(curl -s -X POST "$API_BASE/webhook/audit/submit" \
    -F "questions=[{\"q_id\":\"$QUESTION_ID\",\"files\":[\"test.pdf\"]}]" \
    -F "test.pdf=@$TEST_FILE" \
    -F "domain=$DOMAIN")

# Check if submission was successful
if ! echo "$SUBMIT_RESPONSE" | jq -e '.sessionId' > /dev/null 2>&1; then
    echo -e "${RED}✗ Submission failed${NC}"
    echo "$SUBMIT_RESPONSE" | jq .
    exit 1
fi

SESSION_ID=$(echo "$SUBMIT_RESPONSE" | jq -r '.sessionId')
echo -e "${GREEN}✓ Audit submitted successfully!${NC}"
echo ""
echo "$SUBMIT_RESPONSE" | jq .
echo ""
echo -e "${YELLOW}Session ID: $SESSION_ID${NC}"
echo ""

# Step 2: Poll Status
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo -e "${BLUE}STEP 2: Polling Status (every 3 seconds)${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo ""

STATUS="queued"
PERCENTAGE=0
POLL_COUNT=0
MAX_POLLS=200  # 10 minutes max (200 * 3s = 600s)

while [[ "$STATUS" != "completed" && "$STATUS" != "failed" && $POLL_COUNT -lt $MAX_POLLS ]]; do
    sleep 3
    POLL_COUNT=$((POLL_COUNT + 1))
    
    STATUS_RESPONSE=$(curl -s "$API_BASE/webhook/audit/status/$SESSION_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PERCENTAGE=$(echo "$STATUS_RESPONSE" | jq -r '.overallPercentage')
    CURRENT_STEP=$(echo "$STATUS_RESPONSE" | jq -r '.currentStep')
    
    # Progress bar
    BAR_LENGTH=50
    FILLED_LENGTH=$(( PERCENTAGE * BAR_LENGTH / 100 ))
    BAR=$(printf "%-${BAR_LENGTH}s" "$(printf '#%.0s' $(seq 1 $FILLED_LENGTH))")
    
    echo -ne "\r${YELLOW}[${BAR// /-}] ${PERCENTAGE}% - ${CURRENT_STEP}${NC}    "
    
    if [[ "$STATUS" == "failed" ]]; then
        echo ""
        echo -e "${RED}✗ Audit processing failed${NC}"
        echo "$STATUS_RESPONSE" | jq .
        exit 1
    fi
done

echo ""
echo ""

if [[ $POLL_COUNT -ge $MAX_POLLS ]]; then
    echo -e "${RED}✗ Timeout: Audit did not complete within 10 minutes${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Audit completed successfully!${NC}"
echo ""

# Step 3: Get Results
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo -e "${BLUE}STEP 3: Retrieving Results${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo ""

RESULTS_RESPONSE=$(curl -s "$API_BASE/webhook/audit/results/$SESSION_ID")

if ! echo "$RESULTS_RESPONSE" | jq -e '.results' > /dev/null 2>&1; then
    echo -e "${RED}✗ Failed to retrieve results${NC}"
    echo "$RESULTS_RESPONSE" | jq .
    exit 1
fi

echo -e "${GREEN}✓ Results retrieved!${NC}"
echo ""

# Display summary
OVERALL_SCORE=$(echo "$RESULTS_RESPONSE" | jq -r '.overallScore')
COMPLIANT_COUNT=$(echo "$RESULTS_RESPONSE" | jq -r '.summary.compliantCount')
NON_COMPLIANT_COUNT=$(echo "$RESULTS_RESPONSE" | jq -r '.summary.nonCompliantCount')

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AUDIT RESULTS SUMMARY${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Overall Score:${NC} $OVERALL_SCORE / 100"
echo -e "${GREEN}Compliant:${NC} $COMPLIANT_COUNT"
echo -e "${RED}Non-Compliant:${NC} $NON_COMPLIANT_COUNT"
echo ""

# Display each question result
echo "$RESULTS_RESPONSE" | jq -r '.results[] | "
────────────────────────────────────────────────────────
Question: \(.question)
Question ID: \(.qId)
Domain: \(.questionDomain)

EVALUATION:
  Compliant: \(.evaluation.compliant)
  Score: \(.evaluation.score) / 100
  Confidence: \(.evaluation.confidence)%

FINDINGS:
\(.evaluation.findings)

EVIDENCE SUMMARY:
\(.evaluation.evidence_summary)

GAPS:
\(if .evaluation.gaps | length > 0 then (.evaluation.gaps | map("  • " + .) | join("\n")) else "  (None identified)" end)

RECOMMENDATIONS:
\(if .evaluation.recommendations | length > 0 then (.evaluation.recommendations | map("  • " + .) | join("\n")) else "  (None provided)" end)
"'

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Save full results to file
RESULTS_FILE="audit_results_${SESSION_ID}.json"
echo "$RESULTS_RESPONSE" | jq . > "$RESULTS_FILE"
echo -e "${GREEN}Full results saved to: $RESULTS_FILE${NC}"
echo ""

echo -e "${GREEN}✓ Test completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  • View full results: cat $RESULTS_FILE | jq ."
echo "  • Test with different questions: Edit QUESTION_ID in this script"
echo "  • Test multiple questions: Use Yaak or modify this script"
echo ""
