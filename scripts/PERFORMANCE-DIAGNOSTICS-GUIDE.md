# Performance Diagnostics Guide

## Problem Statement
Single-question executions are taking 2.5 minutes instead of the expected 25-30 seconds with GPU acceleration.

## Quick Diagnosis (Run These First)

### 1. Check GPU Utilization
```bash
./scripts/check_gpu_usage.sh
```

**What it checks:**
- GPU availability and driver version
- Current GPU utilization (should be >50% during processing)
- Memory usage
- Which processes are using GPU
- Service health (Ollama, Florence)

**Expected output:**
- GPU utilization should spike to 70-90% during processing
- Both Ollama and Florence should show in GPU process list
- Memory usage should be 10-15GB during active processing

### 2. Analyze Execution Timing
```bash
python3 scripts/analyze_execution_timing.py
```

**What it checks:**
- Step-by-step breakdown of most recent execution
- Which steps are taking longest
- Cache hit/miss rates
- Evidence file sizes
- Bottleneck identification

**Expected output:**
- Total duration should be <60 seconds for single question
- LLM evaluation: 5-10 seconds
- Evidence extraction: 1-5 seconds per file
- RAG search: <2 seconds

### 3. Compare Recent Sessions
```bash
python3 scripts/analyze_execution_timing.py --compare
```

Shows timing trends across last 5 sessions to identify if slowdown is consistent or intermittent.

## Common Root Causes & Solutions

### Cause 1: GPU Not Being Used (Most Likely)

**Symptoms:**
- GPU utilization stays at 0-5% during processing
- Execution times match CPU baseline (2-3 minutes)
- No processes shown in `nvidia-smi` output

**Diagnosis:**
```bash
# Check if services can see GPU
docker compose exec ollama nvidia-smi
docker compose exec florence-service nvidia-smi

# Check Florence device
docker compose logs florence-service | grep -i "device\|cuda\|cpu"

# Check Ollama model
curl http://localhost:11434/api/tags
```

**Solutions:**

1. **Florence not using GPU:**
   ```bash
   # Check Florence logs
   docker compose logs florence-service | tail -50
   
   # Look for: "Using device: cuda" (good) vs "Using device: cpu" (bad)
   
   # If using CPU, rebuild Florence service:
   docker compose down florence-service
   docker compose build --no-cache florence-service
   docker compose up -d florence-service
   ```

2. **Ollama not using GPU:**
   ```bash
   # Check if GPU runtime is enabled
   docker compose logs ollama | grep -i gpu
   
   # Verify model is loaded
   curl http://localhost:11434/api/tags | jq
   
   # Reload model with GPU
   docker compose restart ollama
   docker compose exec ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M
   ```

3. **Docker GPU runtime not configured:**
   ```bash
   # Check docker GPU support
   docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
   
   # If fails, install nvidia-container-toolkit
   # See: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
   ```

### Cause 2: Large Files / Too Much Context

**Symptoms:**
- GPU utilization is good (>50%)
- Extraction step takes >30 seconds
- LLM evaluation takes >60 seconds
- Large data_size in evidence analysis

**Diagnosis:**
```bash
# Check evidence file sizes
python3 scripts/analyze_execution_timing.py | grep -A 5 "EVIDENCE FILES"

# Check for large extracted_data
psql -U n8n -d compliance_db -c "
SELECT 
    file_name,
    LENGTH(extracted_data::text) / 1024 as size_kb,
    jsonb_array_length(extracted_data->'pages') as pages
FROM audit_evidence 
ORDER BY LENGTH(extracted_data::text) DESC 
LIMIT 10;
"
```

**Solutions:**

1. **Reduce image resolution for OCR:**
   Edit `Dockerfile` and change pdftoppm resolution:
   ```dockerfile
   # Change from -r 300 to -r 150
   pdftoppm -png -r 150 input.pdf output
   ```

2. **Implement chunking for large documents:**
   - Split large PDFs into smaller chunks before processing
   - Process each chunk separately
   - Combine results

3. **Limit context sent to LLM:**
   - Reduce RAG search results (top 3 instead of top 5)
   - Summarize evidence before sending to LLM
   - Use hierarchical RAG (planned enhancement)

### Cause 3: Network Latency Between Services

**Symptoms:**
- GPU utilization is sporadic (spikes then drops)
- Many small delays add up
- Services are responding but slow

**Diagnosis:**
```bash
# Test service response times
time curl -X POST http://localhost:5000/caption -H "Content-Type: application/json" -d '{"image_url": "test.png"}'
time curl http://localhost:11434/api/generate -d '{"model": "mistral-nemo", "prompt": "test"}'
time curl http://localhost:6333/collections
```

**Solutions:**

1. **Increase Docker network performance:**
   ```yaml
   # In docker-compose.prod.yml
   networks:
     default:
       driver: bridge
       driver_opts:
         com.docker.network.driver.mtu: 1500
   ```

2. **Use connection pooling:**
   - Configure n8n HTTP nodes with keep-alive
   - Increase timeout values if needed

### Cause 4: Database Query Performance

