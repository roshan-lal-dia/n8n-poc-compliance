# n8n Workflows - Quick Start Guide

## 📦 Three Workflows Created

### 1️⃣ Workflow A: Universal Extractor
**File:** `workflow-a-universal-extractor.json`  
**Purpose:** Extract text and images from PDF/DOCX/PPTX/images  
**Webhook:** `POST http://172.206.67.83:5678/webhook/extract`

**What it does:**
- Accepts file uploads via multipart/form-data
- Detects file type (PDF, DOCX, PPTX, PNG, JPG)
- Converts documents to PDF → extracts images
- Runs OCR (Tesseract) + Vision analysis (Florence-2)
- Returns structured JSON with full text and per-page data

**Test Command:**
```bash
curl -X POST http://172.206.67.83:5678/webhook/extract \
  -F "file=@/path/to/document.pdf"
```

---

### 2️⃣ Workflow B: KB Ingestion
**File:** `workflow-b-kb-ingestion.json`  
**Purpose:** Load compliance standards into Qdrant vector database  
**Webhook:** `POST http://172.206.67.83:5678/webhook/kb/ingest`

**What it does:**
- Calls Universal Extractor to process standard document
- Chunks text into 1000-word segments (200-word overlap)
- Generates embeddings using `nomic-embed-text` (Ollama)
- Stores vectors in Qdrant collection `compliance_standards`
- Records metadata in `kb_standards` Postgres table

**Test Command:**
```bash
curl -X POST "http://172.206.67.83:5678/webhook/kb/ingest?standardName=ISO27001&domain=Security&version=2022" \
  -F "file=@/path/to/standard.pdf"
```

**⚠️ IMPORTANT: Initialize Qdrant Collection First**
```bash
curl -X PUT http://172.206.67.83:6333/collections/compliance_standards \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }'
```

---

### 3️⃣ Workflow C: Audit Orchestrator
**File:** `workflow-c-audit-orchestrator.json`  
**Purpose:** Run AI-powered compliance audits with RAG  
**Webhook:** `POST http://172.206.67.83:5678/webhook/audit/run`

**What it does:**
1. Loads audit questions from `audit_questions` table (filtered by domain)
2. Retrieves evidence from `audit_evidence` table (by session_id)
3. For each question:
   - Generates query embedding
   - Searches Qdrant for relevant standards (RAG)
   - Calls LLM (llama3.2) for evaluation
   - Logs results to `audit_logs`
4. Computes overall compliance score
5. Returns detailed audit report

**Test Command:**
```bash
# Step 1: Create audit session
psql -h 172.206.67.83 -U n8n -d compliance_db -c \
  "INSERT INTO audit_sessions (session_id, domain, initiated_by) \
   VALUES (uuid_generate_v4(), 'Data Architecture', 'api_user') \
   RETURNING session_id;"

# Step 2: Upload evidence (repeat for each question)
curl -X POST http://172.206.67.83:5678/webhook/extract \
  -F "file=@/path/to/evidence.pdf" \
  > evidence.json

# Step 3: Store evidence in DB
# (Use the extracted data + session_id + q_id)

# Step 4: Run audit
curl -X POST http://172.206.67.83:5678/webhook/audit/run \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "<session-id-from-step-1>",
    "domain": "Data Architecture"
  }'
```

---

## 🚀 Import Instructions

### Method 1: n8n UI
1. Open http://172.206.67.83:5678
2. Login: `admin` / `ComplianceAdmin2026!`
3. Click **"+"** → **Import from File**
4. Upload each JSON file:
   - `workflow-a-universal-extractor.json`
   - `workflow-b-kb-ingestion.json`
   - `workflow-c-audit-orchestrator.json`
5. Activate each workflow (toggle switch)

### Method 2: Copy to VM
```bash
scp workflows/*.json azure-compliance:~/n8n-poc-compliance/workflows/
```

Then import via n8n UI.

---

## 🔧 Configuration Checklist

### 1. Postgres Credentials
Each workflow uses a Postgres node with credential ID "1" named "Compliance DB".

**Create in n8n:**
- Go to **Credentials** → **+ Add Credential**
- Type: **Postgres**
- Name: `Compliance DB`
- Host: `postgres`
- Port: `5432`
- Database: `compliance_db`
- User: `n8n`
- Password: `ComplianceDB2026!`
- SSL: `disable`

### 2. Qdrant Collection
```bash
curl -X PUT http://172.206.67.83:6333/collections/compliance_standards \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }'
```

