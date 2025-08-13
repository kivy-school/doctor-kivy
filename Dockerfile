# Dockerfile for Kivy rendering environment
FROM python:3.11-slim

# Install system dependencies for Kivy and virtual display
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libgl1 \
    libsdl2-2.0-0 \
    curl \
    libmtdev1 \
    x11-utils \
    && rm -rf /var/lib/apt/lists/*
 
# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Create app directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies with uv
RUN uv sync --frozen

# Create work directory for user scripts
RUN mkdir -p /work

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Default command (can be overridden)
CMD ["tail", "-f", "/dev/null"]
