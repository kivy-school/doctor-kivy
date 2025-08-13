# Build script for Doctor Kivy Docker images
Write-Host "🏗️ Building Doctor Kivy Docker Images..." -ForegroundColor Green

# Build main image
Write-Host "📦 Building main kivy-renderer:latest image..." -ForegroundColor Yellow
docker build -t kivy-renderer:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to build main image" -ForegroundColor Red
    exit 1
}

# Build prewarmed image with correct context
Write-Host "🔥 Building prewarmed image..." -ForegroundColor Yellow
docker build -t kivy-renderer:prewarmed -f docker/prewarmed/Dockerfile.prewarmed .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to build prewarmed image" -ForegroundColor Red
    exit 1
}

Write-Host "✅ All images built successfully!" -ForegroundColor Green

# List images
Write-Host "📋 Docker images:" -ForegroundColor Cyan
docker images | Select-String "kivy-renderer"
