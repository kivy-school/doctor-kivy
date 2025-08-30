import os

import asynckivy as ak
from kivy.app import App, stopTouchApp
from kivy.clock import Clock
from kivy.core.window import Window

from templates.base import _install_bg

all_widgets = []
widget_durations = {
    "Button": 0.8,
    "ToggleButton": 0.8,
    "CheckBox": 0.8,
    "TabbedPanelHeader": 0.8,
    "Switch": 0.8,
    "TextInput": 2,
    "ScrollView": 1.5,  # Could be up to 3.0s if both x and y scroll
    "Video": 3.0,
}


def discover_elements(widget=None):
    """Recursively discover all widgets in the application and save them in a list"""
    if widget is None:
        widget = App.get_running_app().root
        print("Discovering all widgets in the application...")

    # Add current widget to the list
    all_widgets.append(widget)

    # Print current widget info
    widget_type = type(widget).__name__
    print("Found widget:", widget_type)

    # ScreenManager: traverse all screens, even inactive
    if hasattr(widget, "screens"):
        for screen in widget.screens:
            discover_elements(screen)

    # TabbedPanel: traverse all tabs and their content
    elif hasattr(widget, "tab_list"):
        for tab in widget.tab_list:
            discover_elements(tab)

    # TabbedPanelHeader: traverse all tabs and their content
    elif hasattr(widget, "content"):
        discover_elements(widget.content)

    # Normal children
    elif hasattr(widget, "children") and widget.children:
        for child in widget.children[::-1]:
            discover_elements(child)

    # Print summary when done with root discovery
    if widget == App.get_running_app().root:
        print("\nTotal widgets found:", len(all_widgets))
        print("Widgets saved in all_widgets list for later use")


def calculate_total_duration(speed_up=1.0):
    """Calculate total duration for all widget actions"""
    total_duration = 0.0

    for widget in all_widgets:
        widget_type = type(widget).__name__

        if widget_type in widget_durations:
            duration = widget_durations[widget_type]

            # Special case for ScrollView - could be double if both x and y scroll
            if widget_type == "ScrollView":
                scroll_directions = 0
                if hasattr(widget, "do_scroll_x") and widget.do_scroll_x:
                    scroll_directions += 1
                if hasattr(widget, "do_scroll_y") and widget.do_scroll_y:
                    scroll_directions += 1
                duration *= max(1, scroll_directions)  # At least 1 direction

            total_duration += duration / speed_up

    return total_duration


def calculate_optimal_speed(max_duration=21.0):
    """Calculate the optimal speed_up factor to fit within max_duration"""
    base_duration = calculate_total_duration(speed_up=1.0)

    print("Base duration (speed_up=1.0):", round(base_duration, 2), "seconds")
    print("Target maximum duration:", max_duration, "seconds")

    if base_duration <= max_duration:
        print("No speed-up needed!")
        return 1.0

    optimal_speed = base_duration / max_duration
    print("Need to speed up by factor of", round(optimal_speed, 2))

    return optimal_speed


