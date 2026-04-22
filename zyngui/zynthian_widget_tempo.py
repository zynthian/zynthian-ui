#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Tempo"
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngui import zynthian_widget_base
from zyngine.zynthian_signal_manager import zynsigman

# ------------------------------------------------------------------------------
# Zynthian Widget Class for "Tempo"
# ------------------------------------------------------------------------------


class zynthian_widget_tempo(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        self.widget_canvas = tkinter.Canvas(self,
            highlightthickness=0,
            relief='flat',
            bg=zynthian_gui_config.color_panel_bg)
        self.widget_canvas.grid(sticky='news')

        # Create custom GUI elements (position and size set when canvas is grid and size applied)
        self.bpm_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.CENTER,
            width=0,
            text="",
            font=(zynthian_gui_config.font_family, 10),
            fill=zynthian_gui_config.color_panel_tx
        )
        self.widget_canvas.bind("<ButtonPress-1>", self.tap)

    def on_size(self, event):
        if super().on_size(event):
            fs = self.width // 16
            self.widget_canvas.coords(self.bpm_text, self.width // 2, self.height // 2)
            self.widget_canvas.itemconfigure(self.bpm_text, width=9 * fs, font=(zynthian_gui_config.font_family, fs))

    def show(self):
        super().show()
        try:
            self.set_tempo(self.zyngui.state_manager.zynseq.get_tempo())
        except:
            pass
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, self.set_tempo)

    def hide(self):
        super().hide()
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, self.set_tempo)

    def set_tempo(self, tempo):
        self.widget_canvas.itemconfigure(self.bpm_text, text=f"{tempo:.1f} BPM")

    def tap(self, event):
        self.zyngui.state_manager.zynseq.tap_tempo()

# ------------------------------------------------------------------------------
