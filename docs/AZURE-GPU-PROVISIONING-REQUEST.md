# Azure GPU VM Provisioning Request & AI Model Upgrade Plan

**Project:** NPC Compliance AI System  
**Date:** February 23, 2026  
**Prepared by:** Engineering Team  
**Priority:** Time-bound — NVv3 retirement window is active

---

## 1. Summary

We are requesting provisioning of an NVv3-series GPU VM (Tesla M60) under the special arrangement being facilitated by the Azure team. This document covers:

1. A full technical upgrade plan to move our AI stack from CPU-based to GPU-accelerated inference using Microsoft's official model collection
2. All ports, URLs, and network access requirements needed for the machine to be operational from day zero

---

## 2. Why This Upgrade

Our current compliance AI system runs all inference workloads on CPU. This causes:

- **Florence vision model:** 8–12 seconds per image (needs < 1s)
- **LLM compliance reasoning:** ~30 seconds per audit job (needs < 5s)
- **No Arabic OCR quality:** Tesseract eng+ara is brittle on compliance PDFs
- **Low context window:** llama3.2 at 32K tokens is insufficient for large compliance documents

With the GPU VM, all of these improve by 10–20× and we can load substantially better models — all from Microsoft's official collection on Hugging Face.

---

## 3. VM Specifications (What We Will Receive)

Based on the offered hardware under the NVv3 special arrangement:

| Attribute | Specification |
|---|---|
| VM Series | Azure NVv3-series (retiring Sept 30, 2026) |
| GPU Model | NVIDIA Tesla M60 |
| GPU Architecture | Maxwell (CUDA Compute Capability 5.2) |
| CUDA Cores | 4096 total (2048 per GPU) |
| VRAM | 16 GB GDDR5 per board (8 GB per GPU partition) |
| GPUs per Board | 2 |
| Max Board Config | NV48s_v3 = 4 partitions = **48 GB usable VRAM** (confirmed) |
| CUDA Support | CUDA 12.x compatible (CC 5.2 minimum met) |
| Retirement Date | September 30, 2026 |

---

## 4. Requested VM SKU

**Preferred:** `Standard_NV48s_v3` — 48 GB VRAM total, 48 vCPUs, 448 GiB RAM  
**Acceptable fallback:** `Standard_NV24s_v3` — 24 GB VRAM, 24 vCPUs, 224 GiB RAM

**OS:** Ubuntu 22.04 LTS  
**Storage:** Minimum 256 GB SSD OS disk + 512 GB data disk (for model caches)  
**NVIDIA Container Toolkit:** Pre-installed or permissioned for install at first boot

---

## 5. VRAM Allocation Plan

| Docker Service | Model Loaded | VRAM (Q4_K_M) | VRAM (FP16 option) |
|---|---|---|---|
| `florence-service` | Florence-2-large-ft + LayoutLMv3-base + Table-Transformer (detection + structure) | ~4.5 GB | ~5.5 GB |
| `ollama` | Mistral Nemo 12B Instruct (`mistral-nemo:12b`) | ~7.5 GB | **~24 GB** |
| `embedding-service` | multilingual-e5-large | ~1.1 GB | ~2.2 GB |
| System / Docker overhead | — | ~1.5 GB | ~1.5 GB |
| **Total** | | **~14.6 GB** | **~33.2 GB** |
| **Available VRAM** | | **48 GB confirmed** | **48 GB confirmed** |

With 48 GB VRAM available, we have two viable serving modes:
- **Q4_K_M (default, recommended):** ~15 GB used, 33 GB free — minimal memory, fastest cold start
- **FP16 (higher quality):** ~33 GB used, 15 GB free — better reasoning quality from Mistral Nemo, still fits comfortably

Recommendation: start with Q4_K_M, benchmark reasoning quality on a sample audit batch, then switch to FP16 if needed. Single command in Ollama: `ollama pull mistral-nemo:12b-instruct-2407-fp16`.

---

## 6. Model Change Plan

All models are being replaced with or upgraded to Microsoft's official model collection on Hugging Face ([huggingface.co/microsoft/collections](https://huggingface.co/microsoft/collections)).

### 6.1 Vision, OCR & Document Intelligence

