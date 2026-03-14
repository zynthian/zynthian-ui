#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI full screen modal
#
# Copyright (C) 2026 Fernando Moyano <jofemodo@zynthian.org>
#                    Brian Walton <brian@riban.co.uk>
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

# ------------------------------------------------------------------------------
# Zynthian fullscreen modal GUI Class
# ------------------------------------------------------------------------------


# Class implements renaming dialog
class zynthian_gui_fullscreen_modal(tkinter.Frame):

    # Function to initialise class
    #  function: Callback function called when <Enter> pressed
    def __init__(self):
        tkinter.Frame.__init__(self, zynthian_gui_config.top, bg=zynthian_gui_config.color_bg)
        self.grid_propagate(False)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.width = zynthian_gui_config.display_width
        self.height = zynthian_gui_config.display_height
        self.shown = False

    def on_size(self, event=None):
        self.width = zynthian_gui_config.display_width
        self.height = zynthian_gui_config.display_height

    def build_view(self):
        return True

    def hide(self):
        if self.shown:
            self.shown = False
            self.grid_forget()

    def show(self):
        if self.zyngui.test_mode:
            logging.warning("TEST_MODE: {}".format(self.__class__.__module__))
        if not self.shown:
            self.grid(row=0, column=0, rowspan=3, columnspan=10, sticky="nsew")
            self.tkraise()
            self.shown = True
