#!/bin/bash

# Force Ollama to use GPU for inference (not just model loading)

echo "========================================="
echo "Force Ollama GPU Inference"
echo "========================================="
echo ""

echo "Current issue: Model loads into VRAM but inference uses CPU"
echo ""

echo "Step 1: Unload all models from memory"
echo "-----------------------------------"
# This forces Ollama to reload models with new settings
docker restart compliance-ollama

echo "Waiting for Ollama to restart (30 seconds)..."
sleep 30

echo ""
echo "Step 2: Test inference with explicit GPU settings"
echo "-----------------------------------"

# Start GPU monitoring
nvidia-smi dmon -s u -c 10 > /tmp/gpu_inference_test.txt &
MONITOR_PID=$!

sleep 2

# Test with explicit num_gpu parameter
echo "Testing inference with num_gpu=1 parameter..."
START=$(date +%s.%N)

curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo:12b-instruct-2407-q4_K_M",
  "prompt": "Write a detailed paragraph about data governance and compliance requirements.",
  "stream": false,
  "options": {
    "num_gpu": 1,
    "num_thread": 4,
    "num_ctx": 2048
  }
}' > /tmp/inference_result.json

END=$(date +%s.%N)

wait $MONITOR_PID 2>/dev/null || true

DURATION=$(echo "$END - $START" | bc)

echo ""
echo "Inference completed in ${DURATION} seconds"
echo ""

# Check GPU usage
echo "GPU utilization during inference:"
cat /tmp/gpu_inference_test.txt
echo ""

MAX_GPU=$(cat /tmp/gpu_inference_test.txt | awk 'NR>1 && $3 ~ /^[0-9]+$/ {print $3}' | sort -n | tail -1)

# Check response
RESPONSE=$(cat /tmp/inference_result.json | jq -r '.response' 2>/dev/null)
if [ -n "$RESPONSE" ] && [ "$RESPONSE" != "null" ]; then
    echo "✓ Inference successful"
    echo "Response length: ${#RESPONSE} characters"
else
    echo "✗ Inference failed or returned null"
    cat /tmp/inference_result.json
fi

echo ""
echo "========================================="
echo "Analysis:"
echo "========================================="

if [ -z "$MAX_GPU" ]; then
    echo "🔴 Could not measure GPU utilization"
elif [ "$MAX_GPU" -lt 10 ]; then
    echo "🔴 PROBLEM PERSISTS: GPU utilization only ${MAX_GPU}%"
    echo ""
    echo "This means Ollama is using CPU despite having GPU access."
    echo ""
    echo "Possible causes:"
    echo "1. Ollama version doesn't support GPU inference properly"
    echo "2. CUDA libraries not properly linked"
    echo "3. Model format incompatible with GPU"
    echo ""
    echo "Let's check Ollama logs for CUDA errors:"
    echo ""
    docker logs compliance-ollama 2>&1 | grep -i "cuda\|gpu\|error" | tail -20
    echo ""
    echo "Next steps:"
    echo "1. Check if Ollama is using the right CUDA library"
    echo "2. May need to use a different Ollama image with GPU support"
else
    echo "🎉 SUCCESS! GPU utilization: ${MAX_GPU}%"
    echo ""
    if (( $(echo "$DURATION > 15" | bc -l) )); then
        echo "⚠ But inference is slower than expected (${DURATION}s)"
        echo "Expected: 5-10 seconds with full GPU usage"
    else
        echo "✓ Inference speed is excellent (${DURATION}s)"
        echo ""
        echo "Performance is now optimized!"
        echo "- GPU utilization: ${MAX_GPU}%"
        echo "- Inference time: ${DURATION}s"
        echo "- Expected per-question time: 20-30 seconds (was 150s)"
    fi
fi

rm -f /tmp/gpu_inference_test.txt /tmp/inference_result.json

echo ""
echo "========================================="
echo "Ollama Configuration Check"
echo "========================================="
echo ""

echo "Environment variables:"
docker exec compliance-ollama env | grep OLLAMA | sort
echo ""

echo "CUDA library paths:"
docker exec compliance-ollama ls -la /usr/lib/ollama/ 2>/dev/null || echo "Cannot access /usr/lib/ollama/"
echo ""

echo "Loaded models:"
curl -s http://localhost:11434/api/tags | jq -r '.models[] | "\(.name) - \(.size / 1024 / 1024 / 1024 | floor)GB"'
