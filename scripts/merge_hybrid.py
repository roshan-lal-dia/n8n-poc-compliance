import json
import sys
import os
import difflib

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# Read input file path from arguments
if len(sys.argv) < 2:
    print(json.dumps({"error": "Usage: python merge_hybrid.py <input_json_path>"}))
    sys.exit(1)

input_path = sys.argv[1]

# Read input JSON
try:
    with open(input_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
except Exception as e:
    print(json.dumps({"error": f"Failed to read input file: {str(e)}"}))
    sys.exit(1)

# Sort items by page number
items.sort(key=lambda x: x.get('json', {}).get('pageNumber', 0))

if not items:
    print(json.dumps({"error": "No items to process"}))
    sys.exit(0)

# Extract common data from first item
first_item_json = items[0].get('json', {})
file_prefix = first_item_json.get('filePrefix', '')
pdf_path = f"/tmp/n8n_processing/{file_prefix}input.pdf"

# Process PDF if available
pdf_pages = {}
if pdfplumber and os.path.exists(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                pdf_pages[i + 1] = {
                    "text": page.extract_text() or "",
                    "tables": page.extract_tables()
                }
    except Exception as e:
        # Just ignore PDF processing errors
        pass

full_parts = []
provenance = []

for item in items:
    item_json = item.get('json', {})
    page_num = item_json.get('pageNumber')
    ocr_text = item_json.get('extractedText', '')
    vision_raw = item_json.get('visionRaw', '')
    
    vision_desc = ""
    if vision_raw.strip().startswith('{'):
        try:
            parsed = json.loads(vision_raw)
            if 'description' in parsed:
                vision_desc = f"\n[Visual Analysis: {parsed['description']}]"
        except:
            pass

    pdf_data = pdf_pages.get(page_num, {"text": "", "tables": []})
    pdf_text = pdf_data["text"]
    tables = pdf_data["tables"]

    final_text = ocr_text
    source = "ocr"

    if pdf_text and len(pdf_text.strip()) > 50:
        ratio = difflib.SequenceMatcher(None, ocr_text[:1000], pdf_text[:1000]).ratio()
        if ratio > 0.6:
            final_text = pdf_text
            source = "pdfplumber"
        else:
            final_text = f"{pdf_text}\n\n[OCR Supplemental]:\n{ocr_text}"
            source = "hybrid"
    
    tables_md = ""
    if tables:
        for table in tables:
            cleaned_table = [[str(cell or '').replace('\n', ' ') for cell in row] for row in table]
            if cleaned_table and cleaned_table[0]:
                headers = cleaned_table[0]
                tables_md += f"\n\n| {' | '.join(headers)} |\n| {' | '.join(['---']*len(headers))} |\n"
                for row in cleaned_table[1:]:
                    if len(row) == len(headers):
                        tables_md += f"| {' | '.join(row)} |\n"
        source += " + tables"

    full_parts.append(f"--- Page {page_num} ---\nSrc: {source}\n\n{final_text}{tables_md}{vision_desc}")
    provenance.append({"page": page_num, "source": source})

# Prepare result
result = {
    "fullDocument": "\n\n".join(full_parts),
    "provenance": provenance,
    "filePrefix": file_prefix,
    "criteriaTemplate": first_item_json.get('criteriaTemplate'),
    "evaluationCriteria": first_item_json.get('evaluationCriteria', {}),
    "passingScore": first_item_json.get('passingScore', 70)
}

# Print JSON to stdout for n8n to capture
print(json.dumps(result))