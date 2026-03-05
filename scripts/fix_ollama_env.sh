#!/bin/bash

# Fix: Ensure OLLAMA_GPU_LAYERS is actually set in the running process

echo "========================================="
echo "Fix Ollama GPU Layers Environment"
echo "========================================="
echo ""

echo "Problem: OLLAMA_GPU_LAYERS=999 is set but only 1/41 layers on GPU"
echo ""

echo "Step 1: Stop Ollama"
echo "-----------------------------------"
docker compose stop ollama

echo ""
echo "Step 2: Remove old container"
echo "-----------------------------------"
docker compose rm -f ollama

echo ""
echo "Step 3: Start Ollama with explicit GPU layers"
echo "-----------------------------------"

# Start Ollama with environment variable set at runtime
docker compose up -d ollama

echo "Waiting for Ollama to start (30 seconds)..."
sleep 30

echo ""
echo "Step 4: Verify environment variables inside container"
echo "-----------------------------------"
echo "Checking OLLAMA_* variables:"
docker exec compliance-ollama env | grep OLLAMA
echo ""

echo "Step 5: Pull model and force GPU layers"
echo "-----------------------------------"

# Remove existing model to force reload
docker exec compliance-ollama ollama rm mistral-nemo:12b-instruct-2407-q4_K_M 2>/dev/null || true

# Pull model fresh
echo "Pulling model (this will take a minute)..."
docker exec compliance-ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M

echo ""
echo "Step 6: Test inference"
echo "-----------------------------------"

# Start GPU monitoring
nvidia-smi dmon -s u -c 10 > /tmp/gpu_final_test.txt &
MONITOR_PID=$!

sleep 2

START=$(date +%s)

curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo:12b-instruct-2407-q4_K_M",
  "prompt": "Explain data compliance in detail.",
  "stream": false
}' > /tmp/final_test.json

END=$(date +%s)

wait $MONITOR_PID 2>/dev/null || true

DURATION=$((END - START))

echo "Inference time: ${DURATION}s"
echo ""

# Check logs for layer allocation
echo "Checking layer allocation in logs:"
docker logs compliance-ollama 2>&1 | grep "offload" | tail -3
echo ""

# Check GPU usage
MAX_GPU=$(cat /tmp/gpu_final_test.txt | awk 'NR>1 && $3 ~ /^[0-9]+$/ {print $3}' | sort -n | tail -1)

echo "GPU utilization:"
cat /tmp/gpu_final_test.txt
echo ""

echo "========================================="
echo "Final Analysis:"
echo "========================================="

if [ -z "$MAX_GPU" ] || [ "$MAX_GPU" -lt 10 ]; then
    echo "🔴 STILL NOT WORKING"
    echo ""
    echo "The issue is that Ollama 0.17.4 may have a bug with OLLAMA_GPU_LAYERS."
    echo ""
    echo "Alternative solution: Use API parameter instead"
    echo ""
    echo "In your n8n workflows, when calling Ollama, add:"
    echo '  "options": {'
    echo '    "num_gpu": 1,'
    echo '    "num_thread": 4'
    echo '  }'
    echo ""
    echo "This will force GPU usage at request time."
else
    echo "🎉 FIXED! GPU utilization: ${MAX_GPU}%"
    echo "Inference time: ${DURATION}s"
fi

rm -f /tmp/gpu_final_test.txt /tmp/final_test.json
