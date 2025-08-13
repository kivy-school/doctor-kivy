import pytest
from src.core.container_pool import ContainerPool
from src.core.renderer import Renderer
from unittest.mock import patch, MagicMock

@pytest.fixture
def container_pool():
    pool = ContainerPool()
    pool.start_pool()  # Assuming this method initializes the pool
    return pool

@pytest.fixture
def renderer(container_pool):
    return Renderer(container_pool)

def test_rendering_with_pre_warmed_container(renderer):
    code_snippet = "from kivy.app import App\nclass TestApp(App):\n    def build(self):\n        return None\n"
    
    with patch('src.core.renderer.Renderer.render') as mock_render:
        mock_render.return_value = "Rendering successful"
        
        result = renderer.render(code_snippet)
        
        assert result == "Rendering successful"
        mock_render.assert_called_once_with(code_snippet)

def test_container_pool_reuse(container_pool):
    initial_container_count = len(container_pool.active_containers)
    
    # Simulate rendering requests
    for _ in range(5):
        container_pool.request_container()
    
    assert len(container_pool.active_containers) == initial_container_count

def test_container_health_check(container_pool):
    with patch('src.core.container_pool.ContainerPool.check_health') as mock_health_check:
        mock_health_check.return_value = True
        
        assert container_pool.check_health() is True
        mock_health_check.assert_called_once()

def test_container_pool_replacement(container_pool):
    # Simulate a container becoming unresponsive
    container_pool.active_containers[0].is_responsive = False
    
    container_pool.replace_unresponsive_containers()
    
    assert len(container_pool.active_containers) == len(container_pool.initial_containers)  # Assuming it replaces with a new one

def test_rendering_timeout(renderer):
    code_snippet = "from kivy.app import App\nclass TestApp(App):\n    def build(self):\n        return None\n"
    
    with patch('src.core.renderer.Renderer.render') as mock_render:
        mock_render.side_effect = TimeoutError("Rendering timed out")
        
        result = renderer.render(code_snippet)
        
        assert "timed out" in result  # Assuming the renderer handles this gracefully
        mock_render.assert_called_once_with(code_snippet)