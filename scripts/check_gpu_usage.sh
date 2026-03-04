#!/bin/bash

# Quick GPU utilization checker
# Usage: ./scripts/check_gpu_usage.sh

echo "========================================="
echo "GPU Utilization Check"
echo "========================================="
echo ""

# Check if nvidia-smi exists
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found"
    echo "GPU drivers may not be installed or GPU is not available"
    exit 1
fi

echo "1. GPU Information:"
echo "-------------------"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
echo ""

echo "2. Current GPU Usage:"
echo "---------------------"
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.free --format=csv
echo ""

echo "3. Processes Using GPU:"
echo "-----------------------"
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
echo ""

echo "4. Checking Service GPU Access:"
echo "--------------------------------"

# Check Ollama
echo -n "Ollama (Mistral Nemo): "
if curl -s http://localhost:11434/api/tags | grep -q "mistral-nemo"; then
    echo "✓ Model loaded"
else
    echo "✗ Model not loaded or service not responding"
fi

# Check Florence
echo -n "Florence service: "
if curl -s http://localhost:5000/health | grep -q "healthy\|ok"; then
    echo "✓ Service responding"
else
    echo "✗ Service not responding"
fi

echo ""
echo "5. Real-time GPU Monitoring (10 seconds):"
echo "------------------------------------------"
echo "Watching GPU utilization for 10 seconds..."
for i in {1..10}; do
    GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)
    MEM_UTIL=$(nvidia-smi --query-gpu=utilization.memory --format=csv,noheader,nounits)
    echo "[$i/10] GPU: ${GPU_UTIL}% | Memory: ${MEM_UTIL}%"
    sleep 1
done

echo ""
echo "========================================="
echo "Recommendations:"
echo "========================================="

GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)
if [ "$GPU_UTIL" -lt 10 ]; then
    echo "⚠ GPU utilization is very low (<10%)"
    echo "  Possible causes:"
    echo "  - Services are using CPU instead of GPU"
    echo "  - No active processing happening"
    echo "  - GPU passthrough not configured correctly"
    echo ""
    echo "  Check:"
    echo "  - Florence logs: docker compose logs florence-service | tail -50"
    echo "  - Ollama logs: docker compose logs ollama | tail -50"
fi

echo ""
echo "To monitor continuously: watch -n 1 nvidia-smi"
