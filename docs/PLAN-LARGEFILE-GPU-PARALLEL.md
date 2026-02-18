# Plan: Large File Optimisation, GPU Support & Parallel Processing

**Status:** Decision required before implementation  
**Priority:** High — precondition for production readiness  
**Last Updated:** February 18, 2026

---

## Scope

Three interrelated concerns addressed in this document:

| # | Concern | Current state | Goal |
|---|---------|--------------|------|
| 1 | **Large file chunking** | Full-text passed to LLM in one shot — context window overflows on large docs | Smart chunking that preserves semantic meaning |
| 2 | **GPU-accelerated inference** | Florence-2 + Ollama both run on CPU — 3-6× slower | CUDA-aware containers with optional GPU fallback |
| 3 | **Parallel job processing** | Single cron-based C2 worker pops one job at a time (10 s poll) | Multiple workers or event-driven dispatch, GPU-aware |

These are planned together because GPU availability directly affects the chunking strategy (GPU allows larger context with faster inference) and the concurrency model (a single GPU must be shared or time-sliced).

---

## Part 1: Large File Chunking and Context Management

### Problem

Workflow C2 today consolidates **all** extracted text from all pages of all evidence files into a single string and sends it to Ollama. For a 50-page PDF this can exceed 15,000 tokens — well beyond `llama3.2`'s 8K context window. The model silently truncates, potentially cutting the most relevant evidence.

### Recommended Approach: Hierarchical RAG over Evidence

Instead of dumping the full text, treat the evidence document the same way standards are handled — chunk it, embed it, search it.

```
Evidence file
    │
    ▼
Workflow A (extract)
    │── full_text (per page)
    │
    ▼
Chunk into segments (configurable, e.g. 512 tokens / 128 overlap)
    │
    ▼
Embed each chunk (nomic-embed-text, same model as KB)
    │
    ▼
Store in Qdrant: collection "evidence_<sessionId>"
    │
    ▼
RAG search: query = audit question text
    │── Top K most relevant evidence chunks (e.g. K=5)
    │
    ▼
Build prompt with: question + standards context + evidence chunks
    │
    ▼
Ollama: concise, relevant context — no truncation
    │
    ▼
Clean up: delete "evidence_<sessionId>" collection on completion
```

### Implementation Details

#### Chunking Parameters (Workflow C2 Code Node)

```javascript
// Recommended starting config — tune based on model and file type
const CHUNK_SIZE_TOKENS  = 512;   // ~400 words
const CHUNK_OVERLAP      = 128;   // ~100 words
const TOP_K_EVIDENCE     = 5;     // How many chunks feed into the prompt
const TOP_K_STANDARDS    = 5;     // Unchanged from current
```

For token-accurate chunking without a tokeniser library in n8n's JS sandbox, use character-based approximation (1 token ≈ 4 characters):

```javascript
const CHARS_PER_CHUNK   = 2048;  // ≈ 512 tokens
const CHARS_OVERLAP     = 512;   // ≈ 128 tokens
```

#### Semantic Boundary Preservation

Splitting mid-sentence loses meaning. Before chunking, split text at paragraph/sentence boundaries:

```javascript
function chunkText(text, chunkSize, overlap) {
  const paragraphs = text.split(/\n{2,}|\r\n{2,}/);
  const chunks = [];
  let current = '';

  for (const para of paragraphs) {
    if ((current + para).length > chunkSize && current.length > 0) {
      chunks.push(current.trim());
      // Overlap: keep last `overlap` chars of current chunk
      current = current.slice(-overlap) + '\n\n' + para;
    } else {
      current += (current ? '\n\n' : '') + para;
    }
  }
  if (current.trim()) chunks.push(current.trim());
  return chunks;
}
```

#### Qdrant Collection Per Session

Use a **per-session ephemeral collection** for evidence (`evidence_<sessionId>`) to:
- Keep evidence isolated between concurrent sessions
- Enable cleanup on completion without impacting other sessions or the `compliance_standards` collection

```bash
# Create on session start
POST /collections/evidence_<sessionId>
{ "vectors": { "size": 768, "distance": "Cosine" } }

# Delete on session completion
DELETE /collections/evidence_<sessionId>
```

> **Alternative (simpler, no ephemeral collections):** Use a `payload filter` on the existing `compliance_standards` collection by adding `session_id` and `collection_type: "evidence"` metadata to evidence points — filter at query time and delete by payload filter. Avoids collection creation overhead but mixes standards and evidence in one collection.

#### Updated Prompt Structure