async def trigger_actions_on_all_widgets(speed_up=1.0):
    """Example method to demonstrate looping over all widgets and triggering actions"""
    estimated_duration = calculate_total_duration(speed_up)
    print("\nTriggering actions on", len(all_widgets), "widgets:")
    print(
        "Estimated total duration:",
        round(estimated_duration, 2),
        "seconds (speed_up=" + str(round(speed_up, 2)) + ")",
    )
    print("=" * 50)

    await ak.sleep(1)

    for i, widget in enumerate(all_widgets):
        widget_type = type(widget).__name__
        print(str(i + 1) + ". " + widget_type + ": ", end="")

        if widget_type in {
            "Button",
            "ToggleButton",
            "CheckBox",
            "TabbedPanelHeader",
        }:
            widget.trigger_action(0.6 / speed_up)
            await ak.sleep(0.8 / speed_up)
            print("triggered")

        elif widget_type == "Switch":
            widget.active = not widget.active
            await ak.sleep(0.8 / speed_up)
            print("toggled to", widget.active)

        elif widget_type == "TextInput":
            text = "Tested by Dr. Kivy"
            print("typing '" + text + "'...")
            for char in text:
                widget.insert_text(char)
                await ak.sleep(0.125 / speed_up)
            print("done")

        elif widget_type == "ScrollView":
            actions = []
            # check if should scroll x or y
            if hasattr(widget, "do_scroll_x") and widget.do_scroll_x:
                actions.append("scroll_x")
                # animate scrolling right / left
                if widget.scroll_x == 0:
                    await ak.anim_attrs(widget, scroll_x=1, duration=1.5 / speed_up)
                else:
                    await ak.anim_attrs(widget, scroll_x=0, duration=1.5 / speed_up)
            if hasattr(widget, "do_scroll_y") and widget.do_scroll_y:
                actions.append("scroll_y")
                # animate scrolling up / down
                if widget.scroll_y == 0:
                    await ak.anim_attrs(widget, scroll_y=1, duration=1.5 / speed_up)
                else:
                    await ak.anim_attrs(widget, scroll_y=0, duration=1.5 / speed_up)
            print("scrolled", ", ".join(actions) if actions else "none")
        elif widget_type == "Video":
            widget.state = "play"

            # Wait for video to load using asynckivy event waiting
            print("waiting for video to load...", end="", flush=True)
            if widget._video is None:
                print(" video not loaded.")
                continue

            await ak.event(widget._video, "on_load")
            print(" loaded.")

            real_duration = widget._video.duration

            print("video duration: ", real_duration)
            video_duration = (
                real_duration if real_duration and real_duration <= 3 else 3
            )
            print("playing for", round(video_duration / speed_up, 2), "s...")
            await ak.sleep(video_duration / speed_up)
            widget.state = "stop"
            print("played for", round(video_duration / speed_up, 2), "s")
        else:
            print("no action defined")

        await ak.sleep(1)

        # TODO: RstDocument, Popup, Slider, Scatter, Spinner


# Main orchestrator function
async def record_kivy_demo_video(*_):
    """
    Main function that orchestrates the entire video recording process:
    1. Discovers interactive elements
    2. Calculates optimal timing/speed to interact with them
    3. Triggers all interactions while recording
    4. Saves the final video
    """
    # draw opaque background into the on-screen buffer
    _install_bg()

    # Discover all interactive elements
    discover_elements()

    # Calculate optimal speed_up to fit within 21 seconds
    optimal_speed = calculate_optimal_speed(max_duration=21.0)
    print("Calculated optimal speed_up:", round(optimal_speed, 2))

    # Clear images
    clear_images_folder()

    # Start video recording here
    # TODO verify if 1/60 is the right interval
    Clock.schedule_interval(export_to_png, 1 / 60)

    # Start recording and trigger interactions
    await trigger_actions_on_all_widgets(speed_up=optimal_speed)

    # TODO: Stop recording and save video
    Clock.unschedule(export_to_png)
    create_video_from_images()


def create_video_from_images():
    print("Creating video")
    work_dir = os.path.join(os.getcwd(), "work")
    os.system(
        f'ffmpeg -y -framerate 60 -i "{os.path.join(work_dir, "kivy_screenshot_%d.png")}" -c:v libx264 -profile:v high -crf 20 -pix_fmt yuv420p kivy_video.mp4'
    )
    running_app = App.get_running_app()
    if running_app is not None:
        running_app.stop()
    else:
        stopTouchApp()
    exit()


def clear_images_folder():
    for file in os.listdir(os.path.join(os.getcwd(), "work")):
        if file.endswith(".png"):
            print(f"Removing {file}")
            os.remove(os.path.join(os.getcwd(), "work", file))


def export_to_png(self, *args):
    image_number = len(os.listdir(os.path.join(os.getcwd(), "work"))) + 1
    root = App.get_running_app().root
    output_path = os.path.join(
        os.getcwd(), "work", f"kivy_screenshot_{image_number}.png"
    )
    root.export_to_png(output_path)


def arm_video_recording(*_):
    Window.unbind(on_flip=arm_video_recording)
    Clock.schedule_once(lambda dt: ak.managed_start(record_kivy_demo_video()), 0)


Window.bind(on_flip=arm_video_recording)
