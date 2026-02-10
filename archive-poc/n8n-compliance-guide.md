# Complete Guide: Building a Compliance Document Evaluator in n8n
## Modular AI-Powered Document Analysis System

**Version 1.0 | February 2026**  
**For: First-time n8n Users**

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [n8n Concepts You'll Learn](#n8n-concepts-youll-learn)
3. [Architecture Design](#architecture-design)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Modular Components](#modular-components)
6. [Testing & Debugging](#testing-debugging)
7. [Cost Optimization](#cost-optimization)
8. [Future Enhancements](#future-enhancements)

---

## Project Overview

### What We're Building

An **automated compliance evaluation system** that:

1. Accepts documents (PDF, PPTX, DOCX) for compliance review
2. Routes to appropriate evaluation template based on compliance type
3. Extracts content using Python (text, tables, images)
4. Evaluates against criteria using AI reasoning model
5. Returns structured compliance score + feedback

### Real-World Use Case

**Scenario**: Your organization receives 50+ compliance documents weekly (data strategies, architecture plans, governance policies). Manual review takes 2-3 hours per document. This automation reduces it to 5 minutes.

### System Flow Diagram

Input (API/Manual)
    ↓
[Compliance Type, File Type, File Content]
    ↓
┌─────────────────────────────────┐
│   SWITCH: Compliance Type       │
├─────────────────────────────────┤
│ ├─ Data Strategy Template       │
│ ├─ Data Architecture Template   │
│ ├─ Data Governance Template     │
│ └─ Other Templates...           │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│   File Normalization            │
│   PPTX → PDF                    │
│   DOCX → PDF                    │
│   PDF → PDF (direct)            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│   Python Content Extraction     │
│   ├─ Text Extraction            │
│   ├─ Table Extraction           │
│   └─ Image OCR (optional)       │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│   AI Evaluation                 │
│   Model: GPT-4-mini / Claude    │
│   Prompt: Compliance Criteria   │
└─────────────────────────────────┘
    ↓
Output: Score + Detailed Feedback

---

## n8n Concepts You'll Learn

### 1. **Nodes** - Building Blocks

Think of nodes as **Lego pieces**. Each does one specific task:

- **Webhook Node**: Receives data (like API endpoint)
- **Switch Node**: Routes data based on conditions (if-else logic)
- **Code Node**: Runs Python/JavaScript for custom logic
- **HTTP Request Node**: Calls external APIs
- **Set Node**: Transforms data structure

**Example**: 
Webhook (receives document) 
  → Switch (check file type) 
  → Code (extract content) 
  → HTTP Request (call AI API)

### 2. **Items** - Data Flow

Data flows through n8n as **items** (think: rows in a spreadsheet).

**Example Item Structure**:
{
  "json": {
    "complianceType": "Data Architecture",
    "fileType": "pdf",
    "fileName": "architecture_plan_v2.pdf",
    "extractedText": "...",
    "score": 85
  },
  "binary": {
    "data": {
      "data": "base64_encoded_file_content...",
      "mimeType": "application/pdf",
      "fileName": "architecture_plan_v2.pdf"
    }
  }
}

**Key Points**:
- `json`: Regular data (text, numbers, objects)
- `binary`: Files (PDFs, images, etc.)
- Items flow from node to node, each node can modify them

### 3. **Expressions** - Dynamic Values

Access data using `{{ }}` syntax:

// Get compliance type from current item
{{ $json.complianceType }}

// Get file name from binary data
{{ $binary.data.fileName }}

// Access previous node's data
{{ $('Extract Content').item.json.textContent }}

// Conditional logic
{{ $json.score >= 80 ? 'Pass' : 'Fail' }}

### 4. **Workflow Execution Modes**

- **Manual (Test)**: Click "Execute Workflow" button - for development
- **Active (Production)**: Auto-runs when triggered (webhook receives data)

### 5. **Continue on Fail**

Each node has this setting:
- **True**: If node fails, workflow continues (error stored in item)
- **False**: If node fails, entire workflow stops

**Use case**: Set `true` for optional image extraction, `false` for critical file conversion.

---

## Architecture Design

### Modular Component Breakdown

┌──────────────────────────────────────────┐
│  MODULE 1: INPUT HANDLER                 │
│  - Webhook/Manual Trigger                │
│  - Input Validation                      │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│  MODULE 2: TEMPLATE ROUTER               │
│  - Switch by Compliance Type             │
│  - Load Evaluation Criteria              │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│  MODULE 3: FILE PROCESSOR                │
│  - Sub-module 3A: PPTX → PDF             │
│  - Sub-module 3B: DOCX → PDF             │
│  - Sub-module 3C: PDF Pass-through       │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│  MODULE 4: CONTENT EXTRACTOR             │
│  - Python: pdfplumber (text + tables)    │
│  - Python: pytesseract (OCR images)      │
│  - Combine all content                   │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│  MODULE 5: AI EVALUATOR                  │
│  - Build prompt with criteria            │
│  - Call LLM (GPT-4-mini/Claude)          │
│  - Parse structured response             │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│  MODULE 6: OUTPUT FORMATTER              │
│  - Structure results                     │
│  - Return JSON response                  │
└──────────────────────────────────────────┘

**Why Modular?**
- **Easy Updates**: Change file converter without touching AI evaluator
- **Testing**: Test each module independently
- **Reusability**: Use file processor in other workflows
- **Maintainability**: Clear separation of concerns

---

## Step-by-Step Implementation

### MODULE 1: Input Handler

#### Step 1.1: Create Webhook Trigger

**What it does**: Receives document submission via HTTP POST

**n8n Setup**:
1. Add **Webhook** node
2. Configure:
   - **HTTP Method**: POST
   - **Path**: `/evaluate-compliance`
   - **Authentication**: Header Auth (recommended)
     - Header Name: `X-API-Key`
     - Header Value: `your-secret-key-here`

**Expected Input (JSON)**:
{
  "complianceType": "Data Architecture",
  "fileType": "pdf",
  "fileContent": "base64_encoded_content_or_url",
  "fileName": "architecture_doc.pdf"
}

**Alternative**: Use **Manual Trigger** for testing:
1. Add **Manual Trigger** node
2. Click "Add Field" → Add test data manually

**n8n Concept**: Webhooks create a URL endpoint. When you activate the workflow, n8n gives you a URL like:
https://your-n8n-instance.com/webhook/evaluate-compliance

#### Step 1.2: Validate Input

**What it does**: Ensures required fields exist

Add **IF Node** after webhook:

**Condition Settings**:
// Check if compliance type exists
{{ $json.complianceType !== undefined }}

// AND check file type exists  
{{ $json.fileType !== undefined }}

// AND check file content exists
{{ $json.fileContent !== undefined }}

**Outputs**:
- **True Branch** → Continue to processing
- **False Branch** → Return error response

**Error Response** (add **Set Node** on False branch):
{
  "status": "error",
  "message": "Missing required fields: complianceType, fileType, or fileContent"
}

---

### MODULE 2: Template Router

#### Step 2.1: Switch by Compliance Type

**What it does**: Routes to correct evaluation template

Add **Switch Node**:

**Configuration**:
- **Mode**: Rules
- **Data Type**: String

**Rules**:
1. **Rule 1**: `{{ $json.complianceType }}` equals `Data Strategy` → Output 0
2. **Rule 2**: `{{ $json.complianceType }}` equals `Data Architecture` → Output 1
3. **Rule 3**: `{{ $json.complianceType }}` equals `Data Governance` → Output 2
4. **Rule 4**: `{{ $json.complianceType }}` equals `Data Quality` → Output 3
5. **Fallback**: Default → Output 4 (unknown type)

**n8n Concept**: Switch node creates multiple output paths (like `switch/case` in programming).

#### Step 2.2: Load Evaluation Criteria

For each compliance type, add a **Set Node** to define criteria:

**Example: Data Architecture Template (Output 1)**

Add **Set Node** named "Data Architecture Criteria":

// Set these fields:
{
  "criteriaTemplate": "Data Architecture",
  "evaluationCriteria": {
    "technicalDepth": {
      "weight": 25,
      "description": "Covers data models, schemas, integration patterns"
    },
    "scalability": {
      "weight": 20,
      "description": "Addresses future growth and performance"
    },
    "security": {
      "weight": 20,
      "description": "Data encryption, access controls, compliance"
    },
    "documentation": {
      "weight": 15,
      "description": "Clear diagrams, specifications, standards"
    },
    "feasibility": {
      "weight": 20,
      "description": "Realistic implementation plan and timeline"
    }
  },
  "passingScore": 70,
  "maxScore": 100
}

**Why Set Node?**: It transforms data without code. Perfect for adding structured information.

**Other Templates** (repeat for each output):
- **Data Strategy Criteria** (Output 0)
- **Data Governance Criteria** (Output 2)
- **Data Quality Criteria** (Output 3)

---

### MODULE 3: File Processor (Sub-workflows)

**n8n Concept**: Use **Execute Workflow** node to call reusable sub-workflows.

#### Sub-workflow 3A: PPTX to PDF Converter

**Create new workflow**: "Convert PPTX to PDF"

**Nodes**:

1. **Manual Trigger** (accepts input from parent workflow)

2. **Code Node** (Python) - Convert PPTX to PDF:

# Required packages: python-pptx, reportlab, Pillow
from pptx import Presentation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import base64

# Get binary data from input
pptx_data = base64.b64decode(items[0].binary['data']['data'])

# Load PPTX
prs = Presentation(BytesIO(pptx_data))

# Create PDF
pdf_buffer = BytesIO()
c = canvas.Canvas(pdf_buffer, pagesize=letter)

# Extract text from each slide
for slide in prs.slides:
    text = []
    for shape in slide.shapes:
        if hasattr(shape, "text"):
            text.append(shape.text)
    
    # Write to PDF page
    y = 750
    for line in text:
        c.drawString(50, y, line[:80])  # Limit line length
        y -= 20
    c.showPage()

c.save()

# Return as binary
pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode()

items[0].binary = {
    'data': {
        'data': pdf_base64,
        'mimeType': 'application/pdf',
        'fileName': items[0].json.get('fileName', 'converted') + '.pdf'
    }
}

return items

**n8n Concept**: Code node can run Python! It has access to `items` array (input data).

**Important**: For Python to work in n8n:
- Your n8n instance needs Python installed
- Install packages: `pip install python-pptx reportlab Pillow`
- Or use Docker image with Python pre-installed

**Alternative (API-based)**:
If Python setup is complex, use external API:

// HTTP Request Node
Method: POST
URL: https://api.cloudconvert.com/v2/convert
Headers:
  Authorization: Bearer YOUR_API_KEY
  Content-Type: application/json
Body:
{
  "tasks": {
    "import-file": {
      "operation": "import/base64",
      "file": "{{ $binary.data.data }}",
      "filename": "{{ $binary.data.fileName }}"
    },
    "convert-file": {
      "operation": "convert",
      "input": "import-file",
      "output_format": "pdf"
    }
  }
}

**Which to choose?**
- **Python**: Free, full control, faster (no API calls)
- **API**: Easier setup, handles complex conversions, costs money

#### Sub-workflow 3B: DOCX to PDF Converter

Similar to 3A, create "Convert DOCX to PDF"

**Code Node (Python)**:
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import base64
from io import BytesIO

# Get DOCX data
docx_data = base64.b64decode(items[0].binary['data']['data'])

# Parse DOCX
doc = Document(BytesIO(docx_data))

# Create PDF
pdf_buffer = BytesIO()
c = canvas.Canvas(pdf_buffer, pagesize=letter)

y = 750
for paragraph in doc.paragraphs:
    text = paragraph.text
    if text:
        c.drawString(50, y, text[:80])
        y -= 20
        if y < 50:  # New page
            c.showPage()
            y = 750

c.save()

# Return as binary
pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode()

items[0].binary = {
    'data': {
        'data': pdf_base64,
        'mimeType': 'application/pdf',
        'fileName': items[0].json.get('fileName', 'converted') + '.pdf'
    }
}

return items

Required package: `pip install python-docx reportlab`

#### Step 3.3: Route to Correct Converter

**Back in main workflow**, after criteria loading, add **Switch Node** for file type:

**Rules**:
1. `{{ $json.fileType.toLowerCase() }}` equals `pdf` → Output 0 (skip conversion)
2. `{{ $json.fileType.toLowerCase() }}` equals `pptx` → Output 1 (PPTX converter)
3. `{{ $json.fileType.toLowerCase() }}` equals `docx` → Output 2 (DOCX converter)
4. Fallback → Error (unsupported file type)

**On each output**:
- **Output 0**: Continue directly (already PDF)
- **Output 1**: Add **Execute Workflow** node → Select "Convert PPTX to PDF"
- **Output 2**: Add **Execute Workflow** node → Select "Convert DOCX to PDF"

**n8n Concept**: Execute Workflow node calls another workflow. It's like calling a function in programming.

---

### MODULE 4: Content Extractor

#### Step 4.1: Extract Text and Tables from PDF

**Code Node (Python)** - Named "Extract PDF Content":

import pdfplumber
import base64
from io import BytesIO

# Get PDF binary data
pdf_data = base64.b64decode(items[0].binary['data']['data'])

# Open PDF
pdf_file = BytesIO(pdf_data)
extracted_content = {
    'text': [],
    'tables': [],
    'page_count': 0
}

with pdfplumber.open(pdf_file) as pdf:
    extracted_content['page_count'] = len(pdf.pages)
    
    for page_num, page in enumerate(pdf.pages, 1):
        # Extract text
        text = page.extract_text()
        if text:
            extracted_content['text'].append({
                'page': page_num,
                'content': text
            })
        
        # Extract tables
        tables = page.extract_tables()
        for table_num, table in enumerate(tables, 1):
            extracted_content['tables'].append({
                'page': page_num,
                'table_number': table_num,
                'data': table
            })

# Combine all text
all_text = '\n\n'.join([t['content'] for t in extracted_content['text']])

# Store in item
items[0].json['extractedText'] = all_text
items[0].json['extractedTables'] = extracted_content['tables']
items[0].json['pageCount'] = extracted_content['page_count']

return items

**Required package**: `pip install pdfplumber`

**n8n Concept**: Code nodes modify `items[0].json` to add new data fields. Next nodes can access this data.

#### Step 4.2: OCR for Images (Optional)

**Code Node (Python)** - Named "OCR Images":

import pytesseract
from pdf2image import convert_from_bytes
import base64

# Get PDF data
pdf_data = base64.b64decode(items[0].binary['data']['data'])

# Convert PDF to images
images = convert_from_bytes(pdf_data)

# OCR each page
ocr_text = []
for page_num, image in enumerate(images, 1):
    text = pytesseract.image_to_string(image)
    if text.strip():
        ocr_text.append({
            'page': page_num,
            'content': text
        })

# Combine OCR text with extracted text
items[0].json['ocrText'] = ocr_text
items[0].json['combinedContent'] = items[0].json['extractedText'] + '\n\n' + '\n\n'.join([t['content'] for t in ocr_text])

return items

**Required packages**: 
pip install pytesseract pdf2image
apt-get install tesseract-ocr poppler-utils  # System dependencies

**Settings**: Set **Continue on Fail** = `true` (OCR is optional)

**n8n Tip**: For Docker deployment, use custom Dockerfile:
FROM n8nio/n8n:latest
USER root
RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils
RUN pip install pdfplumber pytesseract pdf2image python-docx python-pptx reportlab
USER node

#### Step 4.3: Combine All Content

**Set Node** - Named "Prepare Content for AI":

// Fields to set:
{
  "fullContent": "{{ $json.combinedContent ?? $json.extractedText }}",
  "hasImages": "{{ $json.ocrText ? true : false }}",
  "hasTables": "{{ $json.extractedTables.length > 0 }}",
  "contentSummary": {
    "pages": "{{ $json.pageCount }}",
    "textLength": "{{ $json.extractedText.length }}",
    "tableCount": "{{ $json.extractedTables.length }}",
    "estimatedTokens": "{{ Math.ceil($json.extractedText.length / 4) }}"
  }
}

**n8n Concept**: Set node is visual way to transform data. Use it instead of Code node when possible (easier to maintain).

---

### MODULE 5: AI Evaluator

#### Step 5.1: Build Evaluation Prompt

**Code Node (JavaScript)** - Named "Build AI Prompt":

const item = items[0].json;

// Get criteria from earlier step
const criteria = item.evaluationCriteria;
const complianceType = item.criteriaTemplate;
const content = item.fullContent;

// Build structured prompt
const prompt = `You are an expert compliance evaluator specializing in ${complianceType}.

DOCUMENT CONTENT:
---
${content.substring(0, 12000)}  // Limit to ~3k tokens
---

EVALUATION CRITERIA:
${Object.entries(criteria).map(([key, val]) => 
  `- ${key} (${val.weight}%): ${val.description}`
).join('\n')}

TASK:
Evaluate this document against the criteria above. For each criterion:
1. Assign a score (0-100)
2. Provide specific evidence from the document
3. List gaps or missing elements

Return ONLY a valid JSON object in this exact format:
{
  "overallScore": <number 0-100>,
  "criteriaScores": {
    "technicalDepth": {"score": <number>, "evidence": "<string>", "gaps": "<string>"},
    "scalability": {"score": <number>, "evidence": "<string>", "gaps": "<string>"}
    // ... other criteria
  },
  "summary": "<brief overall assessment>",
  "recommendations": ["<recommendation 1>", "<recommendation 2>"]
}`;

items[0].json.aiPrompt = prompt;
return items;

**n8n Concept**: JavaScript Code nodes are great for string manipulation and complex logic.

#### Step 5.2: Call LLM API

**Option A: OpenAI GPT-4-mini** (Cost-effective)

Add **HTTP Request** node:

Method: POST
URL: https://api.openai.com/v1/chat/completions

Authentication: Header Auth
  Name: Authorization
  Value: Bearer {{ $env.OPENAI_API_KEY }}

Headers:
  Content-Type: application/json

Body (JSON):
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "system",
      "content": "You are a compliance evaluation expert. Always return valid JSON."
    },
    {
      "role": "user",
      "content": "{{ $json.aiPrompt }}"
    }
  ],
  "temperature": 0.3,
  "max_tokens": 2000,
  "response_format": { "type": "json_object" }
}

**n8n Concept**: `{{ $env.OPENAI_API_KEY }}` accesses environment variables. Set this in n8n settings or Docker environment.

**Cost Estimate**:
- Input: ~3,500 tokens × $0.15/1M = $0.0005
- Output: ~1,000 tokens × $0.60/1M = $0.0006
- **Total per evaluation: ~$0.001 (0.1 cent)**

**Option B: Anthropic Claude 3 Haiku** (Faster, cheaper)

Method: POST
URL: https://api.anthropic.com/v1/messages

Headers:
  x-api-key: {{ $env.ANTHROPIC_API_KEY }}
  anthropic-version: 2023-06-01
  Content-Type: application/json

Body:
{
  "model": "claude-3-haiku-20240307",
  "max_tokens": 2000,
  "messages": [
    {
      "role": "user",
      "content": "{{ $json.aiPrompt }}"
    }
  ]
}

**Cost**: ~$0.0004 per evaluation (60% cheaper than GPT-4-mini)

**Option C: Local Model (Free, slower)**

Use Ollama for free inference:

# Install Ollama locally
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.1:8b

**HTTP Request**:
Method: POST
URL: http://localhost:11434/api/chat

Body:
{
  "model": "llama3.1:8b",
  "messages": [
    {
      "role": "user",
      "content": "{{ $json.aiPrompt }}"
    }
  ],
  "stream": false,
  "format": "json"
}

**Trade-offs**:
| Model | Cost | Speed | Quality |
|-------|------|-------|---------|
| GPT-4-mini | $0.001 | Fast (2s) | Best |
| Claude Haiku | $0.0004 | Fastest (1s) | Excellent |
| Llama 3.1 | Free | Slow (10s) | Good |

**Recommendation**: Start with GPT-4-mini (best quality), switch to Claude if cost is concern.

#### Step 5.3: Parse AI Response

**Code Node (JavaScript)** - Named "Parse AI Response":

const item = items[0].json;

// Extract response (different structure per provider)
let aiResponse;

if (item.choices) {
  // OpenAI format
  aiResponse = JSON.parse(item.choices[0].message.content);
} else if (item.content) {
  // Anthropic format
  aiResponse = JSON.parse(item.content[0].text);
} else if (item.message) {
  // Ollama format
  aiResponse = JSON.parse(item.message.content);
}

// Validate response structure
if (!aiResponse.overallScore || !aiResponse.criteriaScores) {
  throw new Error('Invalid AI response format');
}

// Store parsed response
items[0].json.evaluationResults = aiResponse;

// Calculate pass/fail
const passingScore = item.passingScore || 70;
items[0].json.passed = aiResponse.overallScore >= passingScore;

return items;

**n8n Concept**: Always validate external API responses. Use `throw new Error()` to stop workflow on critical failures.

---

### MODULE 6: Output Formatter

#### Step 6.1: Structure Final Response

**Set Node** - Named "Format Output":

// Remove unnecessary fields, keep only results
{
  "complianceType": "{{ $json.criteriaTemplate }}",
  "fileName": "{{ $binary.data.fileName }}",
  "evaluationDate": "{{ $now.toISO() }}",
  "results": {
    "overallScore": "{{ $json.evaluationResults.overallScore }}",
    "passed": "{{ $json.passed }}",
    "passingThreshold": "{{ $json.passingScore }}",
    "criteriaScores": "{{ $json.evaluationResults.criteriaScores }}",
    "summary": "{{ $json.evaluationResults.summary }}",
    "recommendations": "{{ $json.evaluationResults.recommendations }}"
  },
  "metadata": {
    "pageCount": "{{ $json.pageCount }}",
    "hasImages": "{{ $json.hasImages }}",
    "hasTables": "{{ $json.hasTables }}",
    "processingTime": "{{ $now.diff($execution.startedAt, 'seconds').seconds }} seconds"
  }
}

#### Step 6.2: Return Response

**If using Webhook trigger**, add **Respond to Webhook** node:

Response Code: 200
Response Body:
{{ $json }}

**If using Manual trigger**, results appear in execution panel.

---

## Complete Workflow Summary

**Full node sequence**:

1. Webhook Trigger
    ↓
2. Validate Input (IF node)
    ↓ [True]
3. Switch: Compliance Type
    ├─→ [Output 0] Set: Data Strategy Criteria
    ├─→ [Output 1] Set: Data Architecture Criteria
    ├─→ [Output 2] Set: Data Governance Criteria
    └─→ [Output 3] Set: Data Quality Criteria
    ↓
4. Switch: File Type
    ├─→ [PDF] Continue
    ├─→ [PPTX] Execute Workflow: Convert PPTX to PDF
    └─→ [DOCX] Execute Workflow: Convert DOCX to PDF
    ↓
5. Code: Extract PDF Content
    ↓
6. Code: OCR Images (Continue on Fail = true)
    ↓
7. Set: Prepare Content for AI
    ↓
8. Code: Build AI Prompt
    ↓
9. HTTP Request: Call LLM API
    ↓
10. Code: Parse AI Response
    ↓
11. Set: Format Output
    ↓
12. Respond to Webhook

---

## Modular Components

### How to Swap Components

**Example: Switch from GPT-4-mini to Claude**

1. Find "HTTP Request: Call LLM API" node
2. Click to edit
3. Change URL to Anthropic endpoint
4. Update headers (remove Authorization, add x-api-key)
5. Adjust body structure
6. Update "Parse AI Response" node to handle Anthropic format

**No other nodes need changes!** That's modularity.

### Component Library

**File Converters**:
- ✅ PPTX → PDF (Sub-workflow)
- ✅ DOCX → PDF (Sub-workflow)
- 🔜 XLSX → PDF (future)
- 🔜 HTML → PDF (future)

**Content Extractors**:
- ✅ PDF text (pdfplumber)
- ✅ PDF tables (pdfplumber)
- ✅ Image OCR (pytesseract)
- 🔜 Audio transcription (Whisper)

**LLM Providers**:
- ✅ OpenAI (gpt-4o-mini)
- ✅ Anthropic (claude-3-haiku)
- ✅ Ollama (llama3.1)
- 🔜 Google (gemini-pro)
- 🔜 Azure OpenAI

**Compliance Templates**:
- ✅ Data Strategy
- ✅ Data Architecture
- ✅ Data Governance
- ✅ Data Quality
- 🔜 Security Policy
- 🔜 Privacy Impact Assessment

---

## Testing & Debugging

### Test Data (Manual Trigger)

**For initial testing**, use Manual Trigger with this data:

{
  "complianceType": "Data Architecture",
  "fileType": "pdf",
  "fileName": "test_architecture.pdf",
  "fileContent": "<paste base64 encoded PDF here>"
}

**How to get base64 content**:
# Linux/Mac
base64 your_file.pdf | tr -d '\n' > file_base64.txt

# Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your_file.pdf"))

### Debugging Tips

**1. Check Each Node's Output**

After execution, click each node to see:
- Input items (what it received)
- Output items (what it produced)
- Execution time
- Errors (if any)

**2. Use Console Logging**

In Code nodes:
# Python
print(f"Processing file: {items[0].json.get('fileName')}")
print(f"Extracted {len(items[0].json.get('extractedText', ''))} characters")

// JavaScript
console.log('Compliance type:', items[0].json.complianceType);
console.log('Criteria:', items[0].json.evaluationCriteria);

Logs appear in n8n execution panel.

**3. Test Sub-workflows Independently**

Open "Convert PPTX to PDF" workflow, add Manual Trigger with test PPTX, execute.

**4. Common Issues**

| Issue | Cause | Solution |
|-------|-------|----------|
| "Python not found" | n8n doesn't have Python | Use n8n Docker image with Python or install globally |
| "Module not found" | Missing Python package | `pip install <package>` in n8n environment |
| "Invalid binary data" | Base64 decoding error | Verify base64 string is valid |
| "AI returns invalid JSON" | LLM didn't follow format | Add `response_format: json_object` to OpenAI call |
| "Webhook timeout" | Execution > 30 seconds | Enable queue mode or optimize processing |

---

## Cost Optimization

### Current Cost Breakdown (per evaluation)

| Component | Cost | Notes |
|-----------|------|-------|
| File Conversion (API) | $0.002 | If using CloudConvert |
| File Conversion (Python) | $0 | Free (self-hosted) |
| PDF Extraction | $0 | Python libraries |
| LLM (GPT-4-mini) | $0.001 | ~4,500 tokens |
| LLM (Claude Haiku) | $0.0004 | ~4,500 tokens |
| LLM (Ollama) | $0 | Free (self-hosted) |
| **Total (cloud LLM)** | **$0.001-0.003** | **$1-3 per 1000 evaluations** |
| **Total (self-hosted)** | **$0** | **Free (hardware costs only)** |

### Optimization Strategies

**1. Use Smaller Models First**

If document < 10 pages:
  → Use GPT-4-mini ($0.001)
Else:
  → Chunk document, use Claude Haiku ($0.0004)

**2. Cache Extracted Content**

After extraction, store in database:
CREATE TABLE processed_documents (
  file_hash VARCHAR(64) PRIMARY KEY,
  extracted_content TEXT,
  created_at TIMESTAMP
);

If same file resubmitted, skip extraction (saves time, not cost).

**3. Batch Processing**

Process 100 documents in single workflow execution (queue mode):
- Reduces overhead
- Better resource utilization

**4. Local Models for High Volume**

If processing > 1000 docs/month:
- Initial cost: GPT-4-mini = $1
- Local Llama 3.1: $0

Break-even: Immediate (if you have GPU)

**Hardware req for Llama 3.1 8B**:
- RAM: 16GB
- GPU: 8GB VRAM (RTX 3060 Ti or better)
- Speed: ~10 tokens/sec

---

## Future Enhancements

### Phase 2 Features

**1. Multi-file Support**

Accept ZIP archives with multiple documents:
Input: compliance_package.zip
  ├─ architecture.pdf
  ├─ strategy.docx
  └─ governance.pptx

Process each → Aggregate scores

**2. Visual Analysis**

Extract and analyze diagrams:
# GPT-4 Vision API
{
  "model": "gpt-4-vision-preview",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Evaluate this architecture diagram"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
      ]
    }
  ]
}

