#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Splash Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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

import tkinter
import logging
import os

# Zynthian specific modules
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian Splash GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_splash:

    def __init__(self):
        self.shown = False
        self.zyngui = zynthian_gui_config.zyngui
        self.width = zynthian_gui_config.display_width
        self.height = zynthian_gui_config.display_height

        self.canvas = tkinter.Canvas(zynthian_gui_config.top,
                                     width=self.width,
                                     height=self.height,
                                     bg=zynthian_gui_config.color_bg,
                                     bd=0,
                                     highlightthickness=0)

        self.image = None

    def hide(self):
        if self.shown:
            self.shown = False
            self.canvas.grid_forget()

    def show(self, text):
        if self.zyngui.test_mode:
            logging.warning("TEST_MODE: {}".format(self.__class__.__module__))
        if len(text) > 40:
            font_size = 28
        else:
            font_size = 36
        strlen = len(text) * font_size / 2
        pos_x = self.width / 2 - strlen / 2
        pos_y = int(self.height / 10)
        try:
            os.system('convert -strip -family \\"{}\\" -pointsize {} -fill white -draw "text {},{} \\"{}\\"" {}/img/fb_zynthian_boot.jpg {}/img/fb_zynthian_message.jpg'.format(
                zynthian_gui_config.font_family, font_size, pos_x, pos_y, text, os.environ.get("ZYNTHIAN_CONFIG_DIR"), os.environ.get("ZYNTHIAN_CONFIG_DIR")))
            self.img = tkinter.PhotoImage(
                file="/zynthian/config/img/fb_zynthian_message.jpg")
            if self.image is None:
                self.image = self.canvas.create_image(
                    0, 0, anchor='nw', image=self.img)
            else:
                self.canvas.itemconfig(self.image, image=self.img)
        except:
            pass
        if not self.shown:
            self.shown = True
            self.canvas.grid()

    def zynpot_cb(self, i, dval):
        pass

    def zyncoder_read(self):
        pass

    def refresh_loading(self):
        pass

    def switch_select(self, t='S'):
        pass

    def back_action(self):
        return False

# -------------------------------------------------------------------------------
