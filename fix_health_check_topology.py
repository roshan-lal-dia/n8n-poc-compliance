import json
import sys

def fix_topology(file_path):
    with open(file_path, 'r') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. Add "Merge Health & Data" node
    merge_node = {
        "parameters": {
            "mode": "combine",
            "combineBy": "combineByPosition",
            "options": {}
        },
        "id": "merge-health-data",
        "name": "Merge Health & Data",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [900, 460] 
    }
    # Validate Binary was pushed to 1060 (Original 460 + 600)
    # Actually wait. In previous script:
    # ServiceHealthCheck at 460
    # CheckHealthStatus at 680
    # Validate Binary was pushed to 460 + 600 = 1060.
    
    # We want:
    # Webhook -> ServicesHealthCheck (460) -> CheckHealthStatus (680) -> Merge (Inputs 1)
    # Webhook -> Validate Binary (Position 460, Parallel) -> Merge (Inputs 0)
    
    # Let's verify Validate Binary original position. It was 460.
    # The previous script pushed it to 1060.
    # We want Validate Binary at 460 again? Or 680?
    # Let's put Validate Binary at 680 (parallel to CheckHealthStatus)
    # And Merge at 900.
    
    # Update node positions
    for node in nodes:
        if node['name'] == "Validate Binary":
            node['position'] = [680, 200] # Above Check Health Status
        if node['name'] == "Services Health Check":
            node['position'] = [460, 460]
        if node['name'] == "Check Health Status":
            node['position'] = [680, 460]
        if node['name'] == "Set Binary Filename":
            node['position'] = [1120, 300] # It was 680 originally, pushed to 1280. Bring it back a bit.

    nodes.append(merge_node)

    # 2. Wire Connections
    
    # Reset Webhook
    # Connect Webhook to BOTH "Validate Binary" and "Services Health Check"
    connections["Webhook: Extract Content"] = {
        "main": [
            [
                { "node": "Validate Binary", "type": "main", "index": 0 },
                { "node": "Services Health Check", "type": "main", "index": 0 }
            ]
        ]
    }

    # Reset Services Health Check
    connections["Services Health Check"] = {
        "main": [
            [ { "node": "Check Health Status", "type": "main", "index": 0 } ]
        ]
    }

    # Check Health Status
    # Success -> Merge Input 1 (Index 1 in zero-based API? No Merge inputs are by index)
    # Index 0 in Merge node inputs corresponds to input 1.
    # Index 1 corresponds to input 2.
    # We want Data (Validate Binary) on Input 1 (Index 0).
    # We want Health (Check Health Status) on Input 2 (Index 1).
    connections["Check Health Status"] = {
        "main": [
            [ { "node": "Merge Health & Data", "type": "main", "index": 1 } ], # Success
            [ { "node": "Set Service Error", "type": "main", "index": 0 } ]    # Failure
        ]
    }

    # Reset Validate Binary
    # Success -> Merge Input 0 (Index 0)
    # Fail -> Error No File
    connections["Validate Binary"] = {
        "main": [
            [ { "node": "Merge Health & Data", "type": "main", "index": 0 } ], # Output 0 -> Merge Input 0
            [ { "node": "Error: No File", "type": "main", "index": 0 } ]      # Output 1
        ]
    }

    # Merge Node Output -> Set Binary Filename
    connections["Merge Health & Data"] = {
        "main": [
            [ { "node": "Set Binary Filename", "type": "main", "index": 0 } ]
        ]
    }
    
    # Ensure "Set Binary Filename" doesn't have old parents
    # It used to be connected from Validate Binary (in original) or Check Health Status (in broken).
    # We ensure no one else connects to it in the connections map implicitly, 
    # but the `connections` dict is keyed by Source Node.
    # So we just overwrote "Validate Binary" and "Check Health Status" outputs. 
    # That clears old links to "Set Binary Filename".

    workflow['nodes'] = nodes
    workflow['connections'] = connections

    with open(file_path, 'w') as f:
        json.dump(workflow, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fix_topology(sys.argv[1])
    else:
        print("Usage: python script.py <path_to_workflow>")
