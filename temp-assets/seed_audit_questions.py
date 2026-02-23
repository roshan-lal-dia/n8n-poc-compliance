#!/usr/bin/env python3
"""
ETL: Seed audit_questions from CSV + Excel.

CSV  → dmn_question_id, domain_id, question_year, flags
Excel → compliance question (EN only), accepted evidence (EN only), sub-specifications

Matching key: normalised English question text
"""

import re
import subprocess
import sys
import unicodedata
import pandas as pd

# ── paths ──────────────────────────────────────────────────────────────────────
CSV_PATH   = "dmn_questions_export-after-fida-confirmation-23rdFeb.csv"
XLSX_PATH  = "Compliance Questionnaire_DI Inputs.xlsx"

# Sheets that are NOT data sheets
NON_DATA_SHEETS = {"Cover Page", "Document Purpose & Scope", "Version Control", "New Approach"}

# Arabic unicode block
ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

# ── helpers ────────────────────────────────────────────────────────────────────

def is_arabic_line(line: str) -> bool:
    return bool(ARABIC_RE.search(line))

def english_only(text: str) -> str:
    """Keep only lines that contain NO Arabic characters. Return None if empty."""
    if not text or (not isinstance(text, str)):
        return None
    lines = [l for l in text.splitlines() if l.strip() and not is_arabic_line(l)]
    result = "\n".join(lines).strip()
    return result if result else None

def norm(text: str) -> str:
    """Normalise for matching: lower, collapse whitespace, strip punctuation."""
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = ARABIC_RE.sub("", t)
    t = re.sub(r'[\n\r]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'[^\w\s]', '', t)
    return t

def pg_escape(s):
    """Escape a Python string for embedding in a PostgreSQL dollar-quoted block."""
    if s is None:
        return "NULL"
    # Use $$ quoting; if $$ appears in text, use $_q_$
    tag = "$$"
    if "$$" in s:
        tag = "$_q_$"
    return f"{tag}{s}{tag}"

# ── 1. Read CSV ────────────────────────────────────────────────────────────────
print("Reading CSV …")
csv_df = pd.read_csv(CSV_PATH)

# Build lookup: normalised_question_text → row info
csv_lookup = {}
for _, row in csv_df.iterrows():
    q_text = str(row.get("dmn_question_text", "") or "")
    key = norm(q_text)
    if not key:
        continue
    csv_lookup[key] = {
        "question_id":               str(row["dmn_question_id"]),
        "domain_id":                  str(row["dmn_domain_id"]),
        "question_year":              int(row.get("dmn_question_year") or 2026),
        "is_document_upload_enabled": bool(row.get("dmn_is_document_upload_enabled", False)),
        "is_cloud_sync_enabled":      bool(row.get("dmn_is_cloud_sync_enabled", False)),
        "cloud_sync_api_url":         row.get("dmn_cloud_sync_api_curl") or None,
        "question_text":              q_text.strip(),
    }

print(f"  CSV rows loaded: {len(csv_lookup)}")

# ── 2. Read Excel ──────────────────────────────────────────────────────────────
print("Reading Excel …")
xl = pd.ExcelFile(XLSX_PATH)

records = []

for sheet_name in xl.sheet_names:
    if sheet_name in NON_DATA_SHEETS:
        continue

    raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)

    # Find header row: the row that contains "Compliance Questions"
    header_row = None
    for i, row in raw.iterrows():
        if any("Compliance Questions" in str(v) for v in row.values):
            header_row = i
            break

    if header_row is None:
        print(f"  [{sheet_name}] – no header row found, skipping")
        continue

    df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    # Identify columns (may have slight naming variations)
    def find_col(candidates):
        for c in df.columns:
            for cand in candidates:
                if cand.lower() in c.lower():
                    return c
        return None

    col_q   = find_col(["Compliance Questions"])
    col_ev  = find_col(["Acceptance Evidence"])
    col_sub = find_col(["Sub-Specifications"])
    col_sn  = find_col(["Specification Number"])
    col_snm = find_col(["Specification Name"])

    if not col_q:
        print(f"  [{sheet_name}] – 'Compliance Questions' column not found, skipping")
        continue

    for _, row in df.iterrows():
        q_raw  = str(row.get(col_q, "") or "")
        ev_raw = str(row.get(col_ev, "") or "") if col_ev else ""
        sub    = str(row.get(col_sub, "") or "") if col_sub else ""
        spec_n = str(row.get(col_sn, "") or "") if col_sn else ""
        spec_nm= str(row.get(col_snm,"") or "") if col_snm else ""

        q_en  = english_only(q_raw)
        ev_en = english_only(ev_raw)
        sub   = sub.strip() if sub.strip() and sub.strip().lower() not in ("nan","none") else None
        spec_n  = spec_n.strip() if spec_n.strip().lower() not in ("nan","none") else ""
        spec_nm = spec_nm.strip() if spec_nm.strip().lower() not in ("nan","none") else ""

        if not q_en:
            continue

        records.append({
            "sheet":        sheet_name,
            "spec_number":  spec_n,
            "spec_name":    spec_nm,
            "q_en":         q_en,
            "q_norm":       norm(q_en),
            "ev_en":        ev_en,
            "sub_specs":    sub,
        })

