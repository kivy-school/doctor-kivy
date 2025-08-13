# filepath: /kivy-discord-bot/kivy-discord-bot/docker/scripts/container_init.py
import os
import subprocess
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)

def start_container(container_name: str):
    """Start a Docker container from the pre-warmed image."""
    try:
        logging.info(f"Starting container: {container_name}")
        subprocess.run(["docker", "run", "-d", "--name", container_name, "kivy-renderer:prewarmed"], check=True)
        logging.info(f"Container {container_name} started successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to start container {container_name}: {e}")

def main():
    """Initialize the container environment."""
    num_containers = int(os.getenv("NUM_CONTAINERS", 5))  # Default to 5 containers
    container_names = [f"kivy-container-{i}" for i in range(num_containers)]

    # Start the specified number of containers
    for container_name in container_names:
        start_container(container_name)
        time.sleep(1)  # Optional: Add a delay between starting containers

if __name__ == "__main__":
    main()