**3. Comparative Analysis**

Compare document against previous versions:
Input: 
  - Current version (v2.0)
  - Previous version (v1.5)

Output:
  - What improved
  - What regressed
  - Delta score

**4. Interactive Feedback**

After evaluation, let user ask questions:
User: "Why did scalability score low?"
AI: "The document lacks cloud migration strategy and doesn't address data growth beyond 2 years."

**5. Auto-remediation Suggestions**

Generate document sections to fix gaps:
Gap: "Missing data retention policy"
AI generates:
  ### Data Retention Policy
  [Complete policy text based on industry standards]

### Advanced n8n Techniques

**1. Workflow Versioning**

Export workflows to Git:
# Export workflow
n8n export:workflow --id=<workflow_id> --output=./workflows/

# Commit to Git
git add workflows/compliance_evaluator.json
git commit -m "Add table extraction"

**2. Error Notifications**

Add Error Trigger workflow:
Error Trigger (global)
  ↓
Format Error Details
  ↓
Send to Slack:
  "⚠️ Compliance Evaluator failed
   File: {{ $json.fileName }}
   Error: {{ $json.error.message }}"

**3. Performance Monitoring**

Track execution metrics:
// Code node at end
const metrics = {
  workflow: $workflow.name,
  executionTime: $now.diff($execution.startedAt, 'seconds').seconds,
  fileSize: $binary.data.data.length,
  pageCount: $json.pageCount,
  llmTokens: $json.contentSummary.estimatedTokens,
  score: $json.evaluationResults.overallScore
};

