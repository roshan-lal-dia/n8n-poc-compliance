# Quick Fix: GPU Not Being Used

## Problem
Executions taking 2.5 minutes instead of 25-30 seconds.

## Root Cause
Ollama has GPU access but isn't using it for inference (GPU utilization = 0%).

## The Fix (3 steps)

### 1. Update Configuration
The `docker-compose.prod.yml` has been updated with:
```yaml
environment:
  - OLLAMA_GPU_LAYERS=999  # Forces GPU usage
  - OLLAMA_DEBUG=1         # Enables logging
```

### 2. Apply Changes
```bash
cd ~/n8n-poc-compliance
docker compose down
docker compose up -d
```

### 3. Verify
```bash
# Check GPU is being used
bash scripts/check_ollama_gpu.sh

# Monitor during execution
watch -n 1 nvidia-smi
```

## Expected Results
- GPU utilization: 70-90% (was 0%)
- Inference time: 5-10 seconds (was 60-120 seconds)
- Total time: 20-30 seconds (was 150 seconds)

## If Still Not Working
```bash
bash scripts/fix_ollama_gpu.sh
```

See `docs/GPU-PERFORMANCE-FIX.md` for detailed troubleshooting.
