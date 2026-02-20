-- ============================================================
-- Compliance Audit System — Database Schema
-- Version: 2.0  (UUID-aligned, multi-domain)
-- Last updated: 2026-02-20
--
-- Applied migrations:
--   001_cleanup_and_enhance.sql
--   002_uuid_domains_and_questions.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- reserved for future full-text search


-- ============================================================
-- 1. DOMAIN LOOKUP
--    UUIDs deliberately mirror dmn_domains.dmn_domain_id in
--    the app DB so domain IDs are portable across both systems.
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_domains (
    id         UUID         PRIMARY KEY,
    name       VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP    DEFAULT NOW()
);

INSERT INTO audit_domains (id, name) VALUES
    ('a14d13d9-81eb-46da-ab4f-8476c6469dd3', 'Data Architecture and Modeling'),
    ('f1b48d90-4f9a-46b4-b6f7-a1fb2b8d68fd', 'Data Catalog and Metadata Management'),
    ('98b03b0e-3a90-4ffb-a332-25a2de2191b5', 'Data Culture and Literacy'),
    ('9dbe7809-ce9c-471f-84c1-61e02d39b7c7', 'Data Management Strategy and Governance'),
    ('86b0e9f6-aef3-4c93-84c0-b26afbe184cb', 'Data Monetization'),
    ('ad4bdcc2-182a-4d06-bc03-8fca91056c81', 'Data Quality Management'),
    ('75e2eabb-6b69-465e-a6cb-f6bb1b0ed697', 'Data Security, Privacy and Other Regulations'),
    ('6ec7535e-6134-4010-9817-8c0849e8f59b', 'Data Sharing, Integration & Interoperability'),
    ('4d3a47dd-df31-435e-a8da-b5e758ca3668', 'Data Storage and Operations'),
    ('4b793d57-a04e-4618-a275-082fb5c81792', 'Document and Content Management'),
    ('78739b15-7c02-49be-b03e-2b0c2f502c22', 'Master and Reference Data Management'),
    ('91feeabb-ef97-493c-98b8-accdac8324f3', 'Statistics & Analytics')
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- 2. QUESTIONS REGISTRY
--
--   question_id          → dmn_questions.dmn_question_id
--                                  NULL for manually created questions
--   domain_id                   → audit_domains.id  (no FK enforced)
--   prompt_instructions         → AI evaluation context; only
--                                  populated when is_document_upload_enabled
--   cloud_sync_api_url          → API endpoint / curl template; only
--                                  populated when is_cloud_sync_enabled
--   cloud_sync_evaluation_instruction
--                               → How to interpret cloud sync results; only
--                                  populated when is_cloud_sync_enabled
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_questions (
    id                                UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Traceability to the source application DB
    question_id                UUID,

    -- Domain (no FK constraint — references audit_domains.id)
    domain_id                         UUID    NOT NULL,

    -- Content
    question_year                     INTEGER NOT NULL DEFAULT 2026,
    question_text                     TEXT    NOT NULL,

    -- Document-extraction path
    prompt_instructions               TEXT,

    -- Behaviour flags
    is_document_upload_enabled        BOOLEAN NOT NULL DEFAULT FALSE,
    is_cloud_sync_enabled             BOOLEAN NOT NULL DEFAULT FALSE,

    -- Cloud-sync path
    cloud_sync_api_url                TEXT,
    cloud_sync_evaluation_instruction TEXT,

    -- Audit trail
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- One local record per source question (NULLs excluded from uniqueness)
CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_source_id
    ON audit_questions (question_id)
    WHERE question_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_questions_domain_id ON audit_questions (domain_id);
CREATE INDEX IF NOT EXISTS idx_questions_year      ON audit_questions (question_year);

-- Partial indexes — only rows where the flag is active
CREATE INDEX IF NOT EXISTS idx_questions_doc_upload
    ON audit_questions (domain_id)
    WHERE is_document_upload_enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_questions_cloud_sync
    ON audit_questions (domain_id)
    WHERE is_cloud_sync_enabled = TRUE;



-- ============================================================
-- 3. EVIDENCE STORAGE
--    Stores extracted content from user-uploaded documents.
--    question_id / domain_id are UUIDs (no FK enforced).
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_evidence (
    id           SERIAL    PRIMARY KEY,
    session_id   UUID      NOT NULL,
    question_id  UUID,                          -- references audit_questions.id
    domain_id    UUID,                          -- references audit_domains.id

    -- File metadata
    filename         VARCHAR(500),
    file_hash        VARCHAR(64),
    file_size_bytes  BIGINT,

    -- Ordering within a single question's upload set
    evidence_order   INTEGER   DEFAULT 1,

    -- Extracted content
    -- Structure: { "full_text": "...", "pages": [...], "images": [...] }
    extracted_data   JSONB     NOT NULL,

    created_at  TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_evidence_per_session
        UNIQUE (session_id, question_id, file_hash)
);

CREATE INDEX IF NOT EXISTS idx_evidence_session     ON audit_evidence (session_id);
CREATE INDEX IF NOT EXISTS idx_evidence_question_id ON audit_evidence (question_id);
CREATE INDEX IF NOT EXISTS idx_evidence_domain_id   ON audit_evidence (domain_id);
CREATE INDEX IF NOT EXISTS idx_evidence_hash        ON audit_evidence (file_hash);



-- ============================================================
-- 4. KNOWLEDGE BASE METADATA
--    Tracks which standards are embedded in Qdrant.
--    domain_id references audit_domains.id (no FK enforced).
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_standards (
    id            SERIAL        PRIMARY KEY,
    domain_id     UUID,                         -- references audit_domains.id
    standard_name VARCHAR(500)  NOT NULL,
    filename      VARCHAR(500),
    file_hash     VARCHAR(64)   UNIQUE,
    total_chunks  INTEGER       DEFAULT 0,
    qdrant_collection VARCHAR(100) DEFAULT 'compliance_standards',
    uploaded_at   TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_domain_id ON kb_standards (domain_id);
CREATE INDEX IF NOT EXISTS idx_kb_hash      ON kb_standards (file_hash);



-- ============================================================
-- 5. AUDIT EXECUTION LOGS
--    Tracks per-step progress and AI results for each audit run.
--    question_id references audit_questions.id (no FK enforced).
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL    PRIMARY KEY,
    session_id  UUID      NOT NULL,
    question_id UUID,                           -- references audit_questions.id

    -- Execution tracking
    step_name   VARCHAR(200),
    status      VARCHAR(50),                    -- pending | in_progress | completed | failed

    -- AI response payload (full evaluation result)
    ai_response JSONB,

    -- Human-readable context
    message     TEXT,
    percentage  INTEGER   DEFAULT 0,            -- 0–100

    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_session     ON audit_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_logs_question_id ON audit_logs (question_id);
CREATE INDEX IF NOT EXISTS idx_logs_status      ON audit_logs (status);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp   ON audit_logs (created_at DESC);



-- ============================================================
-- 6. AUDIT SESSIONS
--    Master table for each audit run.
--    domain_id references audit_domains.id (no FK enforced).
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_sessions (
    session_id   UUID     PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id    UUID,                          -- references audit_domains.id
    initiated_by VARCHAR(255),
    status       VARCHAR(50) DEFAULT 'pending', -- pending | in_progress | completed | failed

    -- Optional Redis job linkage
    job_id       VARCHAR(100),

    -- Timing
    started_at   TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Summary
    total_questions           INTEGER     DEFAULT 0,
    answered_questions        INTEGER     DEFAULT 0,
    overall_compliance_score  DECIMAL(5,2),     -- 0.00 – 100.00

    -- Flexible extension field
    metadata     JSONB
);

CREATE INDEX IF NOT EXISTS idx_sessions_status    ON audit_sessions (status);
CREATE INDEX IF NOT EXISTS idx_sessions_domain_id ON audit_sessions (domain_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started   ON audit_sessions (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_jobid     ON audit_sessions (job_id);


-- ============================================================
-- HELPER FUNCTION & TRIGGERS
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_questions_updated_at
    BEFORE UPDATE ON audit_questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- GRANTS
-- ============================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO n8n;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO n8n;
GRANT EXECUTE ON ALL FUNCTIONS        IN SCHEMA public TO n8n;


-- ============================================================
-- COMPLETION MESSAGE
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE 'Compliance Audit DB v2.0 initialized.';
    RAISE NOTICE 'Domains seeded: %', (SELECT COUNT(*) FROM audit_domains);
END $$;

