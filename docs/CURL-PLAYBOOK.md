# cURL Playbook — Unifi NPC Compliance Workflows

All commands derive directly from the workflow JSON definitions. No external docs were used.

---

## Global Setup

```bash
BASE="http://172.206.67.83:5678"
API_KEY="your-api-key-here"   # value configured in the 'webhook-api-key' n8n credential (header: X-API-Key)
```

> **Test mode** (workflow not yet activated): swap `/webhook/` → `/webhook-test/` in every URL.

---

## Endpoint Map

| Workflow | Method | Path | Notes |
|---|---|---|---|
| A — Universal Extractor | `POST` | `/webhook/extract` | Sync; returns extracted content |
| B — KB Ingestion | `POST` | `/webhook/kb/ingest` | Sync; embeds + stores in Qdrant + Postgres |
| C1 — Audit Entry | `POST` | `/webhook/audit/submit` | Async; returns 202 + sessionId |
| C3 — Status Poll | `GET` | `/webhook/audit/status/:sessionId` | Sync; returns live progress |
| C4 — Results Retrieval | `GET` | `/webhook/audit/results/:sessionId` | Sync; returns full evaluation |
| C2 — Audit Worker | *(internal — cron every 10 s)* | — | Not callable by users |

---

## Supported File Types (Workflows A, B, C1)

| Extension | Processing |
|---|---|
| `pdf` | pdftoppm → per-page OCR + Florence vision |
| `pptx` | LibreOffice → PDF → pdftoppm → OCR + vision |
| `docx` | LibreOffice → PDF → pdftoppm → OCR + vision |
| `png` / `jpg` / `jpeg` | Copied as single-page image → OCR + vision |
| `xlsx` / `xls` / `xlsm` / `csv` | LibreOffice → PDF → pdftoppm → OCR + vision |

Anything else → **400 `Unsupported file type`**.

---

## Input Modes (Workflows A, B, C1)

Every upload endpoint supports two mutually exclusive input modes:

| Mode | Content-Type | When to use |
|---|---|---|
| **Direct upload** | `multipart/form-data` | File is local / sent from browser |
| **Azure Blob reference** | `application/json` | File already lives in Azure Blob Storage |

Both modes are handled by the same webhook path; the `Fetch Azure Blob` code node detects which mode was used.

---
---

## Workflow A — Universal Extractor

**`POST /webhook/extract`**

Extracts text and vision analysis from a document. Returns a single aggregated JSON with per-page detail. Called internally by Workflow B and C2 as well.

---

### Direct upload: PDF

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/document.pdf"
```

### Direct upload: PPTX

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/slides.pptx"
```

### Direct upload: DOCX

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/policy.docx"
```

### Direct upload: Image (PNG / JPG / JPEG)

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/diagram.png"
```

### Direct upload: Excel / CSV (xlsx, xls, xlsm, csv)

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/data.xlsx"
```

### Azure Blob — single file

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "blobPath": "uploads/document.pdf",
    "azureContainer": "compliance"
  }'
```

> `azureContainer` is optional — defaults to `"compliance"`.

### Azure Blob — multi-file (named fields)

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "blobFiles": {
      "file0": "uploads/report.pdf",
      "file1": { "blobPath": "uploads/annex.docx", "container": "archive" }
    }
  }'
