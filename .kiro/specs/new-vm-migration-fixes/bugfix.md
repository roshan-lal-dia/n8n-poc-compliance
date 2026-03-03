# Bugfix Requirements Document

## Introduction

The n8n compliance audit system experienced multiple failures after migrating to a new VM environment with a different Azure tenant and ngrok-tunneled architecture. The system worked correctly in the previous development environment but now exhibits three critical issues: Azure Blob Storage authentication failures, broken error handling that causes both success and error paths to execute simultaneously, and undefined session IDs preventing audit status polling. These issues prevent the audit workflow from functioning end-to-end.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN workflow C1 attempts to fetch from Azure Blob Storage with new tenant credentials THEN the system returns AuthenticationFailed XML error with message "Server failed to authenticate the request"

1.2 WHEN any workflow encounters an error condition THEN the system executes both success nodes AND error trigger nodes simultaneously

1.3 WHEN audit is submitted via POST to `/webhook/audit/submit` THEN the system returns session_id as `undefined` in the response payload

1.4 WHEN the webhook should return HTTP 500 on error THEN the system fails to return the correct error status code

### Expected Behavior (Correct)

2.1 WHEN workflow C1 attempts to fetch from Azure Blob Storage with new tenant credentials (AccountName=stcompdldevqc01) THEN the system SHALL authenticate successfully and retrieve blob data

2.2 WHEN any workflow encounters an error condition THEN the system SHALL execute only the Error Trigger nodes and skip success path nodes

2.3 WHEN audit is submitted via POST to `/webhook/audit/submit` THEN the system SHALL return a valid session_id (not undefined) in the response payload for status polling

2.4 WHEN the webhook encounters an error THEN the system SHALL return HTTP 500 status code with error JSON payload

### Unchanged Behavior (Regression Prevention)

3.1 WHEN workflows execute successfully without errors THEN the system SHALL CONTINUE TO execute success path nodes and return appropriate success responses

3.2 WHEN audit submission completes successfully THEN the system SHALL CONTINUE TO return HTTP 202 Accepted with valid session_id

3.3 WHEN using master cache optimization THEN the system SHALL CONTINUE TO utilize cached results for performance

3.4 WHEN tracking filenames through the workflow THEN the system SHALL CONTINUE TO maintain filename metadata correctly

3.5 WHEN operating with ngrok-tunneled services (Ollama, Qdrant, n8n) THEN the system SHALL CONTINUE TO communicate correctly with these services

3.6 WHEN workflows A, B, C2, C3, and C4 operate normally THEN the system SHALL CONTINUE TO function as designed
