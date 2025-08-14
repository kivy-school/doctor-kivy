#!/bin/sh
# Entry point for the pre-warmed Kivy rendering container

# Set environment variables
export PYTHONUNBUFFERED=1
export WIDTH=${WIDTH:-800}
export HEIGHT=${HEIGHT:-600}

# Start the X virtual framebuffer
Xvfb :99 -screen 0 ${WIDTH}x${HEIGHT}x24 -nolisten tcp -br &

# Wait for Xvfb to be ready
for i in $(seq 1 50); do
    DISPLAY=:99 xdpyinfo >/dev/null 2>&1 && break
    sleep 0.1
done

# Keep the container running and ready to process rendering requests
echo "Pre-warmed Kivy container is ready to render!" 
tail -f /dev/null  # Keep the container alive