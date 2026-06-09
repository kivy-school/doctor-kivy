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
    ffmpeg \
    xclip \
    xsel \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Create app directory
WORKDIR /app

# Install the same locked dependencies used by the pre-warmed renderer
COPY pyproject.toml .
COPY uv.lock ./
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"
