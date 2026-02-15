# Workflow C2: Audit Worker - Deep Dive Technical Documentation

## Overview
This document explains the complete flow of Workflow C2, which processes audit jobs from a Redis queue, evaluates compliance questions using RAG (Retrieval-Augmented Generation), and generates compliance scores.

---

## 1. Query Text vs Instructions - CLARIFICATION

### The Issue You Observed
You noticed that `queryText` and `instructions` appear to be the same. Here's what's actually happening:

```javascript
const question = $('Load Question').first().json;
const queryText = `${question.question_text}\n\n${question.prompt_instructions || ''}`;
```

### What SHOULD Happen:
- `question.question_text` = "Are security policies documented and approved?"
- `question.prompt_instructions` = "Evaluate whether formal security policies exist, are documented in writing, have been officially approved by management, and are accessible to relevant personnel."
- `queryText` = **Combined string**: 
  ```
  Are security policies documented and approved?
  
  Evaluate whether formal security policies exist, are documented in writing, have been officially approved by management, and are accessible to relevant personnel.
  ```

### Why `queryText` Matters:
The `queryText` is sent to Ollama's embedding model to create a **vector representation** that captures both:
1. **What** is being asked (question_text)
2. **How** to evaluate it (prompt_instructions)

This combined embedding produces better RAG search results because it encodes the evaluation context.

### If They Look The Same:
Check your database - the `prompt_instructions` column in `audit_questions` might be:
- NULL
- Empty string
- Or contains the same text as `question_text` (data entry error)

**Action Required**: Update your `audit_questions` table to ensure each question has distinct `prompt_instructions` that provide evaluation guidance.

---

## 2. RAG Search Flow - How It Actually Works

### Step-by-Step RAG Process

#### Step 2A: Generate Question Embedding
**Node**: "Ollama: Generate Embedding"

```javascript
// INPUT: queryText from previous node
{
  "model": "nomic-embed-text",
  "prompt": "Are security policies documented and approved?\n\nEvaluate whether formal..."
}

// OUTPUT: Vector embedding
{
  "embedding": [0.234, -0.456, 0.789, ... (768 dimensions)]
}
```

**What Gets Embedded**: The QUESTION (with instructions), NOT the evidence files.

#### Step 2B: Search Vector Database
**Node**: "Qdrant: Search Standards"

**What's in Qdrant**:
- Pre-embedded compliance standards chunks (loaded by Workflow B)
- Each chunk has a vector representation of compliance standard text
- Metadata like `standardName`, `domain`, `chunkIndex`

**Search Payload Structure**:
```javascript
{
  vector: [0.234, -0.456, ...],  // Question embedding from Step 2A
  limit: 5,                       // Top 5 results
  with_payload: true,             // Include full text
  filter: {                       // Optional domain filter
    must: [
      { key: 'domain', match: { value: 'ISO 27001' } }
    ]
  }
}
```

**How Search Works**:
1. Qdrant compares the question vector to ALL stored standard vectors
2. Uses cosine similarity to find closest matches
3. Returns top 5 most relevant compliance standard chunks
4. Higher score = more semantically similar to the question

**Why This Is Powerful**:
- Question: "Are passwords encrypted?"
- Qdrant finds standards about "credential protection", "cryptographic controls", "authentication security"
- Even if exact words don't match, semantic meaning does

#### Step 2C: Format RAG Results
**Node**: "Format RAG Results"

**What RAG Returns**:
```javascript
{
  ragSources: [
    {
      rank: 1,
      standardName: "ISO 27001:2013 - Access Control",
      chunkIndex: 42,
      relevanceScore: 0.87,  // High similarity
      text: "Organizations shall implement authentication controls including password complexity requirements, encryption of stored credentials...",
      excerpt: "Organizations shall implement authentication controls including password complexity requirements, encryption of stored credentials, and regular password rotation policies. Passwords must be stored using strong cryptographic hash functions (e.g., bcrypt, Argon2) with appropriate salt values. Default passwords must be changed upon initial system access. Password history should prevent reuse of recent passwords...", // First 600 chars
      metadata: { section: "A.9.4.3", version: "2013" }
    },
    {
      rank: 2,
      standardName: "NIST 800-53 - IA-5 Authenticator Management",
      relevanceScore: 0.82,
      // ... more fields
    },
    // ... 3 more results
  ],
  totalSources: 5
}
```

