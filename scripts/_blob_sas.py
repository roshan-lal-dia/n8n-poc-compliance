#!/usr/bin/env python3
# Usage: _blob_sas.py account_name account_key resource_type container blob_path permissions
# resource_type: "b" = blob, "c" = container, "s" = service (account-level listing)
#
# OAuth mode (preferred): set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET in env.
#   - resource_type "b"/"c": outputs a User Delegation SAS query string (drop-in replacement)
#   - resource_type "s":     outputs "BEARER:<access_token>" for use as Authorization header
#
# Shared Key fallback: used only when OAuth env vars are absent.
#   NOTE: KeyBasedAuthenticationNotPermitted policy will block this mode.
#
# Refs:
#   User Delegation SAS: https://learn.microsoft.com/rest/api/storageservices/create-user-delegation-sas
#   Get User Delegation Key: https://learn.microsoft.com/rest/api/storageservices/get-user-delegation-key
import sys, hmac, hashlib, base64, datetime, urllib.parse, os, json

# ── Load .env from repo root if running on VM (not inside container) ─────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith('#') or '=' not in _line:
                continue
            _k, _, _v = _line.partition('=')
            os.environ.setdefault(_k.strip(), _v.strip())

account_name, account_key, resource_type, container, blob_path, permissions = sys.argv[1:]

sv  = "2020-12-06"
now = datetime.datetime.utcnow()
st  = (now - datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
se  = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

tenant_id     = os.environ.get("AZURE_TENANT_ID", "")
client_id     = os.environ.get("AZURE_CLIENT_ID", "")
client_secret = os.environ.get("AZURE_CLIENT_SECRET", "")
USE_OAUTH     = bool(tenant_id and client_id and client_secret)


def _get_access_token():
    """Client-credentials OAuth2 token for https://storage.azure.com/"""
    import urllib.request, urllib.error
    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://storage.azure.com/.default",
    }).encode()
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[OAUTH ERROR] HTTP {e.code} from token endpoint", file=sys.stderr)
        print(f"[OAUTH ERROR] body: {body}", file=sys.stderr)
        print(f"[OAUTH ERROR] tenant_id={repr(tenant_id)}", file=sys.stderr)
        print(f"[OAUTH ERROR] client_id={repr(client_id)}", file=sys.stderr)
        print(f"[OAUTH ERROR] secret_len={len(client_secret)} secret_last4={repr(client_secret[-4:])}", file=sys.stderr)
        raise


def _get_user_delegation_key(token):
    """
    POST ?restype=service&comp=userdelegationkey
    Returns dict with skoid/sktid/skt/ske/sks/skv/value.
    """
    import urllib.request, xml.etree.ElementTree as ET
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<KeyInfo>'
        f'<Start>{st}</Start>'
        f'<Expiry>{se}</Expiry>'
        '</KeyInfo>'
    ).encode()
    url = (f"https://{account_name}.blob.core.windows.net/"
           "?restype=service&comp=userdelegationkey")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "x-ms-version":  sv,
        "x-ms-date":     now.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "Content-Type":  "application/xml",
    })
    with urllib.request.urlopen(req) as resp:
        root = ET.fromstring(resp.read())
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    def _g(tag):
        el = root.find(f"{ns}{tag}")
        return el.text if el is not None else ""
    return {
        "skoid": _g("SignedOid"),
        "sktid": _g("SignedTid"),
        "skt":   _g("SignedStart"),
        "ske":   _g("SignedExpiry"),
        "sks":   _g("SignedService"),
        "skv":   _g("SignedVersion"),
        "value": _g("Value"),
    }


if USE_OAUTH:
    token = _get_access_token()

    # ── Account-level (list containers): return Bearer token directly ─────────
    if resource_type == "s":
        print(f"BEARER:{token}", end="")
        sys.exit(0)

    # ── Blob / Container: User Delegation SAS ─────────────────────────────────
    dk = _get_user_delegation_key(token)

    sr = "b" if resource_type == "b" else "c"
    canonical = (
        f"/blob/{account_name}/{container}/{blob_path}"
        if resource_type == "b"
        else f"/blob/{account_name}/{container}"
    )

    # MS Learn User Delegation SAS string-to-sign (sv=2020-12-06), 24 fields, no trailing \n
    # https://learn.microsoft.com/rest/api/storageservices/create-user-delegation-sas
    string_to_sign = "\n".join([
        permissions,   # 1  signedPermissions
        st,            # 2  signedStart
        se,            # 3  signedExpiry
        canonical,     # 4  canonicalizedResource
        dk["skoid"],   # 5  signedKeyObjectId
        dk["sktid"],   # 6  signedKeyTenantId
        dk["skt"],     # 7  signedKeyStart
        dk["ske"],     # 8  signedKeyExpiry
        dk["sks"],     # 9  signedKeyService
        dk["skv"],     # 10 signedKeyVersion
        "",            # 11 signedAuthorizedObjectId
        "",            # 12 signedUnauthorizedObjectId
        "",            # 13 signedCorrelationId
        "",            # 14 signedIP
        "https",       # 15 signedProtocol
        sv,            # 16 signedVersion
        sr,            # 17 signedResource
        "",            # 18 signedSnapshotTime
        "",            # 19 signedEncryptionScope
        "",            # 20 rscc
        "",            # 21 rscd
        "",            # 22 rsce
        "",            # 23 rscl
        "",            # 24 rsct
    ])

    key_bytes = base64.b64decode(dk["value"])
    sig       = hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sig_b64   = base64.b64encode(sig).decode()

    qs = urllib.parse.urlencode({
        "sv":    sv,
        "st":    st,
        "se":    se,
        "sks":   dk["sks"],
        "skv":   dk["skv"],
        "skt":   dk["skt"],
        "ske":   dk["ske"],
        "skoid": dk["skoid"],
        "sktid": dk["sktid"],
        "sr":    sr,
        "sp":    permissions,
        "spr":   "https",
        "sig":   sig_b64,
    }, quote_via=urllib.parse.quote)
    print(qs, end="")

else:
    # ── Shared Key SAS fallback (blocked if KeyBasedAuthenticationNotPermitted) ─
    if resource_type == "s":
        string_to_sign = "\n".join([
            account_name, permissions, "b", "sco", st, se, "", "https", sv, "", "",
        ])
        key_bytes = base64.b64decode(account_key)
        sig       = hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
        sig_b64   = base64.b64encode(sig).decode()
        qs = urllib.parse.urlencode({
            "sv": sv, "ss": "b", "srt": "sco", "sp": permissions,
            "st": st, "se": se, "spr": "https", "sig": sig_b64,
        }, quote_via=urllib.parse.quote)
        print(qs, end="")
    else:
        canonical = (
            f"/blob/{account_name}/{container}/{blob_path}"
            if resource_type == "b"
            else f"/blob/{account_name}/{container}"
        )
        string_to_sign = "\n".join([
            permissions, st, se, canonical, "", "", "https", sv,
            resource_type, "", "", "", "", "", "", "",
        ])
        key_bytes = base64.b64decode(account_key)
        sig       = hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
        sig_b64   = base64.b64encode(sig).decode()
        qs = urllib.parse.urlencode({
            "sv": sv, "st": st, "se": se, "sr": resource_type,
            "sp": permissions, "spr": "https", "sig": sig_b64,
        }, quote_via=urllib.parse.quote)
        print(qs, end="")
