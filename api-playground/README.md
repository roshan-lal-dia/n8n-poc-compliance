# Yaak API Requests for Compliance Audit System

This directory contains Yaak API request definitions for testing the n8n compliance audit workflow.

## Prerequisites

1. **Install Yaak**: Download from https://yaak.app/ or https://github.com/mountain-loop/yaak
2. **Place Test File**: Copy your test PDF to `/tmp/sql_and_dba_advanced_concepts.pdf`
   ```bash
   # If you have it on Windows, transfer it first:
   # Example: Use WinSCP, scp, or similar
   cp /path/to/your/file.pdf /tmp/sql_and_dba_advanced_concepts.pdf
   ```
3. **System Running**: Ensure your n8n instance is running at `http://172.206.67.83:5678`

## Request Files Overview

### Workspace
- **`yaak.wk_fyV8LrMfV8.yaml`** - Main workspace definition

### Test Requests (Use in Order)

1. **`yaak.rq_extract_only.yaml`** - Extract Text Only (SQL PDF)
   - Tests Workflow A (Universal Extractor)
   - Returns raw extracted text
   - No compliance evaluation
   - **Use this first** to verify file extraction works

2. **`yaak.rq_submit_audit.yaml`** - Submit Audit (Single Question)
   - Tests full compliance audit flow
   - Uses one question: `privacy_q1`
   - Returns `sessionId` for polling
   - **Response**: `202 Accepted` with sessionId

3. **`yaak.rq_submit_multi_question.yaml`** - Submit Multi-Question Audit
   - Tests multiple questions against same file
   - Uses: `privacy_q1` and `privacy_q2`
   - Shows shared file deduplication

4. **`yaak.rq_get_status.yaml`** - Get Audit Status
   - Poll progress of submitted audit
   - Replace `SESSION_ID_HERE` with actual sessionId
   - **Poll every 3 seconds** until `status: "completed"`

5. **`yaak.rq_get_results.yaml`** - Get Audit Results
   - Retrieve final compliance evaluation
   - Replace `SESSION_ID_HERE` with actual sessionId
   - Only works when status is "completed"

### Existing Requests (Legacy)
- `yaak.rq_5cUm62xk6a.yaml` - dev extract (old format)
- `yaak.rq_5ybLnngfcD.yaml` - evaluate-compliance pdf (old format)
- `yaak.rq_e833qqoNsK.yaml` - evaluate-compliance docx (old format)
- `yaak.rq_w8aPRVY2nD.yaml` - evaluate-compliance pptx (old format)

## Usage Flow

### Step 1: Extract Text (Optional Test)
```yaml
Request: 0. Extract Text Only (SQL PDF)
Expected Response:
{
  "success": true,
  "extractedText": "... SQL content ...",
  "fileType": "pdf",
  "pageCount": 250
}
```

### Step 2: Submit Audit
```yaml
Request: 1. Submit Audit (SQL PDF)
Expected Response (202):
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "jobId": "abc-123-def-456",
  "status": "queued",
  "totalQuestions": 1,
  "message": "Audit submitted successfully...",
  "estimatedCompletionMinutes": 5
}
```

**Copy the `sessionId` from response!**

### Step 3: Poll Status (Every 3 seconds)
```yaml
Request: 2. Get Audit Status
URL: Replace SESSION_ID_HERE with actual sessionId
Example: http://172.206.67.83:5678/webhook/audit/status/550e8400-e29b-41d4-a716-446655440000

Expected Response:
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "overallPercentage": 47,
  "currentStep": "evaluating",
  "totalQuestions": 1,
  "answeredQuestions": 0,
  "questionProgress": [
    {
      "qId": "privacy_q1",
      "status": "in_progress",
      "step": "evaluating",
      "percentage": 85
    }
  ]
}
```

**Keep polling until `status: "completed"` and `overallPercentage: 100`**

### Step 4: Get Results
```yaml
Request: 3. Get Audit Results
URL: Replace SESSION_ID_HERE with actual sessionId

Expected Response (200):
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "overallScore": 83.5,
  "totalQuestions": 1,
  "results": [
    {
      "qId": "privacy_q1",
      "question": "Are there documented access controls and PII handling procedures?",
      "evaluation": {
        "compliant": true,
        "score": 87,
        "confidence": 85,
        "findings": "...",
        "evidence_summary": "...",
        "gaps": [],
        "recommendations": [...]
      }
    }
  ]
}
```