// Send to analytics
await fetch('http://analytics-api/metrics', {
  method: 'POST',
  body: JSON.stringify(metrics)
});

return items;

**4. Queue Mode for Production**

Enable in docker-compose.yml:
services:
  n8n:
    environment:
      - EXECUTIONS_PROCESS=queue
      - QUEUE_BULL_REDIS_HOST=redis
  
  redis:
    image: redis:7
  
  n8n-worker:
    image: n8nio/n8n:latest
    command: worker
    deploy:
      replicas: 3

Benefits:
- Handle 1000+ concurrent evaluations
- Auto-scaling workers
- Fault tolerance

---

## n8n Best Practices for This Project

### 1. Naming Conventions

**Good**:
- `Extract PDF Content` (describes action)
- `Data Architecture Criteria` (specific)
- `Parse AI Response` (clear purpose)

**Bad**:
- `Code Node 1` (meaningless)
- `Process` (vague)
- `Temp` (unclear)

### 2. Use Sticky Notes

Add notes for complex sections:
📝 "This section converts all file types to PDF for uniform processing.
    Supported: PPTX, DOCX, PDF
    Future: XLSX, HTML"

### 3. Error Handling Strategy

**Critical nodes** (Continue on Fail = false):
- Input validation
- File conversion
- AI API call
- Output formatting

