# n8n Compliance Engine — Project Journey & Reference

> **26 days · 115 commits · 6 workflows · 8 services · 3 branches**
>
> Feb 3 – Feb 28, 2026 | Roshan Lal J

---

## Interactive Timeline

Open [`docs/journey-timeline.html`](file:///c:/Users/infaw/Downloads/poc-unifi/n8n-poc-compliance/docs/journey-timeline.html) in any browser for the full interactive commit-by-commit visualization with filtering and milestone markers.

---

## Phase-by-Phase Journey

### Phase 0 — Foundation (Feb 3–9) · 19 commits

**Where it started.** A single compliance workflow, one Dockerfile, and a dream.

| What was built | Key decisions |
|---|---|
| `docker-compose.yml` with n8n + Postgres + Qdrant + Redis | Chose n8n as the orchestration layer for low-code flexibility |
| Florence-2 sidecar for image analysis | Sidecar pattern instead of in-process — allows GPU offloading later |
| `pdf2image` service → then removed in favor of `pdftoppm` | Learned: custom services add complexity; shell commands suffice |
| Gotenberg for DOCX/PPTX → PDF conversion | Reliable LibreOffice-based conversion without installing Office |
| Task runner configuration for JS + Python | n8n task runners can run arbitrary code safely |

**Milestone:** First working extraction — PDF → Images → Florence-2 → Text ✅

---

### Phase 1 — Core Workflows (Feb 10–16) · 30 commits

**The monolith splits.** A single `compliance-poc.json` became 6 independent, composable workflows.

| Workflow | Purpose |
|---|---|
| **A** — Universal Extractor | PDF/DOCX/XLSX → structured text via Florence-2 OCR |
| **B** — KB Ingestion | Upload compliance standards → chunk → embed → Qdrant |
| **C1** — Audit Entry | Accept file uploads, validate, enqueue to Redis |
| **C2** — Audit Worker | Redis → RAG search → AI evaluation → score |
| **C3** — Status Poll | Check audit session progress |
| **C4** — Results Retrieval | Retrieve completed audit results |

**Key findings:**
- Redis as job queue between C1 → C2 decouples submission from processing
- `executeCommand` nodes are fragile — must handle `pdftoppm` timing with wait nodes
- SQL injection via single quotes required escaping in all Postgres nodes
- `NODE_FUNCTION_ALLOW_BUILTIN` must allow `crypto` for hashing

**Milestone:** Multi-workflow architecture operational ✅

---

### Phase 2 — Azure Integration (Feb 17–19) · 7 commits

**Cloud storage enters.** Files now come from Azure Blob Storage, not just direct uploads.

- **Azure Blob fetch node** added to Workflows A, B, and C1 — generates SAS tokens at runtime
- Connection string parsing with fallback to individual env vars
- API documentation moved from `WORKFLOW-GUIDE.md` to `FILE-MAP.md`
- HTTP request workflows added for external audit submission

**Key finding:** Azure SAS token generation requires exact field ordering (sv=2020-12-06 has 16 fields). One wrong `\n` breaks everything.

---

### Phase 3 — Database & Auth (Feb 20–21) · 9 commits

**Production hardening.** Schema v2 with proper UUIDs and webhook authentication.

- All tables migrated to UUID primary keys (was `serial`)
- `q_id` → `question_id` renamed across all 6 workflows for consistency
- Webhook API key authentication (`httpHeaderAuth`) added to all endpoints
- File hash calculation standardized to use `Buffer` for binary safety
- `schema.sql` and `seed.sql` created for repeatable database setup

**Key finding:** n8n's `getBinaryDataBuffer()` signature changed in v2.6+ — must pass `(itemIndex, propertyName)`.

---

### Phase 4 — Audit Orchestration (Feb 23) · 12 commits

**Real data, real questions.** 159 audit questions seeded from Excel, GPU provisioning planned.

- Excel to CSV extraction scripts for seeding `audit_questions`
- `specification_number` and `accepted_evidence` columns added
- Progress percentage calculation refined (per-question granularity)
- Azure GPU VM provisioning request drafted (A10 GPU selected)
- Python-based Excel extraction in Workflow A (replacing LibreOffice for `.xlsx`)

**Key finding:** Hybrid search (vector + keyword) outperforms pure vector similarity for compliance standards where exact regulation numbers matter.

---

### Phase 5 — Azure Deployment (Feb 24) · 2 commits

**First production deploy.** PR #1 merged, system running on Azure VM.

- GitHub Actions deployment workflow created
- Deployment guide documented
- First pull request merged: `new-arch` → `main`

**Milestone:** n8n compliance engine running on Azure VM ✅

---

### Phase 6 — Evidence & Caching (Feb 25–26) · 18 commits

**Optimization sprint.** Master caching and evidence filename tracking.

- **Master cache** in `audit_logs` — skip re-evaluation of identical questions + evidence
- Original filenames preserved through the entire pipeline (was using internal temp paths)
- Evidence consolidation scripts for debugging
- Blob download script enhanced with special character escaping
- Multiple PRs merged (#2, #3)

**Key finding:** Evidence summaries leaked internal file paths like `/tmp/n8n-xyz.pdf` into AI prompts. Fixed by carrying `sourceFiles` metadata from the Build AI Prompt node.

---

### Phase 7 — GPU Architecture (Feb 27) · 13 commits

**GPU acceleration.** Major upgrade from CPU-only inference to dedicated GPU VM.

| Component | Before (CPU) | After (GPU) |
|---|---|---|
| LLM | Llama 3.2 3B | **Mistral Nemo 12B** |
| OCR/Vision | Florence-2 (CPU) | Florence-2 (CUDA, **SDPA attention**) |
| Embeddings | Custom service | **Ollama nomic-embed-text** |
| Hardware | Standard VM | **A10 GPU (24GB VRAM)** |

**Key findings:**
- `flash_attn` is not compatible with all GPU architectures — use `sdpa` attention as fallback
- Azure network connections to `apk`/`pip` repos are flaky — retry loops essential in Dockerfiles
- nomic-embed-text via Ollama is simpler and faster than a custom embedding microservice
- Florence-2 now handles both OCR text extraction AND vision analysis in a single pass

**Milestone:** GPU acceleration live — 6× faster inference ✅

---

### Phase 8 — Error Handling & Polish (Feb 28) · 4 commits

**Production hardening.** Comprehensive error recovery across all workflows.

- **Error Trigger nodes** added to all 6 workflows (global unhandled exception catchers)
- `continueOnFail: true` on all HTTP, Postgres, and shell command nodes
- Webhook workflows return HTTP 500 with structured error JSON on failure
- Workflow C2 marks sessions as `failed` in DB on error (enables C3 to report failures)
- PowerShell KB upload script for bulk ingestion of 14 standards
- Node.js patching script (`add_error_handling.js`) used for programmatic workflow modification

**Milestone:** Production-ready system ✅

---

## Final Architecture

```
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

## Key Lessons Learned

### Infrastructure
1. **Sidecar pattern wins** — Florence-2 as a standalone service allows GPU offloading without touching n8n
2. **Redis job queue** decouples synchronous API from async processing (C1 → C2)
3. **Docker networking** — services communicate via container names (`http://ollama:11434`)
4. **Retry loops in Dockerfiles** are essential for Azure VMs with flaky network

### n8n-Specific
5. **`continueOnFail: true`** is critical on every HTTP/DB/shell node for production robustness
6. **Error Trigger nodes** are disconnected from the main flow but fire automatically on unhandled errors
7. **Binary data handling** changed in n8n 2.6+ — use `getBinaryDataBuffer(itemIndex, propertyName)`
8. **`NODE_FUNCTION_ALLOW_BUILTIN`** must include `crypto` for hashing operations
9. **Task runner VM sandbox** does not have `URLSearchParams` — build query strings manually

### AI/ML
10. **Hybrid search > pure vector** for regulatory compliance (exact spec numbers matter)
11. **SDPA attention** is a safe fallback when `flash_attn` isn't available
12. **nomic-embed-text** via Ollama is the simplest embedding solution (768-dim, no custom service)
13. **Mistral Nemo 12B** provides significantly better compliance evaluation than Llama 3.2 3B

### Data Pipeline
14. **File hash deduplication** prevents re-ingesting the same KB standard
15. **Original filenames** must be carried through the entire pipeline — internal temp paths pollute AI prompts
16. **UUID standardization** across all tables prevents type mismatch bugs

---

## Repository Structure (Final)

```
n8n-poc-compliance/
├── docker-compose.yml          # 8-service orchestration
├── Dockerfile                  # n8n + Python + pdftoppm
├── florence/                   # Florence-2 OCR/Vision sidecar
│   ├── app.py                  # Flask API (GPU-accelerated)
│   └── Dockerfile
├── workflows/
│   └── unifi-npc-compliance/
│       ├── workflow-a-*.json   # Universal Extractor
│       ├── workflow-b-*.json   # KB Ingestion
│       ├── workflow-c1-*.json  # Audit Entry
│       ├── workflow-c2-*.json  # Audit Worker
│       ├── workflow-c3-*.json  # Status Poll
│       └── workflow-c4-*.json  # Results Retrieval
├── migrations/
│   ├── schema.sql              # Full database DDL
│   ├── seed.sql                # Domain + question data
│   ├── audit_domains.csv       # 13 domains
│   └── audit_questions.csv     # 159 questions
├── scripts/
│   ├── upload-kb.ps1           # Bulk KB upload (14 standards)
│   └── ...
└── docs/
    ├── journey-timeline.html   # Interactive visualization
    └── PROJECT-JOURNEY.md      # This document
```

---

## Branches

| Branch | Purpose | Status |
|---|---|---|
| `main` | Production-ready code | Active, auto-deployed |
| `new-arch` | Development branch for new features | Active, PRs merged to main |
| `project-cpu-only-baseline` | CPU-only reference before GPU upgrade | Archived |

---

*Generated Feb 28, 2026 — Roshan Lal J*
