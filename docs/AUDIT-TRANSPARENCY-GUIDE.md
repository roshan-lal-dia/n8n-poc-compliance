# Compliance Audit System - Complete Transparency Guide

**Purpose:** This document explains EXACTLY how the compliance audit system works internally, enabling you to verify every step, understand what's happening "under the hood", and debug issues. No AI black boxes - full transparency.

**Last Updated:** February 10, 2026

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [File Upload & Storage (Large File Support)](#2-file-upload--storage-large-file-support)
3. [Job Queue & Background Processing](#3-job-queue--background-processing)
4. [Evidence Extraction Pipeline](#4-evidence-extraction-pipeline)
5. [Deduplication Logic](#5-deduplication-logic)
6. [Evidence Consolidation & Limits](#6-evidence-consolidation--limits)
7. [RAG Search (Standards Retrieval)](#7-rag-search-standards-retrieval)
8. [AI Prompt Construction](#8-ai-prompt-construction)
9. [AI Evaluation Process](#9-ai-evaluation-process)
10. [Scoring & Aggregation](#10-scoring--aggregation)
11. [Status Tracking & Percentages](#11-status-tracking--percentages)
12. [Evidence Cleanup Policy](#12-evidence-cleanup-policy)
13. [Debugging & Verification Queries](#13-debugging--verification-queries)
14. [Manual Audit Reproduction](#14-manual-audit-reproduction)

---

## 1. System Architecture Overview

### Components

```
┌─────────────────┐
│   Client/UI     │
│  (HTTP Calls)   │
└────────┬────────┘
         │ POST /webhook/audit/submit (multipart)
         ↓
┌─────────────────┐
│  Workflow C1    │  Validate → Hash Files → Store to Disk → Queue Job
│  Entry Point    │  (Immediate Response: 202 Accepted)
└────────┬────────┘
         │ LPUSH to Redis
         ↓
┌─────────────────┐
│   Redis Queue   │  compliance:jobs:pending (FIFO)
│   (Job Store)   │
└────────┬────────┘
         │ RPOP (every 10s)
         ↓
┌─────────────────┐
│  Workflow C2    │  Extract → RAG → AI → Log → Aggregate
│  Worker (Cron)  │  (Background Processing)
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────────┐
│   audit_logs    │◄─────│  audit_sessions  │
│   (Progress)    │      │  (Master Record) │
└─────────────────┘      └──────────────────┘
         ↑
         │ Client polls every 3s
         │ GET /webhook/audit/status/:sessionId
         │
┌─────────────────┐
│  Workflow C3    │  Status Polling
│  (Real-time)    │  Returns: percentage, step, ETA
└─────────────────┘

After Completion:
GET /webhook/audit/results/:sessionId → Workflow C4 → Full Results
```

### Data Flow Summary

1. **Upload Phase (C1)**: Files → Disk (`/tmp/n8n_processing/sessions/{sessionId}/`), Job → Redis
2. **Processing Phase (C2)**: Redis → Worker → Workflow A → Postgres → Qdrant → Ollama → Postgres
3. **Monitoring Phase (C3)**: Postgres →  Status response (every 3s)
4. **Result Phase (C4)**: Postgres → Complete evaluation results

---

## 2. File Upload & Storage (Large File Support)

### Why Disk-Based Storage?

**Problem:** 300MB+ files cannot fit in n8n's in-memory buffer without crashing.  
**Solution:** Stream files directly to disk, store only metadata in memory/database.

### Upload Process (Workflow C1)

**Step 1: Multipart Parse**

```javascript
// Client sends:
POST /webhook/audit/submit
Content-Type: multipart/form-data

questions=[{"q_id":"q1","files":["doc1.pdf","doc2.docx"]}]
&doc1.pdf=<binary_data>
&doc2.docx=<binary_data>
&domain=Security
```

**Step 2: Size Validation**

```typescript
const totalSize = files.reduce((sum, f) => sum + f.fileSize, 0);
if (totalSize > 500 * 1024 * 1024) {  // 500MB limit
  throw new Error(`Total file size exceeds 500MB`);
}
```

**Why 500MB?** Balance between usefulness (multiple large reports) and memory safety.

**Step 3: Hash Calculation**

```javascript
const hash = crypto.createHash('sha256')
  .update(Buffer.from(binaryData, 'base64'))
  .digest('hex');
// Example: a3f7b8c2e1d4f6... (64-character hash)
```

**Purpose:** 
- Deduplication (same file uploaded multiple times)
- Unique file identification
- Integrity verification

**Step 4: Disk Storage**

```javascript
const sessionDir = `/tmp/n8n_processing/sessions/${sessionId}`;
fs.mkdirSync(sessionDir, { recursive: true });

const diskPath = path.join(sessionDir, `${hash}.bin`);
fs.writeFileSync(diskPath, buffer);
```

**Directory Structure:**
```
/tmp/n8n_processing/
└── sessions/
    └── 550e8400-e29b-41d4-a716-446655440000/
        ├── a3f7b8c2e1d4f6...bin  (hash of doc1.pdf)
        └── 7b2e9a1f3c5d8e...bin  (hash of doc2.docx)
```

**Why hash as filename?** Prevents name collisions if multiple files named "report.pdf" uploaded.

### Verification Query

```sql
-- Check session directory exists:
SELECT job_id, session_id FROM audit_sessions WHERE session_id = '<SESSION_ID>';

-- Files should exist at:
-- /tmp/n8n_processing/sessions/<SESSION_ID>/*.bin
```

```bash
# List files in session directory:
ls -lh /tmp/n8n_processing/sessions/<SESSION_ID>/
# Expected output: One .bin file per uploaded document
```

---

## 3. Job Queue & Background Processing

### Redis Queue Architecture

**Queue Name:** `compliance:jobs:pending` (List data structure)

**Why Redis?**
- Simple FIFO queue (LPUSH/RPOP)
- Atomic operations (thread-safe)
- Fast (in-memory)
- Persistent (AOF enabled)

**Job Payload Structure:**

```json
{
  "jobId": "abc-123-def-456",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "Security",
  "questions": [
    {
      "q_id": "privacy_q1",
      "evidence_files": [
        {
          "hash": "a3f7b8c2...",
          "originalName": "doc1.pdf",
          "fieldName": "doc1.pdf"
        }
      ]
    }
  ],
  "fileMap": {
    "a3f7b8c2...": {
      "fileName": "doc1.pdf",
      "fileSize": 2457600,
      "mimeType": "application/pdf",
      "diskPath": "/tmp/n8n_processing/sessions/.../a3f7b8c2...bin"
    }
  },
  "sessionDir": "/tmp/n8n_processing/sessions/550e8400...",
  "status": "queued",
  "createdAt": "2026-02-10T10:30:00.000Z"
}
```

### Worker Poll Cycle (Workflow C2)

**Trigger:** Cron every 10 seconds

```
10:30:00 → Check queue → Empty → Exit
10:30:10 → Check queue → Job found → Process
10:30:20 → Check queue → Already processing → Exit (skip)
...
```

**Dequeue Operation:**

```redis
RPOP compliance:jobs:pending
# Returns: Job JSON or (nil) if empty
```

**Why RPOP (not LPOP)?**  
FIFO behavior: oldest jo bs processed first.

### Graceful Degradation

**Scenario:** 10 audits submitted while worker busy processing one.

**Behavior:**
```
Queue depth: 0 → 1 → 2 → ... → 10
Worker: Process job 1 (2 min) → Process job 2 (2 min) → ...
Client: Polls status every 3s, sees "queued" → "processing" → "completed"
```

**No Rejections:** All jobs queued, processed sequentially. Client sees accurate ETAs.

### Verification Commands

```bash
# Check queue depth:
docker exec compliance-redis redis-cli LLEN compliance:jobs:pending

# Peek at next job (without removing):
docker exec compliance-redis redis-cli LRANGE compliance:jobs:pending -1 -1

# Check if job is processing (session status):
docker exec compliance-db psql -U n8n -d compliance_db -c \
  "SELECT session_id, status FROM audit_sessions WHERE status = 'processing';"
```

---

## 4. Evidence Extraction Pipeline

### Workflow A Integration

**What:** Universal file extractor (OCR + Vision AI)  
**Input:** Binary file from disk  
**Output:** JSONB with full_text, pages, diagrams

**Call from Workflow C2:**

```javascript
// Read file from disk (not database!)
const fileBuffer = fs.readFileSync(fileData.diskPath);
const base64Data = fileBuffer.toString('base64');

// HTTP POST to Workflow A
const extraction = await httpRequest({
  url: 'http://localhost:5678/webhook/extract',
  method: 'POST',
  body: {
    data: base64Data,
    mimeType: fileData.mimeType,
    fileName: fileData.fileName
  },
  timeout: 300000  // 5 min for large files
});
```

**Extraction Components:**

| Tool | Purpose | Output |
|------|---------|--------|
| LibreOffice | DOCX/PPTX → PDF | Standardized PDF |
| pdftoppm | PDF → PNG images (per page) | Page-1.png, Page-2.png, ... |
| Tesseract OCR | PNG → Text (eng, ara) | Plain text per page |
| Florence-2 | PNG → Vision analysis | Diagram descriptions |

**Per-Page Processing:**

```javascript
// Parallel execution for each page:
Page 1: [OCR Thread] + [Vision Thread] → Merge results
Page 2: [OCR Thread] + [Vision Thread] → Merge results
...

// Aggregation:
{
  "fullDocument": "combined text from all pages",
  "pages": [
    {
      "pageNumber": 1,
      "text": "OCR output...",
      "wordCount": 378,
      "visionAnalysis": {"description": "Flowchart showing..."},
      "isDiagram": false
    }
  ],
  "totalPages": 12,
  "totalWords": 4532,
  "has Diagrams": true
}
```

### Extraction Quality Indicators

**OCR Confidence:** Not currently exposed (Tesseract doesn't provide per-word confidence in stdout mode).

**Vision Analysis:** Florence-2 provides text descriptions, not confidence scores.

**To Verify Quality:**

```sql
SELECT filename,
       extracted_data->'totalPages' as pages,
       extracted_data->'totalWords' as words,
       extracted_data->'hasDiagrams' as diagrams,
       LENGTH(extracted_data->>'fullDocument') as text_length
FROM audit_evidence
WHERE session_id = '<SESSION_ID>';

-- Good extraction:
-- - words > 100 (per page)
-- - text_length > 1000
-- - hasDiagrams = true if document contains charts/diagrams
```

---

## 5. Deduplication Logic

### Scope: Within-Session Only

**Principle:** If the same file (by hash) is uploaded for multiple questions in one session, extract only once.

**Implementation (Workflow C2):**

```sql
-- Before extracting, check cache:
SELECT file_hash, extracted_data
FROM audit_evidence
WHERE session_id = :session_id
  AND q_id = :q_id
  AND file_hash = ANY(:evidence_hashes);
```

**Decision Tree:**

```
File hash: a3f7b8c2...
                │
                ↓
    ┌───────────┴───────────┐
    │  EXISTS in DB?        │
    └───────────┬───────────┘
                │
        ┌───────┴───────┐
       YES             NO
        │               │
    Use cached     Call Workflow A
    extracted_data     │
        │              Store to DB
        └───────┬──────┘
                │
          Consolidate evidence
```

**Example Scenario:**

```json
Questions: [
  {"q_id": "q1", "files": ["report.pdf"]},
  {"q_id": "q2", "files": ["report.pdf", "appendix.pdf"]}
]

Processing Flow:
Q1: Extract report.pdf (500ms) → Store → Use
Q2: Check cache → report.pdf FOUND → Use cached
    Extract appendix.pdf (600ms) → Store → Use
    
Total Extraction Time: 1.1s (saved 500ms)
```

**Why No Cross-Session Dedup?**

Evidence deleted after session completion (see Section 12). Can't reference deleted data.

### Verification Query

```sql
-- Check for duplicates within session:
SELECT q_id, file_hash, filename, created_at
FROM audit_evidence
WHERE session_id = '<SESSION_ID>'
ORDER BY file_hash, created_at;

-- If same hash appears multiple times with different created_at = dedup failed
-- If same hash appears once but used by multiple questions = dedup worked
```

---

## 6. Evidence Consolidation & Limits

### Why Limits?

**Problem:** AI models have context limits (llama3.2 = 32K tokens ≈ 128K chars).  
**Solution:** Truncate evidence to fit in prompt while preserving meaning.

### Consolidation Logic (Workflow C2)

**Per-File Limit:**

```javascript
for (const evidence of allEvidence) {
  const fullText = evidence.extractedData.fullDocument;
  const truncated = fullText.substring(0, 50000); // 50K chars per file
  
  combinedText += `\n\n=== ${evidence.filename} ===\n${truncated}`;
}
```

**Why 50K per file?** Preserves ~25-30 pages of text, catches executive summaries.

**Overall Limit:**

```javascript
if (combinedText.length > 200000) {
  combinedText = combinedText.substring(0, 200000);
  combinedText += '\n\n[Evidence truncated at 200,000 characters]';
}
```

**Why 200K total?** Leaves room for standards (3K chars) + question (500 chars) in 32K token context.

### Truncation Impact

**What's Lost:**
- Later pages of multi-document submissions
- Appendices, glossaries, reference sections

**What's Preserved:**
- First 50K chars per file (typically first 25-30 pages)
- Multi-file context (up to 4 full documents at 50K each)

**Mitigation Strategy:**
Guide users to submit concise evidence (executive summaries, key sections) rather than 300-page full reports.

### Verification Queries

```sql
-- Check evidence sizes:
SELECT q_id, filename,
       LENGTH(extracted_data->>'fullDocument') as original_chars,
       CASE
         WHEN LENGTH(extracted_data->>'fullDocument') > 50000 THEN 'TRUNCATED'
         ELSE 'FULL'
       END as status
FROM audit_evidence
WHERE session_id = '<SESSION_ID>'
ORDER BY q_id;

-- Check consolidation effect:
SELECT q_id,
       COUNT(*) as file_count,
       SUM(LENGTH(extracted_data->>'fullDocument')) as total_original,
       CASE
         WHEN SUM(LENGTH(extracted_data->>'fullDocument')) > 200000 THEN 200000
         ELSE SUM(LENGTH(extracted_data->>'fullDocument'))
       END as actual_used_chars
FROM audit_evidence
WHERE session_id = '<SESSION_ID>'
GROUP BY q_id;
```

---

## 7. RAG Search (Standards Retrieval)

### Purpose

Retrieve relevant compliance standards from knowledge base to inform AI evaluation.

### Process (Workflow C2)

**Step 1: Generate Question Embedding**

```javascript
// Call Ollama embedding API:
POST http://ollama:11434/api/embeddings
{
  "model": "nomic-embed-text",
  "prompt": "${questionText}\n\n${promptInstructions}"
}

// Returns: {"embedding": [768-dimensional vector]}
```

**Embedding Model Details:**
- Model: nomic-embed-text (optimized for semantic search)
- Dimensions: 768 floats
- Input: Question + instructions (NOT evidence)
- Output: Vector representing question meaning

**Step 2: Search Qdrant**

```javascript
POST http://qdrant:6333/collections/compliance_standards/points/search
{
  "vector": [0.123, -0.456, ...],  // 768 floats
  "limit": 5,
  "with_payload": true,
  "filter": {
    "must": [{"key": "domain", "match": {"value": "Security"}}]
  }
}
```

**Search Parameters:**
- **Limit:** 5 chunks (balance between context and noise)
- **Distance:** Cosine similarity (range: 0.0 - 1.0, higher = more relevant)
- **Filter:** Optional domain filter (only standards for Security/Privacy/etc.)

**Step 3: Format Results**

```javascript
ragSources = [
  {
    rank: 1,
    standardName: "ISO 27001:2022",
    chunkIndex: 42,
    relevanceScore: 0.87,  // Cosine similarity
    text: "Full chunk text (1000 words)",
    excerpt: "First 600 characters..."
  },
  // ... 4 more chunks
]
```

### Relevance Scoring Interpretation

| Score | Meaning | Action |
|-------|---------|--------|
| > 0.9 | Highly relevant | Direct match, trust heavily |
| 0.7 - 0.9 | Relevant | Good match, use confidently |
| 0.5 - 0.7 | Somewhat relevant | May provide context |
| < 0.5 | Weak match | Likely noise (but still included) |

**Current System:** No score filtering - all top 5 chunks included regardless of score.

### Verification Queries

```bash
# Check what standards are loaded:
curl -s http://localhost:6333/collections/compliance_standards | jq .

# Manual embedding generation:
curl -s http://localhost:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"YOUR_QUESTION"}' \
  | jq .embedding > question_emb.json

# Manual search (paste embedding):
curl -s http://localhost:6333/collections/compliance_standards/points/search \
  -H 'Content-Type: application/json' \
  -d "{\"vector\": $(cat question_emb.json), \"limit\": 5, \"with_payload\": true}" \
  | jq '.result[] | {score, standardName: .payload.standardName, text: .payload.text[:200]}'

# Check if domain has standards:
docker exec compliance-db psql -U n8n -d compliance_db -c \
  "SELECT domain, standard_name, total_chunks FROM kb_standards WHERE domain = 'Security';"
```

---

## 8. AI Prompt Construction

### Template (Workflow C2)

```text
COMPLIANCE AUDIT EVALUATION

QUESTION: ${questionText}

INSTRUCTIONS: ${promptInstructions}

RELEVANT COMPLIANCE STANDARDS:
1. [ISO 27001:2022] (Relevance: 0.87)
${chunk1Text (600 chars)}

2. [GDPR Article 32] (Relevance: 0.82)
${chunk2Text (600 chars)}

... (up to 5 chunks)

EVIDENCE FROM SUBMITTED DOCUMENTS:
=== filename1.pdf ===
${evidence1 (max 50K chars)}

=== filename2.docx ===
${evidence2 (max 50K chars)}

---

Evaluate compliance with the question based on the provided evidence and standards.
Respond in JSON format with the following structure:
{
  "compliant": boolean,
  "score": 0-100,
  "confidence": 0-100,
  "findings": "detailed description",
  "evidence_summary": "specific references",
  "gaps": ["list"],
  "recommendations": ["list"]
}
```

### Component Sizes

| Component | Max Size | Actual Typical |
|-----------|----------|----------------|
| Question | ~500 chars | 200-300 chars |
| Instructions | ~2000 chars | 500-1000 chars |
| RAG Standards (5) | 3000 chars | 3000 chars (600 each) |
| Evidence (per file) | 50,000 chars | 20,000-50,000 |
| Evidence (total) | 200,000 chars | 50,000-150,000 |
| **Total Prompt** | ~205,500 chars | ~56,000 chars |

**Token Estimate:** ~51,000 tokens (4 chars/token average) → Fits in 32K context with some headroom.

### Prompt Optimization Techniques

**1. Standards Truncation:**
```javascript
text.substring(0, 600)  // Only excerpt, not full chunk
```
Why: Most relevant info in first 600 chars of 1000-word chunk.

**2. Evidence Sectioning:**
```text
=== filename ===  // Clear file boundaries
```
Why: AI can reference "In security_policy.pdf..." in findings.

**3. JSON Format Enforcement:**
```json
{
  "format": "json",  // Ollama parameter
  "schema": {...}    // Provided in prompt
}
```
Why: Forces structured output, easier parsing.

### Verification (During Live Run)

```javascript
// In Workflow C2, "Build AI Prompt" node:
const prompt = `...`;
console.log("=== PROMPT LENGTH ===", prompt.length);
console.log("=== PROMPT PREVIEW ===", prompt.substring(0, 1000));

// Check in n8n execution logs:
// Settings → Executions → Click execution → View logs
```

**Offline Verification:**

```sql
-- Get question details:
SELECT q_id, question_text, prompt_instructions
FROM audit_questions
WHERE q_id = 'privacy_q1';

-- Approximate prompt size:
SELECT 
  q_id,
  LENGTH(question_text) as q_len,
  LENGTH(prompt_instructions) as inst_len,
  LENGTH(extracted_data->>'fullDocument') as evidence_len,
  CASE 
    WHEN LENGTH(extracted_data->>'fullDocument') > 50000 THEN 50000
    ELSE LENGTH(extracted_data->>'fullDocument')
  END as truncated_evidence_len,
  3000 as rag_approx,
  (...) as estimated_total_prompt_len
FROM audit_evidence e
JOIN audit_questions q ON e.q_id = q.q_id
WHERE e.session_id = '<SESSION_ID>';
```

---

## 9. AI Evaluation Process

### Ollama Configuration

**Model:** llama3.2 (Llama 3.2 3B parameters)

**API Call (Workflow C2):**

```javascript
POST http://ollama:11434/api/generate
{
  "model": "llama3.2",
  "prompt": "<full prompt from section 8>",
  "format": "json",
  "stream": false,
  "options": {
    "temperature": 0.3,
    "num_ctx": 32768,
    "num_predict": 2000
  }
}
```

**Parameters Explained:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| temperature | 0.3 | Low randomness = deterministic responses |
| num_ctx | 32768 | Context window (32K tokens) |
| num_predict | 2000 | Max response length (tokens) |
| stream | false | Return complete response, not chunks |
| format | json | Force JSON output |

**Timeout:** 600,000ms (10 minutes)  
**Why:** Large prompts (50K+ chars) take 2-5 min to process on CPU-only inference.

### Expected Response Schema

```json
{
  "compliant": true,
  "score": 82,
  "confidence": 85,
  "findings": "The document clearly describes data encryption at rest using AES-256 as specified in Section 3.2. Transit encryption via TLS 1.3 is documented in Section 4.1. Key management procedures reference AWS KMS in Section 3.3. Backup encryption confirmed in Section 5.2.",
  "evidence_summary": "Found explicit references in security_policy.pdf pages 8-12. Architecture diagram on page 10 shows encryption layer. Compliance matrix in appendix confirms all requirements met.",
  "gaps": [],
  "recommendations": [
    "Consider documenting key rotation schedule more explicitly",
    "Add encryption performance metrics to monitoring dashboard"
  ]
}
```

**Field Validation:**

```javascript
// Fallback on missing fields:
if (!evaluation.compliant) evaluation.compliant = false;
if (!evaluation.score) evaluation.score = 0;
if (!evaluation.confidence) evaluation.confidence = 0;
if (!evaluation.findings) evaluation.findings = 'No findings provided';
if (!evaluation.gaps) evaluation.gaps = [];
if (!evaluation.recommendations) evaluation.recommendations = [];
```

### Common AI Failures & Handling

**1. JSON Parse Error**

```javascript
try {
  evaluation = JSON.parse(aiResponse.response);
} catch (e) {
  evaluation = {
    compliant: false,
    score: 0,
    confidence: 0,
    findings: 'AI response parsing failed: ' + e.message,
    gaps: ['Unable to evaluate due to format error']
  };
}
```

**Causes:**
- AI didn't follow JSON format (despite `format: json` parameter)
- Response truncated mid-JSON

**2. Hallucination**

**Example:** AI claims "Section 5.2 describes..." but evidence doesn't have section numbers.

**Mitigation:** Include `evidence_summary` field requiring specific references.

**Verification:**
```javascript
// Manual check:
const evidenceText = '<from consolidation stage>';
const aiClaim = evaluation.evidence_summary;

// Search for claimed references:
if (!evidenceText.includes('Section 5.2')) {
  console.warn('Possible hallucination detected');
}
```

**3. Score Inconsistency**

**Example:** `compliant: true` but `score: 45` (contradictory).

**No Automatic Fix:** Trust AI output, log for review.

### Verification Queries

```sql
-- Get raw AI response for manual review:
SELECT q_id,
       ai_response->>'compliant' as compliant,
       ai_response->>'score' as score,
       ai_response->>'findings' as findings
FROM audit_logs
WHERE session_id = '<SESSION_ID>' AND step_name = 'completed';

-- Check for parse failures:
SELECT COUNT(*)
FROM audit_logs
WHERE session_id = '<SESSION_ID>'
  AND ai_response->>'findings' LIKE '%parsing failed%';
```

**Docker Logs (Live Monitoring):**

```bash
# Watch Ollama processing:
docker logs -f compliance-ollama

# Look for:
# - Model loading messages
# - Token processing speeds
# - Memory usage warnings
```

---

## 10. Scoring & Aggregation

### Per-Question Scoring

**Source:** AI evaluation JSON response  
**Fields:**
- `score`: 0-100 (compliance level)
- `confidence`: 0-100 (AI certainty)
- `compliant`: boolean (pass/fail)

**Storage:**

```sql
-- Stored in audit_logs:
INSERT INTO audit_logs (session_id, q_id, ai_response, ...)
VALUES ('<session>', 'privacy_q1', 
        '{"score": 82, "confidence": 85, "compliant": true, ...}', ...)
```

### Session-Level Aggregation (Workflow C2)

**Formula:**

```javascript
const scores = allResults.map(r => r.json.evaluation.score);
const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
const roundedScore = Math.round(avgScore * 100) / 100;  // 2 decimal places
```

**Example:**

```
Question 1: 82
Question 2: 78
Question 3: 91

Average: (82 + 78 + 91) / 3 = 83.67
```

**Update Session:**

```sql
UPDATE audit_sessions
SET overall_compliance_score = 83.67,
    answered_questions = 3,
    status = 'completed'
WHERE session_id = '<session>';
```

### Weighted Scoring (Not Implemented)

**Current:** All questions have equal weight.  
**Future Enhancement:** Add `weight` column to `audit_questions` table.

```sql
-- Hypothetical weighted average:
SELECT SUM(score * weight) / SUM(weight) as weighted_score
FROM results;
```

### Verification Queries

```sql
-- Manual score calculation:
SELECT 
  session_id,
  COUNT(*) as total_questions,
  AVG((ai_response->>'score')::numeric) as calculated_avg,
  (SELECT overall_compliance_score 
   FROM audit_sessions 
   WHERE session_id = '<SESSION_ID>') as stored_score
FROM audit_logs
WHERE session_id = '<SESSION_ID>' AND step_name = 'completed'
GROUP BY session_id;

-- Both should match (calculated_avg ≈ stored_score)

-- Check individual scores:
SELECT q_id,
       ai_response->>'score' as score,
       ai_response->>'confidence' as confidence,
       ai_response->>'compliant' as compliant
FROM audit_logs
WHERE session_id = '<SESSION_ID>' AND step_name = 'completed'
ORDER BY created_at;
```

---

## 11. Status Tracking & Percentages

### Status Flow

```
queued (0%)
    ↓
processing (5-95%)
    ├─ extracting (10-30%)
    ├─ searching (30-80%)
    └─ evaluating (85-95%)
    ↓
completed (100%)
```

###Percentage Calculation Logic (Workflow C2)

**Per-Question Basis:**

```javascript
// Question 1 of 3:
extracting:  10 + (0 / 3 * 80) = 10%
searching:   30 + (0 / 3 * 50) = 30%
evaluating:  85 + (0 / 3 * 10) = 85%
completed:   95 + (0 / 3 * 5)  = 95%

// Question 2 of 3:
extracting:  10 + (1 / 3 * 80) = 37%
searching:   30 + (1 / 3 * 50) = 47%
evaluating:  85 + (1 / 3 * 10) = 88%
completed:   95 + (1 / 3 * 5)  = 97%

// Question 3 of 3:
extracting:  10 + (2 / 3 * 80) = 63%
searching:   30 + (2 / 3 * 50) = 63%
evaluating:  85 + (2 / 3 * 10) = 92%
completed:   95 + (2 / 3 * 5)  = 98%

// Final completion:
100%
```

**Logging:**

```sql
INSERT INTO audit_logs (session_id, q_id, step_name, percentage, ...)
VALUES ('<session>', 'privacy_q1', 'extracting', 10, ...);

-- Updated as processing progresses:
UPDATE audit_logs 
SET step_name = 'searching', percentage = 30
WHERE session_id = '<session>' AND q_id = 'privacy_q1';
```

### Client Polling (Workflow C3)

**Endpoint:** `GET /webhook/audit/status/:sessionId`

**Response:**

```json
{
  "sessionId": "550e8400...",
  "status": "processing",
  "overallPercentage": 47,
  "currentStep": "searching",
  "totalQuestions": 3,
  "answeredQuestions": 1,
  "estimatedCompletionAt": "2026-02-10T10:35:00Z",
  "questionProgress": [
    {"qId": "q1", "status": "success", "percentage": 100},
    {"qId": "q2", "status": "in_progress", "percentage": 47},
    {"qId": "q3", "status": "pending", "percentage": 0}
  ]
}
```

**Polling Strategy:**

```javascript
const interval = setInterval(async () => {
  const status = await fetch(`/webhook/audit/status/${sessionId}`).then(r => r.json());
  
  updateProgressBar(status.overallPercentage);
  
  if (status.status === 'completed') {
    clearInterval(interval);
    fetchResults();
  }
}, 3000);  // Every 3 seconds
```

### Verification Queries

```sql
-- Track percentage progression:
SELECT q_id, step_name, percentage, message, created_at
FROM audit_logs
WHERE session_id = '<SESSION_ID>'
ORDER BY created_at;

-- Expected output: Percentages increase monotonically
-- 0% → 5% → 10% → ... → 100%

-- Calculate stage durations:
WITH stage_times AS (
  SELECT step_name,
         MIN(created_at) as start_time,
         MAX(created_at) as end_time
  FROM audit_logs
  WHERE session_id = '<SESSION_ID>'
  GROUP BY step_name
)
SELECT step_name,
       end_time - start_time as duration
FROM stage_times
ORDER BY start_time;

-- Typical durations:
-- queued: <1s
-- extracting: 30-60s per question
-- searching: 2-5s per question
-- evaluating: 60-120s per question
```

---

## 12. Evidence Cleanup Policy

### When Evidence is Deleted

**Trigger:** Session status = 'completed'  
**Location:** Workflow C2, final cleanup nodes

**What's Deleted:**

1. **Database Records:**
```sql
DELETE FROM audit_evidence WHERE session_id = '<session>';
```

2. **Disk Files:**
```javascript
fs.rmSync(`/tmp/n8n_processing/sessions/${sessionId}`, {
  recursive: true,
  force: true
});
```

**What's Preserved:**

- `audit_sessions` record (metadata)
- `audit_logs` records (including `ai_response` JSON)
- `audit_questions` (master question library)

### Why Delete Evidence?

**Reasons:**
1. **Disk Space:** Evidence can be 100MB+ per session
2. **Privacy:** User-uploaded documents may contain PII
3. **Performance:** Large JSONB columns slow down queries

**Cost:** Can't re-run evaluation on same evidence without re-uploading.

### Deduplication Impact

**Scenario:** Evidence deleted after session 1, same file uploaded in session 2.

```
Session 1:
  - Upload file (hash: a3f7b8c2...)
  - Extract → Store in audit_evidence
  - Complete → DELETE audit_evidence

Session 2:
  - Upload same file (hash: a3f7b8c2...)
  - Check cache → NOT FOUND (deleted from session 1)
  - Extract again → Store
```

**No cross-session dedup** because evidence doesn't persist.

### Verification Queries

```sql
-- Check if evidence exists:
SELECT COUNT(*) FROM audit_evidence WHERE session_id = '<SESSION_ID>';
-- Should return 0 if session completed

-- Verify session record preserved:
SELECT session_id, status, overall_compliance_score, completed_at
FROM audit_sessions
WHERE session_id = '<SESSION_ID>';
-- Should still return row

-- Verify evaluation results preserved:
SELECT q_id, ai_response
FROM audit_logs
WHERE session_id = '<SESSION_ID>' AND step_name = 'completed';
-- Should return all question evaluations

-- Check disk cleanup:
-- ls /tmp/n8n_processing/sessions/<SESSION_ID>
-- Should return: No such file or directory
```

---

## 13. Debugging & Verification Queries

### Session Not Starting

**Symptom:** Status stuck at "queued" indefinitely.

**Checks:**

```bash
# Is Redis queue populated?
redis-cli LLEN compliance:jobs:pending
# Should show (integer) > 0

# Is worker running?
docker logs compliance-n8n --tail 50 | grep "Cron: Every 10s"
# Should show executions every 10s

# Manual dequeue test:
redis-cli RPOP compliance:jobs:pending
# Should return job JSON
```

**Fix:** Restart n8n: `docker restart compliance-n8n`

### Extraction Failures

**Symptom:** Status stuck at "extracting", or score = 0 with findings = "parsing failed".

**Checks:**

```sql
-- Check extraction logs:
SELECT message, created_at
FROM audit_logs
WHERE session_id = '<SESSION_ID>' AND step_name = 'extracting'
ORDER BY created_at DESC;

-- Check if evidence was stored:
SELECT COUNT(*) FROM audit_evidence WHERE session_id = '<SESSION_ID>';
-- Should match number of uploaded files
```

```bash
# Check Workflow A health:
curl http://localhost:5678/webhook/extract/health
# Should return 200 OK

# Check Florence service:
docker logs compliance-florence --tail 50
# Look for OOM errors or connection issues
```

**Fix:** 
- If Florence crashed: `docker restart compliance-florence`
- If file too large: Split into smaller files

### Low Confidence Scores

**Symptom:** All evaluations have `confidence < 50`.

**Cause:** RAG not finding relevant standards.

**Checks:**

```sql
-- Check if standards exist for domain:
SELECT domain, standard_name, total_chunks
FROM kb_standards
WHERE domain = '<YOUR_DOMAIN>';
-- Should return >= 1 row

-- Check question domain matches:
SELECT q.q_id, q.domain, s.standard_name
FROM audit_questions q
LEFT JOIN kb_standards s ON q.domain = s.domain
WHERE q.q_id IN ('<YOUR_QUESTIONS>');
-- Each question should have matching standards
```

```bash
# Check Qdrant collection:
curl -s http://localhost:6333/collections/compliance_standards | jq .result.vectors_count
# Should show > 0
```

**Fix:** Ingest standards via Workflow B before running audits.

### Slow Processing

**Symptom:** Each question takes > 5 minutes.

**Checks:**

```bash
# Check Ollama performance:
docker stats compliance-ollama
# Look for CPU % (should be ~90-100% during evaluation)

# Check if model is loaded:
curl http://localhost:11434/api/tags
# Should list llama3.2 and nomic-embed-text
```

**Bottlenecks:**
- **Ollama:** CPU-bound, add GPU for 10x speedup
- **Extraction:** Large PDFs (100+ pages) take 2-3 min
- **Network:** Internal Docker network should be fast (<1ms latency)

**Mitigation:**
- Use smaller evidence files
- Reduce `num_predict` in Ollama options (faster but shorter responses)

---

## 14. Manual Audit Reproduction

To manually reproduce an audit evaluation and verify AI reasoning:

### Step 1: Get Session Data

```sql
-- Get session info:
SELECT session_id, domain, total_questions
FROM audit_sessions
WHERE session_id = '<SESSION_ID>';

-- Get question details:
SELECT q_id, question_text, prompt_instructions
FROM audit_questions
WHERE q_id = '<Q_ID>';

-- Get evidence (if still exists):
SELECT filename, extracted_data->>'fullDocument' as evidence_text
FROM audit_evidence
WHERE session_id = '<SESSION_ID>' AND q_id = '<Q_ID>';

-- If evidence deleted, extract from ai_response:
SELECT ai_response->>'evidence_summary' as what_ai_saw
FROM audit_logs
WHERE session_id = '<SESSION_ID>' AND q_id = '<Q_ID>' AND step_name = 'completed';
```

### Step 2: Generate Question Embedding

```bash
curl -s -X POST http://localhost:11434/api/embeddings \
  -d '{
    "model": "nomic-embed-text",
    "prompt": "YOUR_QUESTION_TEXT\n\nYOUR_INSTRUCTIONS"
  }' | jq .embedding > question_emb.json
```

### Step 3: Search Qdrant

```bash
curl -s -X POST http://localhost:6333/collections/compliance_standards/points/search \
  -H 'Content-Type: application/json' \
  -d "{
    \"vector\": $(cat question_emb.json),
    \"limit\": 5,
    \"with_payload\": true
  }" | jq '.result[] | {score, standard: .payload.standardName, text: .payload.text[:600]}' \
  > rag_results.json
```

### Step 4: Build Prompt Manually

```bash
cat > manual_prompt.txt <<EOF
COMPLIANCE AUDIT EVALUATION

QUESTION: $(psql ... -c "SELECT question_text FROM audit_questions WHERE q_id = '<Q_ID>'")

INSTRUCTIONS: $(psql ... -c "SELECT prompt_instructions FROM audit_questions WHERE q_id = '<Q_ID>'")

RELEVANT COMPLIANCE STANDARDS:
$(cat rag_results.json)

EVIDENCE FROM SUBMITTED DOCUMENTS:
$(psql ... -c "SELECT extracted_data->>'fullDocument' FROM audit_evidence WHERE session_id = '<SESSION_ID>' AND q_id = '<Q_ID>'")

---

Evaluate compliance... (full template from Section 8)
EOF
```

### Step 5: Call Ollama Directly

```bash
curl -s -X POST http://localhost:11434/api/generate \
  -d "{
    \"model\": \"llama3.2\",
    \"prompt\": \"$(cat manual_prompt.txt | jq -Rs .)\",
    \"format\": \"json\",
    \"stream\": false,
    \"options\": {
      \"temperature\": 0.3,
      \"num_ctx\": 32768,
      \"num_predict\": 2000
    }
  }" | jq .response > manual_ai_response.json
```

### Step 6: Compare Results

```bash
# Get stored result:
psql ... -c "SELECT ai_response FROM audit_logs 
             WHERE session_id = '<SESSION_ID>' AND q_id = '<Q_ID>' 
             AND step_name = 'completed'" \
  > stored_response.json

# Compare:
diff <(jq -S . stored_response.json) <(jq -S . manual_ai_response.json)

# Should show minimal differences (AI has some randomness even at temp=0.3)
```

**If Results Differ Significantly:**
- Check if evidence was truncated differently
- Verify same RAG sources used (Qdrant collection might have changed)
- Check Ollama model version (`docker exec compliance-ollama ollama list`)

---

## Appendix A: Database Schema Quick Reference

```sql
-- Master Question Library
audit_questions (q_id PK, domain, question_text, prompt_instructions)

-- Evidence Storage (temp, deleted after session)
audit_evidence (session_id, q_id, file_hash, extracted_data JSONB)
  UNIQUE(session_id, q_id, file_hash)  -- Deduplication constraint

-- Execution Logs (permanent)
audit_logs (session_id, q_id, step_name, percentage, ai_response JSONB)

-- Session Master (permanent)
audit_sessions (session_id PK, domain, status, overall_compliance_score, job_id)

-- Knowledge Base Metadata
kb_standards (domain, standard_name, file_hash, total_chunks)
```

## Appendix B: Service URLs

| Service | Internal URL | External URL |
|---------|--------------|--------------|
| n8n | http://n8n:5678 | http://<VM_IP>:5678 |
| Postgres | postgres:5432 | <VM_IP>:5432 |
| Redis | redis:6379 | <VM_IP>:6379 |
| Qdrant | http://qdrant:6333 | http://<VM_IP>:6333 |
| Ollama | http://ollama:11434 | http://<VM_IP>:11434 |
| Florence | http://florence:5000 | http://<VM_IP>:5000 |

## Appendix C: Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Total file size exceeds 500MB" | Upload too large | Split files or compress |
| "Session not found" | Invalid session ID | Check spelling, or session expired |
| "Question references file not uploaded" | File name mismatch | Ensure questions JSON matches uploaded files |
| "AI response parsing failed" | LLM didn't return JSON | Check Ollama logs, retry |
| "Extraction timeout" | File too complex | Reduce file size, check system resources |
| "No standards found for domain" | KB not populated | Run Workflow B to ingest standards |

---

**End of Transparency Guide**

For questions or issues, check:
1. This guide
2. `docker logs compliance-<service>`
3. SQL queries in Section 13
4. n8n execution logs (UI → Executions → View)