```
COMPLIANCE QUESTION:
{{ question_text }}

EVALUATION INSTRUCTIONS:
{{ prompt_instructions }}

RELEVANT STANDARDS (from Knowledge Base):
{{ standards_context }}   ← Top 5 chunks from compliance_standards

MOST RELEVANT EVIDENCE EXCERPTS:
{{ evidence_context }}    ← Top 5 chunks from evidence RAG (NEW)

SUPPLEMENTARY EVIDENCE METADATA:
- Total pages: {{ total_pages }}
- File(s): {{ file_names }}
- Diagrams detected: {{ diagram_count }}
- Diagram descriptions: {{ diagram_descriptions }}

EVALUATE COMPLIANCE. Return JSON only:
{
  "compliant": true/false,
  "confidence": 0-100,
  "score": 0-100,
  "evidence_found": ["..."],
  "gaps": ["..."],
  "recommendations": ["..."]
}
```

#### Model Swap Recommendation

| Model | Context window | Speed (CPU) | Speed (GPU A10) | Notes |
|-------|---------------|-------------|-----------------|-------|
| `llama3.2:3b` (current) | 8K tokens | ~30s/response | ~5s | Fast, context-limited |
| `llama3.1:8b` | 128K tokens | ~90s/response | ~15s | Best quality/context balance |
| `mistral-nemo:12b` | 128K tokens | ~180s/response | ~25s | Strongest reasoning |
| `qwen2.5:7b` | 128K tokens | ~80s/response | ~12s | Good multilingual (Arabic docs) |

**Recommendation:** Switch to `llama3.1:8b` when GPU is available. Keep `llama3.2:3b` as CPU fallback.

In `docker-compose.prod.yml`, the Ollama entrypoint can be updated to pull both:
```yaml
entrypoint: ["/bin/sh", "-c",
  "/bin/ollama serve &
   sleep 5;
   /bin/ollama pull llama3.1:8b;
   /bin/ollama pull llama3.2;
   /bin/ollama pull nomic-embed-text;
   wait"]
```

---

## Part 2: GPU Support (Florence-2 + Ollama)

### Current State

Both `florence-service` and `ollama` run on CPU. This is the primary bottleneck:

| Task | CPU time (D4s v5, 4 vCPU) | GPU time (A10 24GB) |
|------|--------------------------|---------------------|
| Florence-2 image caption | ~8-12s/image | ~0.5-1s/image |
| Ollama llama3.2 (3B) response | ~30s | ~5s |
| Ollama llama3.1 (8B) response | ~90s | ~15s |
| Ollama nomic-embed-text | ~2s | ~0.2s |

For a single audit with 5 questions × 3 pages each = 15 Florence calls + 5 Ollama calls = **~3-4 minutes on CPU vs ~20-30s on GPU**.

### What's Needed for GPU

#### Prerequisites on the VM
The target VM must have an NVIDIA GPU and the following installed on the host:

```bash
# Verify GPU
nvidia-smi

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

#### `docker-compose.prod.yml` Changes — Ollama

```yaml
ollama:
  image: ollama/ollama:latest   # GPU-capable image (same tag, detected automatically)
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - OLLAMA_NUM_GPU=1
```

> No model change needed — Ollama auto-detects CUDA and loads layers to GPU.

#### `florence-service/Dockerfile` Changes — Florence-2

The current Dockerfile installs the **CPU-only PyTorch wheel**. For GPU, swap to the CUDA wheel:

```dockerfile
# Current (CPU only):
RUN pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

# GPU (CUDA 12.1):
RUN pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
```

Also update `app.py` to auto-detect CUDA:

```python
# Current:
device = "cpu"

# GPU-aware:
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")
```

And in `docker-compose.prod.yml`:

```yaml
florence:
  build:
    context: ./florence-service
    dockerfile: Dockerfile
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
```

> **GPU memory note:** Florence-2-base needs ~2GB VRAM. `llama3.1:8b` needs ~10GB VRAM. An Azure `NC6s_v3` (Tesla V100 16GB) or `NC4as_T4_v3` (T4 16GB) covers both comfortably.

#### CPU Fallback Strategy

Keep the CPU branch working so the system degrades gracefully when no GPU is available. The `device = "cuda" if torch.cuda.is_available() else "cpu"` pattern handles this automatically for Florence. Ollama also falls back to CPU automatically.

---

## Part 3: Parallel Job Processing

### Current Architecture

```
[Cron: every 10s]
      │
      ▼
Redis RPOP (audit_job_queue) ── empty? → stop
      │
      ▼
Process 1 job: extract → RAG → AI → log
      │
      ▼
[Wait 10s, repeat]
```

**Problems:**
- Only 1 job processed every 10s poll cycle
- If a job takes 4 minutes (CPU), the queue builds up
- Cron-based polling wastes the 10s wait even when queue is busy

### Option A: Multiple C2 Worker Instances (Recommended for now)

Keep Redis queue, but run **N parallel instances** of Workflow C2 in n8n. n8n supports this natively — activate the same cron workflow multiple times via execution concurrency settings.

```
[Cron: every 10s] × 3 instances
  Worker 1 ──► RPOP → Job A
  Worker 2 ──► RPOP → Job B  (atomic — Redis RPOP is threadsafe)
  Worker 3 ──► RPOP → Job C
