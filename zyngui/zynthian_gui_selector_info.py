#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Selector with Extended Info Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
from PIL import Image, ImageTk

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian Selector with Extended Info GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_selector_info(zynthian_gui_selector):

    def __init__(self, selcap='Select', default_icon="zynthian_logo.png", tiny_ctrls=True):
        # Custom layout for GUI selector info
        self.layout = {
            'name': 'gui_selector_info',
            'columns': 2,
            'rows': 4,
            'ctrl_pos': [
                    (0, 1),
                    (1, 1),
                    (2, 1),
                    (3, 1)
            ],
            'list_pos': (0, 0),
            'ctrl_orientation': 'horizontal',
            'ctrl_order': (0, 1, 2, 3),
            'ctrl_width': 0.25
        }
        self.icon_canvas = None
        self.info_canvas = None
        super().__init__(selcap, wide=True, loading_anim=True, tiny_ctrls=tiny_ctrls)
        self.loading_canvas.grid_remove()

        # Canvas for extended info image
        self.icon_canvas = tkinter.Canvas(self.main_frame,
            width=1,  # zynthian_gui_config.fw2, #self.width // 4 - 2,
            height=1,  # zynthian_gui_config.fh2, #self.height // 2 - 1,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_bg)
        self.icon_canvas.bind('<ButtonRelease-1>', self.cb_info_press)
        # Position at top of column containing selector
        self.icon_canvas.grid(row=0, column=self.layout['list_pos'][1] + 1, rowspan=1, sticky="news")

        # Canvas for extended info text
        self.info_canvas = tkinter.Canvas(
            self.main_frame,
            width=1,  # zynthian_gui_config.fw2, #self.width // 4 - 2,
            height=1,  # zynthian_gui_config.fh2, #self.height // 2 - 1,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_bg)
        self.info_canvas.bind('<ButtonRelease-1>', self.cb_info_press)
        # Position at top of column containing selector
        self.info_canvas.grid(row=1, column=self.layout['list_pos'][1] + 1, rowspan=3, sticky="news")

        # Info layout geometry
        self.side_width = int(self.layout['ctrl_width'] * self.width)

        # Info icon layout
        self.icons = {}
        self.icon_size = (self.side_width, self.side_width)
        self.icon_image = self.icon_canvas.create_image(self.side_width // 2, 0, anchor="n")
        self.default_icon = default_icon

        # Info text layout
        info_fs = min(int(0.8 * zynthian_gui_config.font_size), self.side_width // 16)
        xpos = int(0.8 * info_fs)
        ypos = int(-0.3 * info_fs)
        self.description_label = self.info_canvas.create_text(
            xpos, ypos,
            anchor=tkinter.NW,
            justify=tkinter.LEFT,
            width=self.side_width - xpos,
            text="",
            # font=(zynthian_gui_config.font_family, int(0.8 * zynthian_gui_config.font_size)),
            font=("sans-serif", info_fs),
            fill=zynthian_gui_config.color_panel_tx)

    def update_layout(self):
        super().update_layout()
        if self.icon_canvas:
            self.icon_canvas.configure(height=int(0.5 * self.height))

    def get_info(self):
        try:
            info = self.list_data[self.index][-1]
        except:
            return None

        if isinstance(info, list):
            return info
        else:
            return ["", ""]

    def update_info(self):
        info = self.get_info()
        if info:
            self.info_canvas.itemconfigure(self.description_label, text=info[0])
            self.icon_canvas.itemconfigure(self.icon_image, image=self.get_icon(info[1]))

    def get_icon(self, icon_fname):
        if not icon_fname:
            icon_fname = self.default_icon
        if icon_fname not in self.icons:
            try:
                img = Image.open(f"/zynthian/zynthian-ui/icons/{icon_fname}")
                icon = ImageTk.PhotoImage(img.resize(self.icon_size))
                self.icons[icon_fname] = icon
                return icon
            except Exception as e:
                logging.error(f"Can't load info icon {icon_fname} => {e}")
                return zynthian_gui_config.loading_imgs[0]
        else:
            return self.icons[icon_fname]

    def select(self, index=None, set_zctrl=True):
        super().select(index, set_zctrl)
        self.update_info()

    def send_controller_value(self, zctrl):
        if not self.shown:
            return
        if zctrl == self.zselector.zctrl:
            self.select(zctrl.value)

    def cb_info_press(self, event):
        self.zyngui.cuia_help()

# ------------------------------------------------------------------------------
