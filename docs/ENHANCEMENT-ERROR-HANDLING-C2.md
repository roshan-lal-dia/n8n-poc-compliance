# Enhancement: Comprehensive Error Handling for C2 Audit Worker

## Overview

This document describes the planned enhancement to add full error handling coverage across all critical nodes in `workflow-c2-audit-worker.json`. The goal is that **no node failure goes silent** — every failure must mark the session as `failed` in the DB with a meaningful error message.

---

## Current State (Post-Bugfix)

The following nodes already have proper `IF → error sink` guards:

| Node | Guard | Notes |
|---|---|---|
| `Ollama: Generate Embedding` | `IF: Embedding Error?` | Checks `$json.error` exists |
| `Qdrant: Search Standards` | `IF: Qdrant Error?` | Checks `$json.error` exists |
| `Ollama: Evaluate Compliance` | `IF: Evaluation Error?` | Checks `$json.error` exists |
| `Load Question` | `IF: Question Found?` | Checks `$json.id` exists (0 rows guard) |
| `Call Workflow A: Extract` | `C2: Extraction OK?` + `Mark Extraction Failed` | Switch on content presence |

The shared error sink (used by all above):
```
[Prepare Error Data / Prepare Question Not Found Error / Mark Extraction Failed]
  ├──> Mark Session Failed   (UPDATE audit_sessions SET status = 'failed')
  └──> Log Error to DB       (INSERT INTO audit_logs)
```

---

## Gap Analysis — Unguarded Nodes

### Critical Path (must be fixed)

| Node | Type | Risk | Why Unguarded |
|---|---|---|---|
| `Consolidate Evidence Text` | Code | HIGH | `continueOnFail` only — outputs `$json.error` but no IF routes it |
| `Prepare Question for Embedding` | Code | HIGH | Same — silent failure passes bad data downstream |
| `Prepare RAG Search` | Code | MEDIUM | Throws on bad embedding, but error not routed |
| `Build AI Prompt` | Code | MEDIUM | No `continueOnFail`, no guard — crash halts execution |
| `Parse AI Response` | Code | MEDIUM | No `continueOnFail`, no guard — bad Ollama output crashes silently |
| `Combine Extraction Results` | Code | MEDIUM | `continueOnFail` only |

### Non-Critical (fire-and-forget, no fix needed)

| Node | Reason |
|---|---|
| `Update Log: Searching` | Progress log only — `continueOnFail` sufficient |
| `Update Log: Evaluating` | Progress log only — `continueOnFail` sufficient |
| `Log: Start Processing` | Audit log — `continueOnFail` sufficient |
| `Log: Question Start` | Audit log — `continueOnFail` sufficient |
| `Store Evidence to DB` | Has `ON CONFLICT DO NOTHING` — idempotent |

---

## Standard Pattern To Apply

For each unguarded critical node, apply this pattern:

```
[Code Node]
  continueOnFail: true           ← Step 1: enable
       │
       ▼
[IF: <NodeName> Error?]          ← Step 2: new IF node
  condition: $json.error exists
  TRUE  ──► [Prepare Error Data (contextual)]  ─┬──► Mark Session Failed
                                                 └──► Log Error to DB
  FALSE ──► [next happy path node]              ← Step 3: rewire
```

### Key Rules Learned

1. **`$json.error` is n8n's native signal** — when `continueOnFail: true` catches any failure (HTTP, DB, Code throw), n8n outputs `{ "error": { message, name, stack } }`. This is the **only reliable field** to check.

2. **IF nodes must sit DIRECTLY after the guarded node** — intermediate code nodes consume `$json.error` before the IF can check it.

3. **`alwaysOutputData: true`** is required on DB SELECT nodes that may legitimately return 0 rows (e.g. `Load Question`) — otherwise n8n halts execution with "No output data".

4. **One shared error sink** (`Mark Session Failed` + `Log Error to DB`) — each error path needs its own "Prepare X Error" code node to build `{ sessionId, hasSessionId, errorMessage, failedNode, technicalDetails }` before hitting the sink.

5. **`sessionId` must come from a reliable upstream node** — always pull from `$('Split by Question').item.json.sessionId` or `$('Parse Job (Exit if Empty)').first().json.sessionId`, never from the failing node's output.

---

## Implementation Plan

### Phase 1 — Consolidate Evidence Text + Prepare Question for Embedding

**Nodes to add:**
- `IF: Evidence Consolidation Error?` (after `Consolidate Evidence Text`)
- `Prepare Consolidation Error` (Code node — builds error context)
- `IF: Embedding Prep Error?` (after `Prepare Question for Embedding`)
- `Prepare Embedding Prep Error` (Code node)

**Rewiring:**
```
Consolidate Evidence Text → IF: Evidence Consolidation Error?
  TRUE  → Prepare Consolidation Error → [Mark Session Failed, Log Error to DB]
  FALSE → Load Question               (existing path)

Prepare Question for Embedding → IF: Embedding Prep Error?
  TRUE  → Prepare Embedding Prep Error → [Mark Session Failed, Log Error to DB]
  FALSE → Ollama: Generate Embedding   (existing path)
```

