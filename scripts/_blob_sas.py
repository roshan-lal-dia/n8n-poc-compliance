#!/usr/bin/env python3
# Usage: _blob_sas.py account_name account_key resource_type container blob_path permissions
# resource_type: "b" = blob, "c" = container, "s" = service (account-level)
# Refs:
#   Account SAS:  https://learn.microsoft.com/rest/api/storageservices/create-account-sas
#   Service SAS:  https://learn.microsoft.com/rest/api/storageservices/create-service-sas
import sys, hmac, hashlib, base64, datetime, urllib.parse

account_name, account_key, resource_type, container, blob_path, permissions = sys.argv[1:]

sv  = "2020-12-06"
now = datetime.datetime.utcnow()
st  = (now - datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
se  = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

if resource_type == "s":
    # Account SAS — sv=2020-12-06 string-to-sign (10 fields + trailing \n)
    # Confirmed by Azure AuthenticationErrorDetail error output.
    string_to_sign = "\n".join([
        account_name,  # 1  accountName
        permissions,   # 2  signedPermissions
        "b",           # 3  signedServices (b=blob)
        "sco",         # 4  signedResourceTypes (s=service, c=container, o=object)
        st,            # 5  signedStart
        se,            # 6  signedExpiry
        "",            # 7  signedIP (empty)
        "https",       # 8  signedProtocol
        sv,            # 9  signedVersion
        "",            # 10 signedEncryptionScope (empty)
        "",            # 11 produces mandatory trailing \n
    ])
    key_bytes = base64.b64decode(account_key)
    sig_b64   = base64.b64encode(
        hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    print(urllib.parse.urlencode({
        "sv": sv, "ss": "b", "srt": "sco", "sp": permissions,
        "st": st, "se": se, "spr": "https", "sig": sig_b64,
    }, quote_via=urllib.parse.quote), end="")

else:
    # Service SAS — sv=2020-12-06, 16 fields, no trailing \n
    canonical = (
        f"/blob/{account_name}/{container}/{blob_path}"
        if resource_type == "b"
        else f"/blob/{account_name}/{container}"
    )
    string_to_sign = "\n".join([
        permissions,    # 1  signedPermissions
        st,             # 2  signedStart
        se,             # 3  signedExpiry
        canonical,      # 4  canonicalizedResource
        "",             # 5  signedIdentifier
        "",             # 6  signedIP
        "https",        # 7  signedProtocol
        sv,             # 8  signedVersion
        resource_type,  # 9  signedResource ("b" or "c")
        "",             # 10 signedSnapshotTime
        "",             # 11 signedEncryptionScope
        "",             # 12 rscc
        "",             # 13 rscd
        "",             # 14 rsce
        "",             # 15 rscl
        "",             # 16 rsct
    ])
    key_bytes = base64.b64decode(account_key)
    sig_b64   = base64.b64encode(
        hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    print(urllib.parse.urlencode({
        "sv": sv, "st": st, "se": se, "sr": resource_type,
        "sp": permissions, "spr": "https", "sig": sig_b64,
    }, quote_via=urllib.parse.quote), end="")
