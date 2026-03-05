# NPC Compliance AI Document Intelligence System - Technical Status Report

**Project:** n8n Compliance Engine
**Document Date:** March 4, 2026
**Classification:** Technical Documentation

---

## Executive Summary

The NPC Compliance AI Document Intelligence System is an operational AI-powered compliance audit platform that evaluates organizational compliance against 12 data management domains using document analysis, vision AI, and retrieval-augmented generation (RAG). The system is deployed on Azure infrastructure with GPU acceleration and is fully production-ready.

**Key Capabilities:**
- **6 Operational Workflows:** Handles extraction, ingestion, and background evaluation.
- **Microservices Architecture:** 6 containerized services orchestrated via Docker Compose.
- **Compliance Scope:** 159 audit questions across 12 domains.
- **AI/ML Engine:** GPU-accelerated inference utilizing Mistral Nemo 12B and Florence-2-large-ft.
- **Caching Layer:** Master caching system bypassing redundant evaluations.

---

## 1. System Architecture

### 1.1 High-Level Architecture

The system implements an asynchronous job queue architecture with six specialized workflows:

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

### 1.2 Container & Service Architecture

The system is deployed as a suite of 6 tightly integrated Docker containers managed via Docker Compose (`docker-compose.prod.yml`), operating on a dedicated bridge network (`compliance-network`).

1. **`n8n` (Workflow Orchestrator):**
   - **Role:** Main execution engine controlling the 6 workflow pipelines.
   - **Custom Build:** Extends Alpine with Python, poppler-utils (`pdftoppm`), LibreOffice, and OpenJDK 11 for robust local document parsing.
   - **Ports:** `5678`
2. **`postgres` (Relational Database):**
   - **Role:** Central application state, session persistence, caching layer, and execution logs.
   - **Ports:** `5432`
3. **`qdrant` (Vector Database):**
   - **Role:** Scalable vector search engine for the Knowledge Base. Operates with 768-dimensional embeddings to perform hybrid similarity RAG searches.
   - **Ports:** `6333`
4. **`redis` (Job Queue Node):**
   - **Role:** Asynchronous job delegation between synchronous HTTP webhooks and background worker jobs. Binds API requests to LLM evaluation execution smoothly.
   - **Ports:** `6379`
5. **`ollama` (AI LLM & Embedding Engine):**
   - **Role:** GPU-accelerated inference loading `Mistral Nemo 12B` and `nomic-embed-text`. 
   - **Resources:** Provisions 1 NVIDIA GPU logic via passthrough.
   - **Ports:** `11434`
6. **`florence` (Vision / OCR Service):**
   - **Role:** Specialized custom Python Flask sidecar serving HTTP requests from n8n to analyze diagram layout and perform OCR utilizing `Florence-2-large-ft`.
   - **Resources:** Provisions 1 NVIDIA GPU logic via passthrough.
   - **Ports:** `5000`

---

## 2. Infrastructure & Deployment Strategy

### 2.1 Azure Environments & Network
- **Deployment Hub:** Azure Virtual Machine (`NV36ads A10 v5`). Single monolithic instance handles all application concerns for minimized latency and secure data boundaries. Requires Azure GRID vGPU drivers for proper NVIDIA container passthrough.
- **Persistent Object Store:** Azure Blob Storage (`stcompdldevqc01`) acts as the external cold-store for heavy compliance evidence files and template artifacts.
- **External Integration Database:** A secure, read-only Azure PostgreSQL external instance fetches dynamic compliance domains and question properties syncs.

### 2.2 Docker Volume Binding
Volumes map to host storage to ensure persistent state handling independently from the application logic:
- `n8n_data`: Core encrypted webhook and execution metadata.
- `postgres_data`: Table data structures.
- `qdrant_storage`: Persisted vector index matrices.
- `redis_data`: Uncompleted queue pipelines persist restart safely.
- `ollama_data` & `hf_model_cache`: Retains large Language and Vision models (~15GB+) directly, bypassing model re-download during scaling or container restarts.
- `shared_processing`: Dynamically handles moving files out of workflows seamlessly to the visual OCR nodes internally before pipeline ingestion avoiding HTTP-based file bloat.

---

## 3. Workflow Definitions

The n8n system logic is divided into 6 distinct pipelines to handle synchronous endpoints and background processing efficiently:

1. **Workflow A - Universal Extractor** (`/webhook/extract`)
   Converts incoming documents (PDF/DOCX/PPTX/XLSX) to standardized structured text and images, pushing images to Florence-2 for OCR and visual analysis.

2. **Workflow B - KB Ingestion** (`/webhook/kb/ingest`)
   Chunks compliance standard documents (1000 words / 200 overlap), calculates exact SHA-256 deduplication hashes, generating embeddings and upserting directly to Qdrant.

3. **Workflow C1 - Audit Entry** (`/webhook/audit/submit`)
   Accepts evaluation jobs, persists configuration to Postgres, validates files against Azure Blob Storage, and enqueues tasks via Redis. Responds immediately with HTTP 202 and a tracking session ID.

4. **Workflow C2 - Audit Worker** (cron-triggered)
   Pulls jobs from Redis, executes cache lookups, extracts evidence context, runs RAG similarity searches against Qdrant, and orchestrates the Mistral LLM for the final compliance evaluation score. 

5. **Workflow C3 - Status Poll** (`/webhook/audit/status/:sessionId`)
   Returns real-time granular progress updates per audit question.

6. **Workflow C4 - Results Retrieval** (`/webhook/audit/results/:sessionId`)
   Serves the synthesized final compliance reports, scores, identified gaps, and recommendations.

---

## 4. Data & Storage Model

### 4.1 PostgreSQL (compliance_db)
Central hub for maintaining session state, caching, and entity modeling:
- `audit_domains`, `audit_questions`: Domain mappings and evaluation rules.
- `audit_evidence`: Retains exact uploaded user evidence and metadata. 
- `audit_logs`: Per-step execution tracking.
- `audit_sessions`: Root session objects denoting state (`pending`, `processing`, `completed`, `failed`).
- `kb_standards`: Deduplicated compliance standard chunks.

### 4.2 Azure Blob Storage
- **Account:** `stcompdldevqc01`
- **Container Target:** `complianceblobdev`
- Maintains user-uploaded evidence (`compliance_assessment/`), domain guidelines (`guidelines/`), and question templates. Fetches are secured at runtime via restricted SAS tokens scoped to individual extraction executions.

---

## 5. Performance & Processing Metrics

Significant optimization targets have been achieved by implementing a master caching layer.

### 5.1 Processing Throughput
- **With GPU Compute:** 17 seconds per file processing. 
- **Without GPU:** 2 minutes 45 seconds per file processing. 
- **Cache Hit Optimization:** ~100ms response time on cache hit (bypassing full extraction, RAG, and LLM evaluations via SHA-256 evidence hashing lookup).

### 5.2 Compute Resource Allocation (Azure NV36ads A10 v5)
- **Available VRAM:** 24 GB
- **Allocated Usage:** ~13.8 GB (Mistral 12B Q4_K_M + Florence-2 ft fits comfortably).

---

## 6. File Operations & Security Standards

- **Temporary Persistence:** Isolated to `/tmp/n8n_processing/`. Dynamically purged.
- **Concurrency Isolation:** Implementation guarantees no static filenames (e.g., `input.pdf`) are utilized across multi-tenant execution. File operations exclusively use auto-generated prefixed paths (e.g., `{{unique_prefix}}filename.ext`) preventing collision.
- **Original Filename Preservation:** Evidence maps explicitly trace output extraction buffers back to original user-facing filenames for pristine reporting capabilities.
- **Environment Isolation:** All cryptographic secrets, database passkeys, Azure Connection Strings, and webhook API Keys are maintained strictly via environment variables.

---

## 7. Current Deployment Status
The architecture successfully processes concurrent audit flows end-to-end, fetching remote Azure Blobs natively, mapping to local Docker storage mechanisms, running OCR/Vision AI on the fly, and performing robust embedding analysis via standalone microservices. The application is functionally scaled and structurally sound for enterprise workload orchestration.
