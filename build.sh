#!/bin/bash
# Build script for Doctor Kivy Docker images

echo "🏗️ Building Doctor Kivy Docker Images..."

# Build main image
echo "📦 Building main kivy-renderer:latest image..."
docker build -t kivy-renderer:latest .
if [ $? -ne 0 ]; then
    echo "❌ Failed to build main image"
    exit 1
fi

# Build prewarmed image with correct context
echo "🔥 Building prewarmed image..."
docker build -t kivy-renderer:prewarmed -f docker/prewarmed/Dockerfile.prewarmed .
if [ $? -ne 0 ]; then
    echo "❌ Failed to build prewarmed image"
    exit 1
fi

echo "✅ All images built successfully!"

# List images
echo "📋 Docker images:"
docker images | grep kivy-renderer
