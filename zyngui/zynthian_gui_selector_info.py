#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Selector with Extended Info Class
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
        self.info_text = None
        self.default_icon = default_icon
        self.icons = {}

        super().__init__(selcap, wide=True, loading_anim=True, tiny_ctrls=tiny_ctrls)
        self.loading_canvas.grid_remove()

        self.info_text = tkinter.Text(self.main_frame,
            background=zynthian_gui_config.color_bg,
            bd=0,
            highlightthickness=0,
            fg=zynthian_gui_config.color_tx,
            wrap=tkinter.WORD)
        self.info_text.grid(row=0, column=self.layout['list_pos'][1] + 1, rowspan=self.layout['rows'], sticky="news", padx=2, pady=2)
        image = self.get_icon(default_icon)
        self.info_text.image_create("end", image=image)
        self.info_text.insert("end", "\n")

    def update_layout(self):
        super().update_layout()
        if self.info_text:
            self.update_info()

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
        side_width = int(self.layout['ctrl_width'] * self.width)
        fs = min(int(0.8 * zynthian_gui_config.font_size), side_width // 16)
        self.info_text.configure(font=("sans-serif", fs))
        info = self.get_info()
        if info:
            self.info_text.delete("1.0", "end")
            self.info_text.image_create("end", image=self.get_icon(info[1]))
            self.info_text.insert("end", "\n\n")
            self.info_text.insert("end", info[0])

    def get_icon(self, icon_fname):
        if not icon_fname:
            icon_fname = self.default_icon
        try:
            if self.icons[icon_fname][zynthian_gui_config.touch_shown]:
                return self.icons[icon_fname][zynthian_gui_config.touch_shown]
        except:
            pass
        try:
            img = Image.open(f"{self.ui_dir}/icons/{icon_fname}")
            side_width = int(self.layout['ctrl_width'] * zynthian_gui_config.screen_width)
            icon_size = (side_width - 2, side_width - 2)
            icon = ImageTk.PhotoImage(img.resize(icon_size))
            if icon_fname not in self.icons:
                self.icons[icon_fname] = [None, None]
            self.icons[icon_fname][zynthian_gui_config.touch_shown] = icon
            return icon
        except Exception as e:
            logging.error(f"Can't load info icon {icon_fname} => {e}")
            return zynthian_gui_config.loading_imgs[0]

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