**Optional nodes** (Continue on Fail = true):
- Image OCR
- Table extraction enhancements

### 4. Environment Variables

Never hardcode:
// ❌ Bad
const apiKey = "sk-abc123...";

// ✅ Good
const apiKey = $env.OPENAI_API_KEY;

Set in n8n:
# Docker
environment:
  - OPENAI_API_KEY=sk-abc123...
  - ANTHROPIC_API_KEY=sk-ant-abc123...

### 5. Reusable Sub-workflows

Extract common patterns:
- File conversions (already done ✅)
- PDF extraction (candidate for sub-workflow)
- AI evaluation (could be sub-workflow for reuse)

---

## Deployment Checklist

Before going to production:

- [ ] All environment variables set
- [ ] Python packages installed
- [ ] Webhook authentication enabled
- [ ] Error Trigger workflow created
- [ ] Test with real documents (PDF, PPTX, DOCX)
- [ ] Load test (10+ concurrent requests)
- [ ] Monitor execution times
- [ ] Set up backup (export workflows)
- [ ] Document API endpoint for users
- [ ] Configure queue mode (if high volume)
- [ ] Set up logging/monitoring
- [ ] Cost tracking enabled

---

## API Usage Documentation

### Endpoint

POST https://your-n8n-instance.com/webhook/evaluate-compliance

