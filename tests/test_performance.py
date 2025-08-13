import pytest
import time
import asyncio
from src.core.container_pool import ContainerPool
from src.core.renderer import Renderer

@pytest.fixture(scope="module")
def container_pool():
    pool = ContainerPool()
    pool.start_pre_warmed_containers(5)  # Start 5 pre-warmed containers
    yield pool
    pool.stop_all_containers()

@pytest.fixture
def renderer(container_pool):
    return Renderer(container_pool)

def test_rendering_performance(renderer):
    code_snippet = """
from kivy.app import App
from kivy.uix.label import Label

class TestApp(App):
    def build(self):
        return Label(text='Hello, Kivy!')

if __name__ == '__main__':
    TestApp().run()
"""
    start_time = time.time()
    result = asyncio.run(renderer.render(code_snippet))
    end_time = time.time()
    
    assert result is not None
    assert result['content'] == "🎉 Here's your Kivy app screenshot!"
    assert end_time - start_time < 5  # Ensure rendering takes less than 5 seconds

def test_container_health_check(container_pool):
    healthy_containers = container_pool.check_health()
    assert len(healthy_containers) == 5  # Ensure all containers are healthy

def test_rendering_with_cache(renderer):
    code_snippet = """
from kivy.app import App
from kivy.uix.button import Button

class TestApp(App):
    def build(self):
        return Button(text='Click me!')

if __name__ == '__main__':
    TestApp().run()
"""
    # First render should cache the result
    result_first = asyncio.run(renderer.render(code_snippet))
    assert result_first is not None

    # Second render should hit the cache
    result_second = asyncio.run(renderer.render(code_snippet))
    assert result_second is not None
    assert result_first == result_second  # Ensure cached result is the same

def test_batch_rendering(renderer):
    code_snippets = [
        """
from kivy.app import App
from kivy.uix.label import Label

class TestApp1(App):
    def build(self):
        return Label(text='Hello from App 1!')

if __name__ == '__main__':
    TestApp1().run()
""",
        """
from kivy.app import App
from kivy.uix.label import Label

class TestApp2(App):
    def build(self):
        return Label(text='Hello from App 2!')

if __name__ == '__main__':
    TestApp2().run()
"""
    ]
    
    start_time = time.time()
    results = [asyncio.run(renderer.render(code)) for code in code_snippets]
    end_time = time.time()
    
    assert all(result is not None for result in results)
    assert end_time - start_time < 10  # Ensure batch rendering takes less than 10 seconds