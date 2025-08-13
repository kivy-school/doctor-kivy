# Performance Wrapper for Kivy Rendering

from src.core.container_pool import ContainerPool
from src.core.renderer import render_kivy_snippet
import logging

class PerformanceWrapper:
    def __init__(self, pool_size: int):
        self.container_pool = ContainerPool(pool_size)
        logging.info(f"Initialized PerformanceWrapper with a container pool of size {pool_size}")

    async def render(self, interaction, code: str):
        """
        Render the Kivy code using a pre-warmed container from the pool.
        """
        logging.info("🚀 Requesting a container from the pool for rendering")
        container = await self.container_pool.get_container()

        if not container:
            logging.error("❌ No available containers in the pool")
            return {
                "content": "❌ All containers are busy. Please try again later.",
                "files": []
            }

        try:
            logging.info("📝 Rendering Kivy snippet")
            result = await render_kivy_snippet(container, interaction, code)
            return result
        finally:
            logging.info("🔄 Returning container to the pool")
            await self.container_pool.return_container(container)