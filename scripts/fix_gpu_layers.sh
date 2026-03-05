#!/bin/bash

# Fix: Force all 41 layers to GPU

echo "========================================="
echo "Fix GPU Layers Configuration"
echo "========================================="
echo ""

echo "Problem: Only 1/41 layers on GPU (should be 41/41)"
echo ""

echo "Step 1: Create Modelfile with GPU settings"
echo "-----------------------------------"

cat > /tmp/mistral-nemo-gpu.Modelfile << 'EOF'
FROM mistral-nemo:12b-instruct-2407-q4_K_M

PARAMETER num_gpu 1
PARAMETER num_thread 4
EOF

echo "Created Modelfile with GPU parameters"
echo ""

echo "Step 2: Create custom model with GPU settings"
echo "-----------------------------------"

docker exec compliance-ollama ollama create mistral-nemo-gpu -f /tmp/mistral-nemo-gpu.Modelfile

echo ""
echo "Step 3: Test inference with new model"
echo "-----------------------------------"

# Start GPU monitoring
nvidia-smi dmon -s u -c 10 > /tmp/gpu_test_layers.txt &
MONITOR_PID=$!

sleep 2

START=$(date +%s)

curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo-gpu",
  "prompt": "Write a detailed paragraph about data governance.",
  "stream": false
}' > /tmp/test_result.json

END=$(date +%s)

wait $MONITOR_PID 2>/dev/null || true

DURATION=$((END - START))

echo ""
echo "Inference completed in ${DURATION} seconds"
echo ""

# Check GPU usage
MAX_GPU=$(cat /tmp/gpu_test_layers.txt | awk 'NR>1 && $3 ~ /^[0-9]+$/ {print $3}' | sort -n | tail -1)

echo "GPU utilization:"
cat /tmp/gpu_test_layers.txt
echo ""

# Check response
RESPONSE=$(cat /tmp/test_result.json | jq -r '.response' 2>/dev/null)
if [ -n "$RESPONSE" ] && [ "$RESPONSE" != "null" ]; then
    echo "✓ Inference successful"
    echo "Response length: ${#RESPONSE} characters"
else
    echo "✗ Inference failed"
fi

echo ""
echo "========================================="
echo "Results:"
echo "========================================="

if [ -z "$MAX_GPU" ] || [ "$MAX_GPU" -lt 10 ]; then
    echo "🔴 Still not using GPU (${MAX_GPU}%)"
    echo ""
    echo "Checking Ollama logs for layer allocation..."
    docker logs compliance-ollama 2>&1 | grep -i "offload\|layers" | tail -5
else
    echo "🎉 SUCCESS! GPU utilization: ${MAX_GPU}%"
    echo "Inference time: ${DURATION}s"
    
    if [ "$DURATION" -lt 15 ]; then
        echo ""
        echo "✓ Performance is now optimized!"
        echo "  - GPU layers: All on GPU"
        echo "  - Inference: ${DURATION}s (was 66s)"
        echo "  - Expected per-question: 20-30s (was 150s)"
    fi
fi

rm -f /tmp/gpu_test_layers.txt /tmp/test_result.json /tmp/mistral-nemo-gpu.Modelfile

echo ""
echo "If this worked, update your workflows to use 'mistral-nemo-gpu' instead of 'mistral-nemo:12b-instruct-2407-q4_K_M'"