```

**How to enable in n8n:**
- Go to **Settings → Execution** → increase **Concurrent Executions** per workflow
- Or: duplicate Workflow C2 as C2a, C2b, C2c — each with its own cron trigger

**Pros:**
- No architecture change — Redis queue already handles concurrent pops safely
- Works today (CPU or GPU)
- Scales linearly: 4 workers = 4× throughput

**Cons:**
- Each worker independently calls Florence and Ollama — GPU must serve concurrent requests
- GPU time-slicing may cause contention (acceptable for A10 24GB, risk on smaller GPUs)

**Recommended starting point:** 3 concurrent workers on GPU, 1 on CPU.

---

### Option B: Event-driven Dispatch (Drop the Cron)

Replace the cron-based poll with a webhook-triggered chain: C1 (submission) → directly triggers C2 execution via n8n's `Execute Workflow` node.

```
C1: Submit → queue job to Redis → Execute Workflow (C2) asynchronously
                                          │
                                          ▼
                                    C2 starts immediately
                                    (no 10s wait)
```

**Pros:**
- Zero latency between submission and processing start
- No idle poll cycles

**Cons:**
- Loses the queue's backpressure protection — 100 simultaneous submissions = 100 simultaneous C2 executions → possible GPU OOM
- Requires a concurrency limiter (Redis SETNX or n8n queue mode)
- More complex to implement correctly

**Verdict:** Only recommended when combined with a proper job scheduler (e.g., n8n queue mode with Bull/Redis). Not recommended for current architecture.

---

### Option C: Dedicated GPU Worker Service (Future)

Replace the n8n C2 worker with a dedicated Python FastAPI service that:
1. Consumes from `audit_job_queue` (Redis)
2. Runs Florence + Ollama calls directly (bypassing n8n HTTP overhead)
3. Writes results back to Postgres
4. Signals n8n for status updates via webhook

**Pros:**
- Full GPU control (batching, CUDA streams, model caching)
- Can batch multiple Florence calls per GPU pass
- Testable in isolation
- Enables future swap to proprietary models (Azure OpenAI, etc.)

**Cons:**
- Significant rebuild effort
- Duplicates logic currently in n8n workflows
- Two codebases to maintain

**Verdict:** Best long-term architecture once the POC is validated and volume justifies it.

---

## Decision Summary

| Feature | Recommendation | Effort | Prerequisite |
|---------|---------------|--------|-------------|
| Evidence chunking (semantic) | ✅ Implement in Workflow C2 | Medium (1-2 days) | None |
| Per-session Qdrant evidence collection | ✅ Implement | Medium | Evidence chunking |
| Model swap to `llama3.1:8b` | ✅ When GPU available | Low (config change) | GPU VM |
| Florence GPU (CUDA docker) | ✅ When GPU VM provisioned | Low (Dockerfile change) | GPU VM + NVIDIA toolkit |
| Ollama GPU | ✅ When GPU VM provisioned | Low (compose change) | GPU VM + NVIDIA toolkit |
| Multiple C2 workers (Option A) | ✅ Implement now | Low (n8n config) | None |
| Event-driven dispatch (Option B) | ⏳ Future | High | n8n queue mode |
| Dedicated GPU worker service (Option C) | ⏳ Future | Very high | Option A validated |

---

## Recommended Implementation Sequence

```
Phase 1 — No GPU required (implement now)
  1. Multiple C2 workers (3 concurrent) ........... 30 min
  2. Evidence chunking in Workflow C2 .............. 1 day
  3. Per-session evidence Qdrant collection ......... 0.5 day

Phase 2 — Requires GPU VM
  4. Provision Azure NC4as_T4_v3 or NC6s_v3
  5. Install NVIDIA Container Toolkit
  6. Update Florence Dockerfile → CUDA wheel ........ 1 hour
  7. Update docker-compose → GPU deploy keys ........ 30 min
  8. Pull llama3.1:8b, set as default model ......... 30 min
  9. Smoke test: full audit, measure latency ......... 1 hour

Phase 3 — Future
  10. Evaluate dedicated GPU worker service based on volume
```

---

## Azure VM SKU Recommendation for GPU

| SKU | GPU | VRAM | vCPU | RAM | Cost (est.) |
|-----|-----|------|------|-----|-------------|
| `NC4as_T4_v3` | 1× T4 | 16 GB | 4 | 28 GB | ~$0.50/hr |
| `NC6s_v3` | 1× V100 | 16 GB | 6 | 112 GB | ~$0.90/hr |
| `Standard_NC8as_T4_v3` | 1× T4 | 16 GB | 8 | 56 GB | ~$0.75/hr |

**Recommendation:** `NC4as_T4_v3` — affordable, T4 handles Florence-2 + 8B LLM comfortably, standard Azure availability.