## Available Questions

To see all available questions, query the database:

```bash
docker exec compliance-postgres psql -U n8n -d compliance_db -c \
  "SELECT q_id, question_text, domain FROM audit_questions ORDER BY domain, q_id;"
```

Common question IDs by domain:
- **Privacy**: `privacy_q1`, `privacy_q2`, `privacy_q3`
- **Security**: `security_q1`, `security_q2`
- **Data Quality**: `dq_q1`, `dq_q2`

## Modifying Requests

### Change Test File
Edit the `file:` field in request YAML:
```yaml
body:
  form:
  - enabled: true
    file: /path/to/your/file.pdf  # <-- Change this
    name: sql_advanced_concepts.pdf
```

### Change Questions
Edit the `questions` field:
```yaml
body:
  form:
  - enabled: true
    name: questions
    value: '[{"q_id":"security_q1","files":["myfile.pdf"]}]'  # <-- Change this
```

### Change Domain
Edit the `domain` field (optional - auto-detected if omitted):
```yaml
body:
  form:
  - enabled: true
    name: domain
    value: 'Security'  # <-- Change this
```

### Test Multiple Files
```yaml
body:
  form:
  - enabled: true
    name: questions
    value: '[{"q_id":"privacy_q1","files":["file1.pdf","file2.docx"]}]'
  - enabled: true
    file: /path/to/file1.pdf
    name: file1.pdf
  - enabled: true
    file: /path/to/file2.docx
    name: file2.docx
  - enabled: true
    name: domain
    value: Privacy
```

## Troubleshooting

### File Not Found Error
```bash
# Verify file exists
ls -lh /tmp/sql_and_dba_advanced_concepts.pdf

# If missing, copy it:
cp /your/local/path/file.pdf /tmp/sql_and_dba_advanced_concepts.pdf
```

### Invalid Question ID
```json
{
  "error": "Question ID 'invalid_q' not found in audit_questions table",
  "status": 400
}
```

**Solution**: Use `docker exec` command above to list valid question IDs.

### Session Not Found
```json
{
  "error": "Session not found",
  "status": 404
}
```

**Solution**: Double-check sessionId in URL matches response from submit request.

### Connection Refused
```bash
# Check if n8n is running
docker ps | grep compliance-n8n

# Check logs
docker logs compliance-n8n --tail 50

# Restart if needed
cd /home/azureuser/n8n-poc-compliance
docker-compose -f docker-compose.prod.yml up -d
```

## Testing with cURL (Alternative)

If you prefer cURL over Yaak:

```bash
# 1. Submit audit
SESSION_ID=$(curl -s -X POST http://172.206.67.83:5678/webhook/audit/submit \
  -F 'questions=[{"q_id":"privacy_q1","files":["test.pdf"]}]' \
  -F 'test.pdf=@/tmp/sql_and_dba_advanced_concepts.pdf' \
  -F 'domain=Privacy' | jq -r '.sessionId')

echo "Session ID: $SESSION_ID"

# 2. Poll status
watch -n 3 "curl -s http://172.206.67.83:5678/webhook/audit/status/$SESSION_ID | jq '.overallPercentage, .status'"

# 3. Get results (when status = completed)
curl -s http://172.206.67.83:5678/webhook/audit/results/$SESSION_ID | jq .
```

## Additional Resources

- **API Documentation**: [/docs/FRONTEND-API-GUIDE.md](../docs/FRONTEND-API-GUIDE.md)
- **Workflow Guide**: [/workflows/WORKFLOW-GUIDE.md](../workflows/WORKFLOW-GUIDE.md)
- **Deployment Guide**: [/DEPLOYMENT-GUIDE.md](../DEPLOYMENT-GUIDE.md)
- **Yaak Documentation**: https://yaak.app/docs

## Support

For issues or questions:
1. Check n8n logs: `docker logs compliance-n8n --tail 100`
2. Check Redis queue: `docker exec compliance-redis redis-cli LLEN compliance:jobs:pending`
3. Check worker logs: `docker logs compliance-n8n | grep "worker"`
4. Review [AUDIT-TRANSPARENCY-GUIDE.md](../docs/AUDIT-TRANSPARENCY-GUIDE.md)
