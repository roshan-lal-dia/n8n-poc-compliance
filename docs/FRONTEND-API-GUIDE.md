# Frontend API Integration Guide

**Compliance Audit System - Multi-Question Support**  
**Version:** 2.0 (Multi-Question + Background Processing)  
**Last Updated:** February 10, 2026

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Submit Audit (Multi-Question & Multi-File)](#submit-audit)
4. [Poll Status (Real-time Progress)](#poll-status)
5. [Get Results](#get-results)
6. [Error Handling](#error-handling)
7. [Frontend Implementation Examples](#frontend-implementation-examples)
8. [File Size Considerations](#file-size-considerations)
9. [Testing & Debugging](#testing--debugging)

---

## Quick Start

**Base URL:** `http://<VM_IP>:5678`

**Complete Flow:**

```javascript
// 1. Submit audit (returns immediately)
const { sessionId } = await submitAudit(questions, files);

// 2. Poll for progress (every 3 seconds)
const status = await pollUntilComplete(sessionId);

// 3. Get results
const results = await getResults(sessionId);
```

---

## Authentication

**Current:** HTTP Basic Auth (n8n built-in)

```javascript
const headers = {
  'Authorization': 'Basic ' + btoa('admin:ComplianceAdmin2026!')
};
```

**Note:** Webhook endpoints may bypass auth - confirm with n8n settings.

---

## Submit Audit

### Endpoint

```
POST /webhook/audit/submit
Content-Type: multipart/form-data
```

### Request Format

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `questions` | JSON string | Yes | Array of question-file mappings |
| `domain` | String | No | Domain for filtering standards (auto-detected if omitted) |
| `<fileName>` | Binary | Yes | File data (field name must match `questions` mapping) |

**Questions JSON Structure:**

```json
[
  {
    "q_id": "privacy_q1",
    "files": ["privacy_policy.pdf", "data_flow_diagram.png"]
  },
  {
    "q_id": "security_q1",
    "files": ["security_assessment.docx"]
  }
]
```

**Rules:**
- Each `q_id` must exist in `audit_questions` table
- Each file name in `files` array must match an uploaded file field name
- Files can be shared across questions (will be deduplicated during processing)
- Maximum total upload size: 500MB

### JavaScript Example (Fetch API)

```javascript
async function submitAudit(questions, fileMap, domain = 'General') {
  const formData = new FormData();
  
  // Add questions JSON
  formData.append('questions', JSON.stringify(questions));
  
  // Add domain (optional)
  formData.append('domain', domain);
  
  // Add file binaries
  for (const [fileName, fileBlob] of Object.entries(fileMap)) {
    formData.append(fileName, fileBlob, fileName);
  }
  
  const response = await fetch('http://172.206.67.83:5678/webhook/audit/submit', {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Submission failed');
  }
  
  return await response.json();
}

// Usage:
const questions = [
  { q_id: 'privacy_q1', files: ['report.pdf'] },
  { q_id: 'privacy_q2', files: ['appendix.docx'] }
];

const files = {
  'report.pdf': pdfFileBlob,      // File object from <input type="file">
  'appendix.docx': docxFileBlob
};

const result = await submitAudit(questions, files, 'Privacy');
console.log(result);
```

### Response (202 Accepted)

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "jobId": "abc-123-def-456",
  "status": "queued",
  "totalQuestions": 2,
  "message": "Audit submitted successfully. Poll /webhook/audit/status/550e8400-e29b-41d4-a716-446655440000 for progress.",
  "estimatedCompletionMinutes": 5
}
```

**Status Code:** `202 Accepted` (job queued, not yet processed)

### React Example with File Upload

```jsx
import React, { useState } from 'react';

function AuditSubmissionForm() {
  const [files, setFiles] = useState({});
  const [questions, setQuestions] = useState([
    { q_id: 'privacy_q1', files: [] }
  ]);
  
  const handleFileUpload = (e, questionIndex) => {
    const uploadedFiles = Array.from(e.target.files);
    
    // Update files map
    const newFiles = { ...files };
    uploadedFiles.forEach(file => {
      newFiles[file.name] = file;
    });
    setFiles(newFiles);
    
    // Update questions array
    const newQuestions = [...questions];
    newQuestions[questionIndex].files = uploadedFiles.map(f => f.name);
    setQuestions(newQuestions);
  };
  
  const handleSubmit = async () => {
    try {
      const result = await submitAudit(questions, files, 'Privacy');
      
      // Navigate to status page
      window.location.href = `/audit/status/${result.sessionId}`;
    } catch (error) {
      alert('Submission failed: ' + error.message);
    }
  };
  
  return (
    <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
      {questions.map((q, index) => (
        <div key={index}>
          <label>Question: {q.q_id}</label>
          <input 
            type="file" 
            multiple 
            accept=".pdf,.docx,.pptx,.png,.jpg"
            onChange={(e) => handleFileUpload(e, index)}
          />
        </div>
      ))}
      <button type="submit">Submit Audit</button>
    </form>
  );
}
```

---

## Poll Status

### Endpoint

```
GET /webhook/audit/status/:sessionId
```

### Response

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "jobId": "abc-123-def-456",
  "status": "processing",
  "domain": "Privacy",
  "overallPercentage": 47,
  "totalQuestions": 2,
  "answeredQuestions": 1,
  "currentStep": "evaluating",
  "startedAt": "2026-02-10T10:30:00.000Z",
  "completedAt": null,
  "estimatedCompletionAt": "2026-02-10T10:35:00.000Z",
  "overallScore": null,
  "questionProgress": [
    {
      "qId": "privacy_q1",
      "status": "success",
      "step": "completed",
      "percentage": 100,
      "lastUpdate": "2026-02-10T10:33:42.000Z"
    },
    {
      "qId": "privacy_q2",
      "status": "in_progress",
      "step": "evaluating",
      "percentage": 85,
      "lastUpdate": "2026-02-10T10:34:52.000Z"
    }
  ]
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `queued` | Job in Redis queue, not yet started |
| `processing` | Worker actively processing questions |
| `completed` | All questions evaluated successfully |
| `failed` | Error occurred during processing |

### Step Values

| Step | Percentage Range | Description |
|------|------------------|-------------|
| `queued` | 0-5% | Waiting in queue |
| `extracting` | 10-30% | Calling Workflow A for file extraction |
| `searching` | 30-80% | Generating embeddings, querying Qdrant |
| `evaluating` | 85-95% | Ollama AI evaluation |
| `completed` | 100% | Done |

### JavaScript Polling Implementation

```javascript
async function pollUntilComplete(sessionId, onProgress = null) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`http://172.206.67.83:5678/webhook/audit/status/${sessionId}`);
        
        if (!response.ok) {
          clearInterval(interval);
          reject(new Error('Status polling failed'));
          return;
        }
        
        const status = await response.json();
        
        // Callback for UI updates
        if (onProgress) {
          onProgress(status);
        }
        
        // Check completion
        if (status.status === 'completed') {
          clearInterval(interval);
          resolve(status);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          reject(new Error('Audit processing failed'));
        }
        
      } catch (error) {
        clearInterval(interval);
        reject(error);
      }
    }, 3000);  // Poll every 3 seconds
  });
}

