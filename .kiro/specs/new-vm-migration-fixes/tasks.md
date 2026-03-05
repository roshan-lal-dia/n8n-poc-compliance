# Implementation Plan

- [ ] 1. Write bug condition exploration tests
  - **Property 1: Fault Condition** - Azure Auth, Dual Path, and Undefined session_id Bugs
  - **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior - they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate the three bugs exist
  - **Scoped PBT Approach**: For deterministic bugs, scope properties to concrete failing cases to ensure reproducibility

  - [ ] 1.1 Test Azure authentication failure with old tenant credentials
    - Submit audit with blobPath parameter pointing to new tenant storage (stcompdldevqc01)
    - Ensure AZURE_STORAGE_CONNECTION_STRING is missing or contains old credentials (unificdmpblob)
    - Execute: POST /webhook/audit/submit with valid payload including blobPath
    - **EXPECTED OUTCOME**: Test FAILS with HTTP 500 containing "AuthenticationFailed" or "Server failed to authenticate"
    - Document counterexample: exact error message and which workflow (A, B, or C1) failed
    - _Requirements: 2.1_

  - [ ] 1.2 Test dual path execution with validation failure
    - Submit audit with malformed questions JSON to trigger Parse & Validate Input failure
    - Use unfixed workflow C1 with continueOnFail: true on critical nodes
    - Execute: POST /webhook/audit/submit with `{ "questions": "not-an-array" }`
    - **EXPECTED OUTCOME**: Test FAILS - observe both "Build Success Response" and "Format Pipeline Error" nodes execute in n8n logs
    - Document counterexample: execution log showing both paths active simultaneously
    - _Requirements: 2.2, 2.4_

  - [ ] 1.3 Test undefined session_id in response
    - Simulate Create Audit Session failure by using invalid postgres credentials
    - Execute: POST /webhook/audit/submit with valid payload
    - **EXPECTED OUTCOME**: Test FAILS with HTTP 202 response containing `{ "sessionId": undefined }`
    - Document counterexample: exact response payload showing undefined values
    - _Requirements: 2.3_

  - [ ] 1.4 Test partial failure scenario (Redis enqueue failure)
    - Stop Redis container to simulate connection failure
    - Execute: POST /webhook/audit/submit with valid payload
    - **EXPECTED OUTCOME**: Test FAILS with HTTP 202 response but job never appears in Redis queue
    - Document counterexample: response shows success but audit never processes
    - _Requirements: 2.2, 2.4_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Functionality Must Remain Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (successful workflows)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code

  - [ ] 2.1 Test successful direct file upload preservation
    - Observe: Direct file uploads (multipart/form-data) work correctly on unfixed code
    - Write property: For all valid direct uploads, response is HTTP 202 with valid UUID session_id
    - Verify test passes on UNFIXED code
    - _Requirements: 3.1, 3.5_

  - [ ] 2.2 Test master cache optimization preservation
    - Observe: Identical question+evidence combinations use cached results on unfixed code
    - Write property: For all duplicate audit submissions, second audit uses cache (check audit_logs table)
    - Verify test passes on UNFIXED code
    - _Requirements: 3.2_

  - [ ] 2.3 Test filename tracking preservation
    - Observe: Original filenames are preserved in evidence summaries on unfixed code
    - Write property: For all file uploads with original names, those names appear in AI prompts and summaries
    - Verify test passes on UNFIXED code
    - _Requirements: 3.3_

  - [ ] 2.4 Test ngrok service communication preservation
    - Observe: Ollama, Qdrant, and Florence-2 services respond via ngrok tunnels on unfixed code
    - Write property: For all audits requiring RAG/LLM/OCR, services respond correctly via ngrok
    - Verify test passes on UNFIXED code
    - _Requirements: 3.4_

  - [ ] 2.5 Test other workflows preservation (A, B, C2, C3, C4)
    - Observe: Workflows A, B, C2, C3, C4 execute successfully on unfixed code
    - Write property: For all valid inputs to each workflow, execution completes successfully
    - Verify test passes on UNFIXED code
    - _Requirements: 3.5, 3.6_

