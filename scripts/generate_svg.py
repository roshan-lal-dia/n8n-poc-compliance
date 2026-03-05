import base64
import zlib
import urllib.request

mermaid_code = '''flowchart TD
    Frontend["Frontend / API Clients"] <--> n8n["n8n Workflow Engine (6 workflows)"]
    n8n <--> Qdrant["Qdrant (RAG)<br>768-dim"]
    n8n --> Florence["Florence-2 (GPU)<br>OCR + Vision"]
    n8n --> Redis["Redis Queue<br>C1->C2"]
    n8n --> Postgres["PostgreSQL<br>(sessions, evidence, logs, KB)"]
    Florence -.-> Ollama["Mistral Nemo 12B<br>via Ollama"]
    Postgres -.-> Azure["Azure Blob Storage<br>(file uploads)"]
'''

data = mermaid_code.encode('utf-8')
compressed = zlib.compress(data, 9)
encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
url = f'https://kroki.io/mermaid/svg/{encoded}'

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        svg = response.read().decode('utf-8')
    with open('docs/diagrams/system-arch.svg', 'w', encoding='utf-8') as f:
        f.write(svg)
    print('SVG created at docs/diagrams/system-arch.svg')
except Exception as e:
    print(e)
