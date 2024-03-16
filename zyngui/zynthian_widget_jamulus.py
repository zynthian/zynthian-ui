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
        self.widget_canvas.create_text(
            0, 0,
            text="Disconnected",
            font=("DejaVu Sans Mono", int(0.8 * zynthian_gui_config.font_size)),
            fill="grey",
            anchor=tkinter.NW,
            tags=["connection"]
        )

        self.widget_canvas.grid(sticky='news')

    def on_size(self, event):
        super().on_size(event)
        self.legend_height = self.height // 10
        self.fader_height = self.height // 2
        self.channel_width = self.width // 8

    def update_fader_pos(self, channel, value):
        channel_width = self.width // 8
        x0 = int(channel_width * 0.4)
        x1 = int(channel_width * 0.9)
        y0 = int(self.height - self.legend_height - self.fader_height * value / 127)
        y1 = int(y0 - self.fader_height / 5)
        self.widget_canvas.coords(f"fader_{channel}", x0, y0, x1, y1)
        for i in range(1,4):
            y0 -= self.fader_height // 20
            self.widget_canvas.coords(f"fader_line{i}_{channel}", x0+2, y0, x1-2, y0)

    def refresh_gui(self):
        if "connected" in self.monitors:
            if self.monitors["connected"]:
                self.widget_canvas.itemconfig("connection", text="Connected", fill="white")
            else:
                self.widget_canvas.itemconfig("connection", text="Disconnected", fill="grey")
        if "clients" in self.monitors:
            # Update received from server for client config so redraw all client data
            self.levels = []
            self.widget_canvas.delete("clients")
            led_width = self.channel_width // 3
            for i, client in enumerate(self.monitors["clients"]):
                self.levels.append(0)
                x = int(self.channel_width * i)
                y = self.height - self.legend_height
                self.widget_canvas.create_text(
                    x, y,
                    text=client["name"],
                    font=("DejaVu Sans Mono", int(0.8 * zynthian_gui_config.font_size)),
                    fill=zynthian_gui_config.color_panel_tx,
                    width=self.channel_width - 4,
                    anchor=tkinter.NW,
                    tags=["clients", f"client_name_{i}"]
                )
                # Fader
                self.widget_canvas.create_line(
                    x + self.channel_width // 3 * 2,
                    y,
                    x + self.channel_width // 3 * 2,
                    y - int(self.fader_height * 1.2),
                    width = 4,
                    fill="grey"
                )
                self.widget_canvas.create_rectangle(
                    0,0,0,0,
                    fill="grey",
                    tags=["clients", f"fader_{i+1}"]
                )
                self.widget_canvas.create_line(
                    0,0,0,0,
                    width=1,
                    fill="white",
                    tags=["clients", f"fader_line1_{i+1}"]
                )
                self.widget_canvas.create_line(
                    0,0,0,0,
                    width=1,
                    fill="black",
                    tags=["clients", f"fader_line2_{i+1}"]
                )
                self.widget_canvas.create_line(
                    0,0,0,0,
                    width=1,
                    fill="white",
                    tags=["clients", f"fader_line3_{i+1}"]
                )
                self.update_fader_pos(i+1, 127) #TODO: Get actual fader position
                for j in range(10):
                    y = self.height - self.legend_height - int(self.fader_height / 9 * (j + 0.5)) 
                    self.widget_canvas.create_oval(x, y-5, x + led_width, y + self.fader_height // 20, fill="grey", tags=["clients", f"client{i}", f"led_{i}_{j}"])
                    pass
                # Mute button
                button_height = self.height // 10
                self.widget_canvas.create_rectangle(
                    x + 2,
                    20,
                    x + self.channel_width - 2,
                    20 + button_height,
                    fill="grey",
                    tags=["clients", f"mute_{i+1}"]
                )
                self.widget_canvas.create_text(
                    x + self.channel_width // 2,
                    20 + button_height // 2,
                    text="Mute",
                    fill="white",
                    tags=["clients"]
                )
                # Solo button
                self.widget_canvas.create_rectangle(
                    x + 2,
                    22 + button_height,
                    x + self.channel_width - 2,
                    22 + 2 * button_height,
                    fill="grey",
                    tags=["clients", f"solo_{i+1}"]
                )
                self.widget_canvas.create_text(
                    x + self.channel_width // 2,
                    22 + int(1.5 * button_height),
                    text="Solo",
                    fill="white",
                    tags=["clients"]
                )

        if "fader" in self.monitors:
            for fader in self.monitors["fader"]:
                self.update_fader_pos(fader[0], fader[1])
        if "mute" in self.monitors:
            for mute in self.monitors["mute"]:
                if mute[1]:
                    self.widget_canvas.itemconfig(f"mute_{mute[0]}", fill="red")
                else:
                    self.widget_canvas.itemconfig(f"mute_{mute[0]}", fill="grey")
        if "solo" in self.monitors:
            for solo in self.monitors["solo"]:
                if solo[1]:
                    self.widget_canvas.itemconfig(f"solo_{solo[0]}", fill="blue")
                else:
                    self.widget_canvas.itemconfig(f"solo_{solo[0]}", fill="grey")
        # Update client levels
        for client, level in enumerate(self.levels):
            if level != self.processor.engine.levels[client]:
                self.levels[client] = self.processor.engine.levels[client]
                for i in range(self.levels[client]):
                    self.widget_canvas.itemconfig(f"led_{client}_{i}", fill=self.LED_COLOUR[i])
                for i in range(self.levels[client], 10):
                    self.widget_canvas.itemconfig(f"led_{client}_{i}", fill="grey")
