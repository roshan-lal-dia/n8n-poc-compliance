# Agent Context: n8n Workflow Error Handling Fixes
> Generated: 2026-03-03 | Repo: roshan-lal-dia/n8n-poc-compliance | Branch: new-arch
> Use this as first-message context for a new agent session fixing remaining workflows.

---

## 1. Project Overview

n8n 2.6.3 (Self Hosted) compliance audit system.

**Workflows:**
| File | Purpose | Priority |
|------|---------|----------|
| `workflow-c1-audit-entry.json` | Webhook: receives audit job, writes files, enqueues to Redis | ✅ DONE |
| `workflow-a-universal-extractor.json` | Webhook: extracts text/images from uploaded files (PDF/PPTX/DOCX/Excel) | HIGH |
| `workflow-c2-audit-worker.json` | Cron: dequeues Redis jobs, calls A, runs AI eval, writes results to DB | HIGH |
| `workflow-c3-status-poll.json` | Webhook: GET audit job status | HIGH |
| `workflow-c4-results-retrieval.json` | Webhook: GET audit results | HIGH |
| `workflow-b-kb-ingestion.json` | Webhook: ingest knowledge base standards | LOW |
| `workflow-admin-postgres.json` | Webhook: admin DB queries | DO NOT TOUCH |

**Infrastructure:**
- Azure Blob Storage account: `stcompdldevqc01`, container: `complianceblobdev`
- Postgres credential ID: `3ME8TvhWnolXkgqg` name: `postgres-compliance`
- Redis credential ID: `K8jo4houPYYpv2hq` name: `redis-compliance`
- n8n webhook auth credential ID: `webhook-api-key` name: `webhook-api-key`
- Temp files: `/tmp/n8n_processing/`

---

## 2. Root Cause: Why All Workflows Had Silent 200s on Error

### Problem A — `continueOnFail: true` on every node (cascading garbage)
When node A fails with `continueOnFail`, n8n passes `{ "error": "message [line N]" }` as the output JSON to the next node. Node B then tries to use `$json.filePath`, `$json.sessionId`, etc. — gets `undefined`, throws its own useless secondary error. This cascades all the way down, final node gets garbage, response is either 200 or the error message is completely unrelated to the real failure.

**Fix:** Only put `continueOnFail: true` on nodes where you need to explicitly route the error to a different path (Respond 400/500). All other nodes should fail naturally — since `responseMode: "responseNode"` is set, n8n auto-returns 500 if no `Respond to Webhook` node has fired yet.

### Problem B — Wrong `responseMode`
Old value `"onReceived"` fires 202 instantly before any node runs. Client always gets 200/202 regardless of errors.

**Fix:** Webhook node `parameters.responseMode` must be `"responseNode"`.

### Problem C — `Error Trigger` node in same workflow
`Error Trigger` is designed for **separate notification workflows** (e.g. send Slack alert). When placed in the same workflow, it fires in PARALLEL with the success path — not instead of it. The client still sees the success response (or timeout).

**Fix:** Remove `Error Trigger`, `Format Pipeline Error`, and any `Respond: Pipeline Error` nodes connected to it. Replace with explicit `continueOnFail` + IF check only at the points where you need user-facing error messages.

### Problem D — Blob URL encoding
`blobPath` values with spaces (e.g. `Data Quality Scorecard Report Template.pptx`) are put raw into the HTTPS GET URL → Azure returns 404 BlobNotFound. The `canonicalizedResource` for SAS signing must use the **raw** (unencoded) path (Azure spec requirement), but the actual HTTPS URL needs `%20`.

**Fix applied in C1 — apply same fix to all Fetch Azure Blob nodes:**
```js
// WRONG:
return `https://${accountName}.blob.core.windows.net/${container}/${blobPath}?${qs}`;

// CORRECT:
const encodedBlobPath = blobPath.split('/').map(s => encodeURIComponent(s)).join('/');
return `https://${accountName}.blob.core.windows.net/${container}/${encodedBlobPath}?${qs}`;
// Note: canonicalizedResource above still uses raw blobPath — DO NOT encode that
```

### Problem E — IF node `typeValidation: "strict"`
When `$json.error` is `undefined` (node succeeded, no error field on output), strict type validation throws a type error instead of evaluating false. Causes the IF node itself to error.

**Fix:** Set `parameters.conditions.options.typeValidation` to `"loose"` on all IF nodes that check `$json.error`.

### Problem F — Duplicate `Fetch Azure Blob` nodes with same ID
Workflows A and B have two nodes both named `"Fetch Azure Blob"` with the **same node ID**. This breaks n8n's internal deduplication — one effectively shadows the other. Only one should exist per workflow.

**Fix:** Remove the duplicate (second occurrence). Keep the one that is actually connected in `connections`.

---

## 3. Correct Error Handling Pattern (established in C1)

### For webhook workflows (C1, A, B, C3, C4):

```
Webhook (responseMode: responseNode)
  └─> [optional] Fetch Azure Blob (continueOnFail: true)
        └─> IF: Blob Error? (typeValidation: loose, checks $json.error notEmpty)
              ├─ TRUE  ──> Respond: Pipeline Error (500)
              └─ FALSE ──> [next node]
                              └─> Validate/Parse (continueOnFail: true)
                                    └─> IF: Validation Error? (typeValidation: loose)
                                          ├─ TRUE  ──> Respond: Validation Error (400)
                                          └─ FALSE ──> [pipeline nodes - NO continueOnFail]
                                                          └─> ... 
                                                                └─> Respond: Success (202/200)
