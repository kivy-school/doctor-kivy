from typing import List, Dict, Any
import aiodocker
import logging

class DockerService:
    def __init__(self, image_name: str, container_count: int):
        self.image_name = image_name
        self.container_count = container_count
        self.docker_client = aiodocker.Docker()
        self.container_pool: List[aiodocker.DockerContainer] = []

    async def initialize_containers(self) -> None:
        for _ in range(self.container_count):
            container = await self.docker_client.containers.create(
                {
                    "Image": self.image_name,
                    "Cmd": ["/bin/sh", "-c", "while true; do sleep 30; done;"],
                    "Tty": True,
                    "HostConfig": {
                        "AutoRemove": True,
                    },
                }
            )
            await container.start()
            self.container_pool.append(container)
            logging.info(f"Initialized and started container: {container.id}")

    async def get_container(self) -> aiodocker.DockerContainer:
        if self.container_pool:
            return self.container_pool.pop(0)
        else:
            logging.warning("No available containers in the pool.")
            return None

    async def return_container(self, container: aiodocker.DockerContainer) -> None:
        self.container_pool.append(container)

    async def cleanup(self) -> None:
        for container in self.container_pool:
            await container.stop()
            await container.delete()
        self.container_pool.clear()
        await self.docker_client.close()