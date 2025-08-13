from typing import Any, Dict
import logging
import asyncio
from services.docker_service import DockerService
from core.container_pool import ContainerPool

class Renderer:
    def __init__(self, container_pool: ContainerPool):
        self.container_pool = container_pool

    async def render_kivy_app(self, code: str) -> Dict[str, Any]:
        logging.info("🚀 Requesting a container from the pool for rendering")
        container = await self.container_pool.get_available_container()

        if not container:
            logging.error("❌ No available containers in the pool")
            return {"content": "❌ No available containers for rendering."}

        try:
            logging.info("📝 Preparing to render Kivy app")
            result = await self._execute_rendering(container, code)
            return result
        finally:
            await self.container_pool.release_container(container)

    async def _execute_rendering(self, container: str, code: str) -> Dict[str, Any]:
        logging.info(f"🐳 Executing rendering in container: {container}")
        docker_service = DockerService()

        try:
            # Here you would implement the logic to run the Kivy app in the container
            # This is a placeholder for the actual rendering logic
            output = await docker_service.run_kivy_app(container, code)
            return output
        except Exception as e:
            logging.error(f"💥 Rendering failed: {e}", exc_info=True)
            return {"content": f"❌ Rendering failed: {str(e)}"}

    async def health_check(self):
        logging.info("🔍 Performing health check on container pool")
        await self.container_pool.check_health()