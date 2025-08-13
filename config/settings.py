# filepath: kivy-discord-bot/config/settings.py
# Configuration settings for the Kivy Discord bot

class Config:
    DISCORD_TOKEN = "YOUR_DISCORD_TOKEN"
    DOCKER_IMAGE = "kivy-renderer:latest"
    CONTAINER_POOL_SIZE = 5  # Number of pre-warmed containers
    RENDER_TIMEOUT = 30  # Timeout for rendering tasks in seconds
    CACHE_ENABLED = True  # Enable or disable caching of rendered images
    LOGGING_LEVEL = "INFO"  # Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    # Performance settings
    PERFORMANCE_MONITORING_ENABLED = True  # Enable performance monitoring
    MAX_RENDER_TIME = 60  # Maximum time allowed for rendering a Kivy app in seconds

    # Health check settings
    HEALTH_CHECK_INTERVAL = 10  # Interval for health checks in seconds
    MAX_UNRESPONSIVE_TIME = 30  # Time before a container is considered unresponsive

    # Other settings can be added as needed
