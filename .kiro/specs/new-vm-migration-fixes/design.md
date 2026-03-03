# New VM Migration Fixes - Bugfix Design

## Overview

The n8n compliance audit system experienced three critical failures after migrating to a new Azure VM with a different tenant (AccountName=stcompdldevqc01) and ngrok-tunneled architecture. This design addresses: (1) Azure Blob Storage authentication failures due to hardcoded old tenant credentials, (2) broken error handling causing dual execution of both success and error paths simultaneously, and (3) undefined session_id values in webhook responses preventing audit status polling. The fix strategy involves updating Azure credentials across all workflows, correcting the continueOnFail configuration to prevent error path leakage, and ensuring proper session_id propagation through the response chain.

## Glossary

- **Bug_Condition (C)**: The conditions that trigger each of the three bugs - Azure auth failures, dual path execution, and undefined session_id responses
- **Property (P)**: The desired behavior - successful Azure authentication, exclusive error path execution, and valid session_id in responses
- **Preservation**: Existing functionality that must remain unchanged - master cache optimization, filename tracking, ngrok service communication, and successful workflow execution paths
- **Fetch Azure Blob**: The Code node in workflows A, B, and C1 that generates SAS tokens and downloads files from Azure Blob Storage
- **Error Trigger**: n8n node type that catches unhandled exceptions globally, disconnected from main flow but fires automatically on errors
- **continueOnFail**: n8n node setting that allows workflow to continue to next node even if current node fails, but can cause both success and error paths to execute
- **session_id**: UUID returned by the Create Audit Session node and used for polling audit status via C3 and retrieving results via C4
- **SAS Token**: Shared Access Signature - time-limited Azure Blob Storage access token generated using account name and key
- **Master Cache**: Optimization in audit_logs table that skips re-evaluation of identical question+evidence combinations
- **Ngrok Tunneling**: All services (Ollama, Qdrant, n8n) are accessed via ngrok tunnels in the new VM environment

## Bug Details

### Fault Condition

The bugs manifest in three distinct scenarios:

**Bug 1 - Azure Authentication Failure:**
The Fetch Azure Blob node in workflow C1 (and potentially A, B) attempts to authenticate with Azure Blob Storage using credentials from environment variables. The code has a hardcoded fallback `accountName = $env.AZURE_STORAGE_ACCOUNT_NAME || 'unificdmpblob'` which uses the old tenant account name when the environment variable is not set. The new tenant uses AccountName=stcompdldevqc01, but the connection string may not be properly configured, causing the fallback to use the wrong account.

**Bug 2 - Dual Path Execution:**
When any node with `continueOnFail: true` encounters an error, the workflow continues to the next success-path node AND simultaneously triggers the Error Trigger node. This causes both the success response (HTTP 202) and error response (HTTP 500) to attempt execution, with the error path potentially overriding the success response or causing undefined behavior.

**Bug 3 - Undefined session_id:**
The Build Success Response node in workflow C1 constructs the webhook response using `$('Build Redis Job Payload').first().json.sessionId`. If any node in the chain fails but continues due to `continueOnFail: true`, the Build Redis Job Payload node may not execute or may return empty data, causing sessionId to be undefined in the final response.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type WorkflowExecution
  OUTPUT: boolean
  
  // Bug 1: Azure Auth Failure
  IF input.node == "Fetch Azure Blob" AND
     (input.env.AZURE_STORAGE_CONNECTION_STRING is missing OR
      input.env.AZURE_STORAGE_CONNECTION_STRING contains wrong AccountName) AND
     input.fallbackAccountName == "unificdmpblob" AND
     input.actualTenant == "stcompdldevqc01"
  THEN RETURN true
  
  // Bug 2: Dual Path Execution
  IF input.node.continueOnFail == true AND
     input.node.status == "error" AND
     input.successPathExecuted == true AND
     input.errorTriggerExecuted == true
  THEN RETURN true
  
  // Bug 3: Undefined session_id
  IF input.node == "Build Success Response" AND
     input.referencedNode("Build Redis Job Payload").status == "failed" AND
     input.responsePayload.sessionId == undefined
  THEN RETURN true
  
  RETURN false