```

> Each value can be a plain blob path string (uses `azureContainer` default) or an object with its own `blobPath` + `container`.

---

### Success response (200)

```json
{
  "filePrefix": "1708512000000_a1b2c3d4_",
  "originalFileName": "document.pdf",
  "totalPages": 5,
  "totalWords": 1423,
  "hasDiagrams": false,
  "fullDocument": "Concatenated text from all pages...",
  "pages": [
    {
      "pageNumber": 1,
      "text": "Page 1 content...",
      "wordCount": 310,
      "visionAnalysis": { "caption": "Text-heavy document page" },
      "isDiagram": false
    }
  ]
}
```

> `isDiagram: true` when `wordCount < 50` (image-heavy / diagram slide).

---

### Error: no file and no blobPath / blobFiles (400)

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```json
{ "error": "No file provided", "status": 400 }
```

### Error: unsupported file type (400)

```bash
curl -s -X POST "$BASE/webhook/extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/file.zip"
```

```json
{ "error": "Unsupported file type: zip", "status": 400 }
```

### Error: service dependency down — Florence / Ollama / Qdrant (503)

The workflow runs a health check before processing. If any dependency is unreachable:

```json
{
  "error": "Service Dependency Check Failed. One or more services (Florence, Ollama, Qdrant) are unavailable.",
  "status": 503,
  "details": { "exitCode": 1, "stderr": "..." }
}
```

### Error: missing / wrong API key (401)

```bash
curl -s -X POST "$BASE/webhook/extract" -F "file=@doc.pdf"
```

```json
{ "message": "Authorization data is wrong!" }
```

---
---

## Workflow B — KB Ingestion

**`POST /webhook/kb/ingest`**

Ingests a compliance standard document into the knowledge base: extracts text (via Workflow A), chunks it (1000 words / 200 overlap), embeds each chunk via Ollama `nomic-embed-text`, upserts to Qdrant `compliance_standards`, and records metadata in Postgres. SHA-256 file hash prevents duplicate ingestion.

**Required fields (body or query params alongside the file):**
- `standardName` — display name of the standard
- `domain` — compliance domain (e.g. `"Information Security"`, `"Privacy"`)

**Optional:**
- `version` — defaults to `"1.0"`

---

### Direct upload: new standard

```bash
curl -s -X POST "$BASE/webhook/kb/ingest" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/iso27001.pdf" \
  -F "standardName=ISO 27001:2022" \
  -F "domain=Information Security" \
  -F "version=2022"
```

### Direct upload: DOCX standard (minimal fields)

```bash
curl -s -X POST "$BASE/webhook/kb/ingest" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/gdpr_art32.docx" \
  -F "standardName=GDPR Article 32" \
  -F "domain=Privacy"
```

### Azure Blob — single file ingestion

```bash
curl -s -X POST "$BASE/webhook/kb/ingest" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "blobPath": "standards/nist_csf.pdf",
    "azureContainer": "compliance",
    "standardName": "NIST CSF 2.0",
    "domain": "Cybersecurity",
    "version": "2.0"
  }'
```

---

### Success response (200) — new file ingested

```json
{
  "status": "success",
  "message": "Standard ingested successfully",
  "standardName": "ISO 27001:2022",
  "domain": "Information Security",
  "chunksCreated": 47,
  "dbRecordId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

### Success response (200) — duplicate file (already ingested)

The SHA-256 hash matches an existing DB record; extraction is skipped entirely.

```json
{
  "message": "File already ingested",
  "standardName": "ISO 27001:2022",
  "status": "skipped",
  "dbId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

### Error: no file and no blobPath (400)

```bash
curl -s -X POST "$BASE/webhook/kb/ingest" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "standardName": "ISO 27001", "domain": "Security" }'
```

```json
{ "error": "Missing file or metadata", "status": 400 }
```

### Error: service dependency down (503)

Same 503 shape as Workflow A — KB ingestion calls Workflow A internally; the health check fires first.

---
---

## Workflow C1 — Audit Entry

**`POST /webhook/audit/submit`**

Validates inputs, writes files to disk (`/tmp/n8n_processing/<sessionId>/`), creates an audit session in Postgres, enqueues a job to Redis, and returns **202 Accepted** immediately. Workflow C2 picks up the job asynchronously (every 10 s).

**Content-Type:** `multipart/form-data` (direct) or `application/json` (Azure Blob)

**Required:**
- `questions` — JSON string: array of `{ "question_id": "...", "files": ["<fieldName>", ...] }`
  - `question_id` must match a `question_id` that exists in the Postgres `questions` table
  - `files` must list the **multipart field names** (direct upload) or **blobFiles keys** (Azure Blob) of the uploaded evidence
- At least one evidence file (binary or blobFiles reference)

**Optional:**
- `domain` — string; defaults to `"General"` if omitted

**File size limit:** 500 MB total across all uploaded files.

---

### Direct upload: single question, single file

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[{"question_id":"data_arch_q1","files":["evidence1"]}]' \
  -F "evidence1=@/path/to/architecture_diagram.pdf" \
  -F "domain=Data Architecture"
```

