#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for NAM (Neural Amp Modeler) plugin
#
# Copyright (C) 2015-2025 Jofemodo <fernando@zynthian.org>
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

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

# ------------------------------------------------------------------------------
# Zynthian Widget Class for NAM (Neural Amp Modeler) plugin
# ------------------------------------------------------------------------------


class zynthian_widget_nam(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        self.widget_canvas = tkinter.Canvas(self,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Create custom GUI elements (position and size set when canvas is grid and size applied)

        self.model_title_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx_off,
            text='Model:',
            anchor="w"
        )
        self.model_title_line = self.widget_canvas.create_line(
            0, 0, 0, 0,
            width=1,
            fill=zynthian_gui_config.color_tx_off
        )
        self.model_file_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx,
            text='',
            width=0,
            anchor="nw"
        )

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)

        content_width = round(0.9 * self.width)
        content_height = round(0.1 * self.height)
        x0 = round(0.05 * self.width)
        y0 = round(0.5 * self.height)
        fs_title = content_height // 2
        fs_file = content_height // 3

        self.widget_canvas.coords(self.model_title_label, x0, y0)
        self.widget_canvas.itemconfig(self.model_title_label, font=(zynthian_gui_config.font_family, fs_title))
        self.widget_canvas.coords(self.model_title_line, x0, y0 + content_height // 2,
                                  x0 + content_width, y0 + content_height // 2)
        self.widget_canvas.coords(self.model_file_label, x0, y0 + int(0.8 * content_height))
        self.widget_canvas.itemconfig(self.model_file_label,
                                      font=(zynthian_gui_config.font_family, fs_file),
                                      width=content_width)

        self.widget_canvas.grid(row=0, column=0, sticky='news')

    def refresh_gui(self):
        if "model" in self.processor.controllers_dict:
            parts = os.path.split(self.processor.controllers_dict["model"].value)
            fname = parts[1]
            self.widget_canvas.itemconfig(self.model_file_label, text=fname)

# ------------------------------------------------------------------------------
