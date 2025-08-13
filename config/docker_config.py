# filepath: kivy-discord-bot/config/docker_config.py

class DockerConfig:
    """Configuration settings for Docker containers used in the Kivy bot."""

    # Docker image settings
    PREWARMED_IMAGE = "kivy-renderer:prewarmed"
    RENDER_IMAGE = "kivy-renderer:latest"

    # Container pool settings
    CONTAINER_POOL_SIZE = 5  # Number of pre-warmed containers to maintain
    CONTAINER_HEALTH_CHECK_INTERVAL = 30  # Interval for health checks in seconds

    # Resource limits for containers
    MEMORY_LIMIT = "512m"  # Memory limit for each container
    CPU_LIMIT = "0.5"  # CPU limit for each container

    # Timeout settings
    RENDER_TIMEOUT = 30  # Timeout for rendering tasks in seconds

    @staticmethod
    def get_container_config():
        """Returns the configuration for starting a Docker container."""
        return {
            "Image": DockerConfig.RENDER_IMAGE,
            "HostConfig": {
                "Memory": DockerConfig.MEMORY_LIMIT,
                "CpuQuota": DockerConfig.CPU_LIMIT,
                "AutoRemove": True,
            },
        }