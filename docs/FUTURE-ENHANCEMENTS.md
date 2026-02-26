# Future Enhancements - Compliance Audit System

**Last Updated:** 2026-02-26  
**Status:** Planning & Ideas

---

## 1. Cache Management & Optimization

### 1.1 TTL-Based Cache Invalidation
**Priority:** High  
**Effort:** Medium

Add automatic expiration for cached evaluations:

```sql
ALTER TABLE audit_evidence 
ADD COLUMN expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '90 days';

CREATE INDEX idx_evidence_expires ON audit_evidence (expires_at);
```

**Implementation:**
- Add cleanup job that runs daily
- Configurable TTL per domain or question type
- Soft delete with grace period before permanent removal

**Benefits:**
- Automatic cache freshness
- Prevents stale evaluations
- Reduces manual maintenance

---

### 1.2 Smart Cache Invalidation
**Priority:** Medium  
**Effort:** High

Detect when standards are updated and flag stale cache entries:

```sql
ALTER TABLE audit_evidence 
ADD COLUMN standards_version VARCHAR(50),
ADD COLUMN is_stale BOOLEAN DEFAULT FALSE;

ALTER TABLE kb_standards
ADD COLUMN version VARCHAR(50),
ADD COLUMN updated_at TIMESTAMP;
```

**Implementation:**
- Track version of standards used in each evaluation
- When standards are updated, mark related cache entries as stale
- Option to force re-evaluation or show warning

**Benefits:**
- Ensures evaluations reflect current standards
- Maintains audit trail of which standards were used
- Allows gradual migration to new standards

---

### 1.3 Partial Cache (File-Level)
**Priority:** Low  
**Effort:** Medium

Cache individual file extractions even if full evaluation isn't cached:

**Current:** Cache entire question evaluation (all files together)  
**Enhanced:** Cache each file extraction separately

**Benefits:**
- Faster when some files are reused across questions
- Reduces redundant extraction work
- More granular cache hit tracking

---

## 2. Performance Optimizations

### 2.1 GPU Acceleration for Florence-2
**Priority:** High  
**Effort:** Medium

**Current:** Florence-2 runs on CPU (slow for large images)  
**Enhanced:** Use GPU for vision model inference

**Requirements:**
- Azure VM with GPU (NC-series or NV-series)
- CUDA-enabled PyTorch
- Update Florence Dockerfile

**Expected Impact:**
- 5-10x faster image analysis
- Better handling of large diagrams
- Enables higher resolution processing

**Implementation Steps:**
1. Provision GPU VM (see `docs/AZURE-GPU-PROVISIONING-REQUEST.md`)
2. Update `florence-service/Dockerfile` with CUDA base image
3. Install CUDA-enabled PyTorch
4. Test with large image files
5. Monitor GPU utilization

---

### 2.2 Parallel Question Processing
**Priority:** Medium  
**Effort:** High

**Current:** Questions processed sequentially (one at a time)  
**Enhanced:** Process multiple questions in parallel

**Approaches:**

**Option A: Multi-Worker C2**
- Run multiple instances of Workflow C2
- Each worker pops from same Redis queue
- Requires concurrency control for shared resources

**Option B: Event-Driven Dispatch**
- C1 publishes each question as separate job
- Multiple C2 workers subscribe to job queue
- Better scalability

**Option C: Dedicated GPU Service**
- Separate service for LLM + Florence
- C2 workers call service via HTTP
- Easier to scale GPU resources

**Benefits:**
- 5-question audit completes in ~15s instead of 60s
- Better resource utilization
- Scales horizontally

---

### 2.3 Semantic Evidence Chunking
**Priority:** Low  
**Effort:** High

**Current:** Evidence truncated at character limits (50k per file, 200k total)  
**Enhanced:** Intelligent chunking based on semantic boundaries

**Implementation:**
- Use sentence/paragraph boundaries for chunking
- Create per-session Qdrant collection for evidence
- Retrieve most relevant chunks for each question
- Preserve context across chunks

**Benefits:**
- Better handling of large documents
- More accurate evaluations
- Preserves semantic meaning