---

## 3. Evidence Flow - What Gets Embedded vs What Doesn't

### Clear Distinction:

| Data Type | Gets Embedded? | Purpose |
|-----------|---------------|---------|
| **Compliance Standards** | ✅ YES (by Workflow B) | Stored in Qdrant for RAG search |
| **Questions + Instructions** | ✅ YES (by Workflow C2) | To search Qdrant for relevant standards |
| **Evidence Files (PDFs, DOCX)** | ❌ NO | Extracted as TEXT, sent directly to LLM |

### Why Evidence Files Aren't Embedded:
1. **They're user-submitted proof** - unique to each audit session
2. **Too large** - Embedding millions of user docs is expensive
3. **Not needed** - The LLM reads the full text directly
4. **Temporary** - Evidence is deleted after evaluation

### Evidence Text Flow:
```
Upload PDF → Extract Text (Workflow A) → Store in audit_evidence → 
Load from DB → Concatenate all evidence → Send to LLM as plain text
```

---

## 4. Build AI Prompt - The Complete Context Assembly

### Node: "Build AI Prompt"

**Inputs from 3 Sources**:

1. **Question Data** (from Extract Embedding node):
   ```javascript
   {
     questionId: "Q001",
     questionText: "Are security policies documented?",
     instructions: "Evaluate whether formal security policies exist...",
     questionDomain: "ISO 27001"
   }
   ```

2. **Evidence Data** (from Consolidate Evidence Text node):
   ```javascript
   {
     sessionId: "abc-123",
     qId: "Q001",
     evidenceText: "\n\n=== Evidence File: SecurityPolicy.pdf ===\nCompany Security Policy Document\nVersion 2.1 - Approved by CEO on 2024-01-15\n\n1. Introduction\nThis document establishes...\n\n=== Evidence File: ApprovalEmail.pdf ===\nFrom: ceo@company.com\nSubject: Security Policy Approval...",
     evidenceLength: 45230,
     sourceFiles: [
       { filename: "SecurityPolicy.pdf", pages: 12, words: 3400 },
       { filename: "ApprovalEmail.pdf", pages: 1, words: 250 }
     ]
   }
   ```

3. **RAG Data** (from Format RAG Results node):
   ```javascript
   {
     ragSources: [
       {
         standardName: "ISO 27001:2013 - A.5.1.1",
         relevanceScore: 0.87,
         excerpt: "Policies for information security shall be defined, approved by management, published..."
       },
       // ... more standards
     ]
   }
   ```

### Prompt Construction Logic:

```javascript
// Build RAG section
const ragSection = ragSources.length > 0 
  ? ragSources.map((source, i) => 
      `${i+1}. [${source.standardName}] (Relevance: ${source.relevanceScore.toFixed(2)})
${source.excerpt}
`
    ).join('\n')
  : 'No specific compliance standards found in knowledge base. Evaluate based on general industry best practices.';
```

**Example RAG Section Output**:
```
1. [ISO 27001:2013 - A.5.1.1] (Relevance: 0.87)
Policies for information security shall be defined, approved by management, published and communicated to employees and relevant external parties...

2. [NIST 800-53 - PL-1] (Relevance: 0.82)
Organizations must develop, document, and disseminate security and privacy policies...

3. [SOC 2 - CC1.2] (Relevance: 0.79)
The entity has documented and communicated security policies...
```

### Final Prompt Structure:

```
COMPLIANCE AUDIT EVALUATION

QUESTION: Are security policies documented and approved?

INSTRUCTIONS: Evaluate whether formal security policies exist, are documented in writing, have been officially approved by management, and are accessible to relevant personnel.

RELEVANT COMPLIANCE STANDARDS:
1. [ISO 27001:2013 - A.5.1.1] (Relevance: 0.87)
Policies for information security shall be defined, approved by management, published and communicated...

2. [NIST 800-53 - PL-1] (Relevance: 0.82)
Organizations must develop, document, and disseminate security and privacy policies...

EVIDENCE FROM SUBMITTED DOCUMENTS:
=== Evidence File: SecurityPolicy.pdf ===
Company Security Policy Document
Version 2.1 - Approved by CEO on 2024-01-15
[... full extracted text ...]

=== Evidence File: ApprovalEmail.pdf ===
From: ceo@company.com
Subject: Security Policy Approval
[... full extracted text ...]

---

Evaluate compliance with the question based on the provided evidence and standards.
Respond in JSON format with the following structure:
{
  "compliant": boolean,
  "score": 0-100,
  "confidence": 0-100,
  "findings": "detailed description of what was found",
  "evidence_summary": "specific references to evidence that supports the evaluation",
  "gaps": ["list of missing or insufficient elements"],
  "recommendations": ["actionable improvements"]
}
```

### Handling Long Contexts:

**Size Limits (from "Consolidate Evidence Text" node)**:
- **Per file**: 50,000 characters max
- **Total evidence**: 200,000 characters max
- **Total prompt**: Typically 220,000-250,000 characters (fits in 32k token context)

**Truncation Strategy**:
```javascript
// Per-file truncation
const truncated = fullText.substring(0, 50000);

// Overall truncation
if (combinedText.length > 200000) {
  combinedText = combinedText.substring(0, 200000) + '\n\n[Evidence truncated at 200,000 characters]';
}
```

**Ollama Configuration**:
```javascript
{
  "model": "llama3.2",
  "options": {
    "num_ctx": 32768,      // 32k token context window
    "num_predict": 2000,   // Max 2000 tokens for response
    "temperature": 0.3     // Low temp for consistency
  }
}
```

---

## 5. Score Aggregation - How Final Scores Are Calculated

### Node: "Aggregate Scores"

**Input**: All evaluated questions from "Parse AI Response" node

```javascript
const allResults = $('Parse AI Response').all();
// Example: 5 questions were evaluated

[
  { json: { qId: "Q001", evaluation: { score: 85, compliant: true } } },
  { json: { qId: "Q002", evaluation: { score: 92, compliant: true } } },
  { json: { qId: "Q003", evaluation: { score: 60, compliant: false } } },
  { json: { qId: "Q004", evaluation: { score: 78, compliant: true } } },
  { json: { qId: "Q005", evaluation: { score: 88, compliant: true } } }
]
```

**Calculation**:
```javascript
const scores = allResults.map(r => r.json?.evaluation?.score || 0);
// scores = [85, 92, 60, 78, 88]

const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
// avgScore = (85 + 92 + 60 + 78 + 88) / 5 = 403 / 5 = 80.6

const overallScore = Math.round(avgScore * 100) / 100;
// overallScore = 80.6 (rounded to 2 decimals)
```

**Output**:
```javascript
{
  sessionId: "abc-123",
  overallScore: 80.6,
  totalQuestions: 5,
  questionResults: [
    { qId: "Q001", score: 85, compliant: true },
    { qId: "Q002", score: 92, compliant: true },
    { qId: "Q003", score: 60, compliant: false },
    { qId: "Q004", score: 78, compliant: true },
    { qId: "Q005", score: 88, compliant: true }
  ]
}
```

This overall score is then:
1. Stored in `audit_sessions.overall_compliance_score`
2. Logged to `audit_logs`
3. Returned via Workflow C4 (Results Retrieval)

---

