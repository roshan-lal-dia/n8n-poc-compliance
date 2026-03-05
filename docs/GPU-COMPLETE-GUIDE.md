# GPU Setup & Optimization - Complete Guide

**VM:** Azure NV36ads A10 v5 (NVIDIA A10-24Q vGPU)  
**OS:** Ubuntu 22.04  
**Date:** March 5, 2026  
**Status:** ✅ Production-Ready

This is the complete guide for GPU setup, configuration, and optimization for the NPC Compliance AI System.

---

## Table of Contents

1. [Overview](#overview)
2. [Initial Setup](#initial-setup)
3. [Performance Optimization](#performance-optimization)
4. [Verification & Testing](#verification--testing)
5. [Troubleshooting](#troubleshooting)
6. [Performance Benchmarks](#performance-benchmarks)

---

## Overview

The system uses GPU acceleration for two AI services:
- **Florence-2** (Vision AI): Image analysis and OCR
- **Ollama** (LLM): Text generation and embeddings

**Hardware:**
- GPU: NVIDIA A10-24Q (24GB VRAM)
- Driver: 550.144.06 (CUDA 12.4)
- VRAM Usage: ~18.5GB during peak processing

---

## Initial Setup

### Step 1: Disable Secure Boot

**Why:** Azure VMs with Secure Boot cannot load unsigned kernel modules via SSH.

**Action:**
1. Azure Portal → VM → Settings → Configuration
2. Set "Secure Boot" to **Disabled**
3. Restart VM

**Verify:**
```bash
mokutil --sb-state
# Output: SecureBoot disabled
```

---

### Step 2: Install Azure GRID vGPU Driver

**Why:** Standard NVIDIA drivers don't recognize Azure vGPU partitions.

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential dkms pkg-config linux-headers-$(uname -r)

# Download and install Azure GRID driver
wget -O grid.run "https://go.microsoft.com/fwlink/?linkid=874272"
sudo chmod +x grid.run
sudo ./grid.run -s --dkms

# Verify
nvidia-smi
```

**Expected Output:**
```
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.144.06             Driver Version: 550.144.06     CUDA Version: 12.4     |
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
|   0  NVIDIA A10-24Q                 On  |   00000002:00:00.0 Off |                    0 |
+-----------------------------------------------------------------------------------------+
```

---

### Step 3: Install Docker & Docker Compose

```bash
# Install Docker
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/bin/docker-compose
sudo chmod +x /usr/bin/docker-compose

# Verify
docker --version
docker-compose --version
```

---

### Step 4: Install NVIDIA Container Toolkit

**Why:** Enables Docker containers to access GPU.

```bash
# Add repository
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Verify:**
```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

Should show GPU information.

---

### Step 5: Configure Docker Compose for GPU

**File:** `docker-compose.prod.yml`

#### Ollama Service

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: compliance-ollama
  restart: unless-stopped
  runtime: nvidia
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [ gpu ]
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    - OLLAMA_NUM_GPU=1
    - OLLAMA_GPU_LAYERS=999
    - OLLAMA_DEBUG=1
    - CUDA_VISIBLE_DEVICES=0
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  entrypoint: [ "/bin/sh", "-c", "/bin/ollama serve & sleep 5; /bin/ollama pull mistral-nemo:12b-instruct-2407-q4_K_M; /bin/ollama pull nomic-embed-text; wait" ]
```

#### Florence Service

```yaml
florence:
  build:
    context: ./florence-service
    dockerfile: Dockerfile
  container_name: compliance-florence
  restart: unless-stopped
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [ gpu ]
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
  ports:
    - "5000:5000"
  volumes:
    - shared_processing:/tmp/n8n_processing
    - hf_model_cache:/app/hf_cache
```

**Key Settings:**
- `runtime: nvidia` - Forces NVIDIA runtime
- `OLLAMA_GPU_LAYERS=999` - Loads all model layers to GPU
- `CUDA_VISIBLE_DEVICES=0` - Explicitly sets GPU device

---

## Performance Optimization

### Critical: Ollama API Configuration

**Problem:** Environment variables alone don't force GPU usage. Ollama may load models to VRAM but run inference on CPU.

**Solution:** Add `num_gpu` parameter to **every Ollama API call**.

#### Workflow C2: LLM Evaluation

**File:** `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json`  
**Node:** "Ollama: Evaluate Compliance"

```json
{
  "model": "mistral-nemo:12b-instruct-2407-q4_K_M",
  "prompt": "...",
  "format": "json",
  "stream": false,
  "options": {
    "temperature": 0.3,
    "num_ctx": 32768,
    "num_predict": 2000,
    "num_gpu": 999,
    "num_thread": 4
  }
}
```

#### Workflow C2: Embeddings

**Node:** "Ollama: Generate Embedding"

```json
{
  "model": "nomic-embed-text",
  "prompt": "...",
  "options": {
    "num_gpu": 999,
    "num_thread": 4
  }
}
```

#### Workflow B: KB Ingestion

**File:** `workflows/unifi-npc-compliance/workflow-b-kb-ingestion.json`  
**Node:** "Generate Embedding"

```json
{
  "model": "nomic-embed-text",
  "prompt": "...",
  "options": {
    "num_gpu": 999,
    "num_thread": 4
  }
}
```

**Why This Matters:**
- Without `num_gpu`: Only 1/41 layers on GPU → CPU inference (slow)
- With `num_gpu: 999`: All 41/41 layers on GPU → GPU inference (fast)

---

## Verification & Testing

### Test 1: GPU Driver

```bash
nvidia-smi
```

**Expected:** Shows NVIDIA A10-24Q with 0% utilization (idle).

---

### Test 2: Docker GPU Access

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

**Expected:** Shows GPU information.

---

### Test 3: Ollama Container GPU Access

```bash
docker exec compliance-ollama nvidia-smi
```

**Expected:** Shows GPU (not "Failed to initialize NVML").

---

### Test 4: Ollama GPU Inference

```bash
# In one terminal:
watch -n 1 nvidia-smi

# In another terminal:
time curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo:12b-instruct-2407-q4_K_M",
  "prompt": "Explain data compliance in one sentence.",
  "stream": false,
  "options": {
    "num_gpu": 999,
    "num_thread": 4
  }
}'
```

**Expected Results:**
- GPU-Util: 70-94%
- Time: 10-15 seconds
- Memory: ~18GB during inference

---

### Test 5: Florence GPU Processing

```bash
# In one terminal:
watch -n 0.5 nvidia-smi

# In another terminal (replace with actual PNG path):
time curl -s -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"filePath": "/tmp/n8n_processing/test_page.png"}'
```

**Expected Results:**
- GPU-Util: 30-50%
- Time: 0.5-2 seconds
- Response: JSON with description and OCR text

---

### Test 6: Layer Allocation Check

```bash
docker logs compliance-ollama 2>&1 | grep "offload"
```

**Expected:**
```
load_tensors: offloaded 41/41 layers to GPU
```

**Problem if shows:**
```
load_tensors: offloaded 1/41 layers to GPU
```
→ Missing `num_gpu` parameter in API calls

---

## Troubleshooting

### Issue 1: "No such device" error

**Symptom:** `nvidia-smi` returns "No such device"

**Cause:** Wrong driver (retail instead of GRID)

**Solution:**
```bash
sudo apt-get purge -y '*nvidia*'
sudo apt-autoremove -y
# Reinstall GRID driver (see Step 2)
```

---

### Issue 2: Docker container cannot access GPU

**Symptom:** `docker exec compliance-ollama nvidia-smi` fails

**Cause:** Container lost GPU access

**Solution:**
```bash
cd ~/n8n-poc-compliance
docker-compose -f docker-compose.prod.yml stop ollama
docker rm -f compliance-ollama
docker-compose -f docker-compose.prod.yml up -d ollama
sleep 30
docker exec compliance-ollama nvidia-smi
```

---

### Issue 3: GPU utilization stays at 0%

**Symptom:** GPU-Util is 0% during inference

**Cause:** Only 1/41 layers on GPU (missing `num_gpu` parameter)

**Diagnosis:**
```bash
docker logs compliance-ollama 2>&1 | grep "offload"
```

**Solution:**
1. Verify `num_gpu: 999` is in all Ollama API calls (see Performance Optimization section)
2. Re-import workflows into n8n
3. Test again

---

### Issue 4: Inference still slow (>30 seconds)

**Symptom:** Inference takes 30-60 seconds

**Cause:** Wrong model or CPU fallback

**Solution:**
```bash
# Check loaded models
curl http://localhost:11434/api/tags | jq '.models[].name'

# Should show: mistral-nemo:12b-instruct-2407-q4_K_M
# If not, pull correct version:
docker exec compliance-ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M
```

---

### Issue 5: Out of VRAM errors

**Symptom:** CUDA out of memory errors

**Current VRAM Usage:**
- Florence: ~6.5GB
- Ollama: ~12GB during inference
- Total: ~18.5GB (fits in 24GB)

**Solution (if needed):**
Reduce context window in Ollama calls:
```json
"options": {
  "num_ctx": 16384  // Reduce from 32768
}
```

---

## Performance Benchmarks

### Before GPU Optimization

| Metric | Value |
|--------|-------|
| GPU Utilization | 0% |
| Evidence Extraction | 30-45 seconds |
| LLM Evaluation | 60-120 seconds |
| **Total per Question** | **150 seconds** |
| Layer Allocation | 1/41 on GPU |

### After GPU Optimization

| Metric | Value |
|--------|-------|
| GPU Utilization | 70-94% |
| Evidence Extraction | 1-5 seconds |
| LLM Evaluation | 10-15 seconds |
| **Total per Question** | **20-30 seconds** |
| Layer Allocation | 41/41 on GPU |

### Performance Improvement

- **6-8× faster overall**
- **8-12× faster LLM evaluation**
- **6-9× faster evidence extraction**

---

## Quick Reference Commands

### Monitor GPU
```bash
watch -n 1 nvidia-smi
```

### Check Ollama Logs
```bash
docker logs -f compliance-ollama | grep -i "cuda\|gpu\|offload"
```

### Restart Ollama
```bash
cd ~/n8n-poc-compliance
docker-compose -f docker-compose.prod.yml restart ollama
```

### Test Ollama Inference
```bash
time curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo:12b-instruct-2407-q4_K_M",
  "prompt": "Test",
  "stream": false,
  "options": {"num_gpu": 999, "num_thread": 4}
}'
```

### Test Florence Analysis
```bash
time curl -s -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"filePath": "/tmp/n8n_processing/test.png"}'
```

### Check Layer Allocation
```bash
docker logs compliance-ollama 2>&1 | grep "offload" | tail -1
```

---

## Summary Checklist

✅ **Setup Complete:**
- [ ] Secure Boot disabled
- [ ] Azure GRID vGPU driver installed (550.144.06)
- [ ] Docker & Docker Compose installed
- [ ] NVIDIA Container Toolkit installed
- [ ] docker-compose.prod.yml configured with GPU settings
- [ ] Ollama API calls include `num_gpu: 999`

✅ **Verification Passed:**
- [ ] `nvidia-smi` shows GPU
- [ ] Docker GPU test passes
- [ ] Ollama container can access GPU
- [ ] GPU-Util reaches 70-94% during inference
- [ ] Inference time: 10-15 seconds
- [ ] Layer allocation: 41/41 on GPU
- [ ] Florence processing: 0.5-2 seconds per image

✅ **Performance Achieved:**
- [ ] Total per question: 20-30 seconds (was 150s)
- [ ] 6-8× overall improvement

---

**Document Version:** 1.0  
**Last Updated:** March 5, 2026  
**Status:** Production-Ready ✅
