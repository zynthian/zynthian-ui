#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Confirm Class
#
# Copyright (C) 2023-2026 Markus Heidt <markus@heidt-tech.com>
#                         Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_fullscreen_modal import zynthian_gui_fullscreen_modal

# TODO: Derive confirm from gui base class

# ------------------------------------------------------------------------------
# Zynthian Info GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_confirm(zynthian_gui_fullscreen_modal):

    def __init__(self):
        self.callback = None
        self.callback_params = None
        self.zyngui = zynthian_gui_config.zyngui

        # Main Frame
        super().__init__()

        self.text = tkinter.StringVar()
        self.label_text = tkinter.Label(self,
                                        font=(zynthian_gui_config.font_family,
                                              zynthian_gui_config.font_size, "normal"),
                                        textvariable=self.text,
                                        justify=tkinter.LEFT,
                                        padx=zynthian_gui_config.font_size,
                                        pady=zynthian_gui_config.font_size,
                                        bg=zynthian_gui_config.color_bg,
                                        fg=zynthian_gui_config.color_tx)
        self.label_text.grid(sticky="nsew")

        self.yes_text_label = tkinter.Label(self,
                                            font=(
                                                zynthian_gui_config.font_family,
                                                zynthian_gui_config.font_size*2, "normal"),
                                            text="Yes",
                                            width=3,
                                            justify=tkinter.RIGHT,
                                            padx=zynthian_gui_config.font_size,
                                            pady=zynthian_gui_config.font_size,
                                            bg=zynthian_gui_config.color_ctrl_bg_off,
                                            fg=zynthian_gui_config.color_tx)
        self.yes_text_label.bind("<ButtonRelease-1>", self.cb_yes_push)
        self.yes_text_label.grid(row=1, sticky="e")

        self.no_text_label = tkinter.Label(self,
                                           font=(
                                               zynthian_gui_config.font_family,
                                               zynthian_gui_config.font_size*2, "normal"),
                                           text="No",
                                           width=3,
                                           justify=tkinter.LEFT,
                                           padx=zynthian_gui_config.font_size,
                                           pady=zynthian_gui_config.font_size,
                                           bg=zynthian_gui_config.color_ctrl_bg_off,
                                           fg=zynthian_gui_config.color_tx)
        self.no_text_label.bind("<ButtonRelease-1>", self.cb_no_push)
        self.no_text_label.grid(row=1, sticky="w")

    def show(self, text, callback=None, cb_params=None):
        self.text.set(text)
        self.label_text.config(wraplength=zynthian_gui_config.screen_width-zynthian_gui_config.font_size*2,)
        self.callback = callback
        self.callback_params = cb_params
        if not self.shown:
            super().show()

    def zynpot_cb(self, i, dval):
        pass

    def refresh_loading(self):
        pass

    def switch_select(self, t='S'):
        logging.info("callback %s", self.callback_params)
        self.zyngui.close_screen()
        if self.callback:
            self.callback(self.callback_params)

    def switch(self, i, t):
        if i in [0, 2]:
            return True

    def cb_yes_push(self, event):
        self.zyngui.zynswitch_defered('S', 3)

    def cb_no_push(self, event):
        self.zyngui.zynswitch_defered('S', 1)

# -------------------------------------------------------------------------------
