#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Zynthian Internet Radio"
#
# Copyright (C) 2024 Brian Walton <riban@zynthian.org>
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
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base


class zynthian_widget_inet_radio(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        self.widget_canvas = tkinter.Canvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        self.lbl_title = self.widget_canvas.create_text(
            20, 20,
            anchor="nw",
            font=(
                zynthian_gui_config.font_family,
                int(1.4 * zynthian_gui_config.font_size)
            ),
            fill=zynthian_gui_config.color_tx_off
        )
        self.lbl_info = self.widget_canvas.create_text(
            20, 60,
            anchor="nw",
            font=(
                zynthian_gui_config.font_family,
                zynthian_gui_config.font_size
            ),
            fill=zynthian_gui_config.color_tx_off
        )
        self.lbl_bitrate = self.widget_canvas.create_text(
            20, 300,
            anchor="sw",
            font=(
                zynthian_gui_config.font_family,
                zynthian_gui_config.font_size
            ),
            fill=zynthian_gui_config.color_tx_off,
        )
        self.lbl_audio = self.widget_canvas.create_text(
            20, 340,
            anchor="sw",
            font=(
                zynthian_gui_config.font_family,
                int(0.7 * zynthian_gui_config.font_size)
            ),
            fill=zynthian_gui_config.color_tx_off,
        )
        self.lbl_codec = self.widget_canvas.create_text(
            20, 360,
            anchor="sw",
            font=(
                zynthian_gui_config.font_family,
                int(0.7 * zynthian_gui_config.font_size)
            ),
            fill=zynthian_gui_config.color_tx_off,
        )
        self.refresh_count = 0
        self.info_page = 0

    def show(self):
        self.refresh_count = 0
        self.info_page = 3
        super().show()

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        self.widget_canvas.itemconfigure(self.lbl_title, width=self.width - 30)
        self.widget_canvas.itemconfigure(self.lbl_info, width=self.width - 30)
        self.widget_canvas.itemconfigure(self.lbl_audio, width=self.width - 30)
        self.widget_canvas.itemconfigure(self.lbl_codec, width=self.width - 30)
        self.widget_canvas.itemconfigure(
            self.lbl_bitrate, width=self.width - 30)
        if self.height >= 400:
            self.widget_canvas.coords(self.lbl_bitrate, 20, self.height - 60)
            self.widget_canvas.coords(self.lbl_audio, 20, self.height - 30)
            self.widget_canvas.coords(self.lbl_codec, 20, self.height - 10)

    def refresh_gui(self):
        self.refresh_count += 1
        if self.refresh_count > 50:
            # Update every 2s
            self.refresh_count = 0
            self.info_page += 1
        if self.height < 400:
            # Use one field for smaller displays
            if self.monitors["info"] in ["stream unavailable", "waiting for stream..."]:
                self.info_page = 1
            if self.info_page == 1:
                self.widget_canvas.itemconfigure(
                    self.lbl_title, text=self.monitors["title"])
            elif self.info_page == 2:
                self.widget_canvas.itemconfigure(
                    self.lbl_title, text=self.monitors["info"])
            elif self.info_page == 3:
                self.widget_canvas.itemconfigure(
                    self.lbl_title, text=self.monitors["bitrate"])
            elif self.info_page == 4:
                self.widget_canvas.itemconfigure(
                    self.lbl_title, text=self.monitors["audio"])
            else:
                self.widget_canvas.itemconfigure(
                    self.lbl_title, text=self.monitors["codec"])
                self.info_page = 0
        else:
            self.widget_canvas.itemconfigure(
                self.lbl_title, text=self.monitors["title"])
            self.widget_canvas.itemconfigure(
                self.lbl_info, text=self.monitors["info"])
            self.widget_canvas.itemconfigure(
                self.lbl_audio, text=self.monitors["audio"])
            self.widget_canvas.itemconfigure(
                self.lbl_codec, text=self.monitors["codec"])
            self.widget_canvas.itemconfigure(
                self.lbl_bitrate, text=self.monitors["bitrate"])
