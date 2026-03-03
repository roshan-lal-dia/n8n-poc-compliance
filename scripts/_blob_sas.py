#!/usr/bin/env python3
# Usage: _blob_sas.py account_name account_key resource_type container blob_path permissions
# resource_type: "b" = blob, "c" = container, "s" = service (account-level)
# Reference: https://learn.microsoft.com/en-us/rest/api/storageservices/create-account-sas
import sys, hmac, hashlib, base64, datetime, urllib.parse

account_name, account_key, resource_type, container, blob_path, permissions = sys.argv[1:]

sv = "2020-12-06"
now = datetime.datetime.utcnow()
st = (now - datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
se = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

# Account SAS vs Service SAS have different signature formats
if resource_type == "s":
    # Account SAS (service-level) - for listing containers
    # MS Learn docs define two formats:
    #   Pre-2020-12-06 (9 fields):  ... + signedversion + "\n"
    #   2020-12-06    (10 fields):  ... + signedversion + "\n" + signedEncryptionScope + "\n"
    # The Azure error shows the server is computing with 9 fields (pre-2020-12-06 format),
    # so we use sv=2020-12-06 but sign with the 9-field format + mandatory trailing "\n".
    # The trailing "" in the join produces the required trailing "\n" after signedversion.
    string_to_sign = "\n".join([
        account_name,  # 1  accountName
        permissions,   # 2  signedPermissions (e.g., "l" for list)
        "b",           # 3  signedServices (b=blob)
        "sco",         # 4  signedResourceTypes (s=service, c=container, o=object)
        st,            # 5  signedStart
        se,            # 6  signedExpiry
        "",            # 7  signedIP (empty)
        "https",       # 8  signedProtocol
        sv,            # 9  signedVersion
        "",            # 10 trailing "\n" — required by pre-2020-12-06 spec
    ])
else:
    # Service SAS (blob or container level)
    # Canonical resource
    if resource_type == "b":
        canonical = f"/blob/{account_name}/{container}/{blob_path}"
    else:  # "c"
        canonical = f"/blob/{account_name}/{container}"
    
    # sv=2020-12-06: 16 fields, 15 \n, NO trailing newline
    # signedPermissions, signedStart, signedExpiry, canonicalizedResource,
    # signedIdentifier, signedIP, signedProtocol, signedVersion,
    # signedResource, signedSnapshotTime, signedEncryptionScope,
    # rscc, rscd, rsce, rscl, rsct
    string_to_sign = "\n".join([
        permissions,   # 1  signedPermissions
        st,            # 2  signedStart
        se,            # 3  signedExpiry
        canonical,     # 4  canonicalizedResource
        "",            # 5  signedIdentifier
        "",            # 6  signedIP
        "https",       # 7  signedProtocol
        sv,            # 8  signedVersion
        resource_type, # 9  signedResource  ("b" or "c")
        "",            # 10 signedSnapshotTime
        "",            # 11 signedEncryptionScope  (NEW in 2020-12-06)
        "",            # 12 rscc
        "",            # 13 rscd
        "",            # 14 rsce
        "",            # 15 rscl
        "",            # 16 rsct
    ])

key_bytes = base64.b64decode(account_key)
sig = hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
sig_b64 = base64.b64encode(sig).decode()

# Build query string - different parameters for account SAS vs service SAS
if resource_type == "s":
    # Account SAS query parameters
    qs = urllib.parse.urlencode({
        "sv":  sv,
        "ss":  "b",      # signedServices (blob)
        "srt": "sco",    # signedResourceTypes (service, container, object)
        "sp":  permissions,
        "st":  st,
        "se":  se,
        "spr": "https",
        "sig": sig_b64,
    }, quote_via=urllib.parse.quote)
else:
    # Service SAS query parameters
    qs = urllib.parse.urlencode({
        "sv":  sv,
        "st":  st,
        "se":  se,
        "sr":  resource_type,
        "sp":  permissions,
        "spr": "https",
        "sig": sig_b64,
    }, quote_via=urllib.parse.quote)

print(qs, end="")
