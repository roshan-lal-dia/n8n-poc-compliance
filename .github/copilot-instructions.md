# Copilot instructions for n8n-poc-compliance

## Project context
- This repo contains an n8n workflow definition in compliance-poc.json.
- The workflow is imported into n8n UI, so JSON structure must match the n8n version used by the UI.

## Key rules
- Prefer n8n UI-generated node JSON formats (current UI uses newer schema for Switch and Set nodes).
- When editing compliance-poc.json, keep node `typeVersion` consistent with the UI (e.g., Switch v3.4 and Set v3.4 if created in UI).
- Do not add empty `options: {}` unless the UI schema includes it for that node/version.
- Preserve existing node `id`, `name`, and `position` values unless explicitly asked to change them.
- Keep `connections` consistent with node names; node names are the keys under `connections`.

## n8n schema specifics (observed)
- Switch node (v3.4) uses:
  - parameters.rules.values[] with full condition objects
  - parameters.options.fallbackOutput set to "extra"
- Set node (v3.4) uses:
  - parameters.mode: "raw"
  - parameters.jsonOutput: a JSON string

## Editing guidance
- Make minimal changes; avoid reformatting or reordering nodes.
- Validate that JSON remains valid and importable.

## Code nodes
- Code nodes in n8n DO NOT display print() or console.log() output.
- Always use `return` to output data: `return {"message": "Hello World"}`
- Python: `return {"key": "value"}` or `return _input.all()`
- JavaScript: `return {json: {key: "value"}}` or `return $input.all()`
