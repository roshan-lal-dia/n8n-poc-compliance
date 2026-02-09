# Compliance Audit System - Production Deployment Guide

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       Azure VM (Standard_D4s_v5)             │
│  ┌───────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐   │
│  │   n8n     │  │ Postgres │  │ Qdrant  │  │  Ollama  │   │
│  │Orchestrat │◄─┤ Evidence │  │Knowledge│  │  LLM+    │   │
│  │    or     │  │  & Logs  │  │  Base   │  │Embedding │   │
│  └─────┬─────┘  └──────────┘  └─────────┘  └──────────┘   │
│        │                                                     │
│        ├──► Florence-2 (Vision Analysis)                    │
│        └──► /tmp/n8n_processing (Shared Volume)             │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Azure VM: Standard_D4s_v5 (4 vCPU, 16GB RAM)
- Ubuntu 22.04 LTS
- Docker 20.10+
- Docker Compose v2.24+
- Ports: 5678 (n8n), 5432 (Postgres), 6333 (Qdrant), 11434 (Ollama), 5000 (Florence)

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/roshan-lal-dia/n8n-poc-compliance.git
cd n8n-poc-compliance
```

### 2. Configure Environment
```bash
cp .env.example .env
nano .env  # Update EXTERNAL_IP and passwords
```

### 3. Deploy
```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Access n8n
```
URL: http://YOUR_VM_IP:5678
Username: admin (default)
Password: (check .env file)
```

## 📊 Database Schema

### Key Tables
- **audit_questions**: Master list of compliance questions
- **audit_evidence**: Extracted content from user uploads (JSONB)
- **kb_standards**: Tracks embedded standards in Qdrant
- **audit_logs**: Real-time audit progress tracking
- **audit_sessions**: Master audit execution records

### Sample Question Structure
```json
{
  "q_id": "data_arch_q1",
  "domain": "Data Architecture",
  "question_text": "Does the document describe a clear data architecture?",
  "prompt_instructions": "Look for: data sources, ETL, data warehouse..."
}
```

## 🔄 Workflow Architecture

### Workflow A: Universal Extractor
**Purpose**: Convert any file format to structured JSON

**Input**: Binary file (PDF, DOCX, PPTX, XLSX, images)

**Process**:
1. Calculate SHA-256 hash (deduplication check)
2. Convert to PDF (if needed via LibreOffice)
3. Extract pages as PNG images (pdftoppm)
4. Parallel processing:
   - Tesseract OCR (text extraction)
   - Florence-2 (diagram detection)
5. Merge results using pdfplumber + Python script

**Output**:
```json
{
  "file_hash": "abc123...",
  "extracted_data": {
    "full_text": "Combined text from all pages",
    "pages": [
      {"page": 1, "text": "...", "word_count": 250}
    ],
    "images": [
      {"page": 2, "is_diagram": true, "description": "Architecture diagram"}
    ]
  }
}
```

### Workflow B: Knowledge Base Ingestion
**Purpose**: Embed standards/regulations into Qdrant

**Input**: Standard document + domain label

**Process**:
1. Call Workflow A (extract text)
2. Chunk text (512 tokens, semantic boundaries)
3. Generate embeddings via Ollama (nomic-embed-text)
4. Upsert to Qdrant collection: `compliance_standards`
5. Log metadata in Postgres `kb_standards` table

**Output**: Confirmation + total chunks embedded

### Workflow C: Audit Orchestrator
**Purpose**: Main compliance evaluation workflow

**Input**:
```json
{
  "session_id": "uuid",
  "domain": "Data Architecture",
  "q_id": "data_arch_q1",
  "evidence_file": "binary data"
}
```

**Process**:
1. **Extract Evidence**: Call Workflow A
2. **Store in Postgres**:
   ```sql
   INSERT INTO audit_evidence (session_id, q_id, extracted_data)
   VALUES ($1, $2, $3::jsonb);
   ```
3. **Fetch Question**:
   ```sql
   SELECT question_text, prompt_instructions 
   FROM audit_questions WHERE q_id = $1;
   ```
4. **Semantic Search** (Qdrant):
   - Query: question_text + domain
   - Top 5 relevant KB chunks
5. **Build Master Prompt**:
   ```
   QUESTION: [From Postgres]
   
   RELEVANT STANDARDS: [From Qdrant]
   
   EVIDENCE: [From Postgres extracted_data]
   
   INSTRUCTIONS: [Domain-specific rules]
   
   EVALUATE COMPLIANCE. Return JSON:
   {
     "compliant": true/false,
     "score": 0-100,
     "evidence_found": ["..."],
     "gaps": ["..."],
     "recommendations": ["..."]
   }
   ```
6. **Call Ollama** (llama3.2)
7. **Log Result**:
   ```sql
   INSERT INTO audit_logs (session_id, q_id, ai_response, status)
   VALUES ($1, $2, $3::jsonb, 'completed');
   ```
8. **Cleanup**:
   ```sql
   DELETE FROM audit_evidence WHERE session_id = $1;
   ```

**Output**: AI evaluation JSON + log entry

## 🔍 API Usage

### 1. Upload Standard to Knowledge Base
```bash
curl -X POST http://YOUR_VM_IP:5678/webhook/ingest-standard \
  -F "file=@ISO27001.pdf" \
  -F "domain=Security" \
  -F "standard_name=ISO 27001"
```

### 2. Run Audit
```bash
curl -X POST http://YOUR_VM_IP:5678/webhook/audit \
  -F "domain=Data Architecture" \
  -F "q_id=data_arch_q1" \
  -F "session_id=$(uuidgen)" \
  -F "evidence=@client-architecture.pdf"
```

### 3. Check Progress
```bash
curl http://YOUR_VM_IP:5678/webhook/audit-status?session_id=<UUID>
```

## 🛠️ Maintenance

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f n8n
```

### Database Access
```bash
docker exec -it compliance-db psql -U n8n -d compliance_db

# Example queries
SELECT * FROM audit_questions;
SELECT session_id, status, started_at FROM audit_sessions ORDER BY started_at DESC LIMIT 10;
```

### Qdrant Web UI
```
http://YOUR_VM_IP:6333/dashboard
```

### Backup Database
```bash
docker exec compliance-db pg_dump -U n8n compliance_db > backup_$(date +%Y%m%d).sql
```

### Restart Services
```bash
docker-compose -f docker-compose.prod.yml restart
```

## 📈 Resource Monitoring

### Disk Usage
```bash
docker system df
docker volume ls
du -sh /var/lib/docker/volumes/*
```

### Container Stats
```bash
docker stats
```

### Clean Temp Files (Manual)
```bash
docker exec compliance-n8n rm -rf /tmp/n8n_processing/*
```

## 🔒 Security Considerations

### Current Setup (POC)
- Basic Auth enabled
- Internal Docker network
- No TLS/SSL (HTTP only)
- Firewall: UFW + Azure NSG

### Production Hardening (Future)
1. Enable HTTPS with Let's Encrypt
2. Implement OAuth2/SAML
3. Enable Postgres SSL
4. Add rate limiting
5. Regular security audits

## 🐛 Troubleshooting

### n8n Can't Connect to Postgres
```bash
docker-compose -f docker-compose.prod.yml logs postgres
docker-compose -f docker-compose.prod.yml restart postgres n8n
```

### Ollama Model Not Loading
```bash
docker exec -it compliance-ollama /bin/ollama list
docker exec -it compliance-ollama /bin/ollama pull llama3.2
```

### Florence Service Crashes
```bash
# Check memory usage
docker stats compliance-florence

# Restart with more memory
docker-compose -f docker-compose.prod.yml up -d --force-recreate florence
```

### Ports Not Accessible
```bash
# On VM
sudo ufw status
sudo ufw allow 5678/tcp

# Test locally on VM
curl http://localhost:5678/healthz
```

## 📞 Support

- **GitHub Issues**: https://github.com/roshan-lal-dia/n8n-poc-compliance/issues
- **n8n Community**: https://community.n8n.io
- **Logs**: Always include relevant logs when reporting issues

## 🎯 Next Steps

1. ✅ Deploy infrastructure
2. ⏳ Import workflows into n8n
3. ⏳ Upload 2-3 standard documents
4. ⏳ Test audit API with sample evidence
5. ⏳ Iterate on prompt engineering
6. ⏳ Portal integration

---

**Version**: 1.0  
**Last Updated**: February 9, 2026  
**Maintainer**: Compliance Audit Team
