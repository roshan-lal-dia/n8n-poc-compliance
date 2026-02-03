# n8n Production Setup with Python Libraries

Complete guide for n8n 2.6.3 with external task runners and Python document processing libraries.

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Python Libraries](#-python-libraries)
- [Testing Code Examples](#-testing-code-examples)
- [Configuration](#-configuration)
- [Adding More Packages](#-adding-more-packages)
- [Troubleshooting](#-troubleshooting)
- [Security Checklist](#-security-checklist)

---

## 🚀 Quick Start

### 1. Start n8n

```powershell
docker compose up -d
```

### 2. Access n8n UI

- **URL**: http://localhost:5678
- **Username**: `admin`
- **Password**: `change_this_secure_password`

### 3. Verify Installation

Check containers are running:
```powershell
docker compose ps
```

Expected output:
```
NAME          STATUS
n8n           Up (healthy)
n8n-runners   Up
```

---

## 📦 Python Libraries

### Installed Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| **pdfplumber** | 0.11.4 | Extract text, tables from PDFs |
| **python-pptx** | 1.0.2 | Create/edit PowerPoint presentations |
| **python-docx** | 1.1.2 | Create/edit Word documents |
| **Pillow** | 11.0.0 | Image processing and manipulation |

### Quick Test

```python
import pdfplumber, pptx, docx
from PIL import Image

return {
    "pdfplumber": str(pdfplumber.__version__),
    "python-pptx": str(pptx.__version__),
    "python-docx": str(docx.__version__),
    "Pillow": Image.__version__
}
```

---

## 🧪 Testing Code Examples

### Important: Use `return`, Not `print()`

**❌ This doesn't work in n8n:**
```python
print("Hello World")  # Output goes nowhere
```

**✅ This works:**
```python
return {"message": "Hello World"}  # Output visible in n8n
```

### Hello World Tests

**Python:**
```python
return {
    "message": "Hello World from Python!",
    "python_version": "3.13"
}
```

**JavaScript:**
```javascript
return {
    message: "Hello World from JavaScript!",
    node_version: process.version,
    timestamp: new Date().toISOString()
};
```

### Test All Python Libraries

```python
import pdfplumber
import pptx
import docx
from PIL import Image

result = {
    "status": "success",
    "libraries": {
        "pdfplumber": str(pdfplumber.__version__),
        "python-pptx": str(pptx.__version__),
        "python-docx": str(docx.__version__),
        "Pillow": Image.__version__
    },
    "message": "All libraries loaded successfully!"
}

return result
```

**Expected Output:**
```json
{
  "status": "success",
  "libraries": {
    "pdfplumber": "0.11.4",
    "python-pptx": "1.0.2",
    "python-docx": "1.1.2",
    "Pillow": "11.0.0"
  },
  "message": "All libraries loaded successfully!"
}
```

### Library Usage Examples

#### PDF Processing (pdfplumber)
```python
import pdfplumber

# Process PDF from previous node
# Example: Extract text from first page
pdf_data = $input.first().binary  # Get PDF from input

return {
    "library": "pdfplumber",
    "capability": "Extract text, tables, metadata from PDFs",
    "usage": "with pdfplumber.open(pdf_path) as pdf: text = pdf.pages[0].extract_text()"
}
```

#### PowerPoint (python-pptx)
```python
from pptx import Presentation
from pptx.util import Inches

# Create a presentation
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
title = slide.shapes.title
title.text = "Hello from n8n!"

return {
    "library": "python-pptx",
    "capability": "Create/modify PowerPoint presentations",
    "slides_created": len(prs.slides)
}
```

#### Word Documents (python-docx)
```python
from docx import Document

# Create a document
doc = Document()
doc.add_heading('Document from n8n', 0)
doc.add_paragraph('This was created by n8n workflow.')

return {
    "library": "python-docx",
    "capability": "Create/modify Word documents",
    "paragraphs": len(doc.paragraphs)
}
```

#### Image Processing (Pillow)
```python
from PIL import Image, ImageFilter

# Example: Image metadata
return {
    "library": "Pillow",
    "capability": "Resize, crop, convert, add effects to images",
    "usage": "Image.open(path).resize((800, 600))"
}
```

### How to Run Test Code

1. **Open n8n**: http://localhost:5678
2. **Create New Workflow**:
   - Click "New workflow"
3. **Add Manual Trigger Node**:
   - Click `+` button
   - Search "Manual Trigger"
   - Click to add
4. **Add Code Node**:
   - Click `+` after Manual Trigger
   - Search "Code"
   - Select "Code" node
   - Choose language: Python or JavaScript
5. **Paste Test Code**:
   - Copy any example above
   - Paste in code editor
6. **Execute**:
   - Click "Test workflow" button
7. **View Output**:
   - Click Code node
   - See results in right panel

---

## ⚙️ Configuration

### Architecture

```
┌─────────────────────────────────────────┐
│  n8n Container (2.6.3)                 │
│  - Workflow engine                      │
│  - Web UI (port 5678)                   │
│  - Task broker (port 5679)              │
└────────────┬────────────────────────────┘
             │ HTTP communication
             │
┌────────────▼────────────────────────────┐
│  task-runners Container (custom)        │
│  - Python 3.13 runner                   │
│  - JavaScript runner                    │
│  - Isolated execution environment       │
│  - Libraries: pdfplumber, pptx, etc.    │
└─────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Container orchestration |
| `Dockerfile.runners` | Custom runners image with Python libraries |
| `n8n-task-runners.json` | Package allowlist configuration |
| `build.ps1` | Build script for custom image |
| `.github/copilot-instructions.md` | Code node usage rules |

### Environment Variables

**n8n container:**
- `N8N_RUNNERS_MODE=external` - Use separate runners container (production)
- `N8N_RUNNERS_BROKER_LISTEN_ADDRESS=0.0.0.0` - Allow runners to connect
- `N8N_RUNNERS_AUTH_TOKEN` - Shared secret for authentication

**task-runners container:**
- `N8N_RUNNERS_TASK_BROKER_URI=http://n8n:5679` - Connect to n8n broker
- `N8N_RUNNERS_EXTERNAL_ALLOW` - Comma-separated package allowlist

---

## 🔧 Adding More Packages

### Step 1: Edit Dockerfile

Edit `Dockerfile.runners` and add your package:

```dockerfile
FROM n8nio/runners:2.6.3
USER root
RUN cd /opt/runners/task-runner-python && uv pip install \
    pdfplumber python-pptx python-docx pillow \
    your-new-package-here
USER runner
ENV PYTHONPATH=/opt/runners/task-runner-python:$PYTHONPATH
```

### Step 2: Rebuild Image

```powershell
./build.ps1
```

### Step 3: Update Allowlist

Edit `n8n-task-runners.json` and add package to `N8N_RUNNERS_EXTERNAL_ALLOW`:

```json
{
  "task-runners": [
    {
      "runner-type": "python",
      "env-overrides": {
        "N8N_RUNNERS_EXTERNAL_ALLOW": "pdfplumber,pptx,docx,PIL,your_package"
      }
    }
  ]
}
```

**Important:** Use the import name, not pip package name:
- ✅ `PIL` (import name for Pillow)
- ❌ `pillow` (pip package name)
- ✅ `pptx` (import name for python-pptx)
- ❌ `python-pptx` (pip package name)

### Step 4: Restart

```powershell
docker compose down
docker compose up -d
```

**Note:** Full restart required for config changes to take effect.

---

## 🐛 Troubleshooting

### Python Import Errors

**Error:** `Import of external package 'xxx' is disallowed`

**Solution:**
1. Check package is installed in `Dockerfile.runners`
2. Check package is in `n8n-task-runners.json` allowlist
3. Use correct import name (not pip package name)
4. Rebuild and restart:
   ```powershell
   ./build.ps1
   docker compose down
   docker compose up -d
   ```

### Code Nodes Show No Output

**Problem:** `print()` or `console.log()` don't show anything

**Solution:** Use `return` statement instead:

```python
# ❌ Wrong
print("Hello")

# ✅ Correct
return {"message": "Hello"}
```

See `.github/copilot-instructions.md` for details.

### Task Runners Not Connecting

**Check logs:**
```powershell
docker compose logs task-runners --tail 50
```

**Common issues:**
- Auth token mismatch between n8n and task-runners
- Network connectivity (check `docker compose ps`)
- Config file not mounted properly

**Solution:**
```powershell
docker compose down
docker compose up -d
docker compose logs -f
```

### Container Restart Loops

**Check status:**
```powershell
docker compose ps
```

If `n8n-runners` shows "Restarting":

1. Check logs:
   ```powershell
   docker compose logs task-runners
   ```

2. Verify config syntax:
   ```powershell
   Get-Content n8n-task-runners.json | ConvertFrom-Json
   ```

3. Rebuild image:
   ```powershell
   ./build.ps1
   docker compose restart task-runners
   ```

### Package Not Found After Installation

**Verify package is installed:**
```powershell
docker exec n8n-runners python3 -c "import your_package; print('OK')"
```

If fails:
1. Package not built into image → Edit `Dockerfile.runners` and rebuild
2. Package built but not allowlisted → Update `n8n-task-runners.json`

---

## 🔒 Security Checklist

Before deploying to production:

### Critical Security Settings

- [ ] **Change default passwords**:
  ```yaml
  N8N_BASIC_AUTH_PASSWORD: change_this_secure_password
  ```

- [ ] **Set encryption key** (random 32 characters):
  ```yaml
  N8N_ENCRYPTION_KEY: change_this_32_char_encryption_key_here
  ```

- [ ] **Change runner auth token**:
  ```yaml
  N8N_RUNNERS_AUTH_TOKEN: n8n-runner-secret-token-2026-change-this
  ```

### Network Security

- [ ] Set `N8N_HOST` to your actual domain
- [ ] Set `N8N_PROTOCOL=https` if using TLS
- [ ] Configure reverse proxy (nginx/traefik) for HTTPS
- [ ] Restrict n8n port access (don't expose 5678 publicly)

### Package Security

- [ ] Review `N8N_RUNNERS_EXTERNAL_ALLOW` - only allow needed packages
- [ ] Pin library versions in `Dockerfile.runners`
- [ ] Regularly update base images and libraries
- [ ] Test workflows in staging before production

### Operational Security

- [ ] Set up regular backups of `n8n_data` volume
- [ ] Enable webhook authentication for production workflows
- [ ] Monitor logs for suspicious activity
- [ ] Document all custom packages and their purposes

---

## 📚 Useful Commands

### Container Management

```powershell
# Start everything
docker compose up -d

# Stop everything
docker compose down

# Restart services
docker compose restart

# Check status
docker compose ps

# View all logs
docker compose logs -f

# View specific service logs
docker compose logs n8n -f
docker compose logs task-runners -f
```

### Maintenance

```powershell
# Rebuild custom image
./build.ps1

# Rebuild and restart runners
./build.ps1
docker compose restart task-runners

# Full restart (needed for config changes)
docker compose down
docker compose up -d

# Access n8n shell
docker exec -it n8n sh

# Access runners shell
docker exec -it n8n-runners sh

# Check Python packages
docker exec n8n-runners python3 -m pip list
```

### Debugging

```powershell
# Check if config is mounted
docker exec n8n-runners cat /etc/n8n-task-runners.json

# Test Python package
docker exec n8n-runners python3 -c "import pdfplumber; print(pdfplumber.__version__)"

# View last 50 lines of logs
docker compose logs task-runners --tail 50

# Follow logs in real-time
docker compose logs -f
```

---

## 📖 Resources

- [n8n Documentation](https://docs.n8n.io/)
- [Task Runners Guide](https://docs.n8n.io/hosting/scaling/task-runners/)
- [Docker Deployment](https://docs.n8n.io/hosting/installation/docker/)
- [Code Node Documentation](https://docs.n8n.io/code/builtin/code-node/)

---

## 📝 Notes

### External vs Internal Mode

**External Mode (Current Setup):**
- ✅ Production-recommended
- ✅ Secure isolation
- ✅ Better resource management
- ❌ Complex configuration

**Internal Mode (Alternative):**
- ✅ Simple setup
- ✅ Easier to add packages
- ❌ Less secure (code runs in main process)
- ❌ Not recommended for production

### Why Config Needs Full Restart

The `n8n-task-runners.json` file is read on container startup. Changes require:
```powershell
docker compose down  # Stop containers
docker compose up -d # Start with new config
```

Simple restart (`docker compose restart`) may not reload the mounted file.

---

**Version:** n8n 2.6.3 | **Python:** 3.13 | **Mode:** External runners (production-ready)
