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
        self.width = zynthian_gui_config.display_width
        self.height = zynthian_gui_config.display_height
        tkinter.Frame.__init__(
            self, zynthian_gui_config.top,
            width=self.width,
            height=self.height,
            bg=zynthian_gui_config.color_bg)
        self.grid_propagate(False)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.shown = False
        self.alt_mode = False

    def on_size(self, event=None):
        self.width = zynthian_gui_config.display_width
        self.height = zynthian_gui_config.display_height

    def build_view(self):
        return True

    def hide(self):
        if self.shown:
            self.shown = False
            self.place_forget()

    def show(self):
        if not self.shown:
            self.place(x=0, y=0)
            self.tkraise()
            self.shown = True

    # --------------------------------------------------------------------------
    # CUIA
    # --------------------------------------------------------------------------

    # By default, fullscreen modals have no ALT mode.
    # To implement ALT mode, child classes have to redefine get_alt_mode() returning self.alt_mode
    def get_alt_mode(self):
        #return self.alt_mode
        return False

    def cuia_toggle_alt_mode(self, params=None):
        self.alt_mode = not self.alt_mode
        return True