## 6. Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: DEQUEUE & PREPARE                                           │
│ Redis Queue → Parse Job → Extract fileMap, sessionDir               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: SPLIT BY QUESTION (Loop starts here)                        │
│ Job with 3 questions → 3 parallel executions                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: EVIDENCE EXTRACTION (per question)                          │
│ Check Cache → Load from DB or Extract (Workflow A) → Store to DB    │
│ Result: Full text of all evidence files for this question           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: RAG RETRIEVAL (per question)                                │
│                                                                      │
│ Question + Instructions                                              │
│         ↓                                                            │
│  [Embed with Ollama]                                                 │
│         ↓                                                            │
│  Question Vector: [0.23, -0.45, 0.78, ...]                          │
│         ↓                                                            │
│  [Search Qdrant Vector DB]                                           │
│         ↓                                                            │
│  Top 5 Relevant Compliance Standards:                                │
│  - ISO 27001:2013 - A.5.1.1 (score: 0.87)                           │
│  - NIST 800-53 - PL-1 (score: 0.82)                                 │
│  - SOC 2 - CC1.2 (score: 0.79)                                      │
│  - CIS Controls v8 - 4.1 (score: 0.76)                              │
│  - GDPR Article 24 (score: 0.71)                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: BUILD MASTER PROMPT                                         │
│                                                                      │
│ Combine:                                                             │
│  ✓ Question text                                                     │
│  ✓ Evaluation instructions                                           │
│  ✓ RAG-retrieved compliance standards (5 excerpts)                   │
│  ✓ Evidence text from submitted files                                │
│                                                                      │
│ Total context: ~50k-250k characters                                  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: LLM EVALUATION                                               │
│                                                                      │
│ Send to Ollama (llama3.2, 32k context)                              │
│         ↓                                                            │
│ LLM reads:                                                           │
│  - What question is asking                                           │
│  - How to evaluate (instructions)                                    │
│  - What standards require (RAG results)                              │
│  - What evidence shows (submitted docs)                              │
│         ↓                                                            │
│ LLM generates JSON:                                                  │
│ {                                                                    │
│   "compliant": true,                                                 │
│   "score": 85,                                                       │
│   "confidence": 90,                                                  │
│   "findings": "SecurityPolicy.pdf shows formal policy document...",  │
│   "evidence_summary": "Policy v2.1 approved by CEO on 2024-01-15", │
│   "gaps": ["No evidence of employee acknowledgment"],               │
│   "recommendations": ["Implement policy acknowledgment tracking"]   │
│ }                                                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: STORE RESULTS (per question)                                │
│ → Write to audit_logs with JSON response                            │
│ → Update session percentage (5→10→30→85→95)                         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: AGGREGATE (after all questions)                             │
│                                                                      │
│ Question 1: 85 points                                                │
│ Question 2: 92 points                                                │
│ Question 3: 60 points                                                │
│ ─────────────────────                                                │
│ Average: 79 points                                                   │
│                                                                      │
│ → Update audit_sessions.overall_compliance_score = 79               │
│ → Update audit_sessions.status = 'completed'                        │
│ → Set completed_at timestamp                                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: CLEANUP                                                      │
│ → Delete /tmp/n8n_processing/{sessionId}/ directory                 │
│ → Delete audit_evidence rows (keep audit_logs for history)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Key Insights & Design Decisions

### Why Separate Embedding for Questions vs Standards?
- **Questions**: Embedded on-demand for each audit (dynamic)
- **Standards**: Pre-embedded once and stored (static reference library)
- This avoids re-embedding standards millions of times

### Why RAG Instead of Fine-Tuning?
- **Flexibility**: Update standards without retraining
- **Transparency**: See which standards influenced the evaluation
- **Accuracy**: LLM sees exact standard text, not compressed weights
- **Cost**: Cheaper than training custom models

### Why Cache Evidence Extractions?
- **Performance**: PDF extraction is slow (2-10 seconds per file)
- **Consistency**: Same file, same extraction across questions
- **Cost**: Reduces Workflow A calls by ~70%