**Symptoms:**
- Cache lookup takes >5 seconds
- Evidence retrieval is slow
- Many database operations in logs

**Diagnosis:**
```bash
# Check for missing indexes
psql -U n8n -d compliance_db -c "
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public';
"

# Check slow queries
psql -U n8n -d compliance_db -c "
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
"
```

**Solutions:**

1. **Add missing indexes:**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_audit_logs_session_step 
   ON audit_logs(session_id, step_name);
   
   CREATE INDEX IF NOT EXISTS idx_audit_evidence_session_question 
   ON audit_evidence(session_id, question_id);
   ```

2. **Vacuum and analyze:**
   ```bash
   psql -U n8n -d compliance_db -c "VACUUM ANALYZE;"
   ```

### Cause 5: Redis Queue Bottleneck

**Symptoms:**
- Long delay between C1 submission and C2 processing
- Jobs pile up in queue
- Worker seems idle

**Diagnosis:**
```bash
# Check Redis queue
docker compose exec redis redis-cli LLEN audit_queue
docker compose exec redis redis-cli LRANGE audit_queue 0 -1

# Check worker activity
docker compose logs n8n | grep "Audit Worker" | tail -20
```

**Solutions:**

1. **Reduce worker poll interval:**
   - Change C2 cron from "every 10 seconds" to "every 5 seconds"

2. **Add multiple workers:**
   - Configure n8n execution concurrency
   - Run multiple C2 workflow instances

## Step-by-Step Troubleshooting Process

### Step 1: Verify GPU is Available
```bash
nvidia-smi
```
If this fails, GPU drivers are not installed or GPU is not available.

### Step 2: Check Service Health
```bash
./scripts/check_gpu_usage.sh
```
All services should be responding.

### Step 3: Run a Test Execution
```bash
# Submit a simple test audit
curl -X POST http://localhost:5678/webhook/audit/submit \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "questions": ["question-uuid"],
    "files": ["simple-test.pdf"]
  }'

# Get session_id from response
SESSION_ID="<from-response>"

# Monitor in real-time
watch -n 1 "curl -s http://localhost:5678/webhook/audit/status/$SESSION_ID | jq"
```

### Step 4: Analyze Results
```bash
python3 scripts/analyze_execution_timing.py $SESSION_ID
```

### Step 5: Monitor GPU During Execution
```bash
# In one terminal
watch -n 1 nvidia-smi

# In another terminal
# Submit audit and watch GPU utilization spike
```

## Expected Performance Benchmarks

### With GPU (Target)
- Evidence extraction: 1-5 seconds per file
- RAG search: 1-2 seconds
- LLM evaluation: 5-10 seconds
- **Total per question: 10-20 seconds**

### Without GPU (Baseline)
- Evidence extraction: 8-15 seconds per file
- RAG search: 2-3 seconds
- LLM evaluation: 30-60 seconds
- **Total per question: 45-90 seconds**

### Current (Problem State)
- **Total per question: 150 seconds (2.5 minutes)**

This indicates either:
1. GPU is not being used at all (most likely)
2. Severe bottleneck in one component
3. Network/IO issues between services

## Quick Fixes to Try First

### Fix 1: Restart All Services
```bash
docker compose down
docker compose up -d
sleep 30  # Wait for services to start
./scripts/check_gpu_usage.sh
```

### Fix 2: Verify GPU Passthrough
```bash
# Check docker-compose.prod.yml has:
# services:
#   ollama:
#     deploy:
#       resources:
#         reservations:
#           devices:
#             - driver: nvidia
#               count: all
#               capabilities: [gpu]
```

### Fix 3: Check Florence Device Selection
```bash
# In florence-service/app.py, verify:
# device = "cuda" if torch.cuda.is_available() else "cpu"
# print(f"Using device: {device}")

docker compose logs florence-service | grep "Using device"
```

### Fix 4: Verify Ollama Model
```bash
# Check loaded models
curl http://localhost:11434/api/tags | jq '.models[].name'

# Should show: mistral-nemo:12b-instruct-2407-q4_K_M
# If not, reload:
docker compose exec ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M
```

## Monitoring Commands

### Continuous GPU Monitoring
```bash
watch -n 1 nvidia-smi
```

### Continuous Queue Monitoring
```bash
watch -n 5 "./scripts/monitor_queue.sh --queue"
```

### Real-time Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f florence-service
docker compose logs -f ollama
docker compose logs -f n8n
```

## Getting Help

If none of the above solutions work, collect this diagnostic information:

```bash
# 1. GPU info
nvidia-smi > gpu_info.txt

# 2. Service status
docker compose ps > service_status.txt

# 3. Recent execution analysis
python3 scripts/analyze_execution_timing.py > execution_analysis.txt

# 4. Service logs
docker compose logs --tail=100 florence-service > florence_logs.txt
docker compose logs --tail=100 ollama > ollama_logs.txt
docker compose logs --tail=100 n8n > n8n_logs.txt

# 5. Docker GPU test
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi > docker_gpu_test.txt
```

Then share these files with the team for further investigation.