```

**Key rules:**
- Pipeline nodes (DB, Redis, file writes, code transforms) — **NO `continueOnFail`**. Let them throw. n8n returns 500 automatically since no Respond node has fired.
- Only the entry validation nodes get `continueOnFail` so errors can be routed to an explicit 400 response.
- `Respond: Pipeline Error` catches blob fetch failures explicitly.
- Remove all: `Error Trigger`, `Format Pipeline Error` nodes from webhook workflows.

### For cron/worker workflows (C2):
C2 is a background worker (Cron trigger), not a webhook. It **cannot** respond to a client. Here the pattern is different — `continueOnFail` + explicit error logging to DB is correct. Do **not** apply the webhook error pattern to C2. Review C2 separately.

---

## 4. Per-Workflow Status & Required Fixes

### workflow-a-universal-extractor.json — HIGH PRIORITY

**Current issues:**
1. **Duplicate `Fetch Azure Blob` nodes with same name** — two nodes named `"Fetch Azure Blob"`, both have `continueOnFail: true`. Only one should exist; remove the disconnected duplicate.
2. **`Error Trigger` + `Format Pipeline Error`** — wrong pattern (see Problem C). Remove both nodes and their connections.
3. **`continueOnFail` on 17 nodes** — cascading garbage problem. Strip `continueOnFail` from all pipeline nodes; keep only on `Fetch Azure Blob` (blob path) and any input validation node.
4. **Blob URL encoding** — apply the `encodeURIComponent` fix to the `generateSasUrl` function (same code as C1).
5. **IF typeValidation** — set to `"loose"` on any IF node checking `$json.error`.
6. Already has `responseMode: "responseNode"` ✓
7. Already has correct account name `stcompdldevqc01` and container `complianceblobdev` ✓

**Node list (32 nodes):**
`Webhook: Extract Content, Validate Binary, Error: No File, Set Binary Filename, Switch by File Type, Write Temp File, Extract Images, Convert PPTX to PDF, Convert DOCX to PDF, Copy Single Image, Extract Excel (Python), Parse Excel Result, Respond Error Excel, Error: Unsupported Type, List Generated Images, Prepare Generated File List, Florence Vision Analysis, Parse OCR & Vision, Aggregate Pages, Respond to Webhook, Respond Error, Respond Error Type, Services Health Check, Check Health Status, Set Service Error, Respond Error Service, Merge Health & Data, Fetch Azure Blob [x2 - DUPLICATE], Error Trigger [REMOVE], Format Pipeline Error [REMOVE], Respond: Pipeline Error`

**Respond nodes (keep all):** `Respond Error Excel, Respond to Webhook, Respond Error, Respond Error Type, Respond Error Service, Respond: Pipeline Error`

---

### workflow-c2-audit-worker.json — HIGH PRIORITY

**Current issues:**
1. **No webhook** — this is a Cron job. Do NOT apply webhook response pattern.
2. **`continueOnFail` on 34+ nodes** — same cascading problem. However, for a worker, the pattern is: fail fast on critical path nodes, use the existing `Error Trigger → Extract Error Details → Mark Session Failed → Log Error to DB` chain which is appropriate.
3. **Review the `Error Trigger` chain** — for a cron worker, `Error Trigger` in the same workflow IS valid (there's no webhook to respond to). Verify it correctly marks the session as `failed` in Postgres.
4. **No blob fetch in this workflow** — C2 calls Workflow A via HTTP (`Call Workflow A: Extract` node), so blob URL encoding fix is not needed here.
5. **`continueOnFail` strategy for C2:** Critical path nodes (Update Session: Processing, Ollama calls, DB writes for results) should NOT have `continueOnFail` so they surface to the Error Trigger. Logging/non-critical nodes can keep it.

**Node list (41 nodes):**
`Cron: Every 10s, Dequeue Job from Redis, Parse Job (Exit if Empty), Update Session: Processing, Log: Start Processing, Split by Question, Log: Question Start, Check Evidence Cache, Prepare Files for Extraction, Check if Extraction Needed, Call Workflow A: Extract, C2: Extraction OK?, Mark Extraction Failed, Combine Extraction Results, Prepare Evidence Inserts, Store Evidence to DB, Consolidate Evidence Text, Load Question, Update Log: Searching, Prepare Question for Embedding, Ollama: Generate Embedding, Extract Embedding, Prepare RAG Search, Qdrant: Search Standards, Format RAG Results, Build AI Prompt, Update Log: Evaluating, Ollama: Evaluate Compliance, Parse AI Response, Log Evaluation Result, Aggregate Scores, Update Session: Completed, Log: Final Completion, Cleanup: Temp Files, Check Master Cache, Is Cached?, Format Cached Response, Error Trigger, Extract Error Details, Mark Session Failed, Log Error to DB`

---

### workflow-c3-status-poll.json — HIGH PRIORITY

**Current issues:**
1. **`Error Trigger` + `Format Server Error`** — wrong pattern for webhook workflow. Remove both.
2. **`continueOnFail` on 4 nodes** (`Extract Session ID, Query Session, Query Recent Logs, Build Status Response`) — strip it; let nodes fail naturally for auto-500.
3. Already has `responseMode: "responseNode"` ✓
4. No blob fetch — URL encoding fix not needed.
5. Already has all three Respond nodes: `Respond: Status (200), Respond: Error (404), Respond: Server Error (500)` — keep all.

**Correct flow after fix:**
```
Webhook -> Extract Session ID -> Query Session -> [IF not found -> Respond: Error 404]
  -> Query Recent Logs -> Build Status Response -> Respond: Status (200)
  (any throw -> auto 500 since responseNode mode)
