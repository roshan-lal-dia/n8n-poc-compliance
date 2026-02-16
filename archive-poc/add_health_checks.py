import json
import sys

def modify_workflow(file_path):
    with open(file_path, 'r') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. Shift existing nodes to the right
    # Webhook is at 240. We want to insert checks after it. 
    # Current next node is Validate Binary at 460.
    # We will insert:
    # - Services Health Check at 460
    # - Check Health Status at 680
    # - Validate Binary moves to 900+
    
    SHIFT_AMOUNT = 600
    
    for node in nodes:
        if node['name'] != "Webhook: Extract Content" and node['position'][0] >= 400:
            node['position'][0] += SHIFT_AMOUNT

    # 2. Add new nodes
    new_nodes = [
        {
            "parameters": {
                "command": "curl -sf --max-time 5 http://florence:5000/health && curl -sf --max-time 5 http://ollama:11434/ && curl -sf --max-time 5 http://qdrant:6333/healthz"
            },
            "id": "services-health-check",
            "name": "Services Health Check",
            "type": "n8n-nodes-base.executeCommand",
            "typeVersion": 1,
            "position": [460, 460],
            "continueOnFail": True
        },
        {
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
                                        "id": "health-check-pass",
                                        "leftValue": "={{ $json.exitCode }}",
                                        "rightValue": 0,
                                        "operator": {
                                            "type": "number",
                                            "operation": "equals"
                                        }
                                    }
                                ],
                                "combinator": "and"
                            }
                        }
                    ]
                },
                "options": {
                    "fallbackOutput": "extra"
                }
            },
            "type": "n8n-nodes-base.switch",
            "typeVersion": 3.4,
            "position": [680, 460],
            "id": "check-health-status",
            "name": "Check Health Status"
        },
        {
            "parameters": {
                "mode": "raw",
                "jsonOutput": "={{ { \"error\": \"Service Dependency Check Failed. One or more services (Florence, Ollama, Qdrant) are unavailable.\", \"status\": 503, \"details\": $json } }}"
            },
            "id": "set-service-error",
            "name": "Set Service Error",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [680, 680]
        },
        {
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ $json }}",
                "options": {
                    "responseCode": 503
                }
            },
            "id": "respond-error-service",
            "name": "Respond Error Service",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [900, 680]
        }
    ]

    nodes.extend(new_nodes)

    # 3. Update Connections
    # Remove Webhook -> Validate Binary
    if "Webhook: Extract Content" in connections:
        # Find connection to Validate Binary and remove it
        new_main = []
        for conn_group in connections["Webhook: Extract Content"]["main"]:
            new_group = [c for c in conn_group if c["node"] != "Validate Binary"]
            if new_group:
                new_main.append(new_group)
        
        # Add connection to Services Health Check
        # Assuming index 0 is the main output
        if not new_main:
            new_main = [[{"node": "Services Health Check", "type": "main", "index": 0}]]
        else:
            new_main[0].append({"node": "Services Health Check", "type": "main", "index": 0})
            
        connections["Webhook: Extract Content"]["main"] = new_main
    else:
        # Should exist
        connections["Webhook: Extract Content"] = {
            "main": [[{"node": "Services Health Check", "type": "main", "index": 0}]]
        }

    # Connect Services Health Check -> Check Health Status
    connections["Services Health Check"] = {
        "main": [
            [
                {
                    "node": "Check Health Status",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Connect Check Health Status -> Validate Binary (Index 0 - Match)
    # Connect Check Health Status -> Set Service Error (Index 1 - Fallback/Extra) (Actually Switch v3 has output 0 for rule 1, output 1 for rule 2? No switch v3 defines outputs based on rules order + fallback)
    # Rule 0 is "exitCode == 0". Fallback is "extra".
    # So index 0 is Success, index 1 is Fail.
    connections["Check Health Status"] = {
        "main": [
            [
                {
                    "node": "Validate Binary",
                    "type": "main",
                    "index": 0
                }
            ],
            [
                {
                    "node": "Set Service Error",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Connect Set Service Error -> Respond Error Service
    connections["Set Service Error"] = {
        "main": [
            [
                {
                    "node": "Respond Error Service",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
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