END FUNCTION
```

### Examples

**Bug 1 - Azure Authentication Failure:**
- User submits audit via POST /webhook/audit/submit with blobPath parameter
- Fetch Azure Blob node reads AZURE_STORAGE_CONNECTION_STRING from environment
- Connection string is missing or contains old AccountName=unificdmpblob
- Code falls back to hardcoded 'unificdmpblob' account name
- SAS token generation uses wrong account name
- Azure returns HTTP 403 with XML error: "Server failed to authenticate the request"
- Expected: Should use AccountName=stcompdldevqc01 and authenticate successfully

**Bug 2 - Dual Path Execution:**
- Parse & Validate Input node fails due to malformed JSON
- Node has continueOnFail: true, so workflow continues to Create Audit Session
- Simultaneously, Error Trigger node fires and executes Format Pipeline Error → Respond: Pipeline Error
- Create Audit Session may also fail, continuing down the success path
- Eventually Build Success Response executes with invalid/missing data
- Both Respond: Accepted (HTTP 202) and Respond: Pipeline Error (HTTP 500) attempt to send responses
- Expected: Only error path should execute, returning HTTP 500 immediately

**Bug 3 - Undefined session_id:**
- Create Audit Session node fails (e.g., database connection error)
- Node has continueOnFail: true, so workflow continues
- Subsequent nodes (Prepare File Writes, Write Binary File, etc.) execute with missing session data
- Build Redis Job Payload never receives valid sessionId
- Build Success Response references $('Build Redis Job Payload').first().json.sessionId
- Response payload contains: `{ "sessionId": undefined, "jobId": undefined, ... }`
- Client cannot poll status because session_id is undefined
- Expected: Should return HTTP 500 error immediately when Create Audit Session fails

**Edge Case - Partial Success:**
- Workflow executes successfully until Enqueue Job to Redis fails (Redis connection timeout)
- Session was created in database with valid session_id
- continueOnFail: true allows workflow to continue
- Build Success Response executes with valid sessionId but job was never enqueued
- Response returns HTTP 202 with valid session_id, but audit never processes
- Expected: Should detect Redis failure and return HTTP 500, or implement retry logic

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Master cache optimization in audit_logs table must continue to skip re-evaluation of identical question+evidence combinations
- Original filename tracking through the pipeline must continue to preserve sourceFiles metadata
- Ngrok-tunneled service communication (Ollama, Qdrant, n8n) must continue to work correctly
- Workflows A, B, C2, C3, and C4 must continue to function as designed
- Successful audit submission flow (no errors) must continue to return HTTP 202 with valid session_id
- File hash deduplication and validation logic must remain unchanged
- Redis job queue mechanism (C1 → C2) must continue to decouple submission from processing
- Database schema and query patterns must remain unchanged

**Scope:**
All inputs that do NOT trigger the three bug conditions should be completely unaffected by this fix. This includes:
- Successful audit submissions with valid files and proper Azure credentials
- Direct file uploads (not using Azure Blob Storage)
- Workflows that don't use Azure Blob fetch (C2, C3, C4, admin-postgres)
- Error scenarios that are properly handled by existing error paths
- Status polling and results retrieval operations

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely root causes are:

### Bug 1 - Azure Authentication Failure

1. **Missing Environment Variable**: The AZURE_STORAGE_CONNECTION_STRING environment variable is not set in the new VM's docker-compose.yml or .env file, causing the code to fall back to the hardcoded 'unificdmpblob' account name.

2. **Incorrect Connection String**: The connection string is set but contains the old tenant's AccountName=unificdmpblob instead of the new AccountName=stcompdldevqc01.

3. **Wrong Account Key**: The connection string has the correct AccountName but uses the old tenant's AccountKey, causing authentication to fail.

4. **Multiple Workflow Instances**: Workflows A, B, and C1 all have Fetch Azure Blob nodes with identical code. The fix must be applied to all three workflows, but only C1 may have been updated.

### Bug 2 - Dual Path Execution

1. **Incorrect continueOnFail Usage**: Phase 8 added `continueOnFail: true` to all nodes for "production hardening," but this setting is inappropriate for critical nodes like Create Audit Session, Parse & Validate Input, and Enqueue Job to Redis. When these nodes fail, the workflow should stop immediately and return an error, not continue down the success path.

2. **Missing Conditional Logic**: The Build Success Response node does not check whether previous critical nodes succeeded before constructing the response. It blindly references data that may not exist.

3. **Error Trigger Misconfiguration**: The Error Trigger node fires on any unhandled exception, but when continueOnFail: true is set, exceptions are "handled" by continuing the workflow, so the Error Trigger may fire while the success path is also executing.

4. **No Response Guard**: Both Respond: Accepted and Respond: Pipeline Error nodes can execute in the same workflow run, with the last one to execute overriding the first (or causing undefined behavior).

### Bug 3 - Undefined session_id

1. **Cascading Failure**: When Create Audit Session fails but continueOnFail: true allows the workflow to continue, all downstream nodes receive empty or invalid data. The Build Redis Job Payload node cannot construct a valid job without a sessionId, so it returns undefined.

2. **Missing Null Checks**: The Build Success Response node does not validate that sessionId exists before including it in the response payload. JavaScript allows undefined values in object literals, so `{ sessionId: undefined }` is valid syntax but produces invalid API responses.

3. **Incorrect Node Reference**: The Build Success Response node may be referencing the wrong node or using an incorrect path to access sessionId (e.g., $json.sessionId vs $json.session_id).

4. **Data Loss in Aggregation**: The Aggregate Files node reconstructs the data structure from multiple items. If any item is missing sessionId due to upstream failures, the aggregated result may have undefined sessionId.

## Correctness Properties

Property 1: Fault Condition - Azure Authentication with New Tenant

_For any_ workflow execution where Azure Blob Storage is accessed (workflows A, B, C1) and the environment is configured with the new tenant credentials (AccountName=stcompdldevqc01), the fixed Fetch Azure Blob node SHALL successfully authenticate using the connection string from AZURE_STORAGE_CONNECTION_STRING, generate a valid SAS token, and download the requested blob without authentication errors.

**Validates: Requirements 2.1**

Property 2: Fault Condition - Exclusive Error Path Execution

_For any_ workflow execution where a critical node (Parse & Validate Input, Create Audit Session, Enqueue Job to Redis) encounters an error, the fixed workflow SHALL execute only the Error Trigger path, return HTTP 500 with structured error JSON, and SHALL NOT execute any success-path nodes (Build Success Response, Respond: Accepted) after the failure point.

**Validates: Requirements 2.2, 2.4**

Property 3: Fault Condition - Valid session_id in Response

_For any_ workflow execution where the audit submission completes successfully through all critical nodes, the fixed Build Success Response node SHALL return a response payload containing a valid UUID session_id (not undefined, not null) that can be used for subsequent status polling via workflow C3.

**Validates: Requirements 2.3**

Property 4: Preservation - Successful Workflow Execution

_For any_ workflow execution that does NOT encounter errors (all nodes succeed), the fixed workflows SHALL continue to execute the success path, return HTTP 202 Accepted with valid session_id, utilize master cache optimization, maintain filename metadata, and communicate correctly with ngrok-tunneled services, producing exactly the same behavior as the original unfixed code.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct, the following changes are required:

#### File: `workflows/unifi-npc-compliance/workflow-c1-audit-entry.json`

**Node: Fetch Azure Blob (id: fetch-azure-blob-c1)**

**Specific Changes**:
1. **Remove Hardcoded Fallback**: Delete the line `if (!accountName) accountName = $env.AZURE_STORAGE_ACCOUNT_NAME || 'unificdmpblob';` and replace with a strict requirement that AZURE_STORAGE_CONNECTION_STRING must be set.

2. **Add Validation**: After parsing the connection string, validate that accountName and accountKey are both present and throw a descriptive error if either is missing.

3. **Log Account Name**: Add console.log statement to log the parsed accountName for debugging: `console.log('Azure Blob: Using account', accountName);`

4. **Update Error Message**: Enhance the error message to include instructions for setting the connection string with the new tenant credentials.

**Node: Parse & Validate Input (id: b135bedb-52bf-44ab-8792-fbc75357b314)**

**Specific Changes**:
1. **Remove continueOnFail**: Change `"continueOnFail": true` to `"continueOnFail": false` (or remove the property entirely, as false is the default). This node validates input and should fail fast if validation fails.

**Node: Create Audit Session (id: 82ceda42-6c52-4a2d-bdc6-8aecd13587d7)**

**Specific Changes**:
1. **Remove continueOnFail**: Change `"continueOnFail": true` to `"continueOnFail": false`. This is a critical node - if session creation fails, the entire workflow should stop.

**Node: Enqueue Job to Redis (id: c466ed1c-c19c-4dc5-bab8-77802814355a)**

**Specific Changes**:
1. **Remove continueOnFail**: Change `"continueOnFail": true` to `"continueOnFail": false`. If Redis enqueue fails, the audit will never process, so we should return an error immediately.

**Node: Build Success Response (id: 81a33153-285b-460a-9dc1-7fc2851a6647)**

**Specific Changes**:
1. **Add Null Check**: Modify the jsonOutput expression to validate that sessionId exists before constructing the response:
   ```javascript
   const payload = $('Build Redis Job Payload').first().json;
   if (!payload || !payload.sessionId) {
     throw new Error('Session ID is missing - audit submission failed');
   }
   return {
     sessionId: payload.sessionId,
     jobId: payload.jobId,
     status: "queued",
     totalQuestions: payload.totalQuestions,
     message: "Audit submitted successfully. Poll /webhook/audit-status-webhook/audit/status/" + payload.sessionId + " for progress.",
     estimatedCompletionMinutes: Math.ceil(payload.totalQuestions * 2.5)
   };
   ```

**Node: Fetch Azure Blob (id: fetch-azure-blob-c1)**

**Specific Changes**:
1. **Keep continueOnFail: true**: This node should continue on fail because Azure Blob fetch is optional (direct file uploads are also supported). However, if it fails, it should throw a clear error that will be caught by the Error Trigger.

#### File: `workflows/unifi-npc-compliance/workflow-a-universal-extractor.json`

**Node: Fetch Azure Blob (id: fetch-azure-blob-a)**

**Specific Changes**:
1. **Apply Same Azure Credential Fix**: Update the Fetch Azure Blob node with the same changes as workflow C1 (remove hardcoded fallback, add validation, log account name).

#### File: `workflows/unifi-npc-compliance/workflow-b-kb-ingestion.json`

**Node: Fetch Azure Blob (id: fetch-azure-blob-b)**

**Specific Changes**:
1. **Apply Same Azure Credential Fix**: Update the Fetch Azure Blob node with the same changes as workflows C1 and A.

#### File: `.env` or `docker-compose.prod.yml`

**Environment Variables**

**Specific Changes**:
1. **Update AZURE_STORAGE_CONNECTION_STRING**: Ensure the connection string is set with the new tenant credentials:
   ```
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=stcompdldevqc01;AccountKey=<new-tenant-key>;EndpointSuffix=core.windows.net
   ```

2. **Remove Old Fallback Variables**: Remove AZURE_STORAGE_ACCOUNT_NAME if it exists, as it may contain the old account name and cause confusion.

3. **Document in .env.example**: Update .env.example to show the new tenant account name as the example.

### Implementation Strategy

1. **Phase 1 - Environment Configuration**: Update the .env file or docker-compose.prod.yml with the new Azure tenant credentials. Restart the n8n container to load the new environment variables.

2. **Phase 2 - Azure Credential Fix**: Update the Fetch Azure Blob nodes in workflows A, B, and C1 to remove the hardcoded fallback and add validation. Deploy all three workflows.

3. **Phase 3 - Error Handling Fix**: Update workflow C1 to remove continueOnFail from critical nodes (Parse & Validate Input, Create Audit Session, Enqueue Job to Redis) and add null checking to Build Success Response. Deploy workflow C1.

4. **Phase 4 - Verification**: Test each bug scenario to confirm the fix:
   - Test Azure Blob fetch with new tenant credentials
   - Test error scenarios to confirm only error path executes
   - Test successful submission to confirm valid session_id is returned

## Testing Strategy

### Validation Approach

The testing strategy follows a three-phase approach: first, surface counterexamples that demonstrate each bug on unfixed code; second, verify the fix resolves each bug; third, verify existing functionality is preserved.

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate the three bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Create test cases that trigger each bug condition and observe the failures on the UNFIXED code. Document the exact error messages and behavior.

**Test Cases**:

1. **Azure Auth Failure Test**: Submit audit with blobPath parameter pointing to a file in the new tenant's storage account (will fail on unfixed code with HTTP 403 authentication error)
   - Setup: Ensure AZURE_STORAGE_CONNECTION_STRING is either missing or contains old credentials
   - Execute: POST /webhook/audit/submit with `{ "blobPath": "test/sample.pdf", "azureContainer": "compliance", "questions": [...] }`
   - Expected Counterexample: HTTP 500 error with message containing "Server failed to authenticate the request" or "AuthenticationFailed"

2. **Dual Path Execution Test**: Submit audit with malformed questions JSON to trigger Parse & Validate Input failure (will fail on unfixed code by executing both success and error paths)
   - Setup: Use unfixed workflow C1 with continueOnFail: true on all nodes
   - Execute: POST /webhook/audit/submit with `{ "questions": "not-an-array" }`
   - Expected Counterexample: Observe in n8n execution logs that both "Build Success Response" and "Format Pipeline Error" nodes execute, or receive HTTP response with mixed success/error data

3. **Undefined session_id Test**: Simulate Create Audit Session failure by temporarily breaking database connection (will fail on unfixed code by returning undefined session_id)
   - Setup: Temporarily change postgres credentials in workflow C1 to invalid values, or stop postgres container
   - Execute: POST /webhook/audit/submit with valid payload
   - Expected Counterexample: HTTP 202 response with `{ "sessionId": undefined, "jobId": undefined, ... }`

4. **Partial Failure Test**: Simulate Redis connection failure after successful session creation (may fail on unfixed code by returning success response even though job was never enqueued)
   - Setup: Stop Redis container after workflow starts
   - Execute: POST /webhook/audit/submit with valid payload
   - Expected Counterexample: HTTP 202 response with valid session_id, but job never appears in Redis queue and audit never processes

**Expected Counterexamples**:
- Azure authentication failures with HTTP 403 or XML error responses
- Workflow execution logs showing both success and error nodes executing simultaneously
- API responses containing undefined or null values for session_id
- Possible causes: missing environment variables, incorrect continueOnFail configuration, missing null checks in response construction

### Fix Checking

**Goal**: Verify that for all inputs where the bug conditions hold, the fixed workflows produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := executeFixedWorkflow(input)
  ASSERT expectedBehavior(result)
END FOR

FUNCTION expectedBehavior(result)
  // Bug 1: Azure auth should succeed
  IF result.bugType == "azure_auth" THEN
    RETURN result.statusCode == 200 AND result.blobDownloaded == true
  
  // Bug 2: Only error path should execute
  IF result.bugType == "dual_path" THEN
    RETURN result.statusCode == 500 AND 
           result.errorPathExecuted == true AND
           result.successPathExecuted == false
  
  // Bug 3: session_id should be valid UUID
  IF result.bugType == "undefined_session" THEN
    RETURN result.statusCode == 500 OR
           (result.statusCode == 202 AND isValidUUID(result.sessionId))
  
  RETURN false
END FUNCTION
```

