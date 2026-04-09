#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Zynthian Internet Radio"
#
# Copyright (C) 2024-2026 Brian Walton <riban@zynthian.org>
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
from PIL import Image as Image, ImageTk

from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

mon_list = ["title", "info", "bitrate", "channels", "codec","title", "info", "bitrate", "channels", "codec"]

class zynthian_widget_inet_radio(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        self.widget_canvas = tkinter.Canvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        """ Layout:
        ____________________________
        | Title                    |
        | Info or artwork          |
        |                          |
        |                          |
        | Bitrate                  |
        | CODEC           Channels |
        |--------------------------|
        """

        self.lbl_title = self.widget_canvas.create_text(
            0, 0,
            anchor="nw",
            fill=zynthian_gui_config.color_tx_off
        )
        self.lbl_info = self.widget_canvas.create_text(
            0, 0,
            anchor="nw",
            fill=zynthian_gui_config.color_tx_off
        )
        self.img_art = self.widget_canvas.create_image(
            0, 0,
            anchor="sw"
        )
        self.lbl_bitrate = self.widget_canvas.create_text(
            0, 0,
            anchor="sw",
            fill=zynthian_gui_config.color_tx_off,
        )
        self.lbl_channels = self.widget_canvas.create_text(
            0, 0,
            anchor="se",
            fill=zynthian_gui_config.color_tx_off,
        )
        self.lbl_codec = self.widget_canvas.create_text(
            0, 0,
            anchor="sw",
            fill=zynthian_gui_config.color_tx_off,
        )
        self.refresh_count = 0
        self.info_page = 0
        self.art_path = ""

    def show(self):
        self.refresh_count = 0
        self.info_page = 3
        super().show()

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        self.widget_canvas.itemconfigure(self.lbl_title, font=(zynthian_gui_config.font_family, int(0.055*self.height)))
        self.widget_canvas.itemconfigure(self.lbl_info, width=0.9*self.width, font=(zynthian_gui_config.font_family, int(0.04*self.height)))
        self.widget_canvas.itemconfigure(self.lbl_bitrate, width=0.9*self.width, font=(zynthian_gui_config.font_family, int(0.04*self.height)))
        self.widget_canvas.itemconfigure(self.lbl_channels, width=0.9*self.width, font=(zynthian_gui_config.font_family, int(0.03*self.height)))
        self.widget_canvas.itemconfigure(self.lbl_codec, width=0.9*self.width, font=(zynthian_gui_config.font_family, int(0.03*self.height)))

        x = int(0.04 * self.height)
        self.widget_canvas.coords(self.lbl_title, x, int(0.02*self.height))
        self.widget_canvas.coords(self.lbl_info, x, int(0.15*self.height))
        self.widget_canvas.coords(self.img_art, x, int(0.92*self.height))
        self.widget_canvas.coords(self.lbl_bitrate, x, int(0.92*self.height))
        self.widget_canvas.coords(self.lbl_channels, int(0.98*self.width), int(0.98*self.height))
        self.widget_canvas.coords(self.lbl_codec, x, int(0.98*self.height))

        self.art_path = ""
        self.title_width = self.widget_canvas.bbox(self.lbl_title)[3-1]

    def refresh_gui(self):
        self.refresh_count += 1
        if self.monitors["reset"]:
            self.info_page = 0
            self.monitors["reset"] = False
        elif self.refresh_count < 50:
            # Update every 2s
            return
        self.refresh_count = 0
        if self.height < 300:
            # Use one field for smaller displays
            for i in range(self.info_page, 10):
                if self.monitors[mon_list[i]]:
                    self.widget_canvas.itemconfigure(self.lbl_title, text=self.monitors[mon_list[i]])
                    self.info_page = (i + 1) % 5
                    break
        else:
            self.widget_canvas.itemconfigure(
                self.lbl_title, text=self.monitors["title"])
            self.widget_canvas.itemconfigure(
                self.lbl_info, text=self.monitors["info"])
            self.widget_canvas.itemconfigure(
                self.lbl_channels, text=self.monitors["channels"])
            self.widget_canvas.itemconfigure(
                self.lbl_codec, text=self.monitors["codec"])
            self.widget_canvas.itemconfigure(
                self.lbl_bitrate, text=self.monitors["bitrate"])
            if self.art_path != self.monitors["artwork"]:
                self.art_path = self.monitors["artwork"]
                if self.art_path:
                    try:
                        img = Image.open(self.art_path)
                        img_height = int(self.height * 0.5)
                        img = img.resize((img_height, img_height), Image.Resampling.LANCZOS)
                        self.image = ImageTk.PhotoImage(img)
                        self.widget_canvas.itemconfig(self.img_art, image=self.image)
                    except Exception as e:
                        self.widget_canvas.itemconfig(self.img_art, image="")
                        self.image = None
                else:
                    self.widget_canvas.itemconfig(self.img_art, image="")
                    self.image = None
