# filepath: /kivy-discord-bot/kivy-discord-bot/src/templates/kivy_script_template.py
"""
This template is used for rendering Kivy applications in a Docker container.
It includes a mechanism to take a screenshot after the application has run for a specified duration.
"""

template = '''
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
from kivy.app import stopTouchApp

def take_screenshot_and_exit(_dt):
    try:
        screenshot_path = '/work/kivy_screenshot.png'
        print("Attempting to save screenshot to: ", screenshot_path)

        from kivy.base import EventLoop
        root = EventLoop.window.children[0] if EventLoop.window.children else None
        if root and hasattr(root, 'export_to_png'):
            print("Using root.export_to_png method")
            root.export_to_png(screenshot_path)
        else:
            print("Using Window.screenshot method")
            path = Window.screenshot(name=screenshot_path)
            print("Window.screenshot saved to: ", path)

        import os
        if os.path.exists(screenshot_path):
            file_size = os.path.getsize(screenshot_path)
            print("Screenshot saved successfully! File size: ", file_size, "bytes")
        else:
            print("ERROR: Screenshot file not found at: ", screenshot_path)
            work_files = os.listdir('/work')
            print("Files in /work: ", work_files)

    except Exception as e:
        print("Screenshot failed: ", e)
        import traceback
        traceback.print_exc()
    finally:
        running_app = App.get_running_app()
        if running_app is not None:
            running_app.stop()
        else:
            stopTouchApp()
        exit()

def arm_once(*_):
    Window.unbind(on_flip=arm_once)
    Clock.schedule_once(take_screenshot_and_exit, 15)

Window.bind(on_flip=arm_once)

print("🚀 Starting user code...")
# User code starts here
{user_code}
'''