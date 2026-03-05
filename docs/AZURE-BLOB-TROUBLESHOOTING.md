# Azure Blob Storage — Troubleshooting & Admin Escalation Guide

Use this doc when `_blob_sas.py` or `blob_browser.sh` fail in a new Azure environment.
Run `./scripts/debug_azure.sh` first and match the error below.

---

## Error: `AuthenticationFailed` — Signature did not match

**Full error example:**
```
AuthenticationErrorDetail: Signature did not match. String to sign used was stcompdldevqc01\nl\nb\n...
```

**Cause:** The account key in `.env` is either:
- Wrong (old tenant key copied into new tenant config), or
- Stale (key was rotated in Azure portal since it was captured)

**Fix — ask admin:**
> "Can you confirm the current active key1 value for storage account `<account_name>`?
> Go to: Azure Portal → Storage Accounts → `<account_name>` → Security + Networking → Access Keys → Show key1"

Then update `.env` using:
```bash
python3 - << 'EOF'
import os, re
env_path = "/home/azadmin/n8n-poc-compliance/.env"
new_key  = "<PASTE_NEW_KEY_HERE>"
new_conn = f"DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey={new_key};EndpointSuffix=core.windows.net"
with open(env_path) as f: content = f.read()
content = re.sub(r"AZURE_STORAGE_ACCOUNT_KEY=.*\n?", "", content)
content = re.sub(r"AZURE_STORAGE_CONNECTION_STRING=.*\n?", "", content)
content = content.rstrip("\n") + f"\nAZURE_STORAGE_ACCOUNT_KEY={new_key}\nAZURE_STORAGE_CONNECTION_STRING={new_conn}\n"
with open(env_path, "w") as f: f.write(content)
print("Done")
EOF
```

> ⚠️ Never use `sed` to update the key — the `/` and `+` characters in base64 keys break sed substitution.

---

## Error: `KeyBasedAuthenticationNotPermitted`

**Full error example:**
```xml
<Code>KeyBasedAuthenticationNotPermitted</Code>
<Message>Key based authentication is not permitted on this storage account.</Message>
```

**Cause:** The storage account has "Allow storage account key access" **disabled**, either manually or enforced by an Azure Policy at subscription/resource group level.

**Fix — ask admin (Option A, fastest):**
> "Please enable 'Allow storage account key access' on storage account `<account_name>`.
> Go to: Azure Portal → Storage Accounts → `<account_name>` → Settings → Configuration → Allow storage account key access → **Enabled** → Save"

**Fix — ask admin (Option B, if policy blocks Option A):**
> "There appears to be an Azure Policy preventing key-based auth on this storage account.
> Can you either:
> (a) Exempt storage account `<account_name>` from the policy, or
> (b) Assign the VM's Managed Identity `Storage Blob Data Contributor` role on the storage account so we can use OAuth instead?"

---

## Error: `AADSTS7000232` — MSI identity should not use ClientSecretCredential

**Full error example:**
```json
{"error":"invalid_client","error_description":"AADSTS7000232: MSI identity (xxxxxxxx) should not use ClientSecretCredential"}
```

**Cause:** The `AZURE_CLIENT_ID` in `.env` is a **Managed Identity**, not a Service Principal. Managed Identities cannot use client secrets — they authenticate via the VM's IMDS endpoint (`169.254.169.254`).

**Fix — ask admin:**
> "The client ID `<client_id>` appears to be a user-assigned Managed Identity, not a Service Principal.
> Can you assign this Managed Identity to the VM `<vm_name>`?
> Go to: Azure Portal → Virtual Machines → `<vm_name>` → Identity → User assigned → Add → select the identity"
>
> Also confirm: does this identity have `Storage Blob Data Contributor` role on storage account `<account_name>`?
> Go to: Storage Account → Access Control (IAM) → Role assignments → check for the identity"

---

## Error: `Identity not found` from IMDS

**Full error example:**
```json
{"error":"invalid_request","error_description":"Identity not found"}
```

**Cause:** A Managed Identity `AZURE_CLIENT_ID` is set in `.env`, but that identity **is not assigned to this VM**. The identity exists in Entra ID but hasn't been attached.

**Fix — ask admin:**
> "The Managed Identity `<client_id>` is not assigned to VM `<vm_name>`.
> Please assign it via:
> Azure Portal → Virtual Machines → `<vm_name>` → Identity → User assigned → Add
>
> Alternatively, enable key-based auth on the storage account (see `KeyBasedAuthenticationNotPermitted` section above)."

---

## Error: `AADSTS700016` — Application not found in tenant

**Full error example:**
```json
{"error":"unauthorized_client","error_description":"AADSTS700016: Application with identifier 'xxxxxxxx' was not found in directory..."}
```

**Cause:** The `AZURE_CLIENT_ID` does not exist in the Azure tenant specified by `AZURE_TENANT_ID`, or the wrong tenant ID is configured.

**Fix — ask admin:**
> "The App Registration / Service Principal `<client_id>` was not found in tenant `<tenant_id>`.
> Can you confirm:
> 1. The correct tenant ID for this environment (Azure Portal → Microsoft Entra ID → Overview → Tenant ID)
> 2. Whether App Registration `<client_id>` exists in that tenant (Entra ID → App Registrations → All applications)"

---

## Error: `AADSTS7000215` — Invalid client secret

**Full error example:**
```json
{"error":"invalid_client","error_description":"AADSTS7000215: Invalid client secret provided."}
```

**Cause:** The `AZURE_CLIENT_SECRET` in `.env` is expired or incorrect.

**Fix — ask admin:**
> "The client secret for App Registration `<client_id>` is invalid or expired.
> Please generate a new secret:
> Azure Portal → Microsoft Entra ID → App Registrations → `<client_id>` → Certificates & secrets → New client secret
> Then share the new secret value (not the secret ID)."

---

## Error: `403 Forbidden` after successful token acquisition (OAuth)

**Cause:** Token was obtained successfully but the identity lacks RBAC on the storage account.

**Fix — ask admin:**
> "Authentication succeeds but access is forbidden. The identity `<client_id>` needs the following role on storage account `<account_name>`:
> - **`Storage Blob Data Contributor`** (read + write + generate User Delegation Key)
>   or at minimum **`Storage Blob Data Reader`** (read-only)
>
> Go to: Azure Portal → Storage Accounts → `<account_name>` → Access Control (IAM) → Add role assignment → select the identity"

---

## Quick Diagnostic Checklist

Run `./scripts/debug_azure.sh` and check which step fails:

| Step fails | Most likely cause | Section above |
|---|---|---|
| Step 2 (SAS generation) exits non-zero | Wrong/missing env vars, key has newline | — |
| HTTP 403 `AuthenticationFailed` | Wrong or stale account key | Signature did not match |
| HTTP 403 `KeyBasedAuthenticationNotPermitted` | Key access disabled on account | KeyBasedAuthenticationNotPermitted |
| Token step `AADSTS7000232` | Client ID is a Managed Identity, not SP | AADSTS7000232 |
| Token step HTTP 400 `Identity not found` | MI not assigned to VM | Identity not found |
| Token step `AADSTS700016` | Wrong client ID or tenant ID | AADSTS700016 |
| Token step `AADSTS7000215` | Client secret expired | AADSTS7000215 |
| HTTP 403 after token success | Missing RBAC role | 403 after token |

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Yes | Full connection string (contains account name + key) |
| `AZURE_STORAGE_ACCOUNT_NAME` | Yes | Storage account name (e.g. `stcompdldevqc01`) |
| `AZURE_STORAGE_ACCOUNT_KEY` | Yes | Base64 key1 or key2 from Azure portal |
| `AZURE_TENANT_ID` | OAuth only | Entra ID tenant GUID |
| `AZURE_CLIENT_ID` | OAuth only | App Registration or Managed Identity client ID |
| `AZURE_CLIENT_SECRET` | SP only | App Registration secret (not used for Managed Identity) |

> The `.env` file must not have line breaks inside key values. Use the Python snippet above to safely write `.env` entries that contain special characters (`/`, `+`, `=`, `;`).
