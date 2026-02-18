# Plan: Webhook Endpoint Authentication

**Status:** Ready for implementation  
**Priority:** High — first feature after file cleanup  
**Last Updated:** February 18, 2026

---

## Problem Statement

All n8n webhook endpoints (`/webhook/audit/submit`, `/webhook/audit/status/:id`, `/webhook/audit/results/:id`, `/webhook/kb/ingest`, `/webhook/extract`) are currently **publicly accessible** to anyone who knows the VM IP.

The n8n UI Basic Auth (`N8N_BASIC_AUTH_ACTIVE=true`) protects the **n8n editor UI** only — it does **not** protect webhook calls from external clients (the frontend portal, curl, etc.).

---

## Options Compared

### Option A — API Key Header (Recommended)
Each webhook node adds a "Webhook Auth" credential requiring a custom header:

```
X-API-Key: <secret_key>
```

n8n natively supports this via **Webhook node → Authentication → Header Auth**.

**Pros:**
- Simple, stateless, no session management
- Easy for the frontend to implement (`headers: { 'X-API-Key': '...' }`)
- One credential object shared across all 5 webhook nodes
- Secret stored encrypted in n8n credential store (not in env vars)
- Easy to rotate: update credential → all endpoints immediately protected

**Cons:**
- Key in HTTP header (fine over HTTPS, insecure over plain HTTP without TLS)
- No per-user identity (all callers use the same key for now)

---

### Option B — Basic Auth per Webhook
n8n webhook nodes support built-in Basic Auth (username + password) natively.

**Pros:** No additional credential type needed

**Cons:**
- Separate credential per webhook node (harder to rotate)
- `Authorization: Basic base64(user:pass)` header — same security posture as Option A but more awkward for API clients
- Browser will prompt a login dialog if called from a browser tab directly

---

### Option C — JWT / OAuth2 (Future)
Issue short-lived tokens from an identity provider (Azure AD, Auth0).

**Pros:** Per-user identity, token expiry, refresh flow, audit trail

**Cons:** Significant complexity, requires an IdP, overkill for current POC phase

---

## Recommended Approach: Option A (API Key Header)

### Implementation Steps

#### 1. Create the Credential in n8n
1. Go to n8n UI → **Credentials** → **New Credential**
2. Type: **Header Auth**
3. Name: `webhook-api-key`
4. Header Name: `X-API-Key`
5. Header Value: generate a random 32-char key, e.g.:
   ```bash
   openssl rand -hex 32
   # Example: a3f2c8e1b7d94f0516a2893cd45e6f78a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
   ```
6. Save the credential.

#### 2. Add Auth to Each Webhook Node
For each of the 5 workflows, open the **Webhook trigger node** and set:

- **Authentication**: `Header Auth`
- **Credential**: `webhook-api-key` (the one created above)

Workflows to update:

| Workflow | Webhook Node Name | Path |
|----------|------------------|------|
| Workflow A | Webhook: Extract Content | `POST /webhook/extract` |
| Workflow B | Webhook: Ingest Standard | `POST /webhook/kb/ingest` |
| Workflow C1 | Webhook: Submit Audit | `POST /webhook/audit/submit` |
| Workflow C3 | Webhook: Get Status | `GET /webhook/audit/status/:id` |
| Workflow C4 | Webhook: Get Results | `GET /webhook/audit/results/:id` |

> **Note:** Internal calls — e.g. Workflow B calling `POST /webhook/extract` and Workflow C1 being called from tests — must also include the `X-API-Key` header. Update any internal `HTTP Request` nodes that call other webhooks.

#### 3. Internal Workflow-to-Workflow Calls
Workflow B calls Workflow A internally via HTTP Request node. After adding auth to Workflow A's webhook, update the HTTP Request node in Workflow B:

```
Add Header:
  Name:  X-API-Key
  Value: {{ $credentials.webhookApiKey.value }}
```
Or: hardcode the key in an n8n credential used by the HTTP Request node.

#### 4. Update Frontend Clients
The frontend (and any curl test calls) must add the header:

```javascript
// JavaScript
const headers = {
  'X-API-Key': 'YOUR_API_KEY_HERE'
};
```

```bash
# curl
curl -H "X-API-Key: YOUR_API_KEY_HERE" \
  -X POST http://172.206.67.83:5678/webhook/audit/submit \
  -F '...'
```

#### 5. Update .env.example
Add the API key as an env var reference for documentation purposes:

```dotenv
# Webhook API Key (set in n8n credentials, referenced here for ops awareness)
WEBHOOK_API_KEY=<generate with: openssl rand -hex 32>
```

---

## Testing After Implementation

```bash
# Should return 401 Unauthorized:
curl -X GET http://172.206.67.83:5678/webhook/audit/status/test-session-id

# Should return 404 or valid response (session not found):
curl -H "X-API-Key: YOUR_KEY" \
  http://172.206.67.83:5678/webhook/audit/status/00000000-0000-0000-0000-000000000000
```

---

## Future Hardening (Beyond POC)

| Step | What it adds |
|------|-------------|
| Enable HTTPS (Let's Encrypt) | Prevents key interception over the wire |
| Per-client API keys | Different keys for frontend, admin, CI — revoke individually |
| Rate limiting (nginx reverse proxy) | Prevents abuse |
| Azure AD / JWT tokens | Full per-user identity and audit trail |
| n8n log review | Every webhook execution logged with IP — review in n8n UI → Executions |

---

## Effort Estimate

| Task | Effort |
|------|--------|
| Create credential in n8n UI | 5 min |
| Update 5 webhook nodes | 15 min |
| Update internal HTTP Request nodes | 10 min |
| Update frontend/test scripts | 10 min |
| **Total** | **~40 min** |
