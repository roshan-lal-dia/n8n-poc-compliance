-- ============================================================
-- Migration 002: UUID-aligned Domains & Questions Schema
-- Date:    2026-02-20
-- Scope:
--   1. Create audit_domains lookup table (seeded from app DB)
--   2. Rebuild audit_questions with full UUID schema
--   3. Align audit_evidence, audit_logs, audit_sessions,
--      kb_standards to UUID columns (no FK constraints)
-- ============================================================

BEGIN;

-- ============================================================
-- STEP 1: AUDIT_DOMAINS — Domain lookup table
--   UUIDs deliberately match dmn_domains.dmn_domain_id in the
--   app DB (unifi-cdmp-server-pg) so domain IDs are portable
--   across both systems without translation.
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_domains (
    id   UUID         PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
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
-- STEP 2: AUDIT_QUESTIONS — Full rebuild with UUID schema
--
-- Column notes:
--   question_id          → dmn_questions.dmn_question_id
--                                  (nullable for manually added questions)
--   domain_id                   → audit_domains.id (no FK enforced)
--   prompt_instructions         → AI evaluation context, only meaningful
--                                  when is_document_upload_enabled = TRUE
--   cloud_sync_api_url          → API endpoint / curl template, only
--                                  meaningful when is_cloud_sync_enabled = TRUE
--   cloud_sync_evaluation_instruction
--                               → How to interpret cloud sync API response,
--                                  only meaningful when is_cloud_sync_enabled = TRUE
-- ============================================================

DROP TABLE IF EXISTS audit_questions CASCADE;

CREATE TABLE audit_questions (
    id                              UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Traceability back to the source app DB question
    question_id              UUID,

    -- Domain reference (matches audit_domains.id / dmn_domains.dmn_domain_id)
    domain_id                       UUID    NOT NULL,

    -- Core question content
    question_year                   INTEGER NOT NULL DEFAULT 2026,
    question_text                   TEXT    NOT NULL,

    -- File-extraction path (populated when is_document_upload_enabled = TRUE)
    prompt_instructions             TEXT,

    -- Behaviour flags
    is_document_upload_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    is_cloud_sync_enabled           BOOLEAN NOT NULL DEFAULT FALSE,

    -- Cloud-sync path (populated when is_cloud_sync_enabled = TRUE)
    cloud_sync_api_url              TEXT,
    cloud_sync_evaluation_instruction TEXT,

    -- Audit trail
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Unique: one local record per source question (nulls excluded)
CREATE UNIQUE INDEX idx_questions_source_id
    ON audit_questions (question_id)
    WHERE question_id IS NOT NULL;

-- Lookup indexes
CREATE INDEX idx_questions_domain_id  ON audit_questions (domain_id);
CREATE INDEX idx_questions_year       ON audit_questions (question_year);

-- Partial indexes — only index rows where the flag is active
CREATE INDEX idx_questions_doc_upload
    ON audit_questions (domain_id)
    WHERE is_document_upload_enabled = TRUE;

CREATE INDEX idx_questions_cloud_sync
    ON audit_questions (domain_id)
    WHERE is_cloud_sync_enabled = TRUE;

-- Keep updated_at current
CREATE TRIGGER trg_questions_updated_at
    BEFORE UPDATE ON audit_questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- STEP 3: AUDIT_EVIDENCE — Replace q_id VARCHAR & domain VARCHAR
--         with question_id UUID & domain_id UUID
-- ============================================================

-- Drop old unique constraint that referenced q_id
ALTER TABLE audit_evidence
    DROP CONSTRAINT IF EXISTS unique_evidence_per_session;

-- Add UUID columns
ALTER TABLE audit_evidence
    ADD COLUMN IF NOT EXISTS question_id UUID,
    ADD COLUMN IF NOT EXISTS domain_id   UUID;

-- Remove old string columns
ALTER TABLE audit_evidence
    DROP COLUMN IF EXISTS q_id,
    DROP COLUMN IF EXISTS domain;

-- Restore deduplication constraint on new columns
ALTER TABLE audit_evidence
    ADD CONSTRAINT unique_evidence_per_session
        UNIQUE (session_id, question_id, file_hash);

-- Refresh indexes
DROP INDEX IF EXISTS idx_evidence_qid;
DROP INDEX IF EXISTS idx_evidence_domain;

CREATE INDEX idx_evidence_question_id ON audit_evidence (question_id);
CREATE INDEX idx_evidence_domain_id   ON audit_evidence (domain_id);


-- ============================================================
-- STEP 4: AUDIT_LOGS — Replace q_id VARCHAR with question_id UUID
-- ============================================================

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS question_id UUID;

ALTER TABLE audit_logs
    DROP COLUMN IF EXISTS q_id;

CREATE INDEX IF NOT EXISTS idx_logs_question_id ON audit_logs (question_id);


-- ============================================================
-- STEP 5: AUDIT_SESSIONS — Replace domain VARCHAR with domain_id UUID
-- ============================================================

ALTER TABLE audit_sessions
    ADD COLUMN IF NOT EXISTS domain_id UUID;

ALTER TABLE audit_sessions
    DROP COLUMN IF EXISTS domain;

DROP INDEX IF EXISTS idx_sessions_domain;
CREATE INDEX idx_sessions_domain_id ON audit_sessions (domain_id);


-- ============================================================
-- STEP 6: KB_STANDARDS — Replace domain VARCHAR with domain_id UUID
-- ============================================================

ALTER TABLE kb_standards
    ADD COLUMN IF NOT EXISTS domain_id UUID;

ALTER TABLE kb_standards
    DROP COLUMN IF EXISTS domain;

DROP INDEX IF EXISTS idx_kb_domain;
CREATE INDEX idx_kb_domain_id ON kb_standards (domain_id);


-- ============================================================
-- VERIFICATION
-- ============================================================

DO $$
DECLARE
    domain_count    INTEGER;
    question_cols   INTEGER;
BEGIN
    SELECT COUNT(*) INTO domain_count   FROM audit_domains;
    SELECT COUNT(*) INTO question_cols  FROM information_schema.columns
        WHERE table_name = 'audit_questions';

    RAISE NOTICE '=== Migration 002 Complete ===';
    RAISE NOTICE 'audit_domains seeded: % rows', domain_count;
    RAISE NOTICE 'audit_questions columns: %', question_cols;
    RAISE NOTICE 'All tables aligned to UUID columns (no FK constraints).';
END $$;

COMMIT;
