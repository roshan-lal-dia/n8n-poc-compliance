# Module 3 Findings: Local File Processing & Infrastructure

## Overview
This document summarizes the technical challenges and solutions encountered while implementing Module 3 (File Processor) of the n8n compliance workflow. The goal was to establish a robust, local (Docker-based) pipeline for converting PPTX/DOCX documents to PDF and extracting images, avoiding reliance on external cloud APIs.

## Key Findings & Solutions

### 1. Docker Infrastructure & Permissions
*   **Issue**: Persistence errors and "permission denied" when writing to `/home/node/.n8n`.
*   **Root Cause**: The default Alpine user `node` did not have ownership of the volume mount points or the pre-created directories.
*   **Resolution**: 
    *   Updated `Dockerfile` to explicitly `chown node:node` the data directory.
    *   Ensured the service runs as the correct user context.

### 2. LibreOffice Dependencies
*   **Issue**: LibreOffice conversion failed silently or with "javaldx: Could not find a Java Runtime Environment".
*   **Root Cause**: Alpine's `libreoffice` package requires a valid JRE for certain format conversions (like PPTX), but it is not a hard dependency in the package manager.
*   **Resolution**: Added `openjdk11-jre` to the `Dockerfile` package list.

### 3. Webhook Data Corruption
*   **Issue**: Uploaded files (PPTX) were corrupt (0 bytes or partial headers) when processed by downstream nodes.
*   **Root Cause**: The Webhook node's "Binary Data" option was enabled, which attempted to parse the incoming `multipart/form-data` inconsistently.
*   **Resolution**: 
    *   Disabled "Binary Data" on the Webhook node.
    *   Relied on n8n's standard binary object handling for multipart inputs.

### 4. CLI Execution & Variable Resolution
*   **Issue**: `pdftoppm` and `libreoffice` commands failed with "No such file" because dynamic variables like `{{ $binary.data.fileName }}` occasionally resolved to empty strings or invalid paths during execution time.
*   **Root Cause**: Direct variable interpolation in `Execute Command` nodes can be flaky if the previous node's output structure changes slightly.
*   **Resolution**: 
    *   Implemented a **"Set Binary Filename"** code node.
    *   Forces normalized filenames (`input.pptx`, `input.pdf`) regardless of the uploaded filename.

### 5. Concurrency & File Overwriting
*   **Issue**: Hardcoding filenames to `input.pptx` would cause collisions if two workflows ran simultaneously.
*   **Root Cause**: Shared `/tmp` directory.
*   **Resolution**: 
    *   Added a unique `filePrefix` (random string) generator in the "Set Binary Filename" node.
    *   All temp files are now named with this prefix (e.g., `8k2s_input.pptx`), ensuring isolation.

## Technical Configuration
*   **Temp Directory**: `/tmp/n8n_processing`
*   **Environment Variables Needed**:
    *   `N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES=false`
    *   `N8N_RESTRICT_FILE_ACCESS_TO=/tmp/n8n_processing`

## Next Steps
Proceed to Module 4: Content Extraction, using the now-stable PDF outputs from this module.