### Why Truncate Evidence?
- **Token limits**: LLMs have fixed context windows
- **Quality**: First 50k chars usually contain key info
- **Speed**: Shorter prompts = faster inference

### Why Delete Evidence Files After?
- **Privacy**: User data not stored long-term
- **Storage**: Each audit could be 50-100MB
- **Compliance**: "Right to be forgotten" easier

---

## 8. Troubleshooting Guide

### Issue: "queryText and instructions are the same"
**Cause**: `prompt_instructions` column in database is NULL or empty
**Fix**: Run SQL to populate:
```sql
UPDATE audit_questions 
SET prompt_instructions = 'Evaluate whether [specific criteria]...'
WHERE prompt_instructions IS NULL OR prompt_instructions = '';
```

### Issue: "RAG returns 0 results"
**Cause**: Qdrant collection empty or domain filter too strict
**Fix**: 
1. Check Qdrant: `curl http://qdrant:6333/collections/compliance_standards`
2. Run Workflow B to ingest standards
3. Remove domain filter if using non-standard domains

### Issue: "LLM returns invalid JSON"
**Cause**: Context too long or model hallucinating
**Fix**:
1. Check `promptLength` in "Build AI Prompt" output
2. Reduce evidence file size limits (50k → 30k)
3. Increase `temperature` to 0.5 for more structured output

### Issue: "Overall score is 0"
**Cause**: Aggregation failed, no valid evaluations
**Fix**:
1. Check `audit_logs` for individual question scores
2. Verify "Parse AI Response" is extracting scores correctly
3. Ensure all questions completed before aggregation

---

## 9. Performance Metrics (Typical)

| Stage | Time (per question) | Bottleneck |
|-------|---------------------|------------|
| Cache Check | 50ms | Database query |
| Extraction (cache miss) | 2-8s | PDF processing |
| Question Embedding | 200-500ms | Ollama CPU |
| RAG Search | 100-300ms | Qdrant vector search |
| LLM Evaluation | 10-30s | Ollama inference |
| Store Results | 100ms | Database write |
| **Total** | **12-40s** | **LLM is slowest** |

**For 5 questions**: 60-200 seconds total (1-3 minutes)

---

## 10. Database Schema Reference

### audit_sessions
```sql
session_id UUID PRIMARY KEY
status VARCHAR -- 'pending' → 'processing' → 'completed'
answered_questions INT
overall_compliance_score DECIMAL(5,2)
completed_at TIMESTAMP
```

### audit_logs
```sql
session_id UUID
q_id VARCHAR
step_name VARCHAR -- 'processing', 'extracting', 'searching', 'evaluating', 'completed'
status VARCHAR -- 'in_progress', 'success', 'error'
ai_response JSONB -- {score, compliant, findings, gaps, recommendations}
percentage INT -- Progress 0-100
```

### audit_evidence (cache)
```sql
session_id UUID
q_id VARCHAR
file_hash VARCHAR -- SHA-256 for deduplication
extracted_data JSONB -- {fullDocument, totalPages, totalWords, hasDiagrams}
evidence_order INT
```

### audit_questions (reference)
```sql
q_id VARCHAR PRIMARY KEY
question_text TEXT -- "Are security policies documented?"
prompt_instructions TEXT -- "Evaluate whether formal policies exist..."
domain VARCHAR -- "ISO 27001", "SOC 2", etc.
```

---

## Summary

This workflow implements a sophisticated **RAG-enhanced compliance evaluation system**:

1. **Embeds questions** (not evidence) to find relevant standards
2. **Searches vector DB** for compliance requirements
3. **Combines** standards + evidence + instructions into master prompt
4. **Uses LLM** to evaluate compliance based on all context
5. **Aggregates** individual scores into overall compliance rating

The key innovation is **semantic search of standards** rather than generic LLM knowledge, ensuring evaluations are grounded in actual compliance frameworks.
