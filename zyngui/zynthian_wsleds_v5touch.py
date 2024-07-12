import os
from zyngui import zynthian_gui_config
from zyngui.zynthian_wsleds_v5 import zynthian_wsleds_v5


class touchkeypad_button_colors:
    """
    Fake NeoPixel emulation to change colors of onscreen touch keypad (instead of a wsled strip)
    """
	
    def __init__(self, wsleds):
        self.zyngui = wsleds.zyngui
        # A wanna-be abstraction: reverse derive a named "mode" from the requested colors
        self.mode_map = {}
        self.mode_map[wsleds.wscolor_alt] = 'alt'
        self.mode_map[wsleds.wscolor_active] = 'active'
        self.mode_map[wsleds.wscolor_active2] = 'active2'

    def __setitem__(self, index, value):
        mode = self.mode_map.get(value, None)
        # request color change on the onscreen touchkeypad
        self.zyngui.touch_keypad.set_button_color(index, value, mode)

    def show(self):
        # nothing to do here
        pass


class zynthian_wsleds_v5touch(zynthian_wsleds_v5):
    """
    Emulation of wsleds for onscreen touch keypad V5
    """

    def start(self):
        self.wsleds = touchkeypad_button_colors(self)
        self.light_on_all()

    def setup_colors(self):
		# Predefined colors
        self.wscolor_off = zynthian_gui_config.color_panel_bg
        self.wscolor_white = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_WHITE', "#FCFCFC")
        self.wscolor_red = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_RED', "#FE2C2F") # #FF8A92
        self.wscolor_green = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_GREEN', "#00FA00")
        self.wscolor_yellow = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_YELLOW', "#F0EA00")
        self.wscolor_orange = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_ORANGE', "#FF6A00") # #FFA200
        self.wscolor_blue = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_BLUE', "#1070FE") # lighter: #5397FE, #38EBFF
        self.wscolor_blue_light = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_LIGHTBLUE', "#05FDFF")
        self.wscolor_purple = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_PURPLE', "#D662FE") # #FF80EB
        self.wscolor_default = self.wscolor_blue
        self.wscolor_alt = self.wscolor_purple
        self.wscolor_active = self.wscolor_green
        self.wscolor_active2 = self.wscolor_orange
        self.wscolor_admin = self.wscolor_red
        self.wscolor_low = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_LOW', "#D9EB37")
        # Color Codes
        self.wscolors_dict = {
            str(self.wscolor_off): "0",
            str(self.wscolor_blue): "B",
            str(self.wscolor_green): "G",
            str(self.wscolor_red): "R",
            str(self.wscolor_orange): "O",
            str(self.wscolor_yellow): "Y",
            str(self.wscolor_purple): "P"
}