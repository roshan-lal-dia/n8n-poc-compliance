---
inclusion: auto
---

# Product Overview

This is an AI-powered compliance audit system that evaluates organizational compliance against data management standards using document analysis and RAG (Retrieval-Augmented Generation).

## Core Functionality

The system accepts uploaded evidence documents (PDF, DOCX, PPTX, XLSX, images) and audit questions, then:

1. Extracts text and visual content from documents using OCR and vision AI
2. Searches a vector database of compliance standards for relevant requirements
3. Uses an LLM to evaluate compliance based on submitted evidence and retrieved standards
4. Generates detailed compliance scores, findings, gaps, and recommendations

## Architecture Pattern

Asynchronous job queue architecture with 6 workflows:

- **Workflow A**: Universal document extractor (PDF/Office/images → structured text)
- **Workflow B**: Knowledge base ingestion (compliance standards → Qdrant vector DB)
- **Workflow C1**: Audit job submission (202 Accepted, queues to Redis)
- **Workflow C2**: Background worker (processes queue, runs RAG + LLM evaluation)
- **Workflow C3**: Status polling (real-time progress tracking)
- **Workflow C4**: Results retrieval (completed audit reports)

## Key Features

- Multi-question audit sessions with per-question evaluation
- Evidence caching to avoid re-extracting identical files
- RAG-enhanced evaluation using domain-specific compliance standards
- Vision AI (Florence-2) for diagram and image analysis
- Async processing with progress tracking
- Comprehensive audit trail in PostgreSQL

## Target Users

Government entities and organizations undergoing compliance assessments for data management maturity (12 domains including Data Quality, Security, Governance, etc.)
