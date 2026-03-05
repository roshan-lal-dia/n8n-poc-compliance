# NPC Compliance AI Document Intelligence System - Technical Status Report

**Project:** n8n Compliance AI Document Intelligence Engine
**Document Date:** March 4, 2026

---

## Executive Summary

The NPC Compliance AI Document Intelligence System is an operational AI-powered Document Intelligence Engine that valuates organizational compliance against 12 data management domains using document analysis, vision AI, and retrieval-augmented generation (RAG). The system is deployed on Azure infrastructure with GPU acceleration and is fully production-ready.

**Key Capabilities:**
- **6 Operational Workflows:** Handles extraction, ingestion, and background evaluation.
- **Microservices Architecture:** 6 cleanly decoupled containerized services orchestrated via Docker Compose.
- **Compliance Scope:** 159 audit questions across 12 domains.
- **AI/ML Engine:** GPU-accelerated inference utilizing Mistral Nemo 12B and Florence-2-large-ft.
- **Caching Layer:** Master caching system bypassing redundant evaluations.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

The system uses an async job queue with six workflows that handle different parts of the process:

```text
┌─────────────┐     ┌──────────────────────────────────────────┐     ┌────────────┐
│  Frontend   │────▶│  n8n Workflow Engine (6 workflows)       │────▶│  Qdrant    │
│  / API      │     │  A: Extract  B: Ingest  C1: Submit      │     │  (RAG)     │
│  Clients    │◀────│  C2: Worker  C3: Poll   C4: Results     │◀────│  768-dim   │
└─────────────┘     └───────┬──────────┬───────────┬───────────┘     └────────────┘
                            │          │           │
                    ┌───────▼──┐  ┌────▼────┐  ┌───▼──────────┐
                    │ Florence │  │  Redis  │  │  PostgreSQL  │
                    │ -2 (GPU) │  │  Queue  │  │  (sessions,  │
                    │ OCR +    │  │  C1→C2  │  │   evidence,  │
                    │ Vision   │  └─────────┘  │   logs, KB)  │
                    └──────────┘               └──────────────┘
                    ┌──────────┐               ┌──────────────┐
                    │ Mistral  │               │  Azure Blob  │
                    │ Nemo 12B │               │  Storage     │
                    │ via      │               │  (file       │
                    │ Ollama   │               │   uploads)   │
                    └──────────┘               └──────────────┘
```

---

## 2. Microservices Deep-Dive

The system is deployed as a suite of 6 tightly integrated Docker containers managed via Docker Compose (`docker-compose.prod.yml`), operating on a dedicated bridge network (`compliance-network`).

### 2.1 n8n (Workflow Orchestrator)
- **Role:** Main execution engine orchestrating API logic and background workers.
- **Dockerfile / Build:** Extends the official Alpine/Node image. It is heavily customized to install `python3`, `poppler-utils` (`pdftoppm`), `libreoffice`, and `openjdk11`. This allows the workflow to natively execute Python scripts, parse Excel rules, and convert DOCX/PPTX to PDF/Images immediately without external dependencies.
- **Binary Handling:** Configured with `N8N_DEFAULT_BINARY_DATA_MODE=filesystem` to prevent database bloat, cleanly streaming binaries to memory or isolated disk volumes.
- **Ports:** `5678`

### 2.2 Qdrant (Targeted Vector Database)
- **Role:** High-performance vector search engine for the Knowledge Base.
- **Container Details:** Utilizes `qdrant/qdrant:latest` operating natively via Docker volumes.
- **Configuration:** Operates on 768-dimensional embeddings formatted by our chosen text models. Designed to answer multi-dimensional similarity mapping queries. 
- **Ports:** Exposes `6333` for REST payload execution and `6334` for internal gRPC configuration.

### 2.3 Florence AI (Vision & OCR Sidecar)
- **Role:** Dedicated visual model resolving diagram layouts and processing dense document OCR.
- **Dockerfile / Build:** A custom Docker build located in `./florence-service`. Utilizes a `python:3.10-slim` base, natively installing `PyTorch`, `flash_attn`, and Azure-compatible CUDA dependencies. Wraps Microsoft's `Florence-2-large-ft` within a lightweight Flask API (`app.py`).
- **GPU Interface:** Provisions 1 NVIDIA GPU logic exclusively via Docker `deploy.resources.reservations`.
- **Integration:** Avoids HTTP base64 payload limitations by natively sharing a mounted volume (`/tmp/n8n_processing`) with n8n.
- **Ports:** `5000`

### 2.4 Ollama (AI LLM & Embedding Engine)
- **Role:** Standalone provider for Local Language Inference (`Mistral Nemo 12B`) and Vector Embedding generation (`nomic-embed-text`).
- **Container Details:** Employs the `ollama/ollama:latest` distribution.
- **Initialization & Scaling:** Features a specialized entrypoint script (`/bin/ollama serve & sleep 5; /bin/ollama pull mistral-nemo:12b-instruct-2407-q4_K_M; ...`) ensuring models are bootstrapped automatically upon container spin-up.
- **Hardware Profile:** Configured for unlimited tensor layers (`OLLAMA_GPU_LAYERS=999`) across logical device `CUDA_VISIBLE_DEVICES=0`.
- **Ports:** `11434`

