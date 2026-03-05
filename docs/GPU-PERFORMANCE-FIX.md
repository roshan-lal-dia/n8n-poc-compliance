# GPU Performance Issue - Root Cause Analysis & Fix

**Date:** March 5, 2026  
**Issue:** Single-question executions taking 2.5 minutes instead of expected 25-30 seconds  
**Status:** Root cause identified, fix provided

---

## Problem Summary

Executions are taking 150 seconds (2.5 minutes) per question instead of the expected 25-30 seconds with GPU acceleration.

**Observed Timing:**
- Evidence extraction: 30-45 seconds (expected: 1-5 seconds)
- LLM evaluation: ~2 minutes (expected: 5-10 seconds)
- Total: ~2.5 minutes (expected: 25-30 seconds)

---

## Root Cause Analysis

### What We Found

1. **GPU is detected and available** ✅
   - NVIDIA A10-24Q with 21.6 GiB available
   - Driver version: 550.144.06
   - CUDA version: 12.4

2. **Florence IS using GPU** ✅
   - Two Python processes using 3279MiB each (6.5GB total)
   - Models loaded into VRAM
   - Processing images correctly

3. **Ollama detects GPU but NOT using it for inference** ❌
   - GPU utilization: 0% during processing
   - Models loaded into VRAM but inference runs on CPU
   - This is the bottleneck!

### Evidence from Logs

**nvidia-smi output:**
```
GPU 0: NVIDIA A10-24Q
Memory: 656MiB / 24512MiB (models loaded)
GPU-Util: 0% (NOT PROCESSING!)

Processes:
- python3.10 (Florence): 3279MiB ✓
- python3.10 (Florence): 3279MiB ✓
```

**Ollama logs:**
```
level=INFO msg="inference compute" name=CUDA0 description="NVIDIA A10-24Q" 
total="23.9 GiB" available="21.6 GiB"
```
- Ollama SEES the GPU
- But GPU utilization stays at 0% during inference
- This means it's falling back to CPU

**Florence logs:**
```
INFO:app:Model loaded successfully.
INFO:app:Analyzed /tmp/n8n_processing/xxx_page-1.png: caption=233 chars, ocr=129 chars
```
- Florence is working correctly
- Using GPU for vision tasks

### Why Ollama Isn't Using GPU

**Problem:** Missing environment variables in docker-compose.prod.yml

The Ollama container has GPU access (can run nvidia-smi) but doesn't know it should use GPU for inference.

**Current configuration:**
```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=all
  - OLLAMA_NUM_GPU=1  # Present but not enough
```

**Missing:**
- `OLLAMA_GPU_LAYERS=999` - Forces all model layers to GPU
- `OLLAMA_DEBUG=1` - Enables debug logging to verify GPU usage
- Wrong model tag: `mistral-nemo:12b` instead of `mistral-nemo:12b-instruct-2407-q4_K_M`

---

## The Fix

### Step 1: Update docker-compose.prod.yml

**Change the Ollama service configuration:**

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: compliance-ollama
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
    - OLLAMA_NUM_GPU=1
    - OLLAMA_GPU_LAYERS=999          # NEW: Force all layers to GPU
    - OLLAMA_DEBUG=1                 # NEW: Enable debug logging
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  entrypoint: [ "/bin/sh", "-c", "/bin/ollama serve & sleep 5; /bin/ollama pull mistral-nemo:12b-instruct-2407-q4_K_M; /bin/ollama pull nomic-embed-text; wait" ]
  # ... rest of config
```

**Key changes:**
1. Added `OLLAMA_GPU_LAYERS=999` - ensures all model layers run on GPU
2. Added `OLLAMA_DEBUG=1` - enables logging to verify GPU usage
3. Fixed model tag to use quantized version: `mistral-nemo:12b-instruct-2407-q4_K_M`

### Step 2: Apply the Fix

**On your VM, run:**

```bash
# 1. Stop services
cd ~/n8n-poc-compliance
docker compose down

# 2. The docker-compose.prod.yml has been updated with the fix

# 3. Restart services
docker compose up -d

# 4. Wait for Ollama to load models (2-3 minutes)
docker logs -f compliance-ollama

# 5. Verify GPU is being used
bash scripts/check_ollama_gpu.sh
```

### Step 3: Verify the Fix

**Run diagnostic script:**
```bash
bash scripts/check_ollama_gpu.sh
```

**Expected output:**
- GPU utilization should spike to 70-90% during inference
- Inference time should be 5-10 seconds (not 30-60 seconds)
- Model should show as quantized (Q4_K_M)

**Monitor during actual audit:**
```bash
# In one terminal
watch -n 1 nvidia-smi

