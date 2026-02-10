# Build script for custom n8n runners image
# Run this before starting docker compose

Write-Host "Building custom n8n runners image with Python libraries..." -ForegroundColor Green

docker build -f Dockerfile.runners -t n8n-runners-custom:2.6.3 .

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Build successful! You can now run: docker compose up -d" -ForegroundColor Green
} else {
    Write-Host "✗ Build failed!" -ForegroundColor Red
    exit 1
}
