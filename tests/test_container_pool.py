import unittest
from src.core.container_pool import ContainerPool
from src.services.docker_service import DockerService

class TestContainerPool(unittest.TestCase):
    def setUp(self):
        self.pool = ContainerPool(max_containers=5)
        self.docker_service = DockerService()

    def test_initial_pool_size(self):
        self.assertEqual(len(self.pool.containers), 0)

    def test_add_container(self):
        container = self.docker_service.create_container()
        self.pool.add_container(container)
        self.assertEqual(len(self.pool.containers), 1)

    def test_get_container(self):
        container = self.docker_service.create_container()
        self.pool.add_container(container)
        retrieved_container = self.pool.get_container()
        self.assertIsNotNone(retrieved_container)
        self.assertEqual(retrieved_container, container)

    def test_return_container(self):
        container = self.docker_service.create_container()
        self.pool.add_container(container)
        self.pool.return_container(container)
        self.assertEqual(len(self.pool.containers), 1)

    def test_exceed_max_containers(self):
        for _ in range(6):
            container = self.docker_service.create_container()
            self.pool.add_container(container)
        self.assertEqual(len(self.pool.containers), 5)  # Should not exceed max

    def test_container_health_check(self):
        container = self.docker_service.create_container()
        self.pool.add_container(container)
        self.pool.check_container_health(container)
        self.assertTrue(container.is_healthy)

if __name__ == '__main__':
    unittest.main()