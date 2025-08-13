# Deployment Instructions for Kivy Discord Bot

## Overview

This document provides instructions for deploying the Kivy Discord bot, which utilizes a pre-warmed container strategy to optimize performance for rendering Kivy applications. The bot is designed to efficiently handle rendering requests by reusing Docker containers, thus reducing the overhead associated with starting new containers for each request.

## Prerequisites

Before deploying the bot, ensure that you have the following:

- Docker installed on your machine.
- Docker Compose installed.
- Python 3.11 or higher.
- Required Python packages listed in `requirements.txt`.

## Deployment Steps

### 1. Clone the Repository

Clone the repository to your local machine:

```bash
git clone <repository-url>
cd kivy-discord-bot
```

### 2. Build the Docker Images

Build the Docker images, including the pre-warmed container image:

```bash
# Build the main Docker image
docker build -t kivy-renderer:latest -f docker/Dockerfile .

# Build the pre-warmed Docker image
docker build -t kivy-renderer:prewarmed -f docker/prewarmed/Dockerfile.prewarmed .
```

### 3. Start Pre-warmed Containers

Use the provided script to start a specified number of pre-warmed containers:

```bash
# Start pre-warmed containers
python docker/scripts/container_init.py
```

This script will initialize the containers and keep them running, ready to handle rendering requests.

### 4. Configure Environment Variables

Create a `.env` file based on the `.env.example` file provided in the root directory. Ensure that you set the `DISCORD_TOKEN` and any other necessary environment variables.

### 5. Start the Bot

Run the bot using the following command:

```bash
python src/bot.py
```

Alternatively, you can use Docker Compose to manage the bot and its dependencies:

```bash
docker-compose up
```

### 6. Health Checks

Ensure that the health check script is running to monitor the status of the containers. This can be set up as a cron job or a scheduled task to run periodically:

```bash
python docker/scripts/health_check.py
```

### 7. Monitor Performance

Monitor the performance of the bot and the rendering process. Check the logs for any errors or performance bottlenecks. Adjust the number of pre-warmed containers based on the load and performance metrics.

## Conclusion

By following these steps, you will have a fully deployed Kivy Discord bot that utilizes a pre-warmed container strategy for optimized performance. Regularly monitor the system and make adjustments as necessary to ensure smooth operation.