---

## 3. Model & AI Improvements

### 3.1 Model Upgrade (llama3.1:8b or llama3.2:3b)
**Priority:** Medium  
**Effort:** Low

**Current:** llama3.2 (1B parameters)  
**Options:**
- llama3.1:8b - Better reasoning, slower
- llama3.2:3b - Balanced performance

**Testing Required:**
- Evaluation quality comparison
- Inference time benchmarks
- Memory usage analysis

---

### 3.2 Prompt Engineering Improvements
**Priority:** High  
**Effort:** Low

Enhance AI prompts for better evaluations:

**Areas to improve:**
1. **Evidence citation** - Force specific file references
2. **Gap analysis** - More structured gap identification
3. **Recommendation quality** - Actionable, prioritized suggestions
4. **Confidence scoring** - Better calibration

**Implementation:**
- A/B test prompt variations
- Collect feedback from reviewers
- Iterate based on evaluation quality metrics

---

### 3.3 Multi-Model Ensemble
**Priority:** Low  
**Effort:** High

Use multiple models for cross-validation:

**Approach:**
- Run evaluation with 2-3 different models
- Compare results and flag discrepancies
- Use consensus scoring or weighted average

**Benefits:**
- Higher confidence in evaluations
- Catches model-specific biases
- Better handling of edge cases

---

## 4. Observability & Monitoring

### 4.1 Prometheus Metrics
**Priority:** Medium  
**Effort:** Medium

Export metrics for monitoring:

**Metrics to track:**
- Cache hit rate (per question, per domain)
- Evaluation time (p50, p95, p99)
- Queue depth and processing rate
- Error rates by step
- Model inference time
- Evidence extraction time

**Implementation:**
- Add Prometheus exporter to n8n
- Create Grafana dashboards
- Set up alerts for anomalies

---

### 4.2 Evaluation Quality Metrics
**Priority:** High  
**Effort:** Medium

Track evaluation quality over time:

**Metrics:**
- Human review agreement rate
- Score distribution by domain
- Confidence vs accuracy correlation
- Cache hit impact on quality

**Implementation:**
```sql
CREATE TABLE evaluation_feedback (
  id SERIAL PRIMARY KEY,
  session_id UUID,
  question_id UUID,
  ai_score DECIMAL(5,2),
  human_score DECIMAL(5,2),
  reviewer_id VARCHAR(100),
  feedback_notes TEXT,
  created_at TIMESTAMP
);
```

---

### 4.3 Audit Trail Enhancements
**Priority:** Medium  
**Effort:** Low

Improve transparency and debugging:

**Enhancements:**
- Log RAG sources used in each evaluation
- Track which standards influenced the score
- Record prompt variations and their impact
- Store intermediate processing steps

**Benefits:**
- Better debugging of evaluation issues
- Compliance with audit requirements
- Enables prompt optimization

---

## 5. API & Integration Improvements

### 5.1 Webhook Authentication
**Priority:** High  
**Effort:** Low

Add proper authentication to webhook endpoints:

**Options:**
- API key header (X-API-Key) - Simplest
- JWT tokens - More secure
- OAuth 2.0 - Enterprise-grade

**Implementation:** See `docs/PLAN-WEBHOOK-AUTH.md`

---

### 5.2 Batch Submission API
**Priority:** Medium  
**Effort:** Medium

Allow submitting multiple audits in one request:

```json
POST /webhook/audit/batch
{
  "audits": [
    {
      "domain": "uuid",
      "questions": [...],
      "files": {...}
    },
    {
      "domain": "uuid",
      "questions": [...],
      "files": {...}
    }
  ]
}
```

**Benefits:**
- Reduces API calls
- Better for bulk operations
- Easier integration for frontend

---

### 5.3 Real-Time Progress WebSocket
**Priority:** Low  
**Effort:** High

Replace polling with WebSocket for real-time updates:

**Current:** Frontend polls `/webhook/audit/status/:sessionId` every 2 seconds  
**Enhanced:** WebSocket connection with live progress updates

