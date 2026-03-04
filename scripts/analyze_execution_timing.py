#!/usr/bin/env python3
"""
Execution Timing Analyzer for NPC Compliance AI System
Analyzes database logs to identify performance bottlenecks
Usage: python3 scripts/analyze_execution_timing.py [session_id]
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
from collections import defaultdict

# Load environment variables
def load_env():
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    return env_vars

env = load_env()

# Database connection
DB_CONFIG = {
    'host': env.get('DB_HOST', 'localhost'),
    'port': env.get('DB_PORT', '5432'),
    'database': env.get('DB_NAME', 'compliance_db'),
    'user': env.get('DB_USER', 'n8n'),
    'password': env.get('DB_PASSWORD', '')
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def analyze_session(session_id=None):
    conn = get_connection()
    cur = conn.cursor()
    
    # If no session_id provided, get the most recent one
    if not session_id:
        cur.execute("""
            SELECT session_id, created_at, status
            FROM audit_sessions 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = cur.fetchone()
        if not result:
            print("No sessions found in database")
            return
        session_id, created_at, status = result
        print(f"Analyzing most recent session: {session_id}")
        print(f"Created: {created_at}")
        print(f"Status: {status}")
        print("=" * 80)
        print()
    
    # Get session details
    cur.execute("""
        SELECT 
            session_id,
            status,
            created_at,
            updated_at,
            EXTRACT(EPOCH FROM (updated_at - created_at)) as total_duration
        FROM audit_sessions 
        WHERE session_id = %s
    """, (session_id,))
    
    session = cur.fetchone()
    if not session:
        print(f"Session {session_id} not found")
        return
    
    _, status, created, updated, total_duration = session
    
    print(f"SESSION OVERVIEW")
    print(f"Status: {status}")
    print(f"Total Duration: {total_duration:.2f} seconds ({total_duration/60:.2f} minutes)")
    print(f"Start: {created}")
    print(f"End: {updated}")
    print()
    
    # Get step-by-step timing
    cur.execute("""
        SELECT 
            step_name,
            status,
            created_at,
            updated_at,
            EXTRACT(EPOCH FROM (updated_at - created_at)) as duration,
            question_id,
            ai_response
        FROM audit_logs 
        WHERE session_id = %s
        ORDER BY created_at ASC
    """, (session_id,))
    
    steps = cur.fetchall()
    
    print(f"STEP-BY-STEP BREAKDOWN ({len(steps)} steps)")
    print("-" * 80)
    
    step_timings = defaultdict(list)
    total_time = 0
    
    for step_name, step_status, start, end, duration, question_id, ai_response in steps:
        step_timings[step_name].append(duration)
        total_time += duration
        
        # Color code based on duration
        if duration > 60:
            marker = "🔴 VERY SLOW"
        elif duration > 30:
            marker = "🟡 SLOW"
        elif duration > 10:
            marker = "🟠 MODERATE"
        else:
            marker = "🟢 FAST"
        
        print(f"{marker} {step_name}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Status: {step_status}")
        print(f"  Question: {question_id[:8] if question_id else 'N/A'}...")
        print(f"  Start: {start}")
        print(f"  End: {end}")
        
        if ai_response and len(str(ai_response)) > 100:
            print(f"  Response size: {len(str(ai_response))} chars")
        
        print()
    
    # Summary statistics
    print("=" * 80)
    print("TIMING SUMMARY BY STEP TYPE")
    print("-" * 80)
    
    for step_name, durations in sorted(step_timings.items(), key=lambda x: sum(x[1]), reverse=True):
        count = len(durations)
        total = sum(durations)
        avg = total / count
        min_dur = min(durations)
        max_dur = max(durations)
        
        print(f"{step_name}:")
        print(f"  Count: {count}")
        print(f"  Total: {total:.2f}s ({total/60:.2f}m)")
        print(f"  Average: {avg:.2f}s")
        print(f"  Min: {min_dur:.2f}s | Max: {max_dur:.2f}s")
        print(f"  % of total: {(total/total_time*100):.1f}%")
        print()
    
    # Evidence analysis
    cur.execute("""
        SELECT 
            file_name,
            file_hash,
            COALESCE(jsonb_array_length(extracted_data->'pages'), 0) as page_count,
            LENGTH(extracted_data::text) as data_size,
            created_at
        FROM audit_evidence 
        WHERE session_id = %s
        ORDER BY created_at ASC
    """, (session_id,))
    
    evidence = cur.fetchall()
    
    if evidence:
        print("=" * 80)
        print("EVIDENCE FILES PROCESSED")
        print("-" * 80)
        
        for filename, file_hash, pages, size, created in evidence:
            print(f"File: {filename}")
            print(f"  Hash: {file_hash[:16]}...")
            print(f"  Pages: {pages}")
            print(f"  Data size: {size:,} bytes ({size/1024:.1f} KB)")
            print(f"  Extracted: {created}")
            print()
    
    # Cache performance
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE step_name = 'cache_hit') as cache_hits,
            COUNT(*) FILTER (WHERE step_name = 'cache_miss') as cache_misses,
            COUNT(*) FILTER (WHERE step_name = 'completed') as completed
        FROM audit_logs 
        WHERE session_id = %s
    """, (session_id,))
    
    cache_stats = cur.fetchone()
    if cache_stats:
        hits, misses, completed = cache_stats
        print("=" * 80)
        print("CACHE PERFORMANCE")
        print("-" * 80)
        print(f"Cache hits: {hits}")
        print(f"Cache misses: {misses}")
        print(f"Completed evaluations: {completed}")
        if hits + misses > 0:
            hit_rate = (hits / (hits + misses)) * 100
            print(f"Cache hit rate: {hit_rate:.1f}%")
        print()
    
    # Bottleneck identification
    print("=" * 80)
    print("BOTTLENECK ANALYSIS")
    print("-" * 80)
    
    bottlenecks = []
    
    # Check for slow extraction
    extraction_steps = [d for s, durations in step_timings.items() if 'extract' in s.lower() for d in durations]
    if extraction_steps and max(extraction_steps) > 30:
        bottlenecks.append(("Evidence Extraction", max(extraction_steps), 
                           "Florence service may not be using GPU or files are very large"))
    
    # Check for slow LLM
    llm_steps = [d for s, durations in step_timings.items() if s == 'completed' for d in durations]
    if llm_steps and max(llm_steps) > 60:
        bottlenecks.append(("LLM Evaluation", max(llm_steps), 
                           "Ollama may not be using GPU or context is too large"))
    
    # Check for slow RAG
    rag_steps = [d for s, durations in step_timings.items() if 'rag' in s.lower() or 'search' in s.lower() for d in durations]
    if rag_steps and max(rag_steps) > 10:
        bottlenecks.append(("RAG Search", max(rag_steps), 
                           "Qdrant may be slow or collection is too large"))
    
    if bottlenecks:
        for name, duration, reason in bottlenecks:
            print(f"⚠ {name}: {duration:.2f}s")
            print(f"  Possible cause: {reason}")
            print()
    else:
        print("✓ No major bottlenecks detected")
        print()
    
    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("-" * 80)
    
    if total_duration > 150:  # More than 2.5 minutes
        print("🔴 Execution is taking longer than expected (>2.5 minutes)")
        print()
        print("Immediate actions:")
        print("1. Check GPU utilization: ./scripts/check_gpu_usage.sh")
        print("2. Verify services are using GPU:")
        print("   - Florence: Check logs for 'cuda' or 'cpu' device")
        print("   - Ollama: Check if model is quantized (Q4_K_M)")
        print("3. Check for large files in evidence")
        print("4. Monitor real-time: watch -n 1 nvidia-smi")
        print()
    
    if extraction_steps and sum(extraction_steps) > 60:
        print("⚠ Evidence extraction is a major bottleneck")
        print("  - Verify Florence is using GPU (not CPU)")
        print("  - Check Florence logs: docker compose logs florence-service")
        print("  - Consider reducing image resolution for OCR")
        print()
    
    if llm_steps and sum(llm_steps) > 90:
        print("⚠ LLM evaluation is a major bottleneck")
        print("  - Verify Ollama is using GPU")
        print("  - Check model: curl http://localhost:11434/api/tags")
        print("  - Consider reducing context size or using smaller model")
        print()
    
    cur.close()
    conn.close()

def compare_recent_sessions(limit=5):
    """Compare timing across recent sessions"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            session_id,
            status,
            created_at,
            EXTRACT(EPOCH FROM (updated_at - created_at)) as duration
        FROM audit_sessions 
        ORDER BY created_at DESC 
        LIMIT %s
    """, (limit,))
    
    sessions = cur.fetchall()
    
    print(f"RECENT SESSIONS COMPARISON (Last {limit})")
    print("=" * 80)
    
    for session_id, status, created, duration in sessions:
        if duration:
            marker = "🔴" if duration > 150 else "🟡" if duration > 60 else "🟢"
            print(f"{marker} {session_id}")
            print(f"  Duration: {duration:.2f}s ({duration/60:.2f}m)")
            print(f"  Status: {status}")
            print(f"  Created: {created}")
            print()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--compare":
            compare_recent_sessions()
        else:
            analyze_session(sys.argv[1])
    else:
        analyze_session()