| | Before | After |
|---|---|---|
| **Model** | `microsoft/Florence-2-base` (0.2B params, CPU) | `microsoft/Florence-2-large-ft` (0.77B params, GPU) |
| **OCR** | Tesseract CLI (eng+ara, brittle on PDFs) | Florence-2 native `<OCR>` and `<OCR_WITH_REGION>` tasks |
| **Image captioning** | `<MORE_DETAILED_CAPTION>` basic | `<MORE_DETAILED_CAPTION>` + `<DETAILED_CAPTION>` + `<REGION_TO_DESCRIPTION>` |
| **Table extraction** | None | ✅ Added: Table Transformer detection + structure recognition |
| **Layout parsing** | None | ✅ Added: LayoutLMv3-base for form fields, KV extraction |
| **Speed** | 8–12s per image (CPU) | ~0.5–1s per image (GPU) |
| **HF Link** | — | [microsoft/Florence-2-large-ft](https://huggingface.co/microsoft/Florence-2-large-ft) |

**Additional models loaded in the same `florence-service` container:**

| Model | Purpose | Size | HF Link |
|---|---|---|---|
| `microsoft/layoutlmv3-base` | Structured form/table layout parsing on compliance docs | 125M | [HF link](https://huggingface.co/microsoft/layoutlmv3-base) |
| `microsoft/table-transformer-detection` | Detect table bounding boxes in PDF page images | 28.8M | [HF link](https://huggingface.co/microsoft/table-transformer-detection) |
| `microsoft/table-transformer-structure-recognition-v1.1-all` | Extract row/column structure from detected tables | 28.8M | [HF link](https://huggingface.co/microsoft/table-transformer-structure-recognition-v1.1-all) |

> **Tesseract removed entirely.** Florence-2-large-ft's native OCR replaces `tesseract`, `tesseract-ocr-data-eng`, and `tesseract-ocr-data-ara`. This simplifies our n8n Docker image and improves Arabic compliance document handling.

---

### 6.2 LLM Reasoning

| | Before | After |
|---|---|---|
| **Model** | `llama3.2` (Meta, 3B params) | `mistralai/Mistral-Nemo-Instruct-2407` (12B params) |
| **Context window** | 32,768 tokens (manually configured) | **128,000 tokens native** |
| **Languages** | English only | ✅ en, fr, de, es, it, pt, ru, zh, ja — strong multilingual |
| **Reasoning** | General | ✅ Significantly stronger instruction-following, CoT reasoning, structured output |
| **VRAM (Q4_K_M)** | ~2.5 GB | ~7.5 GB via Ollama |
| **VRAM (FP16)** | N/A | ~24 GB via Ollama — fits within 48 GB |
| **License** | Meta Llama | Apache 2.0 ✅ |
| **How to pull** | `ollama pull llama3.2` | `ollama pull mistral-nemo:12b` |
| **HF Link** | — | [mistralai/Mistral-Nemo-Instruct-2407](https://huggingface.co/mistralai/Mistral-Nemo-Instruct-2407) |

> **Why Mistral Nemo over Phi-3.5-mini or Phi-4?** Mistral Nemo is a 12B model — with 48 GB VRAM confirmed, we are no longer memory-constrained. It offers substantially better reasoning depth for compliance gap analysis compared to 3–4B models. Phi-4 requires BF16 / tensor cores (unavailable on Tesla M60 Maxwell CC 5.2), making it incompatible with this hardware. Mistral Nemo runs cleanly on Maxwell FP16 via Ollama.

---

### 6.3 Embeddings

| | Before | After |
|---|---|---|
| **Model** | `nomic-embed-text` (768-dim via Ollama) | `intfloat/multilingual-e5-large` (1024-dim) |
| **Languages** | English primarily | ✅ 100 languages including Arabic |
| **Vector dimensions** | 768 | 1024 |
| **Quality** | Moderate | Significantly better multilingual retrieval |
| **Serving** | Ollama API | Dedicated Python `embedding-service` (mirrors existing `florence-service` pattern) |
| **VRAM** | CPU (Ollama) | ~1.1 GB GPU |
| **HF Link** | — | [intfloat/multilingual-e5-large](https://huggingface.co/intfloat/multilingual-e5-large) |

> **Note:** `intfloat/multilingual-e5-large` is a Microsoft Research / MSRA collaboration. While it does not live in the `microsoft/` namespace on HF, it is authored by Microsoft Research and represents the best-in-class embedding model for our Arabic+English compliance use case.

> **Qdrant migration required:** The vector dimensions change from 768 → 1024. The `compliance_standards` collection in Qdrant must be recreated and Workflow B (KB Ingestion) must be re-run after deployment.

---

### 6.4 Summary of All Model Changes

| Component | Current Model | New Model | Source |
|---|---|---|---|
| Vision / OCR / Caption | Florence-2-base (CPU) | **Florence-2-large-ft** (GPU) | microsoft/collections |
| Document Layout | ❌ None | **layoutlmv3-base** (GPU) | microsoft/collections |
| Table Detection | ❌ None | **table-transformer-detection** (GPU) | microsoft/collections |
| Table Structure | ❌ None | **table-transformer-structure-recognition-v1.1-all** (GPU) | microsoft/collections |
| LLM Reasoning | llama3.2 (Meta, 3B) | **Mistral-Nemo-Instruct-2407** (12B, GPU) | Mistral AI — Apache 2.0 |
| Embeddings | nomic-embed-text | **multilingual-e5-large** (GPU) | Microsoft Research |
| OCR | Tesseract (CLI) | **Removed** — Florence-2 native OCR used instead | — |

---

## 7. Network Access Requirements

### 7.1 Inbound Firewall Rules (to VM)

| Port | Protocol | Direction | Source | Purpose |
|---|---|---|---|---|
| `22` | TCP | Inbound | **Restrict to known IPs / VPN only** | SSH admin access |
| `5678` | TCP | Inbound | Internal network / VPN | n8n workflow UI and webhooks |

> All other ports (`5000`, `5432`, `6333`, `6379`, `8080`, `11434`) are **internal Docker network only** — they must NOT be exposed to the public internet. Only `5678` and `22` need inbound rules.

---

### 7.2 Outbound Firewall Rules (from VM)

| Port | Protocol | Destination | Purpose |
|---|---|---|---|
| `443` | HTTPS | See Section 7.3 whitelist | All model downloads, package installs, Docker pulls |
| `5432` | TCP | `unifi-cdmp-server-pg.postgres.database.azure.com` | Azure PostgreSQL (read-only compliance app database) |
| `80` | HTTP | Package mirrors | APT / Alpine package manager (can be blocked post-setup) |

---

### 7.3 URL Whitelist (Outbound HTTPS :443)

Please whitelist the following domains on the VM's outbound firewall. These are required for initial provisioning and model download. After the first successful `docker compose up`, model files are cached on disk and most of these can be optionally blocked.

#### Hugging Face (Model Downloads — ~7 GB first run)

```
huggingface.co
cdn-lfs.huggingface.co
cdn-lfs-us-1.huggingface.co
cdn-lfs-us-1.hf.co
hf.co
```

#### NVIDIA (GPU Driver + Container Toolkit — CRITICAL)

```
developer.download.nvidia.com
international.download.nvidia.com
us.download.nvidia.com
nvidia.github.io
```

#### Docker (Container Image Pulls)

```
hub.docker.com
registry-1.docker.io
auth.docker.io
index.docker.io
production.cloudflare.docker.com
ghcr.io
gcr.io
```

#### PyTorch (CUDA Wheels — one-time install)

```
download.pytorch.org
```

#### Ollama (LLM Registry)

```
registry.ollama.ai
ollama.com
```

#### GitHub (Configs, container manifests)

```
github.com
raw.githubusercontent.com
objects.githubusercontent.com
codeload.github.com
```

#### Python Package Manager

```
pypi.org
files.pythonhosted.org
```

#### Linux Package Managers

```
dl-cdn.alpinelinux.org
deb.debian.org
security.debian.org
archive.ubuntu.com
security.ubuntu.com
```

#### Azure (already open — confirm still active)

```
*.blob.core.windows.net
*.postgres.database.azure.com
login.microsoftonline.com
```

---

### 7.4 Internal Docker Port Map (for reference only — no firewall rules needed)

| Port | Service | Purpose |
|---|---|---|
| `5678` | n8n | Workflow engine, webhook receiver |
| `5432` | PostgreSQL | Local compliance audit database |
| `6333` | Qdrant (HTTP) | Vector search (RAG) |
| `6334` | Qdrant (gRPC) | Vector search internal only |
| `6379` | Redis | Async job queue |
| `11434` | Ollama | LLM inference (Phi-3.5-mini) |
| `5000` | florence-service | Vision / OCR / layout inference |
| `8080` | embedding-service | Text embedding (multilingual-e5-large) |

---

## 8. Host-Level Setup Required (Day 0)

The following commands must be run on the VM **before** `docker compose up`. Either the Azure team runs them during provisioning, or we need sudo access to run them ourselves at first login.

### Step 1 — Verify GPU is visible

```bash
nvidia-smi
```

Expected output: Tesla M60 listed with driver version 525+ and CUDA 12.x.

### Step 2 — Install NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Step 3 — Verify GPU passthrough to Docker

```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

Expected: Same Tesla M60 output as Step 1, but from inside a container.

### Step 4 — Confirm disk space

```bash
df -h
```

Minimum required: **50 GB free** for Docker images and model caches (`~7 GB HF models + ~10 GB Docker layers + ~5 GB Ollama GGUF`).

---

## 9. Code Changes Required (Engineering Team)

The following files in the repository need to be updated before deploying on the new VM. This section is for internal tracking.

| File | Change |
|---|---|
| `florence-service/Dockerfile` | Change PyTorch wheel from `cpu` → `cu121`; add `sentence-transformers` for embedding service |
| `florence-service/app.py` | Change model ID `Florence-2-base` → `Florence-2-large-ft`; `device = "cuda"`; add `/layout` and `/tables` endpoints |
| `docker-compose.prod.yml` | Add GPU device reservations to `ollama` and `florence` services; add new `embedding-service` container; change Ollama startup pull from `llama3.2` → `mistral-nemo:12b` |
| `Dockerfile` (n8n custom) | Remove Tesseract and tessdata packages (`tesseract-ocr`, `tesseract-ocr-data-eng`, `tesseract-ocr-data-ara`) |
| `embedding-service/app.py` | New file — Python Flask service wrapping `multilingual-e5-large` |
| `embedding-service/Dockerfile` | New file — Python 3.10-slim + torch CUDA + sentence-transformers |
| Workflow B + C2 JSON | Update embedding endpoint from `http://ollama:11434/api/embeddings` → `http://embedding-service:8080/embed`; update vector size in Qdrant upsert from `768` → `1024` |
| Workflow C2 JSON | Update LLM model name from `llama3.2` → `mistral-nemo:12b` in `Ollama: Evaluate Compliance` node |

---

## 10. Qdrant Data Migration Note

The change from `nomic-embed-text` (768-dim) to `multilingual-e5-large` (1024-dim) means the existing Qdrant vector collection is incompatible. The migration steps are:

1. Drop existing `compliance_standards` collection in Qdrant
2. Recreate with `vector_size: 1024, distance: Cosine`
3. Re-run Workflow B (KB Ingestion) against the compliance standards source documents
4. Verify retrieval quality in Workflow C2 with a test audit

This is a one-time operation and takes approximately 20–30 minutes depending on the size of the knowledge base.

---

## 11. Acceptance Checklist

Once the VM is provisioned and Steps 1–4 in Section 8 are complete, we will verify the following before sign-off:

- [ ] `nvidia-smi` shows Tesla M60 on the host
- [ ] GPU passthrough to Docker containers confirmed
- [ ] `docker compose up` completes without errors
- [ ] `GET http://localhost:5000/health` → `{"status": "ok", "model": "Florence-2-large-ft"}`
- [ ] `GET http://localhost:8080/health` → `{"status": "ok", "model": "multilingual-e5-large"}`
- [ ] `ollama list` shows `mistral-nemo:12b` loaded
- [ ] Workflow A processes a test PDF in < 5 seconds end-to-end
- [ ] Workflow B ingests a test document; Qdrant shows 1024-dim vectors
- [ ] Workflow C2 returns a compliance audit result using Phi-3.5-mini-instruct

---

## 12. Contact & Escalation

| Item | Contact |
|---|---|
| VM provisioning timeline | Azure team |
| Port/firewall requests | Azure network admin |
| URL whitelist | Azure security team |
| Code deployment | Engineering team |
| NVIDIA driver version concerns | Engineering team — CUDA 12.1+ required for our torch wheel |

---

*Document prepared: February 23, 2026*  
*VM retirement deadline: September 30, 2026 (NVv3-series)*  
*NCv3 extended deadline (East US 2, West Europe, US Central): February 28, 2026 — **URGENT if this region is involved***
