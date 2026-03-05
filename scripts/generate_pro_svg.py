import base64
import zlib
import urllib.request

mermaid_code = '''flowchart LR
    classDef default fill:#FFFFFF,stroke:#CBD5E1,stroke-width:2px,color:#334155,rx:6px,ry:6px,font-family:Inter,sans-serif;
    classDef n8n fill:#FF6D5A,stroke:#E04D3A,stroke-width:2px,color:#FFFFFF,font-weight:bold,rx:8px,ry:8px;
    classDef ai fill:#8B5CF6,stroke:#7C3AED,stroke-width:2px,color:#FFFFFF,font-weight:bold,rx:8px,ry:8px;
    classDef db fill:#0F172A,stroke:#020617,stroke-width:2px,color:#F8FAFC,font-weight:bold,rx:8px,ry:8px;
    classDef cloud fill:#0EA5E9,stroke:#0284C7,stroke-width:2px,color:#FFFFFF,font-weight:bold,rx:8px,ry:8px;
    classDef client fill:#10B981,stroke:#059669,stroke-width:2px,color:#FFFFFF,font-weight:bold,rx:8px,ry:8px;

    Client["🌐 Frontend / API Clients"]:::client
    
    subgraph Engine["🏭 Core Orchestration"]
        direction TB
        N8N["⚙️ n8n Workflow Orchestrator<br/>(6 Workflows)"]:::n8n
        
        subgraph Data["💾 Persistence Layer"]
            direction LR
            PG[("PostgreSQL")]:::db
            Redis[("Redis Queue")]:::db
            Qdrant[("Qdrant Vector DB")]:::db
        end
        
        subgraph AITier["🧠 GPU Inference Layer (Passthrough)"]
            direction LR
            Florence["Florence-2<br/>(OCR/Vision API)"]:::ai
            Ollama["Mistral Nemo 12B<br/>(+ nomic-embed)"]:::ai
        end
    end
    
    subgraph Cloud["☁️ Azure Cloud Infrastructure"]
        direction TB
        Blob[("Azure Blob Storage<br/>(Files & Evidence)")]:::cloud
        ExtDB[("Azure PostgreSQL<br/>(Read-Only Data)")]:::cloud
    end

    Client -->|"Webhook POST/GET"| N8N
    
    N8N <-->|"Job Enqueue"| Redis
    N8N <-->|"State & Caches"| PG
    N8N <-->|"RAG Similarity"| Qdrant
    
    N8N <-->|"Image Extent"| Florence
    N8N <-->|"LLM Prompts"| Ollama
    
    N8N -->|"SAS Fetches"| Blob
    N8N -.->|"Dynamic Sync"| ExtDB
    
    style Engine fill:#F8FAFC,stroke:#94A3B8,stroke-width:2px,stroke-dasharray: 4 4,rx:10px
    style Data fill:#F1F5F9,stroke:#CBD5E1,stroke-width:1px,rx:10px
    style AITier fill:#F3F4F6,stroke:#D1D5DB,stroke-width:1px,rx:10px
    style Cloud fill:#F0F9FF,stroke:#BAE6FD,stroke-width:2px,stroke-dasharray: 4 4,rx:10px
'''

data = mermaid_code.encode('utf-8')
encoded = base64.urlsafe_b64encode(zlib.compress(data, 9)).decode('utf-8')
url = 'https://kroki.io/mermaid/svg/' + encoded

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Professional/SVG'})
try:
    with urllib.request.urlopen(req) as r:
        svg = r.read().decode('utf-8')
    with open('docs/diagrams/system-arch.svg', 'w', encoding='utf-8') as f:
        f.write(svg)
    print('Highly polished SVG successfully generated!')
except Exception as e:
    print('Failed:', e)