**`sessionId` source for both:** `$('Split by Question').item.json.sessionId`

---

### Phase 2 — Build AI Prompt + Parse AI Response

**Nodes to add:**
- `IF: Prompt Build Error?` (after `Build AI Prompt`)
- `Prepare Prompt Build Error` (Code node)
- `IF: Parse Error?` (after `Parse AI Response`)
- `Prepare Parse Error` (Code node)

**Note:** `Build AI Prompt` and `Parse AI Response` need `continueOnFail: true` added first.

**`sessionId` source:** `$('Prepare Question for Embedding').item.json.sessionId`

---

### Phase 3 — Prepare RAG Search + Combine Extraction Results

**Nodes to add:**
- `IF: RAG Prep Error?` (after `Prepare RAG Search`)
- `Prepare RAG Prep Error` (Code node)
- `IF: Combine Error?` (after `Combine Extraction Results`)
- `Prepare Combine Error` (Code node)

**`sessionId` source:** `$('Split by Question').item.json.sessionId`

---

## Error Context Template

Each "Prepare X Error" Code node should output:

```js
const sessionId = $('Split by Question').item.json.sessionId || '';
const nativeErr = $input.first().json.error || {};

return [{
  json: {
    sessionId: sessionId,
    hasSessionId: sessionId ? 'true' : 'false',
    errorMessage: nativeErr.message || 'Unknown error in <NodeName>',
    failedNode: '<NodeName>',
    technicalDetails: nativeErr,
    timestamp: new Date().toISOString()
  }
}];
```

---

## n8n Official Patterns (Reference)

From n8n docs, there are 3 tiers of error handling:

| Tier | Mechanism | Use Case |
|---|---|---|
| **Workflow-level** | `settings.errorWorkflow` → Error Trigger node | Last-resort alerts (Slack/email) after execution crashes |
| **Node-level** | `continueOnFail` + IF checks `$json.error` | Business-critical paths — what we use |
| **Code-level** | `throw new Error(...)` inside Code node | Input validation inside a node before bad data propagates |

Our implementation uses **Tiers 2 + 3** together, which is the recommended production pattern for long-running background workers where silent failures are unacceptable.

---

## Visual Architecture (Target State)

```
Cron → Dequeue → Parse Job → Update Session: Processing
                                      │
                              Split by Question (fan-out, 1 per question)
                                      │
                            ┌─────────▼──────────┐
                            │  Check Master Cache │
                            └─────┬──────────┬───┘
                          Cached  │          │ Not Cached
                                  │          ▼
                                  │   Prepare Files → Extract → Combine
                                  │          │ (IF: Combine Error?) [Phase 3]
                                  │          ▼
                                  │   Consolidate Evidence Text
                                  │          │ (IF: Evidence Consolidation Error?) [Phase 1]
                                  ▼          ▼
                            Format Cached  Load Question
                                  │          │ (IF: Question Found?) ✅
                                  └────┬─────┘
                                       ▼
                              Prepare Question for Embedding
                                       │ (IF: Embedding Prep Error?) [Phase 1]
                                       ▼
                              Ollama: Generate Embedding
                                       │ (IF: Embedding Error?) ✅
                                       ▼
                              Extract Embedding → Prepare RAG Search
                                                        │ (IF: RAG Prep Error?) [Phase 3]
                                                        ▼
                                               Qdrant: Search Standards
                                                        │ (IF: Qdrant Error?) ✅
                                                        ▼
                                               Format RAG Results → Build AI Prompt
                                                                          │ (IF: Prompt Build Error?) [Phase 2]
                                                                          ▼
                                                                 Ollama: Evaluate Compliance
                                                                          │ (IF: Evaluation Error?) ✅
                                                                          ▼
                                                                 Parse AI Response
                                                                          │ (IF: Parse Error?) [Phase 2]
                                                                          ▼
                                                          Log Evaluation Result + Aggregate Scores
                                                                          │
                                                              Update Session: Completed
                                                                          │
                                                                 Log: Final Completion
                                                                          │
                                                                  Cleanup: Temp Files

All error paths (✅ done, [Phase N] pending) → Prepare X Error → Mark Session Failed + Log Error to DB
```

---

## Acceptance Criteria

- [ ] Any node failure in the critical path results in `audit_sessions.status = 'failed'`
- [ ] `audit_logs` contains a row with `step_name = 'error'`, `status = 'failed'`, and a descriptive `message` including the node name and error
- [ ] The `metadata` column on `audit_sessions` contains `{ error, failedNode, failedAt, technicalDetails }`
- [ ] The `/status/:sessionId` endpoint returns `{ status: "failed", error: "..." }` for any failed session
- [ ] The `/results/:sessionId` endpoint returns the error details (not empty 200) for failed sessions
- [ ] No session is left in `processing` or `queued` state after a node failure
