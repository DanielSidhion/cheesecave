import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from state import CheeseCaveControllerMode


if os.name == "nt":
    SMALL_FONT_PATH = "C:\\Windows\\Fonts\\dejavusans-bold.ttf"
    MEDIUM_FONT_PATH = "C:\\Windows\\Fonts\\dejavusans-bold.ttf"
    LARGE_FONT_PATH = "C:\\Windows\\Fonts\\dejavusans-bold.ttf"
else:
    SMALL_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    MEDIUM_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    LARGE_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SMALL_FONT = ImageFont.truetype(SMALL_FONT_PATH, 14)
MEDIUM_FONT = ImageFont.truetype(MEDIUM_FONT_PATH, 20)
LARGE_FONT = ImageFont.truetype(LARGE_FONT_PATH, 24)
ICON_FONT = ImageFont.truetype(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "font", "picol.ttf"), 18
)


def get_text_dimensions(font, text):
    (left, top, right, bottom) = font.getbbox(text, anchor="lt")
    return (right - left, bottom - top)


ARROW_UP = "\ue80b"
ARROW_DOWN = "\ue806"
FAN = "\ue89a"
SETTINGS = "\ue9b0"
SHUTDOWN = "\ue86b"
LINK_ADD = "\ue93b"
LINK_EDIT = "\ue93c"
LINK_REMOVE = "\ue93d"

MODE_ICONS = {
    CheeseCaveControllerMode.GENERAL_INFO: [FAN, SETTINGS],
    CheeseCaveControllerMode.HUMIDITY_SET: [ARROW_UP, ARROW_DOWN],
    CheeseCaveControllerMode.SETTINGS: [SHUTDOWN, LINK_EDIT],
    CheeseCaveControllerMode.WATER_SET: [LINK_REMOVE, LINK_ADD],
}

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class DisplayController:
    def __init__(self, display, state):
        self.display = display
        self.state = state

        if self.display is None:
            # This branch is used for emulation.
            self._display_dimension = (250, 122)
        else:
            self._display_dimension = (self.display.width, self.display.height)

        self._image = Image.new("RGB", self._display_dimension, color=WHITE)
        self._image_draw = ImageDraw.Draw(self._image)

        self._temperature_text = ""
        self._humidity_text = ""
        self._desired_humidity_text = ""
        self._time_text = ""
        self._water_level_text = ""

        self._option_bar_width = 0
        self._top_bar_height = 0

    @property
    def width(self):
        return self._display_dimension[0]

    @property
    def height(self):
        return self._display_dimension[1]

    def update_texts(self):
        self._temperature_text = f"{self.state.temperature:.1f} °C {(self.state.temperature * 9 / 5) + 32:.1f} °F"
        self._humidity_text = f"{self.state.humidity:.1f}% RH"
        self._desired_humidity_text = f"Desired {self.state.desired_humidity:.1f}% RH"

        if self.state.has_water:
            self._water_level_text = f"Water {self.state.water_level * 100:.0f}%"
        else:
            self._water_level_text = "No water"

        self._time_text = f'Updated at {datetime.now().strftime("%H:%M")}'

    def show_debug_image(self):
        self.update_image()
        self._image.show()

    def clear_image(self):
        self._image_draw.rectangle(
            [0, 0, self.width + 1, self.height + 1],
            fill=WHITE,
        )

    def _draw_option_bar(self):
        icon_dimensions = [get_text_dimensions(ICON_FONT, i) for i in MODE_ICONS[self.state.mode] if i is not None]
        self._option_bar_width = 6 + max([d[0] for d in icon_dimensions])

        self._image_draw.rectangle(
            [0, 0, self._option_bar_width + 1, self.height + 1], fill=BLACK
        )

        icon1 = MODE_ICONS[self.state.mode][0]
        if icon1 is not None:
            self._image_draw.text(((self._option_bar_width - icon_dimensions[0][0]) / 2, 6), icon1, font=ICON_FONT, fill=WHITE)

        icon2 = MODE_ICONS[self.state.mode][1]
        if icon2 is not None:
            self._image_draw.text(((self._option_bar_width - icon_dimensions[1][0]) / 2, 80), icon2, font=ICON_FONT, fill=WHITE)

    def _draw_texts(self):
        (time_width, time_height) = get_text_dimensions(SMALL_FONT, self._time_text)
        (water_width, water_height) = get_text_dimensions(
            SMALL_FONT, self._water_level_text
        )
        (humidity_width, humidity_height) = get_text_dimensions(
            LARGE_FONT, self._humidity_text
        )
        (temperature_width, temperature_height) = get_text_dimensions(
            MEDIUM_FONT, self._temperature_text
        )
        (desired_humidity_width, desired_humidity_height) = get_text_dimensions(
            SMALL_FONT, self._desired_humidity_text
        )

        used_height = 2

        self._image_draw.text(
            (self._option_bar_width + 5, used_height),
            self._time_text,
            font=SMALL_FONT,
            fill=BLACK,
        )

        used_height += time_height

        unused_height = (
            self.height - used_height - water_height - humidity_height - desired_humidity_height - temperature_height
        )
        top_bottom_padding = (2 * unused_height) / 7
        middle_padding = unused_height / 7

        used_height += top_bottom_padding

        self._image_draw.text(
            (self._option_bar_width + 5, used_height),
            self._water_level_text,
            font=SMALL_FONT,
            fill=BLACK,
        )

        used_height += water_height + middle_padding

        self._image_draw.text(
            (self._option_bar_width + 5, used_height),
            self._humidity_text,
            font=LARGE_FONT,
            fill=BLACK,
        )

        used_height += humidity_height + middle_padding

        self._image_draw.text(
            (
                self._option_bar_width + 5,
                used_height,
            ),
            self._desired_humidity_text,
            font=SMALL_FONT,
            fill=BLACK,
        )

        used_height += desired_humidity_height + middle_padding

        self._image_draw.text(
            (
                self._option_bar_width + 5,
                used_height,
            ),
            self._temperature_text,
            font=MEDIUM_FONT,
            fill=BLACK,
        )

        used_height += temperature_height + top_bottom_padding

    def update_image(self):
        self.update_texts()
        self.clear_image()

        self._draw_option_bar()
        self._draw_texts()

    def update_display(self):
        self.update_image()
        self.display.image(self._image)
        self.display.display()
