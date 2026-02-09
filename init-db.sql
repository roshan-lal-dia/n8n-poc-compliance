-- ============================================
-- Compliance Audit System - Database Schema
-- Version: 1.0
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. QUESTIONS REGISTRY
-- Stores all audit questions per domain
-- ============================================
CREATE TABLE IF NOT EXISTS audit_questions (
    id SERIAL PRIMARY KEY,
    q_id VARCHAR(100) UNIQUE NOT NULL,           -- e.g., "data_arch_q1", "privacy_q2"
    domain VARCHAR(100) NOT NULL,                -- e.g., "Data Architecture", "Privacy"
    question_text TEXT NOT NULL,                 -- The actual question
    prompt_instructions TEXT,                    -- Domain-specific AI instructions
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX idx_questions_domain ON audit_questions(domain);
CREATE INDEX idx_questions_qid ON audit_questions(q_id);

-- ============================================
-- 2. EVIDENCE STORAGE
-- Stores extracted content from user uploads
-- ============================================
CREATE TABLE IF NOT EXISTS audit_evidence (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,                    -- Links to specific audit run
    q_id VARCHAR(100) NOT NULL,                  -- References audit_questions.q_id
    domain VARCHAR(100) NOT NULL,
    
    -- File Metadata
    filename VARCHAR(500),
    file_hash VARCHAR(64) UNIQUE,                -- SHA-256 for deduplication
    file_type VARCHAR(50),                       -- pdf, docx, xlsx, etc.
    
    -- Extracted Content (JSONB for flexibility)
    -- Structure: { "full_text": "...", "pages": [...], "images": [...] }
    extracted_data JSONB NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast retrieval
CREATE INDEX idx_evidence_session ON audit_evidence(session_id);
CREATE INDEX idx_evidence_qid ON audit_evidence(q_id);
CREATE INDEX idx_evidence_domain ON audit_evidence(domain);
CREATE INDEX idx_evidence_hash ON audit_evidence(file_hash);

-- Full-text search index on extracted text
CREATE INDEX idx_evidence_text ON audit_evidence USING GIN ((extracted_data->>'full_text') gin_trgm_ops);

-- ============================================
-- 3. KNOWLEDGE BASE METADATA
-- Tracks which standards are embedded in Qdrant
-- ============================================
CREATE TABLE IF NOT EXISTS kb_standards (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(100) NOT NULL,
    standard_name VARCHAR(255) NOT NULL,         -- e.g., "ISO 27001", "GDPR"
    filename VARCHAR(500),
    file_hash VARCHAR(64) UNIQUE,
    total_chunks INTEGER DEFAULT 0,              -- Number of embedded chunks
    
    -- Metadata for Qdrant collection mapping
    qdrant_collection VARCHAR(100) DEFAULT 'compliance_standards',
    
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_kb_domain ON kb_standards(domain);
CREATE INDEX idx_kb_hash ON kb_standards(file_hash);

-- ============================================
-- 4. AUDIT EXECUTION LOGS
-- Tracks progress and results of each audit
-- ============================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    q_id VARCHAR(100),
    
    -- Execution tracking
    step_name VARCHAR(200),                      -- e.g., "extraction_complete", "ai_analysis_done"
    status VARCHAR(50),                          -- "pending", "in_progress", "completed", "failed"
    
    -- AI Response (if applicable)
    ai_response JSONB,                           -- Full AI evaluation result
    
    -- Metadata
    message TEXT,
    percentage INTEGER,                          -- Progress (0-100)
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for real-time progress tracking
CREATE INDEX idx_logs_session ON audit_logs(session_id);
CREATE INDEX idx_logs_status ON audit_logs(status);
CREATE INDEX idx_logs_timestamp ON audit_logs(created_at DESC);

-- ============================================
-- 5. FILE REGISTRY (Deduplication)
-- Prevents re-processing the same file
-- ============================================
CREATE TABLE IF NOT EXISTS file_registry (
    file_hash VARCHAR(64) PRIMARY KEY,
    original_filename VARCHAR(500),
    file_type VARCHAR(50),
    file_size BIGINT,
    first_processed_at TIMESTAMP DEFAULT NOW(),
    last_accessed_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 6. AUDIT SESSIONS
-- Master table tracking each audit run
-- ============================================
CREATE TABLE IF NOT EXISTS audit_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(100) NOT NULL,
    initiated_by VARCHAR(255),                   -- User/API identifier
    status VARCHAR(50) DEFAULT 'pending',        -- "pending", "in_progress", "completed", "failed"
    
    -- Timing
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Results Summary
    total_questions INTEGER DEFAULT 0,
    answered_questions INTEGER DEFAULT 0,
    overall_compliance_score DECIMAL(5,2),       -- Percentage (0-100)
    
    -- Metadata
    metadata JSONB                               -- Flexible field for additional data
);

CREATE INDEX idx_sessions_status ON audit_sessions(status);
CREATE INDEX idx_sessions_domain ON audit_sessions(domain);
CREATE INDEX idx_sessions_started ON audit_sessions(started_at DESC);

-- ============================================
-- SEED DATA: Sample Questions
-- ============================================
INSERT INTO audit_questions (q_id, domain, question_text, prompt_instructions) VALUES
-- Data Architecture Domain
('data_arch_q1', 'Data Architecture', 
 'Does the document describe a clear data architecture with source systems, data warehouse, and transformation layers?',
 'Look for: data sources, ETL/ELT processes, data warehouse/lake architecture, data flow diagrams. Check if the architecture shows proper separation of concerns and scalability.'),

('data_arch_q2', 'Data Architecture',
 'Are data models and schemas clearly documented?',
 'Verify: entity-relationship diagrams, table schemas, data dictionaries, normalization levels. Ensure documentation is comprehensive and up-to-date.'),

-- Data Engineering Domain  
('data_eng_q1', 'Data Engineering',
 'Does the document describe robust ETL/ELT pipelines with error handling and monitoring?',
 'Check for: pipeline orchestration tools, error handling mechanisms, data quality checks, monitoring dashboards, logging strategies.'),

('data_eng_q2', 'Data Engineering',
 'Is there evidence of data validation and quality controls?',
 'Look for: data validation rules, quality metrics, anomaly detection, data profiling, reconciliation processes.'),

-- Privacy & Security Domain
('privacy_q1', 'Privacy',
 'Does the system implement proper data encryption at rest and in transit?',
 'Verify: encryption standards (AES-256, TLS 1.3), key management, encryption scope (database, files, backups, network).'),

('privacy_q2', 'Privacy',
 'Are there documented access controls and PII handling procedures?',
 'Check for: RBAC implementation, PII identification, data masking, anonymization techniques, access logs, least privilege principle.'),

-- Data Governance Domain
('governance_q1', 'Data Governance',
 'Is there a documented data governance framework and ownership model?',
 'Look for: data stewardship roles, data ownership assignment, governance policies, decision rights, escalation procedures.'),

('governance_q2', 'Data Governance',
 'Does the organization maintain a data catalog and lineage tracking?',
 'Verify: data catalog tools, metadata management, lineage visualization, data classification, business glossary.')

ON CONFLICT (q_id) DO NOTHING;

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for audit_questions
CREATE TRIGGER update_audit_questions_updated_at 
    BEFORE UPDATE ON audit_questions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- View: Session Progress
CREATE OR REPLACE VIEW v_session_progress AS
SELECT 
    s.session_id,
    s.domain,
    s.status,
    s.started_at,
    s.completed_at,
    COUNT(DISTINCT l.q_id) as questions_processed,
    AVG(CASE WHEN l.status = 'completed' THEN 1 ELSE 0 END) * 100 as progress_percentage
FROM audit_sessions s
LEFT JOIN audit_logs l ON s.session_id = l.session_id
GROUP BY s.session_id, s.domain, s.status, s.started_at, s.completed_at;

-- View: Latest Evidence Per Question
CREATE OR REPLACE VIEW v_latest_evidence AS
SELECT DISTINCT ON (session_id, q_id)
    session_id,
    q_id,
    domain,
    filename,
    extracted_data,
    created_at
FROM audit_evidence
ORDER BY session_id, q_id, created_at DESC;

-- ============================================
-- GRANTS (Security)
-- ============================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO n8n;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO n8n;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO n8n;

-- ============================================
-- COMPLETION MESSAGE
-- ============================================
DO $$
BEGIN
    RAISE NOTICE 'Compliance Audit Database Schema Initialized Successfully!';
    RAISE NOTICE 'Total Questions Seeded: %', (SELECT COUNT(*) FROM audit_questions);
END $$;