### Direct upload: multiple questions sharing files

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[
    {"question_id":"privacy_q1","files":["policy","data_map"]},
    {"question_id":"privacy_q2","files":["data_map","risk_register"]},
    {"question_id":"security_q1","files":["risk_register"]}
  ]' \
  -F "policy=@/path/to/privacy_policy.pdf" \
  -F "data_map=@/path/to/data_mapping.docx" \
  -F "risk_register=@/path/to/risk_register.xlsx" \
  -F "domain=Privacy"
```

### Direct upload: mixed file types

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[
    {"question_id":"infosec_q1","files":["pdf_doc","pptx_slides","diagram_img"]}
  ]' \
  -F "pdf_doc=@/path/to/policy.pdf" \
  -F "pptx_slides=@/path/to/overview.pptx" \
  -F "diagram_img=@/path/to/architecture.png" \
  -F "domain=Information Security"
```

### Azure Blob: multi-file evidence (blobFiles)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      {"question_id":"privacy_q1","files":["policy","data_map"]},
      {"question_id":"privacy_q2","files":["data_map"]}
    ],
    "blobFiles": {
      "policy": "evidence/privacy_policy.pdf",
      "data_map": { "blobPath": "evidence/data_mapping.docx", "container": "archive" }
    },
    "domain": "Privacy"
  }'
```

> `questions` can be a JSON array object (not just string) when sending `application/json`.

### Large file test (100 MB+)

```bash
dd if=/dev/urandom of=/tmp/large_evidence.bin bs=1M count=100

curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[{"question_id":"storage_q1","files":["big_file"]}]' \
  -F "big_file=@/tmp/large_evidence.bin" \
  -F "domain=Data Storage"
```

---

### Success response (202)

```json
{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "jobId": "f9e8d7c6-b5a4-3210-9876-fedcba012345",
  "status": "queued",
  "totalQuestions": 3,
  "message": "Audit submitted successfully. Poll /webhook/audit-status-webhook/audit/status/a1b2c3d4-... for progress.",
  "estimatedCompletionMinutes": 8
}
```

> `estimatedCompletionMinutes` = `ceil(totalQuestions × 2.5)`

---

### Error: missing `questions` field (500)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F "evidence=@/path/to/doc.pdf"
```

```json
{
  "error": "Missing \"questions\" parameter. Expected JSON array: [{\"question_id\":\"q1\",\"files\":[\"file1.pdf\"]}]. Received structure: ...",
  "status": 500
}
```

### Error: invalid `questions` JSON (500)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=not-valid-json' \
  -F "f=@doc.pdf"
```

```json
{ "error": "Invalid questions JSON format: Unexpected token ...", "status": 500 }
```

### Error: `questions` is empty array (500)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[]' \
  -F "f=@doc.pdf"
```

```json
{ "error": "Questions must be non-empty array. Got: object", "status": 500 }
```

### Error: question missing `question_id` (500)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[{"files":["doc"]}]' \
  -F "doc=@doc.pdf"
```

```json
{ "error": "Each question must have a \"question_id\" field", "status": 500 }
```

### Error: question has no `files` array (500)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[{"question_id":"q1"}]' \
  -F "doc=@doc.pdf"
```

```json
{ "error": "Question q1 has no files specified", "status": 500 }
```

### Error: `files` references a field name that was not uploaded (500)

```bash
curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[{"question_id":"q1","files":["wrong_name"]}]' \
  -F "actual_file=@doc.pdf"
```

```json
{ "error": "Question q1 references file \"wrong_name\" which was not uploaded", "status": 500 }
```

### Error: total file size > 500 MB (500)

```json
{ "error": "Total file size exceeds 500MB limit (current: 512MB)", "status": 500 }
```

---
---

## Workflow C3 — Status Poll

**`GET /webhook/audit/status/:sessionId`**

Returns the current state of an audit session. Poll every 3–5 s until `status` is `"completed"` or `"failed"`.

**Session lifecycle:** `queued` → `processing` → `completed` | `failed`

---

### Poll a session

```bash
SESSION_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

curl -s "$BASE/webhook/audit/status/$SESSION_ID" \
  -H "X-API-Key: $API_KEY"
```

### Success response (200) — processing

