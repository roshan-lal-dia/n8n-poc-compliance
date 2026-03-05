# NPC Compliance AI Document Intelligence System - Technical Status Report

**Project:** n8n Compliance Engine
**Document Date:** March 4, 2026
**Classification:** Technical Documentation

---

## Executive Summary

The NPC Compliance AI Document Intelligence System is an operational AI-powered compliance audit platform that evaluates organizational compliance against 12 data management domains using document analysis, vision AI, and retrieval-augmented generation (RAG). The system is deployed on Azure infrastructure with GPU acceleration and is fully production-ready.

**Key Capabilities:**
- **6 Operational Workflows:** Handles extraction, ingestion, and background evaluation.
- **Microservices Architecture:** 6 cleanly decoupled containerized services orchestrated via Docker Compose.
- **Compliance Scope:** 159 audit questions across 12 domains.
- **AI/ML Engine:** GPU-accelerated inference utilizing Mistral Nemo 12B and Florence-2-large-ft.
- **Caching Layer:** Master caching system bypassing redundant evaluations.

---

## 1. System Architecture Overview

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

### 2.5 PostgreSQL & Redis (State & Queuing)
- **PostgreSQL (`16-alpine`):** The primary relational pivot. Employs `docker-entrypoint-initdb.d` mapping to auto-seed table clusters natively on creation. Manages audit contexts, logs, master execution caches, and granular evidence mappings.
- **Redis (`7-alpine`):** Provides durable async job delegation. Bound strictly by Docker memory guardrails (`--maxmemory 512mb --maxmemory-policy allkeys-lru`) protecting orchestration from pipeline overflows during concurrent submission spikes.
- **Ports:** PG `5432` | Redis `6379`

---

## 3. Infrastructure & Deployment Strategy

### 3.1 Azure Environments & Network
- **Deployment Hub:** Azure Virtual Machine (`NV36ads A10 v5`). Single monolithic instance handles all application concerns for minimized latency and secure data boundaries. Requires Azure GRID vGPU drivers for proper NVIDIA container passthrough.
- **Persistent Object Store:** Azure Blob Storage (`stcompdldevqc01`) acts as the external cold-store for heavy compliance evidence files and template artifacts.
- **External Integration Database:** A secure, read-only Azure PostgreSQL external instance fetches dynamic compliance domains and question properties syncs.

### 3.2 Docker Volume Binding
Volumes map to host storage to ensure persistent state handling independently from the application logic:
- `n8n_data`: Core encrypted webhook and execution metadata.
- `postgres_data`: Table data structures.
- `qdrant_storage`: Persisted vector index matrices.
- `redis_data`: Uncompleted queue pipelines persist restart safely.
- `ollama_data` & `hf_model_cache`: Retains large Language and Vision models (~15GB+) directly, bypassing model re-download during scaling or container restarts.
- `shared_processing`: Dynamically handles moving files out of workflows seamlessly to the visual OCR nodes internally before pipeline ingestion avoiding HTTP-based file bloat.

---

## 4. Workflow Definitions

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

## 5. Data & Storage Model

### 5.1 PostgreSQL (compliance_db)
Central hub for maintaining session state, caching, and entity modeling:
- `audit_domains`, `audit_questions`: Domain mappings and evaluation rules.
- `audit_evidence`: Retains exact uploaded user evidence and metadata. 
- `audit_logs`: Per-step execution tracking.
- `audit_sessions`: Root session objects denoting state (`pending`, `processing`, `completed`, `failed`).
- `kb_standards`: Deduplicated compliance standard chunks.

### 5.2 Azure Blob Storage
- **Account:** `stcompdldevqc01`
- **Container Target:** `complianceblobdev`
- Maintains user-uploaded evidence (`compliance_assessment/`), domain guidelines (`guidelines/`), and question templates. Fetches are secured at runtime via restricted SAS tokens scoped to individual extraction executions.

---

## 6. Performance & Processing Metrics

Significant optimization targets have been achieved by implementing a master caching layer.

### 6.1 Processing Throughput
- **With GPU Compute:** 17 seconds per file processing. 
- **Without GPU:** 2 minutes 45 seconds per file processing. 
- **Cache Hit Optimization:** ~100ms response time on cache hit (bypassing full extraction, RAG, and LLM evaluations via SHA-256 evidence hashing lookup).

### 6.2 Compute Resource Allocation (Azure NV36ads A10 v5)
- **Available VRAM:** 24 GB
- **Allocated Usage:** ~13.8 GB (Mistral 12B Q4_K_M + Florence-2 ft fits comfortably).

---

## 7. File Operations & Security Standards

- **Temporary Persistence:** Isolated to `/tmp/n8n_processing/`. Dynamically purged.
- **Concurrency Isolation:** Implementation guarantees no static filenames (e.g., `input.pdf`) are utilized across multi-tenant execution. File operations exclusively use auto-generated prefixed paths (e.g., `{{unique_prefix}}filename.ext`) preventing collision.
- **Original Filename Preservation:** Evidence maps explicitly trace output extraction buffers back to original user-facing filenames for pristine reporting capabilities.
- **Environment Isolation:** All cryptographic secrets, database passkeys, Azure Connection Strings, and webhook API Keys are maintained strictly via environment variables.

---

## 8. Current Deployment Status
The architecture successfully processes concurrent audit flows end-to-end, fetching remote Azure Blobs natively, mapping to local Docker storage mechanisms, running OCR/Vision AI on the fly, and performing robust embedding analysis via standalone microservices. The application is functionally scaled and structurally sound for enterprise workload orchestration.
