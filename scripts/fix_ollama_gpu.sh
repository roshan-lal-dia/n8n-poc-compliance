#!/bin/bash

# Fix Ollama GPU utilization issues
# This script ensures Ollama is properly configured to use GPU

set -e

echo "========================================="
echo "Ollama GPU Fix Script"
echo "========================================="
echo ""

echo "Step 1: Checking current Ollama configuration..."
echo "-----------------------------------"

# Check if Ollama container has GPU access
if docker exec compliance-ollama nvidia-smi &>/dev/null; then
    echo "✓ Ollama container can access GPU"
else
    echo "✗ Ollama container CANNOT access GPU"
    echo ""
    echo "This is the problem! Docker GPU passthrough is not working."
    echo ""
    echo "To fix:"
    echo "1. Ensure nvidia-container-toolkit is installed"
    echo "2. Restart Docker daemon: sudo systemctl restart docker"
    echo "3. Recreate containers: docker compose down && docker compose up -d"
    exit 1
fi

echo ""
echo "Step 2: Checking loaded models..."
echo "-----------------------------------"

MODELS=$(curl -s http://localhost:11434/api/tags | jq -r '.models[].name')
echo "Currently loaded models:"
echo "$MODELS"
echo ""

# Check if we have the right model
if echo "$MODELS" | grep -q "mistral-nemo.*12b.*q4"; then
    echo "✓ Correct model is loaded (quantized version)"
    MODEL_NAME=$(echo "$MODELS" | grep "mistral-nemo.*12b.*q4" | head -1)
elif echo "$MODELS" | grep -q "mistral-nemo"; then
    echo "⚠ Mistral Nemo is loaded but may not be the quantized version"
    MODEL_NAME=$(echo "$MODELS" | grep "mistral-nemo" | head -1)
else
    echo "✗ Mistral Nemo is NOT loaded"
    echo ""
    echo "Loading the correct model..."
    docker exec compliance-ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M
    MODEL_NAME="mistral-nemo:12b-instruct-2407-q4_K_M"
fi

echo ""
echo "Step 3: Checking Ollama GPU environment variables..."
echo "-----------------------------------"

docker exec compliance-ollama env | grep -E "CUDA|GPU|NVIDIA" || echo "No GPU environment variables set"

echo ""
echo "Step 4: Testing inference with GPU monitoring..."
echo "-----------------------------------"

# Start GPU monitoring
echo "Starting GPU monitor..."
nvidia-smi dmon -s u -c 10 > /tmp/gpu_test.txt &
MONITOR_PID=$!

# Wait a moment for monitor to start
sleep 2

# Run test inference
echo "Running test inference..."
START=$(date +%s.%N)

curl -s http://localhost:11434/api/generate -d "{
  \"model\": \"mistral-nemo\",
  \"prompt\": \"Write a detailed paragraph about data compliance and governance.\",
  \"stream\": false,
  \"options\": {
    \"num_gpu\": 1,
    \"num_thread\": 4
  }
}" > /tmp/test_response.json

END=$(date +%s.%N)
DURATION=$(echo "$END - $START" | bc)

# Wait for monitor to finish
wait $MONITOR_PID 2>/dev/null || true

echo ""
echo "Inference completed in ${DURATION} seconds"
echo ""

# Analyze GPU usage
echo "GPU utilization during inference:"
cat /tmp/gpu_test.txt
echo ""

MAX_GPU=$(cat /tmp/gpu_test.txt | awk 'NR>1 && $3 ~ /^[0-9]+$/ {print $3}' | sort -n | tail -1)

echo ""
echo "========================================="
echo "Results:"
echo "========================================="

if [ -z "$MAX_GPU" ]; then
    echo "🔴 CRITICAL: Could not measure GPU utilization"
    echo "GPU monitoring failed - check nvidia-smi"
elif [ "$MAX_GPU" -lt 10 ]; then
    echo "🔴 PROBLEM CONFIRMED: GPU utilization was ${MAX_GPU}% (too low)"
    echo ""
    echo "Ollama is NOT using GPU for inference!"
    echo ""
    echo "Root cause: Ollama is likely using CPU fallback"
    echo ""
    echo "Solutions:"
    echo ""
    echo "Option 1: Force GPU usage by setting environment variables"
    echo "  Add to docker-compose.prod.yml under ollama service:"
    echo "    environment:"
    echo "      - OLLAMA_NUM_GPU=1"
    echo "      - OLLAMA_GPU_LAYERS=999"
    echo ""
    echo "Option 2: Rebuild Ollama container with GPU runtime"
    echo "  docker compose down ollama"
    echo "  docker compose up -d ollama"
    echo ""
    echo "Option 3: Check if model is too large for GPU"
    echo "  Try: docker exec compliance-ollama ollama run mistral-nemo:12b-instruct-2407-q4_K_M"
else
    echo "✓ GPU IS BEING USED (peak: ${MAX_GPU}%)"
    
    # Check speed
    if (( $(echo "$DURATION > 20" | bc -l) )); then
        echo "🟡 But inference is slower than expected (${DURATION}s)"
        echo "Expected: 5-10 seconds"
        echo "Possible causes:"
        echo "  - Model not fully loaded into VRAM"
        echo "  - GPU memory fragmentation"
        echo "  - Try restarting Ollama: docker restart compliance-ollama"
    else
        echo "✓ Inference speed is good (${DURATION}s)"
        echo ""
        echo "🎉 Ollama GPU configuration is CORRECT!"
    fi
fi

echo ""
echo "Cleanup..."
rm -f /tmp/gpu_test.txt /tmp/test_response.json

echo ""
echo "========================================="
echo "Next Steps:"
echo "========================================="
echo ""
echo "If GPU is NOT being used:"
echo "1. Edit docker-compose.prod.yml"
echo "2. Add environment variables to ollama service:"
echo "   environment:"
echo "     - OLLAMA_NUM_GPU=1"
echo "     - OLLAMA_GPU_LAYERS=999"
echo "3. Restart: docker compose down && docker compose up -d"
echo ""
echo "If GPU IS being used but slow:"
echo "1. Check VRAM: nvidia-smi"
echo "2. Restart Ollama: docker restart compliance-ollama"
echo "3. Monitor during actual audit: watch -n 1 nvidia-smi"
