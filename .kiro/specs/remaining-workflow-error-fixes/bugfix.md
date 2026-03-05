# Bugfix Requirements Document

## Introduction

This bugfix addresses systematic error handling failures across five n8n workflows (A, B, C2, C3, C4) in the compliance audit system. These workflows currently return silent 200 responses on errors, produce cascading garbage errors, and have architectural issues that prevent proper error reporting to clients. The fix patterns have been established and validated in workflow C1, and must now be applied consistently to the remaining workflows.

The affected workflows handle critical functions: universal file extraction (A), knowledge base ingestion (B), background audit processing (C2), status polling (C3), and results retrieval (C4). All five workflows share the same root causes that were successfully resolved in C1.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN any node in workflows A, B, C3, or C4 fails with `continueOnFail: true` set THEN the system passes `{"error": "message"}` as output to downstream nodes, causing cascading secondary errors with misleading error messages unrelated to the root cause

1.2 WHEN webhook workflows A, B, C3, or C4 have `responseMode: "onReceived"` configured THEN the system returns 202 immediately before any processing occurs, preventing error status codes (400/500) from reaching the client

1.3 WHEN workflows A, B, C3, or C4 contain `Error Trigger` nodes in the same workflow THEN the system fires the error handler in parallel with the success path instead of replacing it, causing the client to still receive success responses despite errors

1.4 WHEN workflows A or B fetch Azure blobs with filenames containing spaces or special characters THEN the system constructs unencoded URLs causing Azure to return 404 BlobNotFound errors

1.5 WHEN IF nodes in workflows A, B, C3, or C4 check `$json.error` with `typeValidation: "strict"` and the field is undefined THEN the system throws a type validation error instead of evaluating the condition as false

1.6 WHEN workflows A and B contain duplicate `Fetch Azure Blob` nodes with identical node IDs THEN the system's internal deduplication breaks, causing one node to shadow the other and preventing proper execution

1.7 WHEN critical path nodes in workflow C2 (cron worker) have `continueOnFail: true` THEN the system suppresses errors that should surface to the Error Trigger, preventing proper failure handling and database logging

### Expected Behavior (Correct)

2.1 WHEN any node in webhook workflows A, B, C3, or C4 fails THEN the system SHALL remove `continueOnFail` from pipeline nodes and allow natural failure propagation, with `continueOnFail: true` only on entry validation nodes that explicitly route to 400/500 response nodes

2.2 WHEN webhook workflows A, B, C3, or C4 process requests THEN the system SHALL use `responseMode: "responseNode"` to enable explicit control over HTTP status codes and automatic 500 responses for unhandled errors

2.3 WHEN workflows A, B, C3, or C4 encounter errors THEN the system SHALL remove `Error Trigger` nodes and use explicit IF checks with `continueOnFail` only at validation points, routing errors to appropriate `Respond` nodes (400 for validation, 500 for pipeline failures)

2.4 WHEN workflows A or B fetch Azure blobs with any filename THEN the system SHALL encode the blob path using `encodeURIComponent` for each path segment in the HTTPS URL while keeping the canonicalizedResource unencoded for SAS signature generation

2.5 WHEN IF nodes in workflows A, B, C3, or C4 check for error conditions THEN the system SHALL use `typeValidation: "loose"` to properly handle undefined values without throwing type errors

2.6 WHEN workflows A and B are processed THEN the system SHALL contain only one `Fetch Azure Blob` node with a unique node ID, removing any duplicate disconnected nodes

2.7 WHEN critical path nodes in workflow C2 (cron worker) fail THEN the system SHALL remove `continueOnFail` from critical nodes (DB writes, Ollama calls, session updates) so errors surface to the existing Error Trigger for proper failure logging

### Unchanged Behavior (Regression Prevention)

3.1 WHEN workflow C1 (audit-entry) is executed THEN the system SHALL CONTINUE TO use the corrected error handling pattern without modification

3.2 WHEN workflow-admin-postgres is executed THEN the system SHALL CONTINUE TO function without any modifications

3.3 WHEN workflows A, B, C3, or C4 successfully process valid requests THEN the system SHALL CONTINUE TO return appropriate success responses (200/202) with correct data

3.4 WHEN workflow C2 successfully processes audit jobs from Redis THEN the system SHALL CONTINUE TO update session status, store results to Postgres, and complete without triggering error handlers

3.5 WHEN workflows fetch Azure blobs with simple filenames (no spaces or special characters) THEN the system SHALL CONTINUE TO successfully download blob content

3.6 WHEN IF nodes evaluate conditions on defined values THEN the system SHALL CONTINUE TO route execution correctly based on the condition result

3.7 WHEN workflows use existing Postgres credentials (ID: 3ME8TvhWnolXkgqg), Redis credentials (ID: K8jo4houPYYpv2hq), and webhook auth (webhook-api-key) THEN the system SHALL CONTINUE TO authenticate successfully

3.8 WHEN workflows reference Azure Blob Storage account `stcompdldevqc01` and container `complianceblobdev` THEN the system SHALL CONTINUE TO access the correct storage resources

3.9 WHEN workflow JSON files are modified THEN the system SHALL CONTINUE TO preserve existing node positions and canvas layout to avoid breaking the visual workflow editor
