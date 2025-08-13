from typing import List
import aiodocker
import asyncio

class ContainerPool:
    def __init__(self, image: str, pool_size: int):
        self.image = image
        self.pool_size = pool_size
        self.containers = []
        self.available_containers = asyncio.Queue()
        self.lock = asyncio.Lock()

    async def initialize_pool(self):
        async with self.lock:
            for _ in range(self.pool_size):
                container = await self.create_container()
                self.containers.append(container)
                await self.available_containers.put(container)

    async def create_container(self):
        docker_client = aiodocker.Docker()
        container = await docker_client.containers.create(
            self.image,
            command=["/bin/sh", "-c", "while true; do sleep 30; done"],  # Keep the container running
            auto_remove=True,
            tty=True
        )
        await container.start()
        return container

    async def get_container(self):
        return await self.available_containers.get()

    async def return_container(self, container):
        await self.available_containers.put(container)

    async def cleanup(self):
        async with self.lock:
            for container in self.containers:
                await container.stop()
                await container.delete()