print(f"  Excel rows extracted: {len(records)}")

# ── 3. Match Excel rows to CSV rows ────────────────────────────────────────────
print("Matching …")
matched   = []
unmatched = []

for rec in records:
    csv_row = csv_lookup.get(rec["q_norm"])
    if csv_row:
        matched.append({**rec, **csv_row})
    else:
        unmatched.append(rec)

print(f"  Matched: {len(matched)}, Unmatched: {len(unmatched)}")
if unmatched:
    print("  Unmatched (first 5):")
    for r in unmatched[:5]:
        print(f"    [{r['sheet']}] {r['spec_number']} – {r['q_en'][:80]}")

# ── 4. Build SQL ───────────────────────────────────────────────────────────────
print("Building SQL …")

sql_parts = ["""
-- ─────────────────────────────────────────────────────────────────────────────
-- Auto-generated by seed_audit_questions.py
-- ─────────────────────────────────────────────────────────────────────────────
BEGIN;

-- Add accepted_evidence column if it doesn't exist
ALTER TABLE audit_questions ADD COLUMN IF NOT EXISTS accepted_evidence TEXT;

"""]

for r in matched:
    qid         = r["question_id"]
    did         = r["domain_id"]
    year        = r["question_year"]
    q_text      = r["question_text"]    # original English from CSV (clean)
    ev_en       = r["ev_en"]
    sub         = r["sub_specs"]
    is_doc      = str(r["is_document_upload_enabled"]).lower()
    is_cloud    = str(r["is_cloud_sync_enabled"]).lower()
    cloud_url   = r.get("cloud_sync_api_url")

    q_text_pg   = pg_escape(q_text)
    ev_pg       = pg_escape(ev_en)
    sub_pg      = pg_escape(sub)
    cloud_pg    = pg_escape(cloud_url)

    sql_parts.append(f"""
INSERT INTO audit_questions
  (question_id, domain_id, question_year, question_text,
   prompt_instructions, accepted_evidence,
   is_document_upload_enabled, is_cloud_sync_enabled, cloud_sync_api_url)
VALUES
  ('{qid}'::uuid, '{did}'::uuid, {year}, {q_text_pg},
   {sub_pg}, {ev_pg},
   {is_doc}, {is_cloud}, {cloud_pg})
ON CONFLICT (question_id) DO UPDATE SET
  question_text               = EXCLUDED.question_text,
  prompt_instructions         = EXCLUDED.prompt_instructions,
  accepted_evidence           = EXCLUDED.accepted_evidence,
  is_document_upload_enabled  = EXCLUDED.is_document_upload_enabled,
  is_cloud_sync_enabled       = EXCLUDED.is_cloud_sync_enabled,
  cloud_sync_api_url          = EXCLUDED.cloud_sync_api_url,
  updated_at                  = now();
""")

sql_parts.append("\nCOMMIT;\n")
sql_parts.append(f"\\echo 'Done. {len(matched)} rows upserted.'\n")

full_sql = "".join(sql_parts)

out_path = "seed_audit_questions.sql"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(full_sql)
print(f"  SQL written to: {out_path}")

# ── 5. Run against live DB ─────────────────────────────────────────────────────
print("Running SQL against compliance-db …")
result = subprocess.run(
    ["docker", "exec", "-i", "compliance-db", "psql", "-U", "n8n", "-d", "compliance_db"],
    input=full_sql.encode("utf-8"),
    capture_output=True,
)
stdout = result.stdout.decode("utf-8", errors="replace")
stderr = result.stderr.decode("utf-8", errors="replace")

print("STDOUT:", stdout[-3000:] if len(stdout) > 3000 else stdout)
if stderr:
    print("STDERR:", stderr[-2000:] if len(stderr) > 2000 else stderr)

if result.returncode != 0:
    print(f"\nERROR: psql exited with code {result.returncode}")
    sys.exit(1)
else:
    print(f"\nSuccess! {len(matched)} rows upserted into audit_questions.")
