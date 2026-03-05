# GPU Setup - Quick Start

**Status:** ✅ Fully Configured and Optimized

---

## Complete Documentation

📖 **See:** [docs/GPU-COMPLETE-GUIDE.md](docs/GPU-COMPLETE-GUIDE.md)

This single comprehensive guide covers everything:
- Initial setup (driver, Docker, NVIDIA toolkit)
- Performance optimization (Ollama configuration)
- Verification and testing
- Troubleshooting
- Performance benchmarks

---

## Quick Verification

### Check GPU is working:
```bash
nvidia-smi
```

### Test Ollama GPU inference:
```bash
time curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral-nemo:12b-instruct-2407-q4_K_M",
  "prompt": "Test",
  "stream": false,
  "options": {"num_gpu": 999, "num_thread": 4}
}'
```

**Expected:** 10-15 seconds, GPU-Util 70-94%

### Test Florence GPU processing:
```bash
time curl -s -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"filePath": "/tmp/n8n_processing/test.png"}'
```

**Expected:** 0.5-2 seconds, GPU-Util 30-50%

---

## Performance Achieved

- **Per question:** 20-30 seconds (was 150 seconds)
- **GPU utilization:** 70-94% during processing
- **Improvement:** 6-8× faster overall

---

## Files Modified

1. ✅ `docker-compose.prod.yml` - GPU runtime configuration
2. ✅ `workflows/unifi-npc-compliance/workflow-c2-audit-worker.json` - Added `num_gpu: 999`
3. ✅ `workflows/unifi-npc-compliance/workflow-b-kb-ingestion.json` - Added `num_gpu: 999`

---

## Need Help?

See the complete guide: [docs/GPU-COMPLETE-GUIDE.md](docs/GPU-COMPLETE-GUIDE.md)