```json
{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "jobId": "f9e8d7c6-b5a4-3210-9876-fedcba012345",
  "status": "processing",
  "domainId": 3,
  "overallPercentage": 45,
  "totalQuestions": 4,
  "answeredQuestions": 1,
  "currentStep": "ai_evaluation",
  "startedAt": "2026-02-21T10:00:00.000Z",
  "completedAt": null,
  "estimatedCompletionAt": "2026-02-21T10:10:00.000Z",
  "overallScore": null,
  "questionProgress": [
    {
      "questionId": "privacy_q1",
      "status": "completed",
      "step": "ai_evaluation",
      "percentage": 100,
      "lastUpdate": "2026-02-21T10:04:30.000Z"
    },
    {
      "questionId": "privacy_q2",
      "status": "processing",
      "step": "extraction",
      "percentage": 40,
      "lastUpdate": "2026-02-21T10:05:10.000Z"
    }
  ]
}
```

### Success response (200) — queued (worker not yet picked up)

```json
{
  "sessionId": "...",
  "status": "queued",
  "overallPercentage": 0,
  "currentStep": "queued",
  "totalQuestions": 2,
  "answeredQuestions": 0,
  "overallScore": null,
  "questionProgress": []
}
```

### Success response (200) — completed

```json
{
  "sessionId": "...",
  "status": "completed",
  "overallPercentage": 100,
  "totalQuestions": 4,
  "answeredQuestions": 4,
  "currentStep": "completed",
  "completedAt": "2026-02-21T10:09:45.000Z",
  "overallScore": 72.5,
  "questionProgress": [ ... ]
}
```

### Success response (200) — failed

```json
{
  "sessionId": "...",
  "status": "failed",
  "overallPercentage": 20,
  "currentStep": "failed",
  "overallScore": null
}
```

### Error: session not found (404)

```bash
curl -s "$BASE/webhook/audit/status/nonexistent-id" \
  -H "X-API-Key: $API_KEY"
```

```json
{ "error": "Session not found", "status": 404 }
```

### Bash polling loop

```bash
SESSION_ID="<your-session-id>"

while true; do
  RESP=$(curl -s "$BASE/webhook/audit/status/$SESSION_ID" -H "X-API-Key: $API_KEY")
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  PCT=$(echo "$RESP"   | python3 -c "import sys,json; print(json.load(sys.stdin).get('overallPercentage',0))")
  echo "$(date '+%H:%M:%S')  status=$STATUS  progress=${PCT}%"
  [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]] && break
  sleep 5
done
```

---
---

## Workflow C4 — Results Retrieval

**`GET /webhook/audit/results/:sessionId`**

Returns full per-question evaluations for a completed session. Returns 404 if the session does not exist or has not yet reached `"completed"` status — always confirm via C3 first.

---

### Fetch results

```bash
SESSION_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

curl -s "$BASE/webhook/audit/results/$SESSION_ID" \
  -H "X-API-Key: $API_KEY"
```

### Success response (200)

```json
{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "domainId": 3,
  "status": "completed",
  "startedAt": "2026-02-21T10:00:00.000Z",
  "completedAt": "2026-02-21T10:09:45.000Z",
  "totalQuestions": 3,
  "answeredQuestions": 3,
  "overallScore": 72.33,
  "summary": {
    "compliantCount": 2,
    "nonCompliantCount": 1,
    "averageConfidence": 84
  },
  "results": [
    {
      "questionId": "privacy_q1",
      "question": "Does the organisation maintain a data processing register?",
      "questionDomain": "Privacy",
      "evaluatedAt": "2026-02-21T10:04:30.000Z",
      "evaluation": {
        "compliant": true,
        "score": 88,
        "confidence": 91,
        "findings": "A comprehensive data processing register was found.",
        "evidence_summary": "Page 3 of privacy_policy.pdf lists all processing activities.",
        "gaps": [],
        "recommendations": ["Consider annual review cadence."]
      }
    },
    {
      "questionId": "privacy_q2",
      "question": "Are DSAR procedures documented?",
      "questionDomain": "Privacy",
      "evaluatedAt": "2026-02-21T10:07:10.000Z",
      "evaluation": {
        "compliant": false,
        "score": 45,
        "confidence": 78,
        "findings": "No formal DSAR procedure found in submitted documents.",
        "evidence_summary": "Privacy policy mentions DSAR but provides no operational procedure.",
        "gaps": ["No DSAR response SLA", "No escalation path defined"],
        "recommendations": [
          "Create a DSAR procedure document with response timelines.",
          "Define responsible team for DSAR requests."
        ]
      }
    }
  ]
}
```

