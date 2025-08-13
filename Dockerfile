# Dockerfile for Kivy rendering environment
FROM python:3.11-slim

# Install system dependencies for Kivy and virtual display
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libgl1 \
    libsdl2-2.0-0 \
    curl \
    libmtdev1 \
    && rm -rf /var/lib/apt/lists/*
 
# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Create app directory
WORKDIR /app

# Initialize uv project and add dependencies
RUN uv init
RUN uv add kivy-reloader pillow
