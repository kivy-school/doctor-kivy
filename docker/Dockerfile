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

# Copy the Kivy app files into the container
COPY ./src /app/src

# Initialize uv project and add dependencies
RUN uv init
RUN uv add kivy-reloader pillow

# Copy the pre-warmed entrypoint script
COPY ./docker/prewarmed/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set the entrypoint for the container
ENTRYPOINT ["/entrypoint.sh"]