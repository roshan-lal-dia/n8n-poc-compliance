# Repository File Map

> What every file and folder does. Keep this updated when adding or removing files.

---

## Root Files

| File | Purpose |
|------|---------|
| `DEPLOYMENT-GUIDE.md` | **Primary deployment reference.** Step-by-step instructions for the current v2.0 system (multi-question, async queue, Redis, C1-C4 workflows). Includes DB migration steps, Qdrant collection init, workflow import, and end-to-end test commands. |
| `FILE-MAP.md` | This file. Describes every file and folder in the repo. |
| `docker-compose.prod.yml` | Docker Compose definition for all 6 services: Postgres, Qdrant, Redis, Ollama, Florence, n8n. Defines volumes, healthchecks, service dependencies, and environment variables. |
| `Dockerfile` | Custom n8n image. Extends the official n8n Alpine image and installs system tools: `libreoffice` (PPTX/DOCX → PDF conversion), `tesseract-ocr` (OCR, eng+ara), `pdftoppm` (PDF → PNG page images), `python3` + `pdfplumber` (text extraction utilities). |
| `deploy.sh` | Convenience shell script for first-time deployment on the Azure VM. Runs `docker compose up`, applies DB migrations, and confirms service health. |
| `init-db.sql` | **Postgres schema bootstrap.** Creates all tables (`audit_questions`, `audit_evidence`, `audit_sessions`, `audit_logs`, `kb_standards`), indexes, triggers, views, and seeds 8 sample audit questions across 4 domains. Runs automatically on first Postgres container start. |
| `.env.example` | Template for the `.env` file. Covers DB password, n8n credentials, VM IP, and encryption key. Copy to `.env` and fill in values before deploying. |
| `.dockerignore` | Excludes `.git`, `.env`, `archive-poc` etc. from Docker build context. |
| `.gitignore` | Standard git ignore — excludes `.env`, `*.log`, `node_modules`, etc. |

---

## `florence-service/`

The Florence-2 vision model runs as a **separate sidecar service** (Debian/Python 3.10) because it cannot be installed on the Alpine-based n8n container. It exposes a small Flask/Gunicorn HTTP API.

| File | Purpose |
|------|---------|
| `app.py` | Flask application. Exposes two endpoints: `GET /health` (readiness probe) and `POST /analyze` (accepts `{ "filePath": "/tmp/n8n_processing/..." }` and returns a detailed image caption from Florence-2). Loads `microsoft/Florence-2-base` at startup in eager-attention CPU mode. Uses `torch.inference_mode()` + `gc.collect()` to minimise memory. |
| `Dockerfile` | Builds the Florence image: Python 3.10-slim base, installs PyTorch CPU wheel, installs `requirements.txt` + Gunicorn. Sets `HF_HOME=/app/hf_cache` so model weights are cached in a named volume. Exposes port 5000. |
| `requirements.txt` | Python dependencies for the Florence service: `flask`, `transformers`, `Pillow`, `torch` (pinned CPU), `einops`, `timm`. |

---

## `workflows/unifi-npc-compliance/`

Six n8n workflow files. Import these manually via the n8n UI (Workflows → Import from File) or `docker cp`.

| File | Purpose |
|------|---------|
| `workflow-a-universal-extractor.json` | **Workflow A — Universal Extractor.** Accepts any file (PDF, DOCX, PPTX, XLSX, PNG, JPG) via `POST /webhook/extract`. Converts to PDF → extracts page images via `pdftoppm` → runs Tesseract OCR and Florence-2 vision analysis in parallel → merges results into structured JSON (`full_text`, `pages[]`, `images[]`). Used internally by Workflow B and Workflow C2. |
| `workflow-b-kb-ingestion.json` | **Workflow B — Knowledge Base Ingestion.** Accepts a compliance standard document via `POST /webhook/kb/ingest?standardName=...&domain=...`. Calls Workflow A to extract text, chunks it (1000 words / 200-word overlap), generates embeddings via `nomic-embed-text` (Ollama), and upserts chunks into Qdrant collection `compliance_standards`. Records metadata in `kb_standards` Postgres table. |
| `workflow-c1-audit-entry.json` | **Workflow C1 — Audit Entry (Job Submission).** `POST /webhook/audit/submit`. Validates uploaded files and questions mapping, calculates SHA-256 hashes, writes files to `/tmp/n8n_processing/<sessionId>/`, creates an `audit_sessions` record, serialises job to Redis list `audit_job_queue` (LPUSH), and immediately returns `202 Accepted` with `sessionId`. |
| `workflow-c2-audit-worker.json` | **Workflow C2 — Audit Worker (Background Processor).** Cron trigger (every 10 s). Pops one job from `audit_job_queue` (RPOP), splits into per-question items, checks evidence cache in Postgres, calls Workflow A to extract evidence, runs RAG (Qdrant semantic search via Ollama embeddings), builds master prompt, calls Ollama (`llama3.2`), logs AI response to `audit_logs`, aggregates scores, and marks `audit_sessions` as `completed`. |
| `workflow-c3-status-poll.json` | **Workflow C3 — Status Polling.** `GET /webhook/audit/status/:sessionId`. Returns real-time progress: session status, overall percentage, per-question step breakdown, and estimated completion time. Reads from `audit_sessions` + `audit_logs`. |
| `workflow-c4-results-retrieval.json` | **Workflow C4 — Results Retrieval.** `GET /webhook/audit/results/:sessionId`. Returns the full completed audit results including per-question AI evaluations (compliant, score, evidence found, gaps, recommendations), overall score, and summary statistics. Only works when session status is `completed`. |

---

## `docs/`

Internal reference documentation. Not needed at runtime.

| File | Purpose |
|------|---------|
| `FRONTEND-API-GUIDE.md` | **API integration guide for frontend developers.** Complete request/response examples (JavaScript Fetch, curl), authentication notes, multipart form field structure, polling pattern, error codes, file size limits, and a ready-to-use React example. The primary reference for anyone calling the API. |
| `AUDIT-TRANSPARENCY-GUIDE.md` | **Deep-dive system internals.** Explains every processing step in detail: how RAG search works, how the AI prompt is constructed, how scores are aggregated, deduplication logic, evidence cleanup policy, and manual SQL queries for debugging and verification. Useful for prompt engineering and debugging AI responses. |
| `WORKFLOW-C2-DEEP-DIVE.md` | **Workflow C2 technical documentation.** Explains the RAG pipeline step-by-step: embedding generation, Qdrant vector search mechanics, prompt construction, Ollama call, response parsing, and the `queryText` vs `instructions` distinction. |
| `findings-module-3.md` | **Module 3 technical findings log.** Explains why the Florence sidecar architecture was chosen (Alpine vs Debian dependency conflict), the shared-volume approach for large image transfer, metadata preservation after parallel branch merges, and OOM mitigation strategies for Florence on CPU. Historical context only — the decisions are already implemented. |
| `PLAN-WEBHOOK-AUTH.md` | **Planning doc: Webhook endpoint authentication.** Compares API key header vs Basic Auth vs JWT. Recommends Option A (Header Auth / `X-API-Key`). Includes step-by-step n8n credential setup, which nodes to update, how to handle internal workflow-to-workflow calls, and frontend integration snippets. Ready to implement. |
| `PLAN-LARGEFILE-GPU-PARALLEL.md` | **Planning doc: Large file chunking, GPU inference, and parallel processing.** Covers: semantic evidence chunking with per-session Qdrant collections, model swap (`llama3.1:8b`), Florence-2 + Ollama CUDA setup, multi-worker C2 concurrency vs event-driven dispatch vs dedicated GPU service. Includes Azure VM SKU recommendations and a phased implementation sequence. Requires decisions before implementation. |
| `diagrams/1st-ittr-workflow-arch.drawio` | Architecture diagram (draw.io format) from the first iteration of the system. For reference only. |

---

## `scripts/`

Operational scripts mounted into the n8n container at `/scripts` (read-only).

| File | Purpose |
|------|---------|
| `monitor_queue.sh` | **Primary ops tool.** Monitors Redis queue depth (`audit_job_queue`), container health, DB session statistics, worker activity, disk usage, and performance metrics. Supports flags: `--watch` (live refresh), `--queue`, `--sessions`, `--health`, `--cleanup` (delete temp files >24h), `--failed`, `--raw` (direct Redis key inspection). Run with `./scripts/monitor_queue.sh --help`. |

---

## `migrations/`

SQL migration scripts applied manually after the initial `init-db.sql` bootstrap.

| File | Purpose |
|------|---------|
| `001_cleanup_and_enhance.sql` | **Applied: 2026-02-10.** Drops `file_registry` table (unused), drops stale views and GIN index, removes the `file_hash` global uniqueness constraint and replaces it with a per-session constraint, adds `file_size_bytes` and `evidence_order` columns to `audit_evidence`, adds `job_id` to `audit_sessions` (for Redis job linkage), drops unused `file_type` column. |

---

## `.github/`

| File | Purpose |
|------|---------|
| `copilot-instructions.md` | GitHub Copilot workspace instructions. Defines project context, n8n schema conventions (Switch v3.4, Set v3.4), CLI command patterns, temp file path rules, and coding guidelines for this repo. |

---

## Key Runtime Paths

| Path | What lives here |
|------|----------------|
| `/tmp/n8n_processing/` | Shared volume between n8n and Florence containers. All temp files during extraction (PDFs, page PNGs, intermediate JSON). Organised as `/tmp/n8n_processing/<sessionId>/`. |
| `/home/node/.n8n/` | n8n internal data: workflow definitions, credentials, execution history. Persisted in Docker volume `n8n_data`. |
| `/app/hf_cache/` | Hugging Face model cache inside Florence container. Persisted in Docker volume `florence_model_cache`. Stores `microsoft/Florence-2-base` weights (~900 MB). |

---

## What Was Removed (and Why)

| Removed | Reason |
|---------|--------|
| `README.prod.md` | v1.0 — superseded entirely by `DEPLOYMENT-GUIDE.md` v2.0 (multi-question async architecture). |
| `test-azure-vm-conn.ps1` | One-off PowerShell connectivity test from initial setup. No longer needed. |
| `archive-poc/` | Historical archive from the first monolithic POC (single-workflow, synchronous). Architecture replaced by C1-C4. |
| `scripts/debug_redis.sh` | Manual Redis debug commands — absorbed into `monitor_queue.sh --raw`. |
| `scripts/merge_hybrid.py` | Original pdfplumber merge script from Module 3 development. Merging is now done inline in Workflow A's JS Code nodes. Not called by any workflow. |
| `workflows/FUNCTIONALITY-COMPARISON.md` | Historical diff between old C-orchestrator and new C1-C4. Stale — no longer relevant. |
| `workflows/WORKFLOW-GUIDE.md` | Quick-start guide referencing the old single-workflow architecture. Content absorbed into `DEPLOYMENT-GUIDE.md` (Qdrant init step added). |