> The `evaluation` object is the raw parsed AI response (JSON object stored in Postgres `ai_response` column). All fields — `compliant`, `score`, `confidence`, `findings`, `evidence_summary`, `gaps`, `recommendations` — are produced by Ollama `llama3.2`.

### Pretty-print to terminal

```bash
curl -s "$BASE/webhook/audit/results/$SESSION_ID" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

### Save to file

```bash
curl -s "$BASE/webhook/audit/results/$SESSION_ID" \
  -H "X-API-Key: $API_KEY" \
  -o "results_${SESSION_ID}.json"
```

### Extract summary line only

```bash
curl -s "$BASE/webhook/audit/results/$SESSION_ID" \
  -H "X-API-Key: $API_KEY" | python3 -c "
import sys, json
r = json.load(sys.stdin)
s = r['summary']
print(f\"Score: {r['overallScore']}  Compliant: {s['compliantCount']}/{r['totalQuestions']}  AvgConfidence: {s['averageConfidence']}%\")
"
```

### Error: session not found or not completed (404)

```bash
curl -s "$BASE/webhook/audit/results/nonexistent-or-in-progress-id" \
  -H "X-API-Key: $API_KEY"
```

```json
{ "error": "Session not found or not completed", "status": 404 }
```

---
---

## Full End-to-End Flow

```bash
BASE="http://172.206.67.83:5678"
API_KEY="your-api-key-here"

# ── 1. Ingest a compliance standard (run once per standard) ───────────────────
curl -s -X POST "$BASE/webhook/kb/ingest" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@./standards/iso27001.pdf" \
  -F "standardName=ISO 27001:2022" \
  -F "domain=Information Security" \
  -F "version=2022"

# ── 2. Submit audit ───────────────────────────────────────────────────────────
SUBMIT=$(curl -s -X POST "$BASE/webhook/audit/submit" \
  -H "X-API-Key: $API_KEY" \
  -F 'questions=[
    {"question_id":"infosec_q1","files":["network","policy"]},
    {"question_id":"infosec_q2","files":["policy","incidents"]}
  ]' \
  -F "network=@./evidence/network_diagram.pdf" \
  -F "policy=@./evidence/security_policy.docx" \
  -F "incidents=@./evidence/incident_log.xlsx" \
  -F "domain=Information Security")

echo "Submit: $SUBMIT"
SESSION_ID=$(echo "$SUBMIT" | python3 -c "import sys,json; print(json.load(sys.stdin)['sessionId'])")
echo "Session: $SESSION_ID"

# ── 3. Poll until done ────────────────────────────────────────────────────────
while true; do
  RESP=$(curl -s "$BASE/webhook/audit/status/$SESSION_ID" -H "X-API-Key: $API_KEY")
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  PCT=$(echo "$RESP"   | python3 -c "import sys,json; print(json.load(sys.stdin).get('overallPercentage',0))")
  echo "$(date '+%H:%M:%S')  $STATUS  ${PCT}%"
  [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]] && break
  sleep 5
done

# ── 4. Retrieve results ───────────────────────────────────────────────────────
if [[ "$STATUS" == "completed" ]]; then
  curl -s "$BASE/webhook/audit/results/$SESSION_ID" \
    -H "X-API-Key: $API_KEY" \
    | python3 -m json.tool | tee "results_${SESSION_ID}.json"
else
  echo "Audit failed — inspect session logs."
fi
```

---

## HTTP Status Code Reference

| Code | Meaning | Workflows |
|---|---|---|
| `200` | OK | A (success), B (success / skipped), C3 (all), C4 (success) |
| `202` | Accepted | C1 (job queued) |
| `400` | Bad Request | A (no file, unsupported type), B (no file) |
| `401` | Unauthorized | All — missing / wrong `X-API-Key` |
| `404` | Not Found | C3 (session missing), C4 (missing or not completed) |
| `500` | Internal error | C1 (validation failures, parse errors, thrown exceptions) |
| `503` | Service Unavailable | A, B — Florence / Ollama / Qdrant health-check failed |