### Headers

Content-Type: application/json
X-API-Key: your-secret-key

### Request Body

{
  "complianceType": "Data Architecture",
  "fileType": "pdf",
  "fileName": "architecture_plan_v2.pdf",
  "fileContent": "base64_encoded_content_here"
}

**Parameters**:

| Field | Type | Required | Options |
|-------|------|----------|---------|
| `complianceType` | string | Yes | "Data Strategy", "Data Architecture", "Data Governance", "Data Quality" |
| `fileType` | string | Yes | "pdf", "pptx", "docx" |
| `fileName` | string | Yes | Original filename |
| `fileContent` | string | Yes | Base64 encoded file |

### Response (Success)

{
  "complianceType": "Data Architecture",
  "fileName": "architecture_plan_v2.pdf",
  "evaluationDate": "2026-02-03T10:30:00.000Z",
  "results": {
    "overallScore": 82,
    "passed": true,
    "passingThreshold": 70,
    "criteriaScores": {
      "technicalDepth": {
        "score": 85,
        "evidence": "Document includes detailed data models, ER diagrams, and integration patterns...",
        "gaps": "Missing API versioning strategy"
      },
      "scalability": {
        "score": 78,
        "evidence": "Addresses horizontal scaling and load balancing...",
        "gaps": "No discussion of multi-region deployment"
      }
      // ... other criteria
    },
    "summary": "Strong technical architecture with clear implementation plan. Minor gaps in scalability and security documentation.",
    "recommendations": [
      "Add API versioning strategy section",
      "Include multi-region deployment considerations",
      "Expand security controls documentation"
    ]
  },
  "metadata": {
    "pageCount": 15,
    "hasImages": true,
    "hasTables": true,
    "processingTime": "8 seconds"
  }
}

