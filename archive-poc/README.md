# n8n Compliance POC (Hybrid Architecture)

A secure, local-only n8n workflow environment designed for compliance document processing. This setup uses a **Sidecar Architecture** to combine the orchestration power of n8n with advanced AI Vision capabilities (Microsoft Florence-2), all running locally without cloud APIs.

---

## 📋 Features

- **Orchestrator**: n8n 2.6.3 (Alpine-based)
- **Vision Engine**: Private Python Sidecar running `microsoft/Florence-2-base`
- **Local Conversion**: 
  - libreoffice (with OpenJDK 11) for converting Office docs to PDF.
  - poppler-utils (pdftoppm) for converting PDFs to high-quality images.
  - Tesseract 5 for OCR (English + Arabic).
- **Privacy**: All processing happens locally. Images are exchanged via a shared Docker volume (`/tmp/n8n_processing`).
- **Safety**: Automated cleanup with safe-guards to prevent data loss.

---

## 🚀 Quick Start

### 1. Requirements
- Docker Desktop (Windows/Mac/Linux)
- Git
- **RAM**: At least 8GB recommended (4GB for containers + OS overhead).

### 2. Start the Environment
This will build the custom images and start the container fleet.

```powershell
docker compose up -d --build
```

### 3. Access n8n
- **URL**: [http://localhost:5678](http://localhost:5678)
- **Username**: `admin`
- **Password**: `change_this_secure_password` (See docker-compose.yml)

---

## ⚙️ Configuration & Architecture

### Docker Structure (Sidecar Pattern)
We use two services communicating via the internal Docker network:

1.  **n8n**: The workflow engine. Handles file uploads, document conversion, and final aggregation.
2.  **florence**: A Python/Flask API that loads the `Florence-2-base` model. It reads images directly from the shared volume to avoid HTTP overhead.

| Tool | Service | Purpose |
|------|---------|---------|
| **LibreOffice** | n8n | Convert PPTX/DOCX to PDF |
| **pdftoppm** | n8n | Extract PDF pages to PNG |
| **Tesseract** | n8n | Optical Character Recognition |
| **Florence-2** | florence | Image captioning & region detection |

### Processing Directory
To ensure file isolation and prevent permission issues, all temporary files are handled in:
N8N_RESTRICT_FILE_ACCESS_TO=/tmp/n8n_processing

**Workflow Rules:**
1. **Always** use a unique prefix for filenames (e.g., {{["Set Filename"].json["filePrefix"]}}_input.pptx) to allow concurrent executions.
2. **Never** rely on {{ .data.fileName }} inside Command nodes as it can be unsafe or empty.

---

## 🧪 Validating the Install

To check if the tools are correctly installed inside the container:

1. Open a terminal to the running container:
   ```powershell
   docker exec -it n8n sh
   ```

2. Test LibreOffice:
   ```sh
   libreoffice --version
   # Expected: LibreOffice 7.x...
   ```

3. Test Pdftoppm:
   ```sh
   pdftoppm -v
   # Expected: pdftoppm version 24.x...
   ```

---

## ⚠️ Important Notes

### No External Task Runners
This branch replaces the complex "Task Runner" architecture with a simpler "Monolithic" approach.
- **Deleted**: docker-compose.override.yml, 	ask-runners container.
- **Reasoning**: Simpler maintenance for local POC; simpler permission management for shared /tmp files.

### Security
- **Basic Auth** is enabled by default.
- **Execute Command** node is **ALLOWED** (NODES_ALLOW_BUILTIN=ExecuteCommand).
- File access is **RESTRICTED** to /tmp/n8n_processing.

---

## 🐛 Troubleshooting

**"javaldx: Could not find a Java Runtime Environment"**
- **Cause**: LibreOffice requires Java for some PPTX operations.
- **Fix**: The Dockerfile now includes openjdk11-jre. Rebuild with docker compose build.

**"Permission denied" in /tmp/n8n_processing**
- **Cause**: The folder might be owned by root.
- **Fix**: The Dockerfile explicitly sets ownership to node:node. If issues persist, run:
  ```sh
  docker exec -u 0 n8n chown -R node:node /tmp/n8n_processing
  ```
