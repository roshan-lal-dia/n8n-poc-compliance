import json

file_path = 'workflows/unifi-npc-compliance/workflow-c1-audit-entry.json'
with open(file_path, 'r') as f:
    wf = json.load(f)

# Find the node
node = next(n for n in wf['nodes'] if n['name'] == 'Parse & Validate Input')

# New Code
new_js = r"""// Parse multipart form data and extract files + questions mapping
const crypto = require('crypto');
const items = $input.all();
const firstItem = items[0];

// Get questions JSON from form data (try multiple locations)
let questionsRaw = firstItem.json?.questions || firstItem.json?.body?.questions || firstItem.json?.query?.questions;

// Debug logging
console.log('First item keys:', Object.keys(firstItem.json || {}));
console.log('Questions raw value:', questionsRaw);

if (!questionsRaw) {
  throw new Error('Missing "questions" parameter. Expected JSON array: [{"q_id":"q1","files":["file1.pdf"]}]. Received structure: ' + JSON.stringify(Object.keys(firstItem.json || {})));
}

let questions;
try {
  questions = typeof questionsRaw === 'string' ? JSON.parse(questionsRaw) : questionsRaw;
} catch (e) {
  throw new Error('Invalid questions JSON format: ' + e.message);
}

if (!questions || !Array.isArray(questions) || questions.length === 0) {
  throw new Error('Questions must be non-empty array. Got: ' + typeof questions);
}

// Extract domain (optional, can be inferred from questions)
const domain = firstItem.json?.domain || firstItem.json?.body?.domain || firstItem.json?.query?.domain || 'General';

// Calculate file stats and validate total size
// We keep the original binary object to avoid data loss (corruption to 9 bytes)
let totalSize = 0;
const fileMetadata = [];

if (firstItem.binary) {
  for (const [fieldName, binaryData] of Object.entries(firstItem.binary)) {
    if (binaryData && binaryData.data) {
      const fileSize = Buffer.byteLength(binaryData.data, 'base64');
      totalSize += fileSize;
      
      fileMetadata.push({
        fieldName: fieldName,
        fileName: binaryData.fileName || fieldName,
        fileSize: fileSize,
        mimeType: binaryData.mimeType || 'application/octet-stream'
      });
    }
  }
}

// Enforce 500MB total limit for large file support
if (totalSize > 500 * 1024 * 1024) {
  throw new Error(`Total file size exceeds 500MB limit (current: ${Math.round(totalSize/1024/1024)}MB)`);
}

// Validate: each question references valid uploaded files
for (const q of questions) {
  if (!q.q_id) {
    throw new Error('Each question must have a "q_id" field');
  }
  if (!q.files || !Array.isArray(q.files) || q.files.length === 0) {
    throw new Error(`Question ${q.q_id} has no files specified`);
  }
  
  for (const fileName of q.files) {
    const found = fileMetadata.find(f => f.fieldName === fileName);
    if (!found) {
      throw new Error(`Question ${q.q_id} references file "${fileName}" which was not uploaded`);
    }
  }
}

// Update JSON content but preserve original binary attachment
firstItem.json = {
  questions,
  domain,
  files: fileMetadata,
  totalSizeMB: Math.round(totalSize / 1024 / 1024 * 100) / 100,
  totalFiles: fileMetadata.length
};

return [firstItem];"""

node['parameters']['jsCode'] = new_js

with open(file_path, 'w') as f:
    json.dump(wf, f, indent=2)
    
print("Successfully patched Parse & Validate Input node")