// Usage:
const finalStatus = await pollUntilComplete(
  sessionId,
  (status) => {
    console.log(`Progress: ${status.overallPercentage}%`);
    updateProgressBar(status.overallPercentage);
  }
);
```

### React Progress Component

```jsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

function AuditStatus() {
  const { sessionId } = useParams();
  const [status, setStatus] = useState(null);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch(`/webhook/audit/status/${sessionId}`);
      const data = await res.json();
      setStatus(data);
      
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(interval);
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, [sessionId]);
  
  if (!status) return <div>Loading...</div>;
  
  return (
    <div>
      <h2>Audit Progress</h2>
      <progress value={status.overallPercentage} max={100} />
      <p>{status.overallPercentage}% - {status.currentStep}</p>
      
      <ul>
        {status.questionProgress.map(q => (
          <li key={q.qId}>
            {q.qId}: {q.percentage}% ({q.step})
          </li>
        ))}
      </ul>
      
      {status.status === 'completed' && (
        <button onClick={() => window.location.href = `/audit/results/${sessionId}`}>
          View Results
        </button>
      )}
    </div>
  );
}
```

---

## Get Results

### Endpoint

```
GET /webhook/audit/results/:sessionId
```

**Prerequisite:** Session status must be `completed`

### Response

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "Privacy",
  "status": "completed",
  "startedAt": "2026-02-10T10:30:00.000Z",
  "completedAt": "2026-02-10T10:35:42.000Z",
  "totalQuestions": 2,
  "answeredQuestions": 2,
  "overallScore": 83.5,
  "results": [
    {
      "qId": "privacy_q1",
      "question": "Are there documented access controls and PII handling procedures?",
      "questionDomain": "Privacy",
      "evaluation": {
        "compliant": true,
        "score": 87,
        "confidence": 85,
        "findings": "Comprehensive PII handling procedures documented in Section 3. RBAC implementation clearly described with role definitions...",
        "evidence_summary": "Found explicit references in privacy_policy.pdf pages 5-8. Data classification matrix on page 7 shows PII categories...",
        "gaps": [],
        "recommendations": [
          "Consider implementing automated PII discovery tools",
          "Add data retention schedule documentation"
        ]
      },
      "evaluatedAt": "2026-02-10T10:33:42.000Z"
    },
    {
      "qId": "privacy_q2",
      "question": "Does the system implement proper data encryption at rest and in transit?",
      "questionDomain": "Privacy",
      "evaluation": {
        "compliant": true,
        "score": 80,
        "confidence": 90,
        "findings": "Encryption at rest: AES-256 confirmed. TLS 1.3 for transport. Key management via AWS KMS documented.",
        "evidence_summary": "Technical spec in security_assessment.docx Section 4.2. Architecture diagram shows encryption layers.",
        "gaps": [
          "Key rotation schedule not explicitly documented"
        ],
        "recommendations": [
          "Document automated key rotation frequency",
          "Add encryption performance monitoring metrics"
        ]
      },
      "evaluatedAt": "2026-02-10T10:35:38.000Z"
    }
  ],
  "summary": {
    "compliantCount": 2,
    "nonCompliantCount": 0,
    "averageConfidence": 88
  }
}
```

### JavaScript Implementation

```javascript
async function getResults(sessionId) {
  const response = await fetch(`http://172.206.67.83:5678/webhook/audit/results/${sessionId}`);
  
  if (response.status === 404) {
    throw new Error('Session not found or not completed yet');
  }
  
  if (!response.ok) {
    throw new Error('Failed to fetch results');
  }
  
  return await response.json();
}

// Usage:
const results = await getResults(sessionId);
console.log(`Overall Score: ${results.overallScore}`);
results.results.forEach(r => {
  console.log(`${r.qId}: ${r.evaluation.score} (${r.evaluation.compliant ? 'PASS' : 'FAIL'})`);
});
```

### React Results Component

```jsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

function AuditResults() {
  const { sessionId } = useParams();
  const [results, setResults] = useState(null);
  
  useEffect(() => {
    fetch(`/webhook/audit/results/${sessionId}`)
      .then(res => res.json())
      .then(data => setResults(data))
      .catch(err => console.error(err));
  }, [sessionId]);
  
  if (!results) return <div>Loading results...</div>;
  
  return (
    <div>
      <h1>Audit Results</h1>
      <div className="summary">
        <h2>Overall Score: {results.overallScore}/100</h2>
        <p>
          {results.summary.compliantCount} Compliant | 
          {results.summary.nonCompliantCount} Non-Compliant
        </p>
        <p>Average Confidence: {results.summary.averageConfidence}%</p>
      </div>
      
      {results.results.map(r => (
        <div key={r.qId} className="question-result">
          <h3>{r.question}</h3>
          <div className={r.evaluation.compliant ? 'pass' : 'fail'}>
            Score: {r.evaluation.score}/100 | 
            Confidence: {r.evaluation.confidence}% |
            {r.evaluation.compliant ? ' COMPLIANT' : ' NON-COMPLIANT'}
          </div>
          
          <div className="findings">
            <h4>Findings</h4>
            <p>{r.evaluation.findings}</p>
          </div>
          
          {r.evaluation.gaps.length > 0 && (
            <div className="gaps">
              <h4>Gaps Identified</h4>
              <ul>
                {r.evaluation.gaps.map((gap, i) => (
                  <li key={i}>{gap}</li>
                ))}
              </ul>
            </div>
          )}
          
          {r.evaluation.recommendations.length > 0 && (
            <div className="recommendations">
              <h4>Recommendations</h4>
              <ul>
                {r.evaluation.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Example Response |
|------|---------|------------------|
| 202 | Accepted | Job queued successfully |
| 400 | Bad Request | Invalid question ID or missing files |
| 404 | Not Found | Session doesn't exist |
| 413 | Payload Too Large | Files exceed 500MB |
| 500 | Server Error | Internal processing error |

### Error Response Format

```json
{
  "error": "Question security_q99 references file \"nonexistent.pdf\" which was not uploaded",
  "status": 400
}
```

### JavaScript Error Handling

```javascript
async function submitAuditSafe(questions, files, domain) {
  try {
    const result = await submitAudit(questions, files, domain);
    return { success: true, data: result };
    
  } catch (error) {
    // Network error
    if (!error.response) {
      return {
        success: false,
        error: 'Network error - check connection'
      };
    }
    
    // Server error
    const errorBody = await error.response.json();
    
    if (error.response.status === 400) {
      return {
        success: false,
        error: `Validation error: ${errorBody.error}`
      };
    } else if (error.response.status === 413) {
      return {
        success: false,
        error: 'Files too large - maximum 500MB total'
      };
    } else {
      return {
        success: false,
        error: `Server error: ${errorBody.error || 'Unknown'}`
      };
    }
  }
}
```

---

## Frontend Implementation Examples

### Complete Vanilla JS Workflow

```html
<!DOCTYPE html>
<html>
<head>
  <title>Compliance Audit</title>
</head>
<body>
  <h1>Submit Compliance Audit</h1>
  
  <form id="auditForm">
    <div>
      <label>Question ID:</label>
      <input type="text" id="qId" value="privacy_q1" />
    </div>
    
    <div>
      <label>Evidence Files:</label>
      <input type="file" id="files" multiple accept=".pdf,.docx,.pptx" />
    </div>
    
    <button type="submit">Submit</button>
  </form>
  
  <div id="status" style="display:none">
    <h2>Processing...</h2>
    <progress id="progress" max="100"></progress>
    <p id="statusText"></p>
  </div>
  
  <div id="results" style="display:none">
    <h2>Results</h2>
    <pre id="resultsJson"></pre>
  </div>
  
  <script>
    const API_BASE = 'http://172.206.67.83:5678';
    
    document.getElementById('auditForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      
      // Collect form data
      const qId = document.getElementById('qId').value;
      const fileInput = document.getElementById('files');
      const files = {};
      
      for (const file of fileInput.files) {
        files[file.name] = file;
      }
      
      const questions = [{
        q_id: qId,
        files: Object.keys(files)
      }];
      
      // Submit
      const formData = new FormData();
      formData.append('questions', JSON.stringify(questions));
      for (const [name, file] of Object.entries(files)) {
        formData.append(name, file);
      }
      
      const submitRes = await fetch(`${API_BASE}/webhook/audit/submit`, {
        method: 'POST',
        body: formData
      });
      
      const { sessionId } = await submitRes.json();
      
      // Show status
      document.getElementById('auditForm').style.display = 'none';
      document.getElementById('status').style.display = 'block';
      
      // Poll status
      const interval = setInterval(async () => {
        const statusRes = await fetch(`${API_BASE}/webhook/audit/status/${sessionId}`);
        const status = await statusRes.json();
        
        document.getElementById('progress').value = status.overallPercentage;
        document.getElementById('statusText').textContent = 
          `${status.overallPercentage}% - ${status.currentStep}`;
        
        if (status.status === 'completed') {
          clearInterval(interval);
          
          // Fetch results
          const resultsRes = await fetch(`${API_BASE}/webhook/audit/results/${sessionId}`);
          const results = await resultsRes.json();
          
          document.getElementById('status').style.display = 'none';
          document.getElementById('results').style.display = 'block';
          document.getElementById('resultsJson').textContent = 
            JSON.stringify(results, null, 2);
        }
      }, 3000);
    });
  </script>
</body>
</html>
```

### Vue.js Example

```vue
<template>
  <div id="app">
    <div v-if="phase === 'upload'">
      <h1>Submit Audit</h1>
      <form @submit.prevent="submitAudit">
        <select v-model="selectedQuestion">
          <option value="privacy_q1">Privacy Q1</option>
          <option value="privacy_q2">Privacy Q2</option>
          <option value="security_q1">Security Q1</option>
        </select>
        
        <input type="file" ref="fileInput" multiple />
        
        <button type="submit">Submit</button>
      </form>
    </div>
    
    <div v-if="phase === 'processing'">
      <h2>Processing Audit...</h2>
      <progress :value="status.overallPercentage" max="100"></progress>
      <p>{{ status.currentStep }} - {{ status.overallPercentage }}%</p>
    </div>
    
    <div v-if="phase === 'results'">
      <h2>Audit Results</h2>
      <div v-for="result in results.results" :key="result.qId">
        <h3>{{ result.question }}</h3>
        <p>Score: {{ result.evaluation.score }}/100</p>
        <p>{{ result.evaluation.findings }}</p>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      phase: 'upload',
      selectedQuestion: 'privacy_q1',
      sessionId: null,
      status: {},
      results: null
    };
  },
  methods: {
    async submitAudit() {
      const files = this.$refs.fileInput.files;
      const formData = new FormData();
      
      const questions = [{
        q_id: this.selectedQuestion,
        files: Array.from(files).map(f => f.name)
      }];
      
      formData.append('questions', JSON.stringify(questions));
      for (const file of files) {
        formData.append(file.name, file);
      }
      
      const res = await fetch('http://172.206.67.83:5678/webhook/audit/submit', {
        method: 'POST',
        body: formData
      });
      
      const data = await res.json();
      this.sessionId = data.sessionId;
      this.phase = 'processing';
      
      this.pollStatus();
    },
    
    async pollStatus() {
      const interval = setInterval(async () => {
        const res = await fetch(`http://172.206.67.83:5678/webhook/audit/status/${this.sessionId}`);
        this.status = await res.json();
        
        if (this.status.status === 'completed') {
          clearInterval(interval);
          await this.fetchResults();
        }
      }, 3000);
    },
    
    async fetchResults() {
      const res = await fetch(`http://172.206.67.83:5678/webhook/audit/results/${this.sessionId}`);
      this.results = await res.json();
      this.phase = 'results';
    }
  }
};
</script>
```

---

## File Size Considerations

### Limits

| Limit | Value | Enforcement |
|-------|-------|-------------|
| Single file upload | ~100MB (practical limit) | Browser/network timeout |
| Total file size | 500MB | Server validation (returns 400) |
| Evidence in prompt | 200KB (200,000 chars) | Truncation (silent) |
| Per-file in prompt | 50KB (50,000 chars) | Truncation (silent) |

### Handling Large Files

**Problem:** 300MB PDF takes 3-5 minutes to extract (OCR + Vision).

**Solutions:**

1. **Pre-Process:**
   ```javascript
   // Compress PDFs before upload
   await compressPDF(file, { quality: 'medium' });
   ```

2. **Split Files:**
   ```javascript
   // Split large document into chapters
   const chapters = await splitPDF(largePDF, maxPages: 50);
   // Submit as separate evidence files
   ```

3. **Show ETA:**
   ```javascript
   // Estimate based on file size
   const estimateMinutes = Math.ceil(totalSizeMB / 10);
   alert(`Estimated completion: ${estimateMinutes} minutes`);
   ```

---

## Testing & Debugging

### Test with cURL

**Submit Audit:**
```bash
curl -X POST http://172.206.67.83:5678/webhook/audit/submit \
  -F 'questions=[{"q_id":"privacy_q1","files":["test.pdf"]}]' \
  -F 'test.pdf=@/path/to/test.pdf' \
  -F 'domain=Privacy'
```

**Check Status:**
```bash
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"
curl http://172.206.67.83:5678/webhook/audit/status/$SESSION_ID
```

**Get Results:**
```bash
curl http://172.206.67.83:5678/webhook/audit/results/$SESSION_ID
```

### Browser DevTools Network Tab

1. Open DevTools (F12)
2. Submit audit
3. Check Network tab for:
   - `audit/submit`: Should return 202, check response JSON
   - `audit/status`: Should return 200, check `overallPercentage` increasing
   - `audit/results`: Should return 200 when complete

### Common Issues

**"Missing file in request"**
- Check `questions` JSON field names match file field names exactly

**"Question references file not uploaded"**
- Verify file field name in FormData matches `files` array in questions

**"Session not found"**
- Check sessionId spelling
- Verify session wasn't deleted (shouldn't happen, but check DB)

**Status stuck at queued**
- Check Redis queue: `docker exec compliance-redis redis-cli LLEN compliance:jobs:pending`
- Check worker logs: `docker logs compliance-n8n --tail 100`

---

## Postman Collection

```json
{
  "info": { "name": "Compliance Audit API" },
  "item": [
    {
      "name": "Submit Audit",
      "request": {
        "method": "POST",
        "url": "{{baseUrl}}/webhook/audit/submit",
        "body": {
          "mode": "formdata",
          "formdata": [
            { "key": "questions", "value": "[{\"q_id\":\"privacy_q1\",\"files\":[\"test.pdf\"]}]", "type": "text" },
            { "key": "test.pdf", "type": "file", "src": "/path/to/test.pdf" },
            { "key": "domain", "value": "Privacy", "type": "text" }
          ]
        }
      }
    },
    {
      "name": "Get Status",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/webhook/audit/status/{{sessionId}}"
      }
    },
    {
      "name": "Get Results",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/webhook/audit/results/{{sessionId}}"
      }
    }
  ],
  "variable": [
    { "key": "baseUrl", "value": "http://172.206.67.83:5678" },
    { "key": "sessionId", "value": "550e8400-e29b-41d4-a716-446655440000" }
  ]
}
```

---

## Summary Checklist

✅ **Submission:**
- [ ] Questions JSON correctly formatted
- [ ] All files referenced in questions are uploaded
- [ ] Total size < 500MB
- [ ] Handle 202 response, save sessionId

✅ **Polling:**
- [ ] Poll every 3 seconds (not more frequently)
- [ ] Update UI with percentage/step
- [ ] Stop polling when status = 'completed' or 'failed'

✅ **Results:**
- [ ] Only fetch when status = 'completed'
- [ ] Display overallScore prominently
- [ ] Show individual question results
- [ ] Highlight gaps and recommendations

✅ **Error Handling:**
- [ ] Network errors (retry logic)
- [ ] 400 errors (show validation message)
- [ ] 404 errors (session not found)
- [ ] Timeout handling (large files)

---

For questions or support, check:
- [Audit Transparency Guide](./AUDIT-TRANSPARENCY-GUIDE.md) - How the system works internally
- [Workflow Guide](../workflows/WORKFLOW-GUIDE.md) - Workflow architecture
- n8n logs: `docker logs compliance-n8n`