**Test Cases**:
1. **Azure Auth Fix Verification**: Submit audit with blobPath using new tenant credentials - should succeed
2. **Error Path Fix Verification**: Submit audit with malformed input - should return HTTP 500 only, no success path execution
3. **session_id Fix Verification**: Submit valid audit - should return HTTP 202 with valid UUID session_id
4. **Redis Failure Fix Verification**: Simulate Redis failure - should return HTTP 500, not HTTP 202

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed workflows produce the same result as the original workflows.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT executeOriginalWorkflow(input) = executeFixedWorkflow(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for successful audit submissions, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Successful Direct Upload Preservation**: Observe that direct file uploads (not using Azure Blob) work correctly on unfixed code, then verify this continues after fix
   - Test: POST /webhook/audit/submit with multipart/form-data containing file uploads
   - Assert: HTTP 202 response with valid session_id, job enqueued to Redis, session created in database

2. **Master Cache Preservation**: Observe that master cache optimization works correctly on unfixed code (identical question+evidence combinations are skipped), then verify this continues after fix
   - Test: Submit two audits with identical questions and evidence files
   - Assert: Second audit uses cached results from first audit (check audit_logs table for cache hits)

3. **Filename Tracking Preservation**: Observe that original filenames are preserved through the pipeline on unfixed code, then verify this continues after fix
   - Test: Submit audit with files named "Policy Document.pdf" and "Compliance Report.xlsx"
   - Assert: Evidence summaries and AI prompts reference original filenames, not internal temp paths like /tmp/n8n-xyz.pdf

4. **Ngrok Service Communication Preservation**: Observe that Ollama, Qdrant, and Florence-2 services are accessible via ngrok tunnels on unfixed code, then verify this continues after fix
   - Test: Submit audit that requires RAG search (Qdrant), LLM inference (Ollama), and OCR (Florence-2)
   - Assert: All services respond correctly, audit completes successfully

5. **Other Workflow Preservation**: Observe that workflows A, B, C2, C3, C4 function correctly on unfixed code, then verify this continues after fix
   - Test: Execute each workflow independently with valid inputs
   - Assert: All workflows complete successfully with expected outputs

### Unit Tests

- Test Azure SAS token generation with new tenant credentials (AccountName=stcompdldevqc01)
- Test Parse & Validate Input node with malformed JSON (should fail immediately, not continue)
- Test Create Audit Session node with invalid database credentials (should fail immediately)
- Test Build Success Response node with missing sessionId (should throw error)
- Test Enqueue Job to Redis with Redis connection failure (should fail immediately)
- Test Error Trigger node activation when critical nodes fail
- Test that Respond: Accepted is NOT called when errors occur
- Test that Respond: Pipeline Error is called with HTTP 500 when errors occur

### Property-Based Tests

- Generate random valid audit submissions and verify all return HTTP 202 with valid UUID session_id
- Generate random invalid audit submissions (malformed JSON, missing fields, invalid file references) and verify all return HTTP 500 with structured error JSON
- Generate random Azure Blob paths and verify all authenticate successfully with new tenant credentials
- Generate random file uploads (direct and Azure Blob) and verify original filenames are preserved
- Generate random question+evidence combinations and verify master cache optimization works correctly

### Integration Tests

- Test full audit flow: submit via C1 → process via C2 → poll status via C3 → retrieve results via C4
- Test Azure Blob fetch in all three workflows (A, B, C1) with new tenant credentials
- Test error scenarios at each critical node and verify only error path executes
- Test that ngrok-tunneled services (Ollama, Qdrant, Florence-2) remain accessible after fix
- Test that database schema and queries remain unchanged after fix
- Test that Redis job queue mechanism continues to work correctly after fix
