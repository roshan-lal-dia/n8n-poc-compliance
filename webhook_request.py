#!/usr/bin/env python3
import subprocess
import sys

# Configuration
url = "http://172.24.11.48:5678/webhook/audit-status-webhook/audit/status/00d0b8b0-a6a2-471e-8b78-8b83b2763215"
api_key = "6e8eadbc1q5mlw63yd2u2cn0hs6jnzf2gljhr486u3dkgm2y311ab345aacb69a901b7a7f"

# Execute curl request
try:
    response = subprocess.run(
        [
            "curl",
            "-X", "GET",
            url,
            "--header", f"X-API-Key: {api_key}"
        ],
        capture_output=True,
        text=True
    )
    
    print("Status Code:", response.returncode)
    print("\nResponse:")
    print(response.stdout)
    
    if response.stderr:
        print("\nError:")
        print(response.stderr)
        
except Exception as e:
    print(f"Error running curl: {e}")
    sys.exit(1)
