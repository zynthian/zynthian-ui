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
from html2text import HTML2Text

from zyngui import zynthian_widget_base
from zyngui import zynthian_gui_config
from zyngine import zynthian_engine_jamulus
from zynautoconnect import get_jackd_samplerate

class zynthian_widget_jamulus(zynthian_widget_base.zynthian_widget_base):

    LED_COLOUR = ["green", "green", "green", "green", "green", "orange", "orange", "red", "red", "red"]
    def __init__(self, parent):
        super().__init__(parent)
        self.levels = []
        self.html2text = HTML2Text()
        self.html2text.ignore_emphasis=True
        self.html2text.ignore_images=True
        self.html2text.ignore_links=True
        self.html2text.ignore_tables=True
        self.html2text.body_width=0
        self.widget_canvas = tkinter.Canvas(self,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.create_text(
            0,0,
            fill="grey",
            text="Disconnected" if get_jackd_samplerate() == 48000 else "Change samplerate\nto 48000",
            font=("DejaVu Sans Mono", int(2 * zynthian_gui_config.font_size)),
            tags="connection_status"
        )

        self.widget_canvas.create_text(
            0, 0,
            font=("DejaVu Sans Mono", int(0.8 * zynthian_gui_config.font_size)),
            fill="white",
            anchor=tkinter.NW,
            tags="chatText"
        )
        self.widget_canvas.create_rectangle(
            self.width - 10, 0, self.width, 20,
            fill="grey",
            tags="local_server_status"
        )

        self.widget_canvas.bind('<ButtonPress-1>', self.on_press)
        self.widget_canvas.bind('<ButtonRelease-1>', self.on_release)
        self.widget_canvas.bind('<B1-Motion>', self.on_motion)
        self.button_map = {}
        self.fader_map = {}
        self.pan_map = {}
        self.fader_zctrl = None
        self.pan_zctrl = None

        self.widget_canvas.grid(sticky='news')

    def on_size(self, event):
        super().on_size(event)
        self.legend_height = self.height // 10
        self.fader_height = self.height // 2
        self.channel_width = self.width // 8
        self.button_height = self.height // 12
        self.widget_canvas.coords("local_server_status", self.width - 10, 0, self.width, 20)
        self.widget_canvas.coords("connection_status", self.width //2, self.height // 2)

    def update_fader_pos(self, channel, value):
        x0 = int(self.channel_width * (channel - 0.6))
        x1 = int(self.channel_width * (channel - 0.1))
        y0 = int(self.height - self.legend_height - self.fader_height * value / 127)
        y1 = int(y0 - self.fader_height / 5)
        self.widget_canvas.coords(f"fader_{channel}", x0, y0, x1, y1)
        for i in range(1,4):
            y0 -= self.fader_height // 20
            self.widget_canvas.coords(f"fader_line{i}_{channel}", x0+2, y0, x1-2, y0)

    def update_pan_pos(self, channel, value):
        x = int(self.channel_width * (channel - 1) + 2 + (self.channel_width - 5) * value / 127)
        y0 = 24 + 2 * self.button_height,
        y1 = int(self.height - self.legend_height - 1.2 * self.fader_height - 2),
        self.widget_canvas.coords(f"pan_{channel}", x, y0, x, y1)

    def cb_scroll_chat(self):
        if self.chat_width + self.chat_pos > self.width - 10:
            self.scrolling_chat = True
            self.chat_pos -= 1
            self.widget_canvas.coords("chatText", self.chat_pos, 0)
            zynthian_gui_config.top.after(10, self.cb_scroll_chat)
        else:
            self.scrolling_chat = False
            zynthian_gui_config.top.after(3000, self.cb_finish_chat)

    def cb_finish_chat(self):
        if self.scrolling_chat == False:
            self.widget_canvas.coords("chatText", 0, 0)
            self.widget_canvas.itemconfig("chatText", fill="grey")

    def refresh_gui(self):
        if "status" in self.monitors:
            if self.monitors["status"] == zynthian_engine_jamulus.STATE_DISCONNECTED:
                self.monitors["clients"] = []
                self.widget_canvas.itemconfig("connection_status", fill="grey", text="Disconnected", state=tkinter.NORMAL)
            elif self.monitors["status"] == zynthian_engine_jamulus.STATE_CONNECTING:
                self.monitors["clients"] = []
                self.widget_canvas.itemconfig("chatText", text="")
                self.widget_canvas.itemconfig("connection_status", fill="white", text="Connecting", state=tkinter.NORMAL)
            elif self.monitors["status"] == zynthian_engine_jamulus.STATE_CONNECTED:
                self.widget_canvas.itemconfig("connection_status", state=tkinter.HIDDEN)
        if "local_server_status" in self.monitors:
            self.widget_canvas.itemconfig("local_server_status", fill="green" if self.monitors["local_server_status"] else "grey")
        if "chatText" in self.monitors:
            if self.monitors["chatText"].startswith("<font color"):
                self.monitors["chatText"] = self.monitors["chatText"].replace("</font>", "</font>:", 1)
            self.widget_canvas.itemconfig("chatText", text=self.html2text.handle(self.monitors["chatText"]).strip().replace('\n', ' | '), fill="white")
            self.chat_pos = 0
            self.widget_canvas.coords("chatText", self.chat_pos, 0)
            self.chat_width = self.widget_canvas.bbox("chatText")[2]
            zynthian_gui_config.top.after(1000, self.cb_scroll_chat)
        if "clients" in self.monitors:
            # Update received from server for client config so redraw all client data
            self.levels = []
            self.fader_map = {}
            self.widget_canvas.delete("strip")
            led_size = self.fader_height // 20
            for i, client in enumerate(self.monitors["clients"]):
                self.levels.append(0)
                x = int(self.channel_width * i)
                y = self.height - self.legend_height
                # Divider
                self.widget_canvas.create_line(
                    x + self.channel_width, 20, x + self.channel_width, self.height,
                    fill="white",
                    tags=["strip"]
                )
                # Legend strip
                self.widget_canvas.create_rectangle(
                    x, y, x + self.channel_width, y + self.legend_height,
                    fill=zynthian_gui_config.color_panel_tx,
                    tags=["strip"]
                )
                self.widget_canvas.create_text(
                    x, y,
                    text=client["name"],
                    font=("DejaVu Sans Mono", int(0.8 * zynthian_gui_config.font_size)),
                    #fill=zynthian_gui_config.color_panel_tx,
                    width=self.channel_width - 4,
                    anchor=tkinter.NW,
                    tags=["strip"]
                )
                # Fader
                self.widget_canvas.create_line(
                    x + self.channel_width // 3 * 2,
                    y,
                    x + self.channel_width // 3 * 2,
                    y - int(self.fader_height * 1.2),
                    width = 4,
                    fill="grey",
                    tags = ["strip"]
                )
                zctrl = self.processor.controllers_dict[f"Fader {i+1}"]
                self.fader_map[self.widget_canvas.create_rectangle(
                    0,0,0,0,
                    fill="grey",
                    tags=["strip", f"fader_{i+1}"]
                )] = zctrl
                self.widget_canvas.create_line(
                    0,0,0,0,
                    width=1,
                    fill="white",
                    tags=["strip", f"fader_line1_{i+1}"]
                )
                self.widget_canvas.create_line(
                    0,0,0,0,
                    width=1,
                    fill="black",
                    tags=["strip", f"fader_line2_{i+1}"]
                )
                self.widget_canvas.create_line(
                    0,0,0,0,
                    width=1,
                    fill="white",
                    tags=["strip", f"fader_line3_{i+1}"]
                )
                self.update_fader_pos(i+1, zctrl.value)
                # Meter LEDs
                for j in range(9):
                    y = self.height - self.legend_height - 2 - int((self.fader_height - 10) / 8 * (j + 0.5))
                    self.widget_canvas.create_oval(x + 2, y, x + 2 + led_size, y + led_size, fill="grey", tags=["strip", f"client{i}", f"led_{i}_{j}"])
                    pass
                # Mute button
                zctrl = self.processor.controllers_dict[f"Mute {i+1}"]
                if zctrl.value:
                    fill = "red"
                else:
                    fill = "grey"
                self.button_map[self.widget_canvas.create_rectangle(
                    x + 2,
                    20,
                    x + self.channel_width - 2,
                    20 + self.button_height,
                    fill=fill,
                    tags=["strip", f"mute_{i+1}"]
                )] = zctrl
                self.widget_canvas.create_text(
                    x + self.channel_width // 2,
                    20 + self.button_height // 2,
                    text="Mute",
                    fill="white",
                    tags=["strip"]
                )
                # Solo button
                zctrl = self.processor.controllers_dict[f"Solo {i+1}"]
                if zctrl.value:
                    fill = "#D0D000"
                else:
                    fill = "grey"
                self.button_map[self.widget_canvas.create_rectangle(
                    x + 2,
                    22 + self.button_height,
                    x + self.channel_width - 2,
                    22 + 2 * self.button_height,
                    fill=fill,
                    tags=["strip", f"solo_{i+1}"]
                )] = zctrl
                self.widget_canvas.create_text(
                    x + self.channel_width // 2,
                    22 + int(1.5 * self.button_height),
                    text="Solo",
                    fill="white",
                    tags=["strip"]
                )
                # Pan
                zctrl = self.processor.controllers_dict[f"Pan {i+1}"]
                self.pan_map[self.widget_canvas.create_rectangle(
                    x + 2,
                    24 + 2 * self.button_height,
                    x + self.channel_width - 2,
                    int(self.height - self.legend_height - 1.2 * self.fader_height - 2),
                    fill="grey",
                    tags=["strip"]
                )] = zctrl
                self.widget_canvas.create_line(
                    0,0,0,0,
                    fill="white",
                    width=3,
                    tags = ["strip", f"pan_{i+1}"]
                )
                self.update_pan_pos(i+1, zctrl.value)


        if "fader" in self.monitors:
            for fader in self.monitors["fader"]:
                self.update_fader_pos(fader[0], fader[1])
        if "pan" in self.monitors:
            for pan in self.monitors["pan"]:
                self.update_pan_pos(pan[0], pan[1])
        if "mute" in self.monitors:
            for mute in self.monitors["mute"]:
                if mute[1]:
                    self.widget_canvas.itemconfig(f"mute_{mute[0]}", fill="red")
                else:
                    self.widget_canvas.itemconfig(f"mute_{mute[0]}", fill="grey")
        if "solo" in self.monitors:
            for solo in self.monitors["solo"]:
                if solo[1]:
                    self.widget_canvas.itemconfig(f"solo_{solo[0]}", fill="#D0D000")
                else:
                    self.widget_canvas.itemconfig(f"solo_{solo[0]}", fill="grey")
        # Update client levels
        try:
            for client, level in enumerate(self.levels):
                if level != self.processor.engine.levels[client]:
                    self.levels[client] = self.processor.engine.levels[client]
                    for i in range(self.levels[client]):
                        self.widget_canvas.itemconfig(f"led_{client}_{i}", fill=self.LED_COLOUR[i])
                    for i in range(self.levels[client], 9):
                        self.widget_canvas.itemconfig(f"led_{client}_{i}", fill="grey")
        except:
            pass # There may be a temporary difference between levels and clients

    def on_press(self, event):
        self.press_event = event
        if (ids := self.widget_canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            for id in ids:
                if id in self.button_map:
                    if self.button_map[id].get_value():
                        self.button_map[id].set_value(0)
                    else:
                        self.button_map[id].set_value(127)
                    return
                elif id in self.fader_map:
                    self.fader_zctrl = self.fader_map[id]
                    self.value = self.fader_zctrl.value
                    self.factor = 127
                    return
                elif id in self.pan_map:
                    self.pan_zctrl = self.pan_map[id]
                    self.value = self.pan_zctrl.value
                    self.factor = 127
                    return

    def on_release(self, event):
        self.fader_zctrl = None
        self.pan_zctrl = None

    def on_motion(self, event):
        if self.fader_zctrl:
            factor = max(20, int((1 - abs((self.press_event.x - event.x) * 2 / self.width)) * 127))
            value = self.value + int((self.press_event.y - event.y) / self.fader_height * factor)
            value = max(min(value, 127), 0)
            self.fader_zctrl.set_value(value)
            # Reset event values to allow dynamic change of factor
            if self.factor != factor:
                self.value = value
                self.press_event.y = event.y
                self.factor = factor
        elif self.pan_zctrl:
            factor = max(20, int((1 - abs((self.press_event.y - event.y) * 2 / self.height)) * 127))
            value = self.value + int((event.x - self.press_event.x) / (self.channel_width - 4) * factor)
            value = max(min(value, 127), 0)
            self.pan_zctrl.set_value(value)
            if self.factor != factor:
                # Reset event values to allow dynamic change of factor
                self.value = value
                self.press_event.x = event.x
                self.factor = factor