```

**Node list (11 nodes):**
`Webhook: Get Status, Extract Session ID, Query Session, Query Recent Logs, Build Status Response, Respond: Status, Error: Not Found, Respond: Error, Error Trigger [REMOVE], Format Server Error [REMOVE], Respond: Server Error`

---

### workflow-c4-results-retrieval.json — HIGH PRIORITY

**Current issues (identical structure to C3):**
1. **`Error Trigger` + `Format Server Error`** — remove both.
2. **`continueOnFail` on 4 nodes** — strip it.
3. Already has `responseMode: "responseNode"` ✓
4. No blob fetch — URL encoding fix not needed.
5. Already has: `Respond: Results (200), Respond: Error (404), Respond: Server Error (500)` — keep all.

**Node list (11 nodes):**
`Webhook: Get Results, Extract Session ID, Query Completed Session, Query Evaluations, Build Results Response, Respond: Results, Error: Not Found, Respond: Error, Error Trigger [REMOVE], Format Server Error [REMOVE], Respond: Server Error`

---

### workflow-b-kb-ingestion.json — LOW PRIORITY

**Current issues:**
1. **Duplicate `Fetch Azure Blob` nodes** — same as Workflow A. Remove disconnected duplicate.
2. **`Error Trigger` + `Format Pipeline Error`** — wrong pattern. Remove.
3. **`continueOnFail` on 15 nodes** — strip from pipeline nodes.
4. **Blob URL encoding** — apply `encodeURIComponent` fix to `generateSasUrl`.
5. Already has `responseMode: "responseNode"` ✓
6. Already has correct account/container names ✓

**Node list (27 nodes):**
`Webhook: Ingest Standard, Validate Input, Error: Missing Data, Normalize Binary Data, Call Universal Extractor, Extraction OK?, Format Extraction Error, Respond: Extraction Failed, Prepare Metadata, Chunk Text, Generate Embedding, Format Qdrant Point, Upsert to Qdrant, Insert to Postgres, Format Response, Respond to Webhook, Note: Collection Init, Calculate File Hash, Check Hash in DB, Is New File?, Set: Already Exists, Restore Data, Fetch Azure Blob [x2 - DUPLICATE], Error Trigger [REMOVE], Format Pipeline Error [REMOVE], Respond: Pipeline Error`

---

## 5. Fetch Azure Blob Node — Full Correct Code

This is the canonical correct `Fetch Azure Blob` code (from C1). Use this for all workflows that have this node:

```javascript
const crypto = require('crypto');
const https = require('https');

const connectionString = $env.AZURE_STORAGE_CONNECTION_STRING || $env.AZURE_BLOB_CONNECTION_STRING;
let accountName, accountKey;
if (connectionString) {
  accountName = connectionString.match(/AccountName=([^;]+)/)?.[1];
  accountKey  = connectionString.match(/AccountKey=([^;]+)/)?.[1];
}
if (!accountName) accountName = $env.AZURE_STORAGE_ACCOUNT_NAME || 'stcompdldevqc01';
if (!accountKey)  accountKey  = $env.AZURE_STORAGE_ACCOUNT_KEY;

