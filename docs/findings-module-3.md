# Module 3 Findings: Local File Processing & Infrastructure

## Overview
This document summarizes the technical evolution and final solution for Module 3 (File Processor & Vision) of the n8n compliance workflow. The initial goal was a single monolithic container, but due to conflicting system dependencies (Alpine vs. Python/Torch libraries), the architecture evolved into a **Sidecar Pattern**.

## Key Findings & Solutions

### 1. The Sidecar Architecture (Alpine + Debian)
*   **Issue**: Installing Florence-2 (transformers, torch, flash_attn) on the Alpine-based `n8n` container caused unsolvable libc/dependency hell and massive image bloat.
*   **Resolution**: Split the architecture into two services in `docker-compose.yml`:
    *   **n8n Service**: Keeps the lightweight Alpine base for orchestration, LibreOffice, and Tesseract.
    *   **Florence Service**: A dedicated Debian/Python 3.10 container exposing a Flask API for the Vision model.
    *   **Communication**: HTTP over the internal Docker network (`http://florence:5000/analyze`).

### 2. Shared Volume for Large Files
*   **Issue**: Passing base64 encoded images between n8n and the Python service via HTTP JSON payloads was inefficient and prone to memory overflows.
*   **Resolution**: Implemented a shared Docker volume (`shared_processing`) mounted at `/tmp/n8n_processing` on both containers.
    *   n8n writes images to disk.
    *   n8n sends the *filepath* to the Florence API.
    *   Florence reads from the disk, processes the image, and returns JSON.

### 3. Metadata Preservation & "Page Undefined"
*   **Issue**: Splitting the workflow into parallel branches (Vision vs. OCR) caused metadata like `pageNumber` to be lost when merging results back together, as the raw API output didn't contain the original n8n context.
*   **Resolution**: 
    1.  **Unique Prefixing**: Every run generates a random `filePrefix` (e.g., `9qwz5j_`) to namespace files on disk.
    2.  **Lookup Logic**: The merging code node now explicitly looks up the `pageNumber` and `originalFile` from the upstream "Prepare Generated File List" node, mapping by array index.

### 4. Safety & Cleanup
*   **Issue**: Using `rm -rf *` is dangerous, but leaving files fills up the disk.
*   **Resolution**: 
    *   Implemented a conditional cleanup command: `if [ -n "{{ $json.filePrefix }}" ]; ...`.
    *   Ensured the `filePrefix` variable is correctly passed to the final node.
    *   This ensures we only delete the specific files for the current run.

### 5. Memory Optimization (OOM Kills)
*   **Issue**: The Florence-2 model frequently crashed the container with Error 137 (OOM) during generation.
*   **Resolution**: 
    *   Reduced `num_beams` to 1 (deterministic decoding).
    *   Set `attn_implementation="eager"` to avoid memory-heavy attention kernels on CPU.
    *   Added standard `gc.collect()` calls in the Python endpoint.

## Final Technical Configuration
*   **Orchestrator**: n8n (Alpine)
*   **Vision Engine**: Microsoft Florence-2-base (Python 3.10 / Debian)
*   **Shared Storage**: `/tmp/n8n_processing` (chmod 777)
*   **OCR**: Tesseract 5 (Eng+Ara)

## Status
Module 3 is **Complete**. The pipeline successfully:
1.  Ingests PPTX/DOCX/PDF.
2.  Converts them to PDF and extracts page images.
3.  Runs OCR (Tesseract) and Vision (Florence-2) in parallel.
4.  Aggregates text and visual descriptions.
5.  Cleans up temporary artifacts safely.
