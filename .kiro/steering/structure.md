---
inclusion: auto
---

# Project Structure

## Root Files

- `docker-compose.prod.yml`: Multi-service orchestration (6 containers)
- `Dockerfile`: Custom n8n image with document processing tools
- `init-db.sql`: PostgreSQL schema bootstrap (auto-runs on first start)
- `FILE-MAP.md`: Comprehensive file/folder documentation (keep updated)
- `Deployment_Guide.docx`: Step-by-step deployment instructions
- `.env.example`: Environment variable template

## Core Directories

### `/workflows/unifi-npc-compliance/`
n8n workflow definitions (JSON format, import via UI):
- `workflow-a-universal-extractor.json`: Document extraction pipeline
- `workflow-b-kb-ingestion.json`: Compliance standards embedding
- `workflow-c1-audit-entry.json`: Job submission endpoint
- `workflow-c2-audit-worker.json`: Background processor (RAG + LLM)
- `workflow-c3-status-poll.json`: Progress tracking endpoint
- `workflow-c4-results-retrieval.json`: Results endpoint

### `/florence-service/`
Standalone vision AI service (Python Flask):
- `app.py`: Florence-2 model inference API
- `Dockerfile`: Python 3.10-slim with PyTorch CPU
- `requirements.txt`: Python dependencies

### `/scripts/`
Operational tools (mounted read-only in n8n container):
- `monitor_queue.sh`: Primary ops tool for system monitoring
- `blob_browser.sh`: Azure Blob Storage inspection
- `excel_extractor.py`: Standalone Excel parsing utility

### `/migrations/`
SQL migration scripts (apply manually after init-db.sql):
- `001_cleanup_and_enhance.sql`: Multi-question support, evidence caching
- `002_uuid_domains_and_questions.sql`: UUID alignment with app DB

### `/docs/`
Technical documentation (not needed at runtime):
- `WORKFLOW-C2-DEEP-DIVE.md`: RAG pipeline technical details
- `COMPLIANCE-APP-DB.md`: External app database schema reference
- `CURL-PLAYBOOK.md`: API testing examples
- `PLAN-LARGEFILE-GPU-PARALLEL.md`: Future optimization planning
- `diagrams/`: Architecture diagrams (draw.io + SVG)

### `/temp-assets/`
Development/seeding utilities:
- `seed_audit_questions.py`: Question import script
- `extractor.py`: Document parsing experiments
- Sample data files

### `/internal-files/`
Configuration snippets and notes (not used by runtime)

### `/.github/`
- `copilot-instructions.md`: GitHub Copilot workspace rules

## Runtime Paths (Inside Containers)

### n8n Container
- `/home/node/.n8n/`: Workflow definitions, credentials, execution history (persisted)
- `/tmp/n8n_processing/`: Shared temp file volume (organized by sessionId)
- `/scripts/`: Mounted operational scripts (read-only)
- `/workflows/`: Mounted workflow JSON files (read-only)

### Florence Container
- `/app/hf_cache/`: Hugging Face model cache (~900MB, persisted)
- `/tmp/n8n_processing/`: Shared with n8n for large file transfer

### PostgreSQL Container
- `/var/lib/postgresql/data/`: Database files (persisted)
- `/docker-entrypoint-initdb.d/`: Init scripts (init-db.sql)

### Qdrant Container
- `/qdrant/storage/`: Vector database storage (persisted)

### Ollama Container
- `/root/.ollama/`: Model weights and config (persisted)

## Docker Volumes

Named volumes for data persistence:
- `n8n_data`: n8n internal data
- `postgres_data`: Database files
- `redis_data`: Queue persistence
- `qdrant_storage`: Vector embeddings
- `ollama_data`: LLM model weights
- `florence_model_cache`: Florence-2 model weights
- `shared_processing`: Temp file exchange between n8n and Florence

## Folder Conventions

### Temp File Organization
```
/tmp/n8n_processing/
  ├── <sessionId-1>/
  │   ├── evidence_file_1.pdf
  │   ├── evidence_file_2.docx
  │   └── page_images/
  │       ├── page_001.png
  │       └── page_002.png
  ├── <sessionId-2>/
  └── ...
```

Cleanup: Files older than 24h are removed by `monitor_queue.sh --cleanup`

### Workflow Import Location
Place new workflow JSON files in `/workflows/unifi-npc-compliance/` and import via n8n UI (Workflows → Import from File)

### Migration Application
Place new SQL migrations in `/migrations/` with sequential numbering:
```
001_description.sql
002_description.sql
003_description.sql
```

Apply manually:
```bash
docker exec -i compliance-db psql -U n8n -d compliance_db < migrations/00X_name.sql
```

## Archive Policy

### `/archive-poc/` (if exists)
Historical POC code from v1.0 architecture. DO NOT use for code generation or reference. Archive only.

## File Naming Conventions

- Workflow files: `workflow-<id>-<name>.json` (e.g., `workflow-c2-audit-worker.json`)
- Migration files: `NNN_description.sql` (e.g., `001_cleanup_and_enhance.sql`)
- Documentation: `UPPERCASE-WITH-DASHES.md` (e.g., `WORKFLOW-C2-DEEP-DIVE.md`)
- Scripts: `lowercase_with_underscores.sh` (e.g., `monitor_queue.sh`)

## Key Integration Points

### n8n ↔ Florence
- Shared volume: `/tmp/n8n_processing/`
- HTTP API: `http://florence:5000/analyze`
- File transfer: n8n writes file → Florence reads same path

### n8n ↔ Ollama
- HTTP API: `http://ollama:11434/api/`
- Endpoints: `/api/generate` (LLM), `/api/embeddings` (vectors)

### n8n ↔ Qdrant
- HTTP API: `http://qdrant:6333/`
- Collection: `compliance_standards`
- Operations: Search, upsert, collection management

### n8n ↔ PostgreSQL
- Direct connection via n8n Postgres node
- Host: `postgres:5432`
- Database: `compliance_db`

### n8n ↔ Redis
- Direct connection via n8n Redis node
- Host: `redis:6379`
- Queue key: `audit_job_queue`

### External App DB (Read-Only)
- Azure PostgreSQL: `unifi-cdmp-server-pg.postgres.database.azure.com`
- Database: `npc_compliance_test`
- Purpose: Question/domain sync, reference data
- SSL required

### Azure Blob Storage
- Container: `compliance`
- Path pattern: `compliance_assessment/{assessmentId}/{entityId}/{domainId}/{questionId}/{file}`
- Access: Via connection string in environment variables