**Benefits:**
- Reduced server load
- Instant updates
- Better user experience

---

## 6. Data Management

### 6.1 Evidence Archival
**Priority:** Medium  
**Effort:** Medium

Move old evidence to cold storage:

**Implementation:**
- After 90 days, move evidence to Azure Blob Storage
- Keep metadata in database with blob reference
- Lazy load from blob when needed

**Benefits:**
- Reduces database size
- Lower storage costs
- Maintains historical data

---

### 6.2 Question Versioning
**Priority:** Low  
**Effort:** Medium

Track changes to questions over time:

```sql
CREATE TABLE audit_questions_history (
  id SERIAL PRIMARY KEY,
  question_id UUID,
  version INTEGER,
  question_text TEXT,
  prompt_instructions TEXT,
  changed_by VARCHAR(100),
  changed_at TIMESTAMP,
  change_reason TEXT
);
```

**Benefits:**
- Audit trail of question changes
- Ability to compare evaluations across versions
- Rollback capability

---

## 7. User Experience

### 7.1 Evaluation Explanation
**Priority:** High  
**Effort:** Medium

Provide detailed explanation of how score was calculated:

**Enhancements:**
- Show which evidence supported the score
- Highlight gaps found in evidence
- Explain which standards were applied
- Provide confidence breakdown

**Implementation:**
- Enhance LLM prompt to include reasoning
- Structure response with explanation sections
- Add UI to display explanations

---

### 7.2 Interactive Evidence Review
**Priority:** Low  
**Effort:** High

Allow reviewers to see extracted evidence:

**Features:**
- View extracted text with highlighting
- See which parts matched which standards
- Annotate evidence for future reference
- Override AI evaluation with justification

---

## 8. Compliance & Security

### 8.1 PII Detection & Redaction
**Priority:** High  
**Effort:** Medium

Automatically detect and redact sensitive information:

**Implementation:**
- Scan extracted text for PII patterns
- Redact before storing in database
- Log redactions for audit trail
- Option to disable for trusted sources

---

### 8.2 Role-Based Access Control
**Priority:** Medium  
**Effort:** High

Implement RBAC for different user types:

**Roles:**
- Auditor - Submit audits, view results
- Reviewer - Review and approve evaluations
- Admin - Manage questions, standards, users
- Read-Only - View completed audits

---

## 9. Testing & Quality

### 9.1 Automated Testing Suite
**Priority:** High  
**Effort:** Medium

Add comprehensive test coverage:

**Test Types:**
- Unit tests for code nodes
- Integration tests for workflows
- End-to-end API tests
- Performance regression tests
- Cache behavior tests

---

### 9.2 Evaluation Benchmarks
**Priority:** Medium  
**Effort:** Medium

Create benchmark dataset for evaluation quality:

**Implementation:**
- Curate set of test questions + evidence
- Human-reviewed "gold standard" evaluations
- Run automated evaluations and compare
- Track quality metrics over time

---

## Implementation Priority Matrix

| Enhancement | Priority | Effort | Impact | Timeline |
|-------------|----------|--------|--------|----------|
| Webhook Authentication | High | Low | High | Week 1 |
| Prompt Engineering | High | Low | High | Week 1-2 |
| TTL-Based Cache | High | Medium | Medium | Week 2-3 |
| GPU Acceleration | High | Medium | High | Week 3-4 |
| Prometheus Metrics | Medium | Medium | Medium | Week 4-5 |
| Evaluation Quality Metrics | High | Medium | High | Week 5-6 |
| PII Detection | High | Medium | High | Week 6-7 |
| Parallel Processing | Medium | High | High | Month 2 |
| Smart Cache Invalidation | Medium | High | Medium | Month 2 |
| Automated Testing | High | Medium | High | Month 2-3 |

---

## Notes

- Priorities may change based on user feedback and business needs
- Effort estimates are rough and may vary
- Some enhancements depend on infrastructure changes (GPU VM, etc.)
- Security and compliance enhancements should be prioritized

---

**Status:** Planning  
**Next Review:** 2026-03-26
