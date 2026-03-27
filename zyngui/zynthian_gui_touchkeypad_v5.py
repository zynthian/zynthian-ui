#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Touchscreen Keypad V5 Class
#
# Copyright (C) 2024-2026 Pavel Vondřička <pavel.vondricka@ff.cuni.cz>
#                         Brian Walton <riban@zynthian.org>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import os
import tkinter
from io import BytesIO
from PIL import Image, ImageTk
import tkinter.font as tkfont

try:
    import cairosvg
except:
    cairosvg = None

# Zynthian specific modules
from zyngui import zynthian_gui_config

LABEL       = 0
ALT_LABEL   = 1
ACT_LABEL   = 2
ACT2_LABEL  = 3
RECT_ID     = 4
TXT_ID      = 5
IMG_ID      = 6
IMG         = 7
TKIMG       = 8
LED_STATE   = 9

# ------------------------------------------------------------------------------
# Zynthian Touchscreen Keypad V5 Class
# ------------------------------------------------------------------------------


class zynthian_gui_touchkeypad_v5(tkinter.Canvas):

    def __init__(self):

        super().__init__(zynthian_gui_config.top,
                width=zynthian_gui_config.display_width,
                height=zynthian_gui_config.display_height,
                bg=zynthian_gui_config.color_bg,
                bd=0,
                highlightthickness=0)
        self.shown = False
        self.button_width = zynthian_gui_config.display_width // 10
        self.button_height = zynthian_gui_config.display_height // 6
        self.bg_color = zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bg, -28)
        self.bg_color_over = zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bg, -22)
        self.border_color = zynthian_gui_config.color_bg
        self.text_color = zynthian_gui_config.color_header_tx

        self.place(x=0, y=0)

        self.buttons = [
            # default label, alt label, rectangle id, text id, image id, image, tk image, led state
            ["OPT\nADMIN", None] + [None] * 8,             #0 OPT
            ["MIX\nLEVEL", None] + [None] * 8,             #1 MIX
            ["CTRL\nPRSET", None] + [None] * 8,           #2 CTRL
            ["ZS3\nSHOT", None] + [None] * 8,              #3 ZS3
            ["ALT\nHELP", None] + [None] * 8,                    #4 ALT
            ["_icons/metronome.svg", None] + [None] * 8,   #5 METRO
            ["PAD\nSTEP", None] + [None] * 8,              #6 PAD
            ["F1", "F5"] + [None] * 8,                     #7 F1
            ["\uf111", None] + [None] * 8,                 #8 RECORD
            ["\uf04d", None] + [None] * 8,                 #9 STOP
            ["\uf04b", None] + [None] * 8,                 #10 PLAY
            ["F2", "F6"] + [None] * 8,                     #11 F2
            ["BACK\nNO", None] + [None] * 8,               #12 BACK
            ["\uf077", None] + [None] * 8,                 #13 UP
            ["SEL\nYES", None] + [None] * 8,               #14 SEL
            ["F3", "F7"] + [None] * 8,                     #15 F3
            ["\uf053", None] + [None] * 8,                 #16 LEFT
            ["\uf078", None] + [None] * 8,                 #17 DOWN
            ["\uf054", None] + [None] * 8,                 #18 RIGHT
            ["F4", "F8"] + [None] * 8                      #19 F4
        ]
        if zynthian_gui_config.touch_navigation == "v5_keypad_left":
            self.x_offset = 0
            layout = (
                (0, 1),
                (2, 6),
                (5, 3),
                (12, 14),
                (4, 13),
                (16, 17, 18, 8, 9, 10, 7, 11, 15, 19)
            )
        else:
            self.x_offset = zynthian_gui_config.display_width - self.button_width * 2
            layout = (
            (0, 1),
            (2, 6),
            (5, 3),
            (12, 14),
            (13, 4),
            (7, 11, 15, 19, 8, 9, 10, 16, 17, 18)
        )

        for row, row_data in enumerate(layout):
            for column, button in enumerate(row_data):
                self.draw_button(row, column, button)

        # update with user settings from the environment
        self.apply_user_config()

    def draw_button(self, row, column, button):
        """ Draw button onto canvas
        Args:
            row: Row in which to draw button
            column: Column in which to draw button
            button: Button index
        """

        try:
            config = self.buttons[button]
            label = config[0]
        except:
            return
        if row == 5:
            x = self.button_width * column
        else:
            x = self.x_offset + self.button_width * column
        y = self.button_height * row
        tag = f"v5_button_{button}"
        config[RECT_ID] = self.create_rectangle(
            x, y,
            x+self.button_width, y+self.button_height,
            outline=zynthian_gui_config.color_bg,
            width=1,
            fill=self.bg_color,
            tags=tag
        )
        if label.startswith('_'):
            # button contains an icon/image instead of a label
            img_width = int(0.6 * self.button_width)
            img_name = label[1:]
            if img_name.endswith('.svg'):
                # convert SVG icon into PNG of appropriate size
                if cairosvg:
                    png = BytesIO()
                    cairosvg.svg2png(url=img_name, write_to=png, output_width=img_width)
                    image = Image.open(png)
                else:
                    png = img_name[:-4]+".png"
                    image = Image.open(png)
                    img_height = int(img_width * image.size[1] / image.size[0])
                    image = image.resize((img_width, img_height), Image.Resampling.LANCZOS)
            elif img_name.endswith('.png'):
                # PNG icons can be imported directly
                image = Image.open(img_name)
                img_height = int(img_width * image.size[1] / image.size[0])
                image = image.resize((img_width, img_height), Image.Resampling.LANCZOS)
            else:
                image = None
            if image:
                # store the original image for the purpose of later changes of color (useful for image icons)
                config[IMG] = image
                config[TKIMG] = ImageTk.PhotoImage(image)
                config[IMG_ID] = self.create_image(
                    x+self.button_width//2, y+self.button_height//2,
                    image=config[TKIMG],
                    tags=tag
                )
        else:
            # Button has a simple text label: either standard text
            # or an icon included in the "forkawesome" font (unicode char >= \uf000)
            if label[0] >= '\uf000':
                font_family = "forkawesome"
                font_size = int(1.5 * zynthian_gui_config.font_size)
            else:
                font_family = zynthian_gui_config.font_family
                if len(label) <= 3:
                    font_size = int(1.3 * zynthian_gui_config.font_size)
                else:
                    font_size = int(0.9 * zynthian_gui_config.font_size)
            font = tkfont.Font(family=font_family, size=font_size)

            #label = label.replace("/", "\n")
            longer_line = ""
            width = 0
            # Find longer line ...
            for line in label.split("\n"):
                w = font.measure(line)
                if (w > width):
                    width = w
                    longer_line = line
            # Reduce font until text fits the button ...
            max_width = int(0.8 * self.button_width)
            while width > max_width:
                font_size -= 1
                if font_size < 5:       # Fontsize smaller than 5 pixels is too small!!
                    break
                font = tkfont.Font(family=font_family, size=font_size)
                width = font.measure(longer_line)

            config[TXT_ID] =  self.create_text(
                x+self.button_width//2, y+self.button_height//2,
                text=label,
                font=font,
                justify=tkinter.CENTER,
                fill=self.text_color,
                tags=tag
            )
        self.tag_bind(tag, "<Button-1>", lambda e,i=button:self.cb_button_push(i))
        self.tag_bind(tag, "<ButtonRelease-1>", lambda e,i=button:self.cb_button_release(i))

    def cb_button_push(self, button):
        """ Handle button press
        Args:
            button: Index of button
        """

        self.move(f"v5_button_{button}", 2, 2)
        zynthian_gui_config.zyngui.cuia_queue.put_nowait(f"zynswitch {button + 4},P")

    def cb_button_release(self, button):
        """ Handle button release
        Args:
            button: Index of button
        """

        self.move(f"v5_button_{button}", -2, -2)
        zynthian_gui_config.zyngui.cuia_queue.put_nowait(f"zynswitch {button + 4},R")

    def set_button_color(self, button, color, mode):
        """ Change color of a button according to the wsleds signal
        Args:
            button: Index of the button
            color : Color requested by the wsled system
            mode : A wanna-be abstraction (string name) of the mode/state - currently
            just derived from the requested color by the `wsleds_v5touch` "fake NeoPixel" emulator
        """

        config = self.buttons[button]
        # don't bother with update if nothing has really changed (redrawing images causes visible blinking!)
        if config[LED_STATE] == mode:
            return
        config[LED_STATE] = mode
        # in case the color is still the original wsled integer number, convert it
        label = config[LABEL]
        if  label.startswith('_'):
            # image buttons must be recomposed to change the foreground color
            image = config[IMG]
            mask = image.convert("LA")
            bgimage = Image.new("RGBA", image.size, color)
            fgimage = Image.new("RGBA", image.size, (0, 0, 0, 0))
            composed = Image.composite(bgimage, fgimage, mask)
            tkimage = ImageTk.PhotoImage(composed)
            config[TKIMG] = tkimage
            self.itemconfig(config[IMG_ID], image=tkimage)
        else:
            # plain text labels may just change the color and possibly also its label if a special label
            # is associated with the requested mode (<=color) in the button definition
            if mode == "alt" and config[ALT_LABEL]:
                label = config[ALT_LABEL]
            else:
                label = config[LABEL]
            self.itemconfig(config[TXT_ID], text=label, fill=color)

    def apply_user_config(self):
        for i, config in enumerate(self.buttons):
            config[LABEL] = os.environ.get(f'ZYNTHIAN_TOUCH_KEYPAD_LABEL_{i+1:02d}_DEFAULT', config[LABEL])
            config[ALT_LABEL] = os.environ.get(f'ZYNTHIAN_TOUCH_KEYPAD_LABEL_{i+1:02d}_ALT', config[ALT_LABEL])
            config[ACT_LABEL] = os.environ.get(f'ZYNTHIAN_TOUCH_KEYPAD_LABEL_{i+1:02d}_ACTIVE', config[ACT_LABEL])
            config[ACT2_LABEL] = os.environ.get(f'ZYNTHIAN_TOUCH_KEYPAD_LABEL_{i+1:02d}_ACTIVE2', config[ACT2_LABEL])
