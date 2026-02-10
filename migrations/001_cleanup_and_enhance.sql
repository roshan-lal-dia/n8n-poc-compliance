-- ============================================
-- Migration: Schema Cleanup & Multi-Question Enhancement
-- Date: 2026-02-10
-- Description: Remove unused objects, enhance evidence handling
-- ============================================

-- ============================================
-- STEP 1: DROP UNUSED OBJECTS
-- ============================================

-- Drop file_registry table (never used by workflows)
DROP TABLE IF EXISTS file_registry CASCADE;

-- Drop views (not actively queried)
DROP VIEW IF EXISTS v_session_progress CASCADE;
DROP VIEW IF EXISTS v_latest_evidence CASCADE;

-- Drop unused GIN index (full-text search not implemented)
DROP INDEX IF EXISTS idx_evidence_text;

-- ============================================
-- STEP 2: ENHANCE EVIDENCE TABLE
-- ============================================

-- Remove unique constraint on file_hash (allow same file in different sessions)
ALTER TABLE audit_evidence DROP CONSTRAINT IF EXISTS audit_evidence_file_hash_key;

-- Add new constraint: unique per session + q_id + hash (dedup within session)
ALTER TABLE audit_evidence ADD CONSTRAINT unique_evidence_per_session 
    UNIQUE(session_id, q_id, file_hash);

-- Add file size tracking
ALTER TABLE audit_evidence ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

-- Add evidence order (for multi-file uploads)
ALTER TABLE audit_evidence ADD COLUMN IF NOT EXISTS evidence_order INTEGER DEFAULT 1;

-- ============================================
-- STEP 3: ENHANCE AUDIT_LOGS FOR STATUS TRACKING
-- ============================================

-- Ensure percentage column exists (should already exist)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='audit_logs' AND column_name='percentage'
    ) THEN
        ALTER TABLE audit_logs ADD COLUMN percentage INTEGER DEFAULT 0;
    END IF;
END $$;

-- ============================================
-- STEP 4: ADD JOB_ID TO SESSIONS (Optional)
-- For linking with Redis job queue
-- ============================================

ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS job_id VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_sessions_jobid ON audit_sessions(job_id);

-- ============================================
-- STEP 5: CLEANUP TRIGGER (Remove unused column)
-- ============================================

-- Drop file_type column from audit_evidence (stored but never queried)
ALTER TABLE audit_evidence DROP COLUMN IF EXISTS file_type;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

DO $$
DECLARE
    evidence_count INTEGER;
    sessions_count INTEGER;
    questions_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO evidence_count FROM audit_evidence;
    SELECT COUNT(*) INTO sessions_count FROM audit_sessions;
    SELECT COUNT(*) INTO questions_count FROM audit_questions;
    
    RAISE NOTICE '=== Migration Complete ===';
    RAISE NOTICE 'Existing evidence records: %', evidence_count;
    RAISE NOTICE 'Existing sessions: %', sessions_count;
    RAISE NOTICE 'Total questions: %', questions_count;
    RAISE NOTICE 'Schema ready for multi-question workflow!';
END $$;
