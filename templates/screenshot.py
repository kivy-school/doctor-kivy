import os

import asynckivy as ak
from kivy.app import App, stopTouchApp
from kivy.clock import Clock
from kivy.core.window import Window

from templates.base import _install_bg


def take_screenshot_and_exit():
    try:
        target_path = "/work/kivy_screenshot.png"
        print("Attempting to save screenshot to:", target_path)

        # Always use Window.screenshot (reads GL RGB buffer)
        actual_path = Window.screenshot(name=target_path)
        print("Window.screenshot saved to:", actual_path)

        # If Kivy auto-numbered (…0001.png), normalize to the expected filename
        if actual_path and actual_path != target_path:
            try:
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.replace(actual_path, target_path)
                print("Renamed", actual_path, "->", target_path)
            except Exception as e:
                print("Rename failed:", e)

        if os.path.exists(target_path):
            file_size = os.path.getsize(target_path)
            print("Screenshot saved successfully. File size:", file_size, "bytes")
        else:
            print("ERROR: Screenshot file not found at:", target_path)
            try:
                print("Files in /work:", os.listdir("/work"))
            except Exception as e:
                print("Failed to list /work:", e)

    except Exception as e:
        print("Screenshot failed:", e)
        import traceback

        traceback.print_exc()
    finally:
        running_app = App.get_running_app()
        if running_app is not None:
            running_app.stop()
        else:
            stopTouchApp()
        exit()


async def fix_bg_and_take_screenshot(*_):
    # draw opaque background into the on-screen buffer
    _install_bg()

    ak.n_frames(1)

    # next frame to ensure it's rendered
    take_screenshot_and_exit()


def arm_once(*_):
    Window.unbind(on_flip=arm_once)
    Clock.schedule_once(lambda dt: ak.managed_start(fix_bg_and_take_screenshot()), 0)


Window.bind(on_flip=arm_once)