### 3. Test Services
```bash
# Test Ollama
curl http://172.206.67.83:11434/api/tags

# Test Qdrant
curl http://172.206.67.83:6333/collections

# Test Florence
curl http://172.206.67.83:5000/health

# Test Postgres
psql -h 172.206.67.83 -U n8n -d compliance_db -c "SELECT COUNT(*) FROM audit_questions;"
```

---

## 📊 Database Schema Reference

### Tables Used
- `audit_questions` - Seed questions per domain (8 rows pre-loaded)
- `audit_sessions` - Tracks each audit run
- `audit_evidence` - Stores extracted content (JSONB)
- `audit_logs` - Evaluation results per question
- `kb_standards` - Metadata for ingested standards
- `file_registry` - SHA-256 deduplication

### Key Views
- `v_session_progress` - Real-time audit progress
- `v_latest_evidence` - Most recent evidence per question

---

## 🎯 Complete End-to-End Test

### Step 1: Ingest a Standard
```bash
curl -X POST "http://172.206.67.83:5678/webhook/kb/ingest?standardName=DataArchGuide&domain=Data%20Architecture&version=1.0" \
  -F "file=@data-architecture-standard.pdf"
```

### Step 2: Create Audit Session
```bash
SESSION_ID=$(psql -h 172.206.67.83 -U n8n -d compliance_db -t -c \
  "INSERT INTO audit_sessions (session_id, domain, initiated_by) \
   VALUES (uuid_generate_v4(), 'Data Architecture', 'test_user') \
   RETURNING session_id;")
echo $SESSION_ID
```

### Step 3: Upload Evidence
```bash
# Extract content
curl -X POST http://172.206.67.83:5678/webhook/extract \
  -F "file=@client-evidence.pdf" > evidence.json

# Store in DB (manual SQL for POC)
psql -h 172.206.67.83 -U n8n -d compliance_db -c \
  "INSERT INTO audit_evidence (session_id, q_id, domain, filename, file_hash, extracted_data) \
   VALUES ('$SESSION_ID', 'data_arch_q1', 'Data Architecture', 'client-evidence.pdf', \
   'abc123', '$(cat evidence.json | jq -c .)'::jsonb);"
```

### Step 4: Run Audit
```bash
curl -X POST http://172.206.67.83:5678/webhook/audit/run \
  -H "Content-Type: application/json" \
  -d "{
    \"sessionId\": \"$SESSION_ID\",
    \"domain\": \"Data Architecture\"
  }" | jq .
```

---

## 🔍 Troubleshooting

### Workflow Fails to Execute
- Check n8n logs: `docker logs compliance-n8n`
- Verify all services are healthy: `docker ps`
- Test internal network: `docker exec compliance-n8n curl http://ollama:11434/api/tags`

### Postgres Connection Errors
- Ensure credential is named exactly `Compliance DB`
- Host must be `postgres` (not `localhost`)
- Port: `5432`

### Qdrant Collection Not Found
- Run the collection initialization curl command
- Verify: `curl http://172.206.67.83:6333/collections`

### Slow LLM Response
- Normal! llama3.2 on CPU takes 30-120 seconds per question
- Check Ollama logs: `docker logs compliance-ollama`

---

## 📈 Performance Notes

**Workflow A (Universal Extractor)**
- PDF (10 pages): ~30-60 seconds
- DOCX/PPTX: +10s for conversion
- OCR + Florence run in parallel per page

**Workflow B (KB Ingestion)**
- 50-page standard: ~5-10 minutes
- Bottleneck: Ollama embeddings (CPU)
- Chunking: ~50 chunks per 5000 words

**Workflow C (Audit Orchestrator)**
- 8 questions: ~10-20 minutes total
- Per question: 60-120 seconds (LLM evaluation)
- Sequential processing (no parallelization)

---

## 🎉 Next Steps

1. **Import all 3 workflows** into n8n
2. **Configure Postgres credential** (see Configuration Checklist)
3. **Initialize Qdrant collection**
4. **Test Workflow A** with a sample PDF
5. **Ingest a standard** with Workflow B
6. **Run full audit** with Workflow C

**All files are ready in:** `workflows/` directory

**API Endpoints:**
- Extractor: `POST http://172.206.67.83:5678/webhook/extract`
- KB Ingest: `POST http://172.206.67.83:5678/webhook/kb/ingest`
- Audit Run: `POST http://172.206.67.83:5678/webhook/audit/run`
