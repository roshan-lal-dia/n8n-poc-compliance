<#
.SYNOPSIS
  Upload all 14 KB standard PDFs to Workflow B (KB Ingestion endpoint).
  
.DESCRIPTION
  Iterates over all PDF files in the KB folder, maps each to its domain GUID,
  and sends a multipart/form-data POST to the n8n KB ingestion webhook.

.PARAMETER BaseUrl
  The n8n webhook base URL (e.g. https://your-vm:5678 or http://localhost:5678)

.PARAMETER ApiKey
  The webhook API key for authentication

.PARAMETER KBFolder
  Path to the folder containing the 14 KB PDFs (default: ..\KB-roshan relative to this script)

.EXAMPLE
  .\upload-kb.ps1 -BaseUrl "https://n8n.example.com" -ApiKey "your-api-key"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$BaseUrl,

    [Parameter(Mandatory=$true)]
    [string]$ApiKey,

    [string]$KBFolder = "$PSScriptRoot\..\..\KB-roshan"
)

# Remove trailing slash from BaseUrl
$BaseUrl = $BaseUrl.TrimEnd('/')

# ============================================
# Domain GUID mapping (from seed.sql)
# ============================================
$domainMap = @{
    # QDKC domain-specific files
    "QDKC - Data Architecture and Modeling"                         = "a14d13d9-81eb-46da-ab4f-8476c6469dd3"
    "QDKC - Data Catalog and Metadata Management"                   = "f1b48d90-4f9a-46b4-b6f7-a1fb2b8d68fd"
    "QDKC - Data Culture and Literacy"                              = "98b03b0e-3a90-4ffb-a332-25a2de2191b5"
    "QDKC - Data Management Strategy and Governance"                = "9dbe7809-ce9c-471f-84c1-61e02d39b7c7"
    "QDKC - Data Monetization"                                      = "86b0e9f6-aef3-4c93-84c0-b26afbe184cb"
    "QDKC - Data Quality Management"                                = "ad4bdcc2-182a-4d06-bc03-8fca91056c81"
    "QDKC - Data Security, Privacy, and Other Regulations"          = "75e2eabb-6b69-465e-a6cb-f6bb1b0ed697"
    "QDKC - Data Storage and Operations"                            = "4d3a47dd-df31-435e-a8da-b5e758ca3668"
    "QDKC - Document & Content Management"                          = "4b793d57-a04e-4618-a275-082fb5c81792"
    "QDKC - Master and Reference Data Management"                   = "78739b15-7c02-49be-b03e-2b0c2f502c22"
    "QDKC - Statistics and Analytics"                                = "91feeabb-ef97-493c-98b8-accdac8324f3"
    "QDKC- Data Sharing, Integration and Interoperability"          = "6ec7535e-6134-4010-9817-8c0849e8f59b"

    # National-level files -> Overall-General domain
    "EnNationalDataPolicy"                                          = "f57f298c-50a6-4dc2-aeab-50d9220ad968"
    "EnNationalDataStandards"                                       = "f57f298c-50a6-4dc2-aeab-50d9220ad968"
}

# ============================================
# Resolve KB folder
# ============================================
$KBFolder = Resolve-Path $KBFolder -ErrorAction Stop
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  KB Standards Bulk Upload" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Base URL : $BaseUrl"
Write-Host "  KB Folder: $KBFolder"
Write-Host ""

$files = Get-ChildItem -Path $KBFolder -Filter "*.pdf" | Sort-Object Name
Write-Host "  Found $($files.Count) PDF files`n" -ForegroundColor Yellow

if ($files.Count -eq 0) {
    Write-Host "  ERROR: No PDF files found in $KBFolder" -ForegroundColor Red
    exit 1
}

# ============================================
# Upload each file
# ============================================
$success = 0
$failed  = 0
$skipped = 0

foreach ($file in $files) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    
    # Look up domain GUID
    $domainId = $domainMap[$baseName]
    if (-not $domainId) {
        Write-Host "  [$($success+$failed+$skipped+1)/$($files.Count)] SKIP  $($file.Name) - no domain mapping found" -ForegroundColor Yellow
        $skipped++
        continue
    }

    $sizeMB = [math]::Round($file.Length / 1MB, 1)
    Write-Host "  [$($success+$failed+$skipped+1)/$($files.Count)] Uploading $($file.Name) ($sizeMB MB)" -ForegroundColor White -NoNewline
    Write-Host " -> domain $domainId" -ForegroundColor DarkGray

    # Build the webhook URL with query parameters
    $webhookUrl = "$BaseUrl/webhook/kb/ingest?standardName=$([uri]::EscapeDataString($baseName))&domain=$domainId&version=2026"

    try {
        # Use curl for reliable multipart upload (PowerShell's Invoke-RestMethod 
        # has issues with large binary files and multipart)
        $result = & curl.exe -s -S --max-time 1800 `
            -X POST $webhookUrl `
            -H "X-API-Key: $ApiKey" `
            -F "file=@$($file.FullName);type=application/pdf" `
            2>&1

        # Parse response
        $response = $result | ConvertFrom-Json -ErrorAction SilentlyContinue

        if ($response.status -eq "success") {
            Write-Host "    -> SUCCESS: $($response.chunksCreated) chunks created" -ForegroundColor Green
            $success++
        }
        elseif ($response.status -eq "skipped") {
            Write-Host "    -> SKIPPED: $($response.message)" -ForegroundColor Yellow
            $skipped++
        }
        else {
            Write-Host "    -> RESPONSE: $result" -ForegroundColor Yellow
            # Still count as success if we got a response
            $success++
        }
    }
    catch {
        Write-Host "    -> FAILED: $($_.Exception.Message)" -ForegroundColor Red
        $failed++
    }

    # Small delay between uploads to avoid overwhelming the server
    Start-Sleep -Seconds 2
}

# ============================================
# Summary
# ============================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Upload Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Success : $success" -ForegroundColor Green
Write-Host "  Skipped : $skipped" -ForegroundColor Yellow
Write-Host "  Failed  : $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host ""
