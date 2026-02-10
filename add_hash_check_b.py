import json
import sys

def modify_workflow(file_path):
    with open(file_path, 'r') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # ==========================================
    # 1. DEFINE NEW NODES
    # ==========================================
    
    # Node: Calculate File Hash
    node_calc_hash = {
        "parameters": {
            "jsCode": "const crypto = require('crypto');\nconst items = $input.all();\nreturn items.map(item => {\n  const binaryKey = Object.keys(item.binary)[0];\n  const binaryData = item.binary[binaryKey];\n  // Calculate SHA-256 hash of the binary data\n  const hash = crypto.createHash('sha256').update(Buffer.from(binaryData.data, 'base64')).digest('hex');\n  \n  return {\n    json: {\n      ...item.json,\n      fileHash: hash\n    },\n    binary: item.binary\n  };\n});"
        },
        "id": "calculate-file-hash",
        "name": "Calculate File Hash",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2896, -336] # Replaces Validate Input's next spot
    }

    # Node: Check DB for Hash
    node_check_db = {
        "parameters": {
            "operation": "executeQuery",
            "query": "SELECT id, standard_name FROM kb_standards WHERE file_hash = $1",
            "options": {}
        },
        "id": "check-hash-db",
        "name": "Check Hash in DB",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": [3100, -336],
        "credentials": {
            "postgres": {
                "id": "3ME8TvhWnolXkgqg",
                "name": "Compliance DB"
            }
        }
    }
    
    # Node: Switch (Exists vs New)
    node_switch_exists = {
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                                "version": 3
                            },
                            "conditions": [
                                {
                                    "id": "is-new",
                                    "leftValue": "={{ $json.id }}",
                                    "rightValue": "",
                                    "operator": {
                                        "type": "boolean",
                                        "operation": "empty"
                                    }
                                }
                            ],
                            "combinator": "and"
                        }
                    }
                ]
            },
            "options": {
                "fallbackOutput": "extra" # Fallback means it was NOT empty, so it Exists
            }
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.4,
        "position": [3300, -336],
        "id": "switch-is-new",
        "name": "Is New File?"
    }
    
    # Node: Already Exists Response
    node_exists_response = {
        "parameters": {
            "mode": "raw",
            "jsonOutput": "={{ { \"message\": \"File already ingested\", \"standardName\": $json.standard_name, \"status\": \"skipped\", \"dbId\": $json.id } }}",
            "options": {}
        },
        "id": "set-exists-msg",
        "name": "Set: Already Exists",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [3500, -150]
    }

    # Update: Insert to Postgres (Fix Query to match Schema)
    # Schema: id, domain, standard_name, filename, file_hash, total_chunks, qdrant_collection, uploaded_at
    # Missing from Schema: version, full_text, metadata. We will omit them or store in a separate table if needed, 
    # but for now let's just insert what fits into kb_standards.
    # We will assume 'metadata' column might be desired, but strict schema doesn't have it.
    # We will map:
    # standard_name -> standard_name
    # domain -> domain
    # content_hash -> file_hash
    # version -> (Dropped or appended to name?)
    # totalChunks -> total_chunks
    
    # Searching for existing Postgres Node to update
    for node in nodes:
        if node['name'] == "Insert to Postgres":
            # Fix the query
            node['parameters']['query'] = """
            INSERT INTO kb_standards (standard_name, domain, file_hash, filename, total_chunks, uploaded_at) 
            VALUES ($1, $2, $3, $4, $5, NOW()) 
            ON CONFLICT (file_hash) DO UPDATE SET uploaded_at = NOW() 
            RETURNING id
            """
            # We need to ensure the INPUT to this node has these values.
            # The input comes from "Upsert to Qdrant".
            # We need to map the values correctly in the expression:
            # $1: standardName
            # $2: domain
            # $3: fileHash (We need to pass this down from the start!)
            # $4: originalFileName
            # $5: chunks count
            
            # Use 'Prepare Metadata' node to carry the fileHash?
            # Or retrieve it? 
            # I will check 'Prepare Metadata' next.
            pass

    # Update: Prepare Metadata (Pass fileHash)
    for node in nodes:
        if node['name'] == "Prepare Metadata":
            # Add fileHash to the output
            new_code = node['parameters']['jsCode'].replace(
                "uploadedAt: new Date().toISOString()", 
                "uploadedAt: new Date().toISOString(),\n      fileHash: $('Calculate File Hash').first().json.fileHash"
            )
            node['parameters']['jsCode'] = new_code

    # Add new nodes
    nodes.extend([node_calc_hash, node_check_db, node_switch_exists, node_exists_response])

    # ==========================================
    # 2. SHIFT EXISTING NODES
    # ==========================================
    # Shift everything after Validate Input to the right to make space
    SHIFT = 800
    for node in nodes:
        if node['position'][0] > 2800 and node['name'] not in ["Webhook: Ingest Standard", "Validate Input", "Calculate File Hash", "Check Hash in DB", "Is New File?", "Set: Already Exists"]:
             node['position'][0] += SHIFT

    # ==========================================
    # 3. WIRE CONNECTIONS
    # ==========================================
    
    # 1. Validate Input -> Calculate File Hash (Instead of Normalize)
    connections["Validate Input"]["main"][0] = [
        { "node": "Calculate File Hash", "type": "main", "index": 0 }
    ]
    
    # 2. Calculate File Hash -> Check Hash in DB
    connections["Calculate File Hash"] = {
        "main": [[{ "node": "Check Hash in DB", "type": "main", "index": 0 }]]
    }
    
    # 3. Check Hash in DB -> Is New File?
    connections["Check Hash in DB"] = {
        "main": [[{ "node": "Is New File?", "type": "main", "index": 0 }]]
    }
    
    # 4. Is New File?
    # True (New/Empty ID) -> Normalize Binary Data
    # False (Exists) -> Set: Already Exists
    connections["Is New File?"] = {
        "main": [
            [ { "node": "Normalize Binary Data", "type": "main", "index": 0 } ], # Output 0
            [ { "node": "Set: Already Exists", "type": "main", "index": 0 } ]    # Output 1
        ]
    }
    
    # 5. Set: Already Exists -> Respond to Webhook
    connections["Set: Already Exists"] = {
        "main": [[{ "node": "Respond to Webhook", "type": "main", "index": 0 }]]
    }
    
    # 6. Normalize Binary Data - Needs to get Binary from "Is New File?"
    # Since Switch passes through data, it works. 
    # But wait, Check Hash in DB replaces the JSON with query result (id, standard_name).
    # We LOST the Binary Data in the Postgres node!
    # Fix: Postgres node removes binary.
    # We must use "Calculate File Hash" data for the "True" branch.
    # But n8n passes output of previous node.
    
    # Solution: We cannot daisy chain easily if Postgres eats binary.
    # We need to MERGE the Postgres result with the original data OR run Postgres separately.
    # Better approach for n8n:
    # Validate -> Calculate Hash -> Check DB -> Switch
    # IF New: We need the Binary Data.
    # The Binary Data was available at "Calculate File Hash".
    # We can use a Merge Node after Switch to "Recover" previous context? No.
    
    # Simpler: Use the "Parameters" in Execute Query to NOT replace execution item? No.
    # Or, simple hack:
    # Put the Postgres check in a separate branch?
    # Or use a Merge node:
    # Branch 1: Calc Hash -> Pass
    # Branch 2: Calc Hash -> Postgres -> Switch
    # Merge (Wait for Switch)? Complex.
    
    # BETTER FIX:
    # Modify `Calculate File Hash` to `Check Hash Availability`?
    # No.
    # Let's use the fact that we can access `$('Calculate File Hash').item.binary` in downstream nodes if we are careful?
    # No, Binary is heavy.
    
    # Standard Pattern:
    # 1. Calc Hash.
    # 2. Postgres Lookup.
    # 3. If Exists -> Stop.
    # 4. If New -> Use "Edit Fields" or "Code" node to restore Binary from `$('Calculate File Hash')`?
    #    Actually, if the PG node loses binary, we can't easily get it back in the stream without reference.
    
    # NEW PLAN:
    # Move Postgres Check to *Parallel* or use a Merge node to join "Data" and "Hash Status".
    
    pass 
    
    # Let's write specific connection logic later. 
    # For now, let's inject a "Restore Binary" node after "Is New File?" (True branch).
    restore_binary_node = {
        "parameters": {
            "jsCode": "const originalItems = $('Calculate File Hash').all();\n// We assume 1-to-1 processing\nreturn originalItems.map(item => ({\n  json: item.json,\n  binary: item.binary\n}));"
        },
        "id": "restore-binary",
        "name": "Restore Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3500, -500] # Start of main pipeline
    }
    nodes.append(restore_binary_node)
    
    # Update connections for Restore
    # Is New File (True) -> Restore Data
    connections["Is New File?"]["main"][0] = [
         { "node": "Restore Data", "type": "main", "index": 0 }
    ]
    
    # Restore Data -> Normalize Binary Data
    connections["Restore Data"] = {
        "main": [[{ "node": "Normalize Binary Data", "type": "main", "index": 0 }]]
    }

    workflow['nodes'] = nodes
    workflow['connections'] = connections

    with open(file_path, 'w') as f:
        json.dump(workflow, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        modify_workflow(sys.argv[1])
    else:
        print("Usage: python script.py <path_to_workflow>")