- [ ] 3. Fix for new VM migration issues (Azure auth, dual path execution, undefined session_id)

  - [ ] 3.1 Update environment configuration with new Azure tenant credentials
    - Update .env or docker-compose.prod.yml with AZURE_STORAGE_CONNECTION_STRING
    - Set AccountName=stcompdldevqc01 with new tenant AccountKey
    - Remove old AZURE_STORAGE_ACCOUNT_NAME variable if present
    - Update .env.example to document new tenant account name
    - Restart n8n container to load new environment variables
    - _Bug_Condition: isBugCondition(input) where input.env.AZURE_STORAGE_CONNECTION_STRING is missing or contains wrong AccountName_
    - _Expected_Behavior: Azure authentication succeeds with new tenant credentials (Property 1)_
    - _Preservation: Existing successful workflows continue to function (Property 4)_
    - _Requirements: 2.1_

  - [ ] 3.2 Fix Azure Blob fetch in workflow C1
    - Remove hardcoded fallback: Delete `accountName = $env.AZURE_STORAGE_ACCOUNT_NAME || 'unificdmpblob'`
    - Add validation: Throw error if accountName or accountKey are missing after parsing connection string
    - Add logging: `console.log('Azure Blob: Using account', accountName)`
    - Update error message to include instructions for setting connection string
    - Keep continueOnFail: true (Azure Blob fetch is optional, direct uploads are supported)
    - _Bug_Condition: isBugCondition(input) where input.fallbackAccountName == "unificdmpblob" and input.actualTenant == "stcompdldevqc01"_
    - _Expected_Behavior: Successful authentication with new tenant (Property 1)_
    - _Preservation: Direct file uploads continue to work (Property 4)_
    - _Requirements: 2.1_

  - [ ] 3.3 Fix Azure Blob fetch in workflow A (Universal Extractor)
    - Apply same changes as workflow C1: remove hardcoded fallback, add validation, add logging
    - Keep continueOnFail: true for optional Azure Blob fetch
    - _Bug_Condition: Same as 3.2 for workflow A_
    - _Expected_Behavior: Successful authentication with new tenant (Property 1)_
    - _Preservation: Workflow A continues to function correctly (Property 4)_
    - _Requirements: 2.1_

  - [ ] 3.4 Fix Azure Blob fetch in workflow B (KB Ingestion)
    - Apply same changes as workflows C1 and A: remove hardcoded fallback, add validation, add logging
    - Keep continueOnFail: true for optional Azure Blob fetch
    - _Bug_Condition: Same as 3.2 for workflow B_
    - _Expected_Behavior: Successful authentication with new tenant (Property 1)_
    - _Preservation: Workflow B continues to function correctly (Property 4)_
    - _Requirements: 2.1_

  - [ ] 3.5 Remove continueOnFail from Parse & Validate Input node in workflow C1
    - Change `"continueOnFail": true` to `"continueOnFail": false` (or remove property)
    - This node validates input and should fail fast if validation fails
    - _Bug_Condition: isBugCondition(input) where input.node.continueOnFail == true and input.node.status == "error"_
    - _Expected_Behavior: Only error path executes, returns HTTP 500 (Property 2)_
    - _Preservation: Successful validations continue to work (Property 4)_
    - _Requirements: 2.2, 2.4_

  - [ ] 3.6 Remove continueOnFail from Create Audit Session node in workflow C1
    - Change `"continueOnFail": true` to `"continueOnFail": false`
    - This is a critical node - if session creation fails, entire workflow should stop
    - _Bug_Condition: isBugCondition(input) where input.node == "Create Audit Session" and input.node.continueOnFail == true_
    - _Expected_Behavior: Only error path executes, returns HTTP 500 (Property 2)_
    - _Preservation: Successful session creation continues to work (Property 4)_
    - _Requirements: 2.2, 2.4_

  - [ ] 3.7 Remove continueOnFail from Enqueue Job to Redis node in workflow C1
    - Change `"continueOnFail": true` to `"continueOnFail": false`
    - If Redis enqueue fails, audit will never process, so return error immediately
    - _Bug_Condition: isBugCondition(input) where input.node == "Enqueue Job to Redis" and input.node.continueOnFail == true_
    - _Expected_Behavior: Only error path executes, returns HTTP 500 (Property 2)_
    - _Preservation: Successful Redis enqueue continues to work (Property 4)_
    - _Requirements: 2.2, 2.4_

  - [ ] 3.8 Add null checks to Build Success Response node in workflow C1
    - Modify jsonOutput expression to validate sessionId exists before constructing response
    - Add code: `const payload = $('Build Redis Job Payload').first().json; if (!payload || !payload.sessionId) { throw new Error('Session ID is missing - audit submission failed'); }`
    - Return structured response only if sessionId is valid UUID
    - _Bug_Condition: isBugCondition(input) where input.responsePayload.sessionId == undefined_
    - _Expected_Behavior: Valid UUID session_id in response or HTTP 500 error (Property 3)_
    - _Preservation: Successful responses continue to return valid session_id (Property 4)_
    - _Requirements: 2.3_

  - [ ] 3.9 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Azure Auth, Dual Path, and Undefined session_id Fixed
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run all tests from task 1 (1.1, 1.2, 1.3, 1.4)
    - **EXPECTED OUTCOME**: All tests PASS (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 3.10 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Functionality Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run all tests from task 2 (2.1, 2.2, 2.3, 2.4, 2.5)
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions)
    - Confirm all preservation properties still hold after fix
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Verify all bug condition tests pass (Azure auth, dual path, session_id)
  - Verify all preservation tests pass (master cache, filename tracking, ngrok services, other workflows)
  - Verify no regressions in existing functionality
  - Ask user if questions arise or if additional testing is needed