### 2.5 PostgreSQL & Redis (Database & Queue)
- **PostgreSQL (`16-alpine`):** Main database that stores audit sessions, logs, cached results, and evidence metadata. Auto-initializes schema on first startup using scripts in `docker-entrypoint-initdb.d`.
- **Redis (`7-alpine`):** Job queue for async processing. Limited to 512MB RAM with LRU eviction to prevent memory issues during high load.
- **Ports:** Postgres `5432`, Redis `6379`

---

## 3. Infrastructure & Deployment Strategy

### 3.1 Azure Environment
- **VM:** Everything runs on a single Azure NV36ads A10 v5 instance. Keeping it all on one machine reduces latency and simplifies security. You need to install Azure GRID vGPU drivers for the NVIDIA GPU to work properly in Docker.
- **Blob Storage:** Azure Blob Storage account `stcompdldevqc01` stores uploaded evidence files and compliance templates.
- **External Database:** There's a separate read-only Azure PostgreSQL instance that we sync compliance domains and questions from.

### 3.2 Docker Volumes
All the important data is stored in Docker volumes so it survives container restarts:
- `n8n_data`: Workflow data and execution history
- `postgres_data`: Database tables
- `qdrant_storage`: Vector embeddings
- `redis_data`: Unfinished jobs in the queue
- `ollama_data` & `hf_model_cache`: AI models (15GB+) so we don't have to re-download them every time
- `shared_processing`: Temporary folder for passing files between n8n and Florence without using HTTP

---

## 4. Workflow Definitions

The system has 6 workflows that handle different parts of the process:

1. **Workflow A - Universal Extractor** (`/webhook/extract`)
   Takes any document (PDF, DOCX, PPTX, XLSX) and extracts text and images. Sends images to Florence-2 for OCR and visual analysis.

2. **Workflow B - KB Ingestion** (`/webhook/kb/ingest`)
   Breaks compliance documents into chunks (1000 words with 200 word overlap), generates SHA-256 hashes to avoid duplicates, creates embeddings, and stores them in Qdrant.

3. **Workflow C1 - Audit Entry** (`/webhook/audit/submit`)
   Receives audit requests, saves them to Postgres, validates that files exist in Azure Blob Storage, adds jobs to Redis queue, and immediately returns a session ID with HTTP 202.

4. **Workflow C2 - Audit Worker** (runs on schedule)
   Pulls jobs from Redis, checks the cache, extracts relevant text from evidence files, searches Qdrant for similar compliance documents, and uses Mistral to generate compliance scores.

5. **Workflow C3 - Status Poll** (`/webhook/audit/status/:sessionId`)
   Returns current progress for each audit question in a session.

6. **Workflow C4 - Results Retrieval** (`/webhook/audit/results/:sessionId`)
   Returns the final compliance report with scores, gaps, and recommendations.

---

## 5. Data & Storage Model

### 5.1 PostgreSQL (compliance_db)
Main database with these tables:
- `audit_domains`, `audit_questions`: Compliance domains and the questions for each one
- `audit_evidence`: Uploaded evidence files and their metadata
- `audit_logs`: Execution logs for debugging
- `audit_sessions`: Audit sessions with status (`pending`, `processing`, `completed`, `failed`)
- `kb_standards`: Compliance document chunks (deduplicated)

### 5.2 Azure Blob Storage
- **Account:** `stcompdldevqc01`
- **Container:** `complianceblobdev`
- Stores uploaded evidence files (`compliance_assessment/`), domain guidelines (`guidelines/`), and question templates. Access is controlled with short-lived SAS tokens.

---

## 6. Performance & Processing Metrics
### 6.1 Processing Speed
- **With GPU:** 17 seconds per file
- **Without GPU:** 2 minutes 45 seconds per file
- **Cache hit:** ~100ms (skips extraction, RAG search, and LLM evaluation by looking up the SHA-256 hash)

### 6.2 GPU Usage (Azure NV36ads A10 v5)
- **Total VRAM:** 24 GB
- **Used:** ~13.8 GB (Mistral 12B Q4_K_M + Florence-2 both fit comfortably)

---

## 7. File Operations & Security

- **Temp files:** Everything goes in `/tmp/n8n_processing/` and gets cleaned up automatically
- **Concurrency:** No hardcoded filenames like `input.pdf`. Every file gets a unique prefix to prevent collisions when processing multiple requests at once.
- **Filename tracking:** We keep track of original filenames so the final report shows the actual file names users uploaded.
- **Secrets:** All passwords, connection strings, and API keys are stored in environment variables, not in code.

---

## 8. Conclusion

The system is running in dev azure environemnt oncurrent audits without issues. It pulls files from Azure Blob Storage, processes them through OCR and vision AI, searches the knowledge base for relevant compliance info, and generates detailed audit reports.
