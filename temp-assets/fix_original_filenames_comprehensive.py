#!/usr/bin/env python3
"""
Comprehensive fix to use original filenames throughout the workflow.
Uses originalFileName from Workflow A response and fileMap from C1.
"""

import json

# Read the workflow file
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'r') as f:
    workflow = json.load(f)

print("Applying comprehensive filename fix...")

# Fix 1: Combine Extraction Results - use originalFileName from Workflow A
for node in workflow['nodes']:
    if node['name'] == 'Combine Extraction Results':
        node['parameters']['jsCode'] = """// Combine extracted results with cached evidence
const currentItems = $input.all();
const preparedItems = $('Prepare Files for Extraction').all();

// Check if this is the FALSE path (no extraction needed)
if (currentItems.length > 0 && currentItems[0].json.allEvidence !== undefined) {
  // Already has the complete structure, pass through
  return currentItems;
}

// This is the TRUE path (extraction happened)
// Get cached evidence from first prepared item
const cachedEvidence = preparedItems[0].json.cachedEvidence || [];
const firstPrepared = preparedItems[0].json;
const questionData = $('Split by Question').item.json;

const allEvidence = [...cachedEvidence];
const newExtractions = [];

// Process each extraction result
for (let i = 0; i < currentItems.length; i++) {
  const extractedData = currentItems[i].json;
  const preparedData = preparedItems[i].json;
  
  // Validate that extraction returned proper data
  if (!extractedData.fullDocument && !extractedData.text) {
    console.error('Extraction failed for file:', preparedData.filename);
    console.error('Got data:', JSON.stringify(extractedData));
    
    // Use empty extraction as fallback
    extractedData.fullDocument = `[Extraction failed for ${preparedData.filename}]`;
    extractedData.totalPages = 0;
    extractedData.totalWords = 0;
    extractedData.hasDiagrams = false;
  }
  
  // CRITICAL: Use originalFileName from Workflow A response (extractedData)
  // This is the actual filename from the API request or ADLS path
  const originalFilename = extractedData.originalFileName || preparedData.filename;
  
  console.log(`File ${preparedData.hash}: using originalFileName="${originalFilename}"`);
  
  allEvidence.push({
    hash: preparedData.hash,
    filename: originalFilename,  // Use original filename from Workflow A
    extractedData: extractedData,
    fileSize: preparedData.fileSize,
    fromCache: false
  });
  
  newExtractions.push({
    hash: preparedData.hash,
    filename: originalFilename,  // Use original filename from Workflow A
    extractedData: extractedData,
    fileSize: preparedData.fileSize
  });
}

return [{
  json: {
    sessionId: firstPrepared.sessionId,
    qId: firstPrepared.qId,
    domain: firstPrepared.domain,
    allEvidence: allEvidence,
    newExtractions: newExtractions,
    totalEvidence: allEvidence.length,
    fromCache: cachedEvidence.length,
    justExtracted: newExtractions.length,
    questionIndex: questionData.questionIndex,
    totalQuestions: questionData.totalQuestions
  }
}];"""
        print("   ✓ Fixed Combine Extraction Results")