if (!accountKey) {
  throw new Error('Azure credentials not found. Set AZURE_STORAGE_CONNECTION_STRING in the n8n container environment.');
}

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => resolve({ buffer: Buffer.concat(chunks), statusCode: res.statusCode, contentType: res.headers['content-type'] || 'application/octet-stream' }));
      res.on('error', reject);
    }).on('error', reject);
  });
}

function generateSasUrl(container, blobPath) {
  const now = new Date();
  const expiry = new Date(now.getTime() + 3600000);
  const sv = '2020-12-06';
  const fmt = (d) => d.toISOString().replace(/\.\d{3}Z$/, 'Z');
  const st = fmt(now);
  const se = fmt(expiry);
  // canonicalizedResource uses RAW path (Azure signing spec requirement)
  const canonicalizedResource = `/blob/${accountName}/${container}/${blobPath}`;
  const stringToSign = ['r', st, se, canonicalizedResource, '', '', 'https', sv, 'b', '', '', '', '', '', '', ''].join('\n');
  const key = Buffer.from(accountKey, 'base64');
  const sig = crypto.createHmac('sha256', key).update(Buffer.from(stringToSign, 'utf8')).digest('base64');
  const qs = 'sv=' + encodeURIComponent(sv) + '&sr=b&sp=r&st=' + encodeURIComponent(st) + '&se=' + encodeURIComponent(se) + '&spr=https&sig=' + encodeURIComponent(sig);
  // URL uses ENCODED path (spaces -> %20, special chars encoded) — NOT the canonicalizedResource
  const encodedBlobPath = blobPath.split('/').map(s => encodeURIComponent(s)).join('/');
  return `https://${accountName}.blob.core.windows.net/${container}/${encodedBlobPath}?${qs}`;
}

async function fetchBlob(container, blobPath) {
  const sasUrl = generateSasUrl(container, blobPath);
  const { buffer, statusCode, contentType } = await httpsGet(sasUrl);
  if (statusCode !== 200) {
    throw new Error(`Azure Blob download failed HTTP ${statusCode} for ${container}/${blobPath}. Body: ${buffer.toString().substring(0, 300)}`);
  }
  return { buffer, contentType };
}

const items = $input.all();
const result = [];

for (const item of items) {
  if (item.binary && Object.keys(item.binary).length > 0) {
    result.push(item);
    continue;
  }
  const bodyData = item.json.body || item.json;
  const blobPath  = bodyData.blobPath;
  const blobFiles = bodyData.blobFiles;
  if (!blobPath && !blobFiles) {
    result.push(item);
    continue;
  }
  if (!item.binary) item.binary = {};
  if (blobPath) {
    const container = bodyData.azureContainer || 'complianceblobdev';
    const { buffer, contentType } = await fetchBlob(container, blobPath);
    const fileName = blobPath.split('/').pop();
    item.binary.data = await this.helpers.prepareBinaryData(buffer, fileName, contentType);
    item.json.azureBlobFetched = true;
    item.json.originalFileName = fileName;
  }
  if (blobFiles) {
    for (const [fieldName, blobInfo] of Object.entries(blobFiles)) {
      const bp = typeof blobInfo === 'string' ? blobInfo : blobInfo.blobPath;
      const container = (typeof blobInfo === 'object' && blobInfo.container) ? blobInfo.container : (item.json.azureContainer || 'complianceblobdev');
      const { buffer, contentType } = await fetchBlob(container, bp);
      const fileName = bp.split('/').pop();
      item.binary[fieldName] = await this.helpers.prepareBinaryData(buffer, fileName, contentType);
    }
    item.json.azureBlobFetched = true;
  }
  result.push(item);
}

return result;
```

---

## 6. n8n Schema Rules (v2.6.3)

- **Switch node v3.4:** `parameters.rules.values[]`, `options.fallbackOutput: "extra"`
- **Set node v3.4:** `parameters.mode: "raw"`, `parameters.jsonOutput`
- **IF node v2:** `parameters.conditions.options.typeValidation` must be `"loose"` when checking fields that may be `undefined`
- **Code node:** `return [{json: {...}}]` — never return plain objects
- **`$('NodeName').first().json`** — always use named node references for cross-branch data access; never rely on `$json` when data came from a different branch
- `continueOnFail: true` causes n8n to output `{json: {error: "message [line N]"}}` — the line number refers to the node's code, not the workflow
- Postgres nodes drop binary data from their output — never route binary through a Postgres node
- File positions in JSON: keep existing `position` values to avoid breaking canvas layout

---

## 7. Approach for Each Fix Session

For each workflow, use a Python script (written to a `.py` file then run, not inline `-c`) to:
1. Load with `encoding='utf-8-sig'` (files have BOM)
2. Make targeted changes
3. Write back with `encoding='utf-8'` (no BOM on output)
4. Validate by re-parsing and printing node list + connections
5. Delete the script

**Never use `sed` or PowerShell string replace on JSON** — escaping is too fragile.