### Response (Error)

{
  "status": "error",
  "message": "Missing required field: complianceType",
  "code": "VALIDATION_ERROR"
}

### Example cURL

curl -X POST https://your-n8n-instance.com/webhook/evaluate-compliance \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "complianceType": "Data Architecture",
    "fileType": "pdf",
    "fileName": "test.pdf",
    "fileContent": "'"$(base64 test.pdf | tr -d '\n')"'"
  }'

---

## Conclusion

You now have a **complete, production-ready compliance evaluation system** built in n8n!

**What you learned**:
- ✅ n8n fundamentals (nodes, items, expressions)
- ✅ Webhook triggers and API integration
- ✅ Modular workflow design
- ✅ Python code nodes for document processing
- ✅ AI/LLM integration (OpenAI, Anthropic, Ollama)
- ✅ Error handling and debugging
- ✅ Cost optimization strategies
- ✅ Production deployment best practices

**Next steps**:
1. Deploy to n8n instance (Docker recommended)
2. Test with your actual compliance documents
3. Adjust evaluation criteria to match your standards
4. Monitor performance and costs
5. Iterate and enhance!

**Questions? Check**:
- n8n Community Forum: https://community.n8n.io
- This guide's debugging section
- n8n official docs: https://docs.n8n.io

**Pro tip**: Start simple (PDF only, one compliance type), then expand. Modular design makes this easy!

Happy automating! 🚀
