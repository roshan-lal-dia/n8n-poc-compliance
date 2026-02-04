# n8n Compliance POC (Local Processing)

A secure, local-only n8n workflow environment designed for compliance document processing. This setup runs n8n with custom tools installed directly in the container to handle document conversion (PPTX/DOCX → PDF → Images) without external cloud APIs.

---

## 📋 Features

- **Base**: 
8nio/n8n:2.6.3
- **Local Conversion**: 
  - libreoffice (with OpenJDK 11) for converting Office docs to PDF.
  - poppler-utils (pdftoppm) for converting PDFs to high-quality images.
- **Privacy**: All processing happens locally in /tmp/n8n_processing. No data leaves the container.
- **Fonts**: Includes Noto and FreeFree fonts for accurate rendering.

---

## 🚀 Quick Start

### 1. Requirements
- Docker Desktop (Windows/Mac/Linux)
- Git

### 2. Start the Environment
This will build the custom image and start the container.

`powershell
docker compose up -d --build
`

### 3. Access n8n
- **URL**: [http://localhost:5678](http://localhost:5678)
- **Username**: dmin
- **Password**: change_this_secure_password (See docker-compose.yml)

---

## ⚙️ Configuration & Architecture

### Docker Structure
The project uses a single **customized n8n image** defined in Dockerfile. It extends the official Alpine-based image to add system-level dependencies meant for the Execute Command node.

| Tool | Purpose | Status |
|------|---------|--------|
| **LibreOffice** | libreoffice --headless --convert-to pdf ... | Installed |
| **OpenJDK 11** | Required for LibreOffice PPTX headers | Installed |
| **Poppler** | pdftoppm for PDF extraction | Installed |

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
   `powershell
   docker exec -it n8n sh
   `

2. Test LibreOffice:
   `ash
   libreoffice --version
   # Expected: LibreOffice 7.x...
   `

3. Test Pdftoppm:
   `ash
   pdftoppm -v
   # Expected: pdftoppm version 24.x...
   `

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
- **Cause**: The folder might be owned by oot.
- **Fix**: The Dockerfile explicitly sets ownership to 
ode:node. If issues persist, run:
  `ash
  docker exec -u 0 n8n chown -R node:node /tmp/n8n_processing
  `

