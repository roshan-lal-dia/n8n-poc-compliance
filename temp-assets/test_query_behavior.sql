-- Test 1: Query returns 1 row when no match (cache miss)
-- Expected: 1 row with NULL values
WITH current_hashes AS (
  SELECT UNNEST(ARRAY['nonexistent_hash_1', 'nonexistent_hash_2']::text[]) AS hash
),
current_hash_count AS (
  SELECT COUNT(*) as cnt FROM current_hashes
),
matching_sessions AS (
  SELECT DISTINCT
    al.session_id,
    al.question_id,
    al.ai_response,
    al.created_at
  FROM audit_logs al
  JOIN audit_evidence ae ON ae.session_id = al.session_id AND ae.question_id = al.question_id
  WHERE al.question_id = '00000000-0000-0000-0000-000000000000'::uuid
    AND al.step_name = 'completed'
    AND al.status = 'success'
    AND al.ai_response IS NOT NULL
    AND ae.file_hash IN (SELECT hash FROM current_hashes)
  GROUP BY al.session_id, al.question_id, al.ai_response, al.created_at
  HAVING COUNT(DISTINCT ae.file_hash) = (SELECT cnt FROM current_hash_count)
  ORDER BY al.created_at DESC
  LIMIT 1
)
SELECT 
  COALESCE(ms.ai_response, NULL::jsonb) as ai_response,
  COALESCE(ms.session_id, NULL::uuid) as cached_session_id,
  COALESCE(ms.created_at, NULL::timestamp) as cached_at,
  CASE 
    WHEN ms.ai_response IS NULL THEN 'CACHE MISS - Will proceed with full flow'
    ELSE 'CACHE HIT - Will bypass extraction & RAG'
  END as cache_status
FROM (SELECT 1) as dummy
LEFT JOIN matching_sessions ms ON true;