# Fix 2: Prepare Files for Extraction - ensure cached evidence uses original filenames
for node in workflow['nodes']:
    if node['name'] == 'Prepare Files for Extraction':
        node['parameters']['jsCode'] = """const questionData = $('Split by Question').item.json;
const cacheResults = $input.all();

console.log('=== PREPARE FILES DEBUG ===');
console.log('Cache results count:', cacheResults.length);

// Extract cached evidence - filter out 'nocache' marker
const cachedEvidence = cacheResults
  .map(item => item.json)
  .filter(item => {
    if (item.file_hash === 'nocache') {
      return false;
    }
    return item && item.file_hash && item.extracted_data;
  });

console.log('Valid cached evidence count:', cachedEvidence.length);

// Determine which files need extraction
const cachedHashes = new Set(cachedEvidence.map(e => e.file_hash));
const filesToExtract = questionData.evidenceFiles.filter(f => !cachedHashes.has(f.hash));

console.log('Files to extract:', filesToExtract.length);

// Build hash-to-original-filename map from questionData.fileMap
const hashToOriginalFilename = {};
for (const fileInfo of questionData.evidenceFiles || []) {
  const fileData = questionData.fileMap[fileInfo.fieldName];
  if (fileData && fileData.fileName) {
    // Extract just filename from path (handles ADLS paths)
    const cleanFilename = fileData.fileName.split('/').pop().split('\\\\').pop();
    hashToOriginalFilename[fileInfo.hash] = cleanFilename;
  }
}

// Store cached evidence for later - use original filenames from fileMap
const cachedEvidenceData = cachedEvidence.map(cached => ({
  hash: cached.file_hash,
  filename: hashToOriginalFilename[cached.file_hash] || cached.filename,  // Use original filename
  extractedData: cached.extracted_data,
  fileSize: cached.file_size_bytes,
  fromCache: true
}));

// Prepare files for extraction (one item per file)
const fs = require('fs');
const filesToProcess = [];
for (const fileInfo of filesToExtract) {
  const fileData = questionData.fileMap[fileInfo.fieldName];
  if (!fileData) {
    throw new Error(`File fieldName "${fileInfo.fieldName}" not found in fileMap. Available: ${Object.keys(questionData.fileMap).join(', ')}`);
  }
  
  let currentBinaryData = fileData.binaryData;
  // If no binary data in memory, try reading from disk
  if (!currentBinaryData && fileData.filePath) {
    try {
      if (fs.existsSync(fileData.filePath)) {
        currentBinaryData = fs.readFileSync(fileData.filePath, 'base64');
        console.log(`Read ${fileData.fileName} from disk: ${fileData.filePath}`);
      } else {
         console.warn(`File path provided but not found: ${fileData.filePath}`);
      }
    } catch (e) {
      console.warn(`Error reading file from disk: ${e.message}`);
    }
  }

  if (!currentBinaryData) {
    throw new Error(`No binary data found for ${fileData.fileName} (checked memory and disk).`);
  }
  
  const actualSize = Buffer.from(currentBinaryData, 'base64').length;
  
  // Extract original filename (handles ADLS paths)
  const originalFilename = hashToOriginalFilename[fileInfo.hash] || fileData.fileName;
  console.log(`Prepared ${originalFilename}: ${actualSize} bytes (hash: ${fileInfo.hash})`);
  
  filesToProcess.push({
    json: {
      sessionId: questionData.sessionId,
      qId: questionData.qId,
      domain: questionData.domain,
      hash: fileInfo.hash,
      filename: originalFilename,  // Use original filename
      fileSize: actualSize,
      mimeType: fileData.mimeType,
      cachedEvidence: cachedEvidenceData
    },
    binary: {
      data: {
        data: currentBinaryData,
        mimeType: fileData.mimeType,
        fileName: originalFilename,  // Use original filename
        fileExtension: originalFilename.split('.').pop()
      }
    }
  });
}

if (filesToProcess.length === 0) {
  console.log('No files to extract, returning cached-only result');
  return[{
    json: {
      sessionId: questionData.sessionId,
      qId: questionData.qId,
      domain: questionData.domain,
      allEvidence: cachedEvidenceData,
      newExtractions: [],
      totalEvidence: cachedEvidenceData.length,
      fromCache: cachedEvidenceData.length,
      justExtracted: 0
    }
  }];
}

return filesToProcess;"""
        print("   ✓ Fixed Prepare Files for Extraction")

# Fix 3: Consolidate Evidence Text - already uses evidence.filename which now has original names
# No changes needed here since it will receive correct filenames from Combine Extraction Results

# Write the modified workflow
with open('workflows/unifi-npc-compliance/workflow-c2-audit-worker.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("\n✓ Comprehensive filename fix applied successfully!")
print("\nChanges:")
print("  1. Combine Extraction Results: Uses originalFileName from Workflow A response")
print("  2. Prepare Files for Extraction: Builds hash-to-filename map from fileMap")
print("  3. Cached evidence: Uses original filenames from fileMap")
print("  4. ADLS paths: Extracts just filename from full path")
print("\nData flow:")
print("  - Multipart upload: fileName from binary → fileMap → originalFileName")
print("  - ADLS: blobPath → extract filename → fileMap → originalFileName")
print("  - Workflow A: Returns originalFileName in response")
print("  - Combine Results: Uses extractedData.originalFileName")
print("  - Consolidate Evidence: Uses evidence.filename (now original)")
print("  - Parse AI Response: Uses sourceFiles[].filename (now original)")
