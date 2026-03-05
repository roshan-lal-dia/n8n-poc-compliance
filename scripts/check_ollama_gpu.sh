#!/bin/bash

# Check if Ollama is actually using GPU for inference
# Run this on the VM

echo "========================================="
echo "Ollama GPU Configuration Check"
echo "========================================="
echo ""

echo "1. Checking loaded models:"
echo "-----------------------------------"
curl -s http://localhost:11434/api/tags | jq -r '.models[] | "\(.name) - Size: \(.size / 1024 / 1024 / 1024 | floor)GB"'
echo ""

echo "2. Checking Ollama environment:"
echo "-----------------------------------"
docker exec compliance-ollama env | grep -E "CUDA|GPU|NVIDIA"
echo ""

echo "3. Testing GPU access from inside Ollama container:"
echo "-----------------------------------"
docker exec compliance-ollama nvidia-smi --query-gpu=name,memory.used --format=csv
echo ""

echo "4. Checking if model is quantized (should be Q4_K_M):"
echo "-----------------------------------"
MODEL_NAME=$(curl -s http://localhost:11434/api/tags | jq -r '.models[0].name')
echo "Current model: $MODEL_NAME"

if [[ "$MODEL_NAME" == *"q4"* ]] || [[ "$MODEL_NAME" == *"Q4"* ]]; then
    echo "✓ Model is quantized (good for GPU)"
else
    echo "⚠ Model may not be quantized - check if it's the right version"
fi
echo ""

echo "5. Testing actual inference with GPU monitoring:"
echo "-----------------------------------"
echo "Starting inference test..."

# Start GPU monitoring in background
nvidia-smi dmon -s u -c 5 > /tmp/gpu_during_inference.txt &
MONITOR_PID=$!

# Run a test inference
START_TIME=$(date +%s)
curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo",
  "prompt": "Explain what compliance means in one sentence.",
  "stream": false
}' > /tmp/ollama_test_response.json
END_TIME=$(date +%s)

# Wait for monitoring to finish
wait $MONITOR_PID

DURATION=$((END_TIME - START_TIME))
echo "Inference completed in ${DURATION} seconds"
echo ""

echo "GPU utilization during inference:"
cat /tmp/gpu_during_inference.txt
echo ""

# Check response
RESPONSE=$(cat /tmp/ollama_test_response.json | jq -r '.response')
if [ -n "$RESPONSE" ]; then
    echo "✓ Inference successful"
    echo "Response: ${RESPONSE:0:100}..."
else
    echo "✗ Inference failed"
    cat /tmp/ollama_test_response.json
fi
echo ""

echo "========================================="
echo "Analysis:"
echo "========================================="

# Check if GPU was used
MAX_GPU=$(cat /tmp/gpu_during_inference.txt | awk 'NR>1 {print $3}' | sort -n | tail -1)
if [ -z "$MAX_GPU" ] || [ "$MAX_GPU" -lt 10 ]; then
    echo "🔴 PROBLEM: GPU utilization was very low (<10%)"
    echo ""
    echo "Possible causes:"
    echo "1. Model is running on CPU instead of GPU"
    echo "2. Model is not properly loaded"
    echo "3. GPU passthrough not working"
    echo ""
    echo "Solutions to try:"
    echo "1. Check docker-compose.prod.yml has GPU configuration"
    echo "2. Restart Ollama: docker restart compliance-ollama"
    echo "3. Reload model: docker exec compliance-ollama ollama pull mistral-nemo:12b-instruct-2407-q4_K_M"
else
    echo "✓ GPU is being used (peak: ${MAX_GPU}%)"
fi

# Check inference speed
if [ "$DURATION" -gt 30 ]; then
    echo "🔴 PROBLEM: Inference is slow (${DURATION}s for simple prompt)"
    echo "Expected: 5-10 seconds with GPU"
    echo "This suggests CPU inference"
elif [ "$DURATION" -gt 15 ]; then
    echo "🟡 WARNING: Inference is slower than expected (${DURATION}s)"
    echo "Expected: 5-10 seconds with GPU"
else
    echo "✓ Inference speed is good (${DURATION}s)"
fi

echo ""
echo "Cleanup:"
rm -f /tmp/gpu_during_inference.txt /tmp/ollama_test_response.json