# In another terminal
# Submit an audit and watch GPU utilization
```

---

## Expected Performance After Fix

### Before Fix (CPU Inference)
- Evidence extraction: 30-45 seconds
- LLM evaluation: 60-120 seconds
- **Total: 150 seconds (2.5 minutes)**
- GPU utilization: 0%

### After Fix (GPU Inference)
- Evidence extraction: 1-5 seconds
- LLM evaluation: 5-10 seconds
- **Total: 10-20 seconds**
- GPU utilization: 70-90% during processing

### Performance Improvement
- **6-8× faster** overall
- **12× faster** LLM evaluation
- **6× faster** evidence extraction

---

## Verification Steps

### 1. Check GPU Access
```bash
docker exec compliance-ollama nvidia-smi
```
Should show GPU information (not "command not found")

### 2. Check Environment Variables
```bash
docker exec compliance-ollama env | grep OLLAMA
```
Should show:
```
OLLAMA_NUM_GPU=1
OLLAMA_GPU_LAYERS=999
OLLAMA_DEBUG=1
```

### 3. Check Loaded Models
```bash
curl http://localhost:11434/api/tags | jq '.models[].name'
```
Should show:
```
"mistral-nemo:12b-instruct-2407-q4_K_M"
"nomic-embed-text:latest"
```

### 4. Test Inference Speed
```bash
time curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo",
  "prompt": "Explain compliance in one sentence.",
  "stream": false
}'
```
Should complete in 5-10 seconds (not 30-60 seconds)

### 5. Monitor GPU During Audit
```bash
# Start monitoring
watch -n 1 nvidia-smi

# Submit audit in another terminal
# GPU utilization should spike to 70-90%
```

---

## Troubleshooting

### If GPU utilization is still 0%

**Check 1: Docker GPU runtime**
```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```
If this fails, Docker GPU passthrough is broken.

**Fix:**
```bash
# Reinstall nvidia-container-toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

**Check 2: Model loaded correctly**
```bash
docker exec compliance-ollama ollama list
```
Should show mistral-nemo with size ~7GB

**Fix:**
```bash
docker exec compliance-ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M
```

**Check 3: VRAM available**
```bash
nvidia-smi --query-gpu=memory.free --format=csv,noheader
```
Should show >10GB free

**Fix:**
```bash
# Restart services to clear VRAM
docker compose restart
```

### If inference is still slow (>20 seconds)

**Possible causes:**
1. Model not fully loaded into VRAM
2. Wrong model version (not quantized)
3. GPU memory fragmentation

**Solutions:**
```bash
# 1. Restart Ollama
docker restart compliance-ollama

# 2. Check model size
curl http://localhost:11434/api/tags | jq '.models[] | {name, size}'

# 3. Monitor VRAM during inference
watch -n 0.5 nvidia-smi
```

---

## Additional Optimizations

### 1. Increase Ollama Concurrency

If you want to process multiple questions in parallel:

```yaml
environment:
  - OLLAMA_NUM_PARALLEL=2  # Process 2 requests simultaneously
```

### 2. Adjust Context Window

For very large documents:

```yaml
environment:
  - OLLAMA_CONTEXT_LENGTH=32768  # Default, can increase to 65536
```

### 3. Enable Flash Attention (if available)

For even faster inference:

```yaml
environment:
  - OLLAMA_FLASH_ATTENTION=true
```

---

## Monitoring Commands

### Real-time GPU monitoring
```bash
watch -n 1 nvidia-smi
```

### Detailed GPU metrics
```bash
nvidia-smi dmon -s u -c 10
```

### Ollama logs
```bash
docker logs -f compliance-ollama | grep -E "GPU|CUDA|inference"
```

### Performance analysis
```bash
python3 scripts/analyze_execution_timing.py
```

---

## Summary

**Root Cause:** Ollama was not configured to use GPU for inference despite having GPU access.

**Fix:** Added `OLLAMA_GPU_LAYERS=999` environment variable to force GPU usage.

**Expected Result:** 6-8× performance improvement (150s → 20s per question).

**Verification:** Run `bash scripts/check_ollama_gpu.sh` to confirm GPU is being used.

---

## Files Modified

1. `docker-compose.prod.yml` - Added GPU environment variables to Ollama service
2. `scripts/check_ollama_gpu.sh` - New diagnostic script
3. `scripts/fix_ollama_gpu.sh` - New fix script
4. `docs/GPU-PERFORMANCE-FIX.md` - This document

---

## Next Steps

1. Apply the fix: `docker compose down && docker compose up -d`
2. Wait for models to load (2-3 minutes)
3. Run verification: `bash scripts/check_ollama_gpu.sh`
4. Test with actual audit
5. Monitor GPU utilization: `watch -n 1 nvidia-smi`

If GPU utilization is still 0% after these steps, run `bash scripts/fix_ollama_gpu.sh` for detailed diagnostics and additional solutions.
