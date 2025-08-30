from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle


def _install_bg(*args):
    if "MDApp" not in globals():
        r, g, b, _ = Window.clearcolor  # respect user's color
    else:
        running_app = App.get_running_app()
        r, g, b, _ = running_app.theme_cls.backgroundColor
    with Window.canvas.before:
        bg_color = Color(r, g, b, 1)  # force opaque alpha
        bg_rect = Rectangle(pos=(0, 0), size=Window.size)

    def _on_resize(*_):
        bg_rect.size = Window.size

    Window.bind(size=_on_resize)
