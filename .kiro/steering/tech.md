---
inclusion: auto
---

# Technology Stack

## Core Services (Docker Compose)

- **n8n** (2.6.3): Workflow orchestration engine (custom Alpine image)
- **PostgreSQL** (16-alpine): Primary database for audit data
- **Qdrant** (latest): Vector database for compliance standards embeddings
- **Redis** (7-alpine): Job queue for async processing
- **Ollama** (latest): LLM inference (llama3.2) and embeddings (nomic-embed-text)
- **Florence** (custom): Vision AI service (microsoft/Florence-2-base) for image analysis

## n8n Custom Image

Base: `n8nio/n8n:2.6.3` on Alpine Linux

Installed tools:
- LibreOffice + OpenJDK 11 (Office document conversion)
- Poppler utils (pdftoppm for PDF → PNG conversion)
- Tesseract OCR (eng + ara language packs)
- Python 3 + pdfplumber, openpyxl, pandas
- Font packages for proper rendering

## Florence Service

- Python 3.10-slim base
- PyTorch CPU-only
- Transformers library with Florence-2-base model
- Flask + Gunicorn HTTP API
- Shared volume with n8n at `/tmp/n8n_processing/`

## Database Schema

PostgreSQL with UUID primary keys, JSONB for flexible data, no FK constraints (application-level integrity).

Key tables:
- `audit_sessions`: Master audit run records
- `audit_questions`: Question registry with AI evaluation instructions
- `audit_evidence`: Extracted document content (cached per session)
- `audit_logs`: Step-by-step execution tracking
- `kb_standards`: Metadata for embedded compliance standards
- `audit_domains`: 12 domain lookup table

## Common Commands

### Start/Stop Services
```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml down
```

### Monitor System
```bash
./scripts/monitor_queue.sh              # Full system status
./scripts/monitor_queue.sh --watch      # Live monitoring
./scripts/monitor_queue.sh --queue      # Queue stats only
./scripts/monitor_queue.sh --cleanup    # Remove old temp files
```

### Database Operations
```bash
# Connect to database
docker exec -it compliance-db psql -U n8n -d compliance_db

# Apply migrations
docker exec -i compliance-db psql -U n8n -d compliance_db < migrations/001_cleanup_and_enhance.sql

# Check session status
docker exec compliance-db psql -U n8n -d compliance_db -c "SELECT session_id, status, overall_compliance_score FROM audit_sessions ORDER BY started_at DESC LIMIT 10;"
```

### Redis Queue Inspection
```bash
# Check queue length
docker exec compliance-redis redis-cli LLEN audit_job_queue

# View queued jobs
docker exec compliance-redis redis-cli LRANGE audit_job_queue 0 -1
```

### Qdrant Operations
```bash
# Check collections
curl http://localhost:6333/collections

# Check collection info
curl http://localhost:6333/collections/compliance_standards
```

### Ollama Model Management
```bash
# List loaded models
docker exec compliance-ollama ollama list

# Pull new model
docker exec compliance-ollama ollama pull llama3.2
```

### View Logs
```bash
docker logs compliance-n8n --tail 100 -f
docker logs compliance-florence --tail 50
docker logs compliance-ollama --tail 50
```

### Cleanup Temp Files
```bash
# Via monitor script (recommended)
./scripts/monitor_queue.sh --cleanup

# Manual cleanup
sudo rm -rf /var/lib/docker/volumes/n8n-poc-compliance_shared_processing/_data/*
```

## File Processing Conventions

### Temp File Path Pattern
All temporary files MUST use `/tmp/n8n_processing/` with unique prefixes:
```
/tmp/n8n_processing/<sessionId>/<filename>
```

Never use static filenames like `input.pdf` - always include session/job ID for concurrency safety.

### CLI Command Construction
Do NOT rely on `{{ $binary.data.fileName }}` in Execute Command nodes (unreliable).

Always construct paths explicitly:
```javascript
const filePrefix = $node["Set Binary Filename"].json["filePrefix"];
const path = `/tmp/n8n_processing/${filePrefix}input.pdf`;
```

## n8n Node Conventions

### Switch Node (v3.4)
Uses `parameters.rules.values[]` and `options.fallbackOutput: "extra"`

### Set Node (v3.4)
Uses `parameters.mode: "raw"` and `parameters.jsonOutput`

### Code Nodes
- `console.log()` output is hidden in production
- Python: `return {"key": "value"}` or `return _input.all()`
- JavaScript: `return {json: {key: "value"}}` or `return $input.all()`

## Environment Variables

Key variables in `.env`:
- `DB_PASSWORD`: PostgreSQL password
- `N8N_USER` / `N8N_PASSWORD`: n8n basic auth
- `WEBHOOK_URL`: Public webhook base URL
- `N8N_ENCRYPTION_KEY`: Credential encryption key
- `AZURE_STORAGE_CONNECTION_STRING`: Blob storage access
- `COMPLIANCE_APP_DB_*`: External app database connection
- `WEBHOOK_API_KEY`: Internal workflow authentication

## Testing

No automated test suite currently. Testing is done via:
1. Manual workflow execution in n8n UI
2. curl commands against webhook endpoints
3. Monitor script for system health checks

## Deployment

Target: Azure VM (Ubuntu)

Deployment steps documented in `Deployment_Guide.docx`:
1. Clone repository
2. Copy `.env.example` to `.env` and configure
3. Run `docker compose up -d`
4. Apply database migrations
5. Import workflows via n8n UI
6. Initialize Qdrant collection
7. Ingest compliance standards via Workflow B

## Performance Characteristics

Typical processing time per question: 12-40 seconds
- Cache check: 50ms
- Extraction (cache miss): 2-8s
- Embedding generation: 200-500ms
- RAG search: 100-300ms
- LLM evaluation: 10-30s (bottleneck)

For 5-question audit: 1-3 minutes total
