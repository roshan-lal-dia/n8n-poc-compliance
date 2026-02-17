# Copilot instructions for n8n-poc-compliance

## Project context
- This repo contains an n8n workflow definition in `compliance-poc.json`.
- The workflow is intended for local execution using Docker with custom CLI tools (`libreoffice`, `pdftoppm`).

## Key rules
- Never try try to import workflows I will do it manually. Just generate the JSON for the nodes and connections.
- **JSON Structure**: Prefer n8n UI-generated node JSON formats. Keep `typeVersion` consistent (e.g., Switch v3.4, Set v3.4).
- **Node IDs/Positions**: Preserve existing `id`, `name`, and `position` values to avoid breaking the UI layout.
- **Connections**: Maintain the strict `connections` object structure where keys are node names.
- Never use the archive-poc folder for any code generation or thinking or answering, it;s only for archive storage.

## File Handling & Local Execution (Module 3)
- **Temp Persistence**: All temporary files must be written to or read from `/tmp/n8n_processing/`.
- **Concurrency**: Do NOT use static filenames (e.g., `input.pdf`).
  - Use a `filePrefix` (generated in "Set Binary Filename" node) for all file operations.
  - Pattern: `/tmp/n8n_processing/{{unique_prefix}}filename.ext`.
- **CLI Commands**:
  - Do NOT rely on `{{ $binary.data.fileName }}` in `Execute Command` nodes; it is unreliable.
  - Construct paths explicitly using the `filePrefix` variable.
  - Example: `libreoffice ... "/tmp/n8n_processing/{{ $node["Set Binary Filename"].json["filePrefix"] }}input.pptx"`

## n8n Schema Specifics
- **Switch Node (v3.4)**: Uses `parameters.rules.values[]` and `options.fallbackOutput: "extra"`.
- **Set Node (v3.4)**: Uses `parameters.mode: "raw"` and `parameters.jsonOutput`.

## Coding Guidelines
- **Code Nodes**: console.log() output is hidden. Use `return` to verify data.
- **Python**: `return {"key": "value"}` or `return _input.all()`
- **JavaScript**: `return {json: {key: "value"}}` or `return $input.all()`
