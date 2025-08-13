#!/bin/bash
# Setup script for Kivy Docker renderer

echo "🐳 Setting up Kivy Docker renderer..."

# Build the Docker image
echo "Building Kivy Docker image..."
docker build -t kivy-renderer:latest .

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo "🚀 You can now run the bot and it will be able to render Kivy snippets"
else
    echo "❌ Failed to build Docker image"
    exit 1
fi

echo "🎉 Setup complete!"
