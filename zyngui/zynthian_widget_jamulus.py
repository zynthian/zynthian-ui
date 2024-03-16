#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Widget Class for "Jamulus" ()
# 
# Copyright (C) 2024 Brian Walton <riban@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

import tkinter
import logging

from zyngine.zynthian_engine_jamulus import zynthian_engine_jamulus
from zyngui import zynthian_widget_base
from zyngui import zynthian_gui_config

class zynthian_widget_jamulus(zynthian_widget_base.zynthian_widget_base):

    LED_COLOUR = ["green", "green", "green", "green", "green", "orange", "orange", "red", "red", "red"]
    def __init__(self, parent):
        super().__init__(parent)
        self.levels = []
        self.widget_canvas = tkinter.Canvas(self,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

    def refresh_gui(self):
        if "clients" in self.monitors:
            self.widget_canvas.delete("clients")
            for i, client in enumerate(self.monitors["clients"]):
                x = int(self.width / 9 * (i + 0.5))
                y = self.height - 20
                self.widget_canvas.create_text(
                    x, y,
                    text=client["name"],
                    font=("DejaVu Sans Mono", int(0.8 * zynthian_gui_config.font_size)),
                    fill=zynthian_gui_config.color_panel_tx,
                    width=self.width // 9 - 4,
                    tags=["clients", f"client_name_{i}"]
            )
        if len(self.processor.engine.levels) != len(self.levels):
            num_clients = len(self.processor.engine.levels)
            self.levels = [0 for i in range(num_clients)]
            self.widget_canvas.delete("level_led")
            for i in range(num_clients):
                x = int(self.width / 9 * (i + 0.5))
                for j in range(10):
                    y = self.height - 40 - int((self.height - 40) / 9 * (j + 0.5)) 
                    self.widget_canvas.create_oval(x-10, y-5, x+10, y+5, fill="grey", tags=["level_led", f"client{i}", f"led_{i}_{j}"])
                    pass
        for client, level in enumerate(self.levels):
            if level != self.processor.engine.levels[client]:
                self.levels[client] = self.processor.engine.levels[client]
                for i in range(self.levels[client]):
                    self.widget_canvas.itemconfig(f"led_{client}_{i}", fill=self.LED_COLOUR[i])
                for i in range(self.levels[client], 10):
                    self.widget_canvas.itemconfig(f"led_{client}_{i}", fill="grey")
