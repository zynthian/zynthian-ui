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

    def __init__(self, selcap='Select', default_icon="zynthian_logo.png", tiny_ctrls=True, zsel_hidden=True, parent=None, topbar=None):
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
        self.zsel_hidden = zsel_hidden
        self.info_text = None
        self.default_icon = default_icon
        self.icons = {}

        super().__init__(selcap, wide=True, loading_anim=True, tiny_ctrls=tiny_ctrls, parent=parent, topbar=topbar)

        self.info_canvas = tkinter.Canvas(
            self.main_frame,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_bg)
        self.grid_info_canvas()
        self.info_text = self.info_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            justify=tkinter.LEFT,
            fill=zynthian_gui_config.color_panel_tx
        )
        self.info_icon = self.info_canvas.create_image(0, 0, anchor=tkinter.NW)

    def grid_info_canvas(self):
        if self.zsel_hidden:
            rowspan = 4
        else:
            rowspan = 3
        self.info_canvas.grid(row=0, column=self.layout['list_pos'][1] + 1, rowspan=rowspan, sticky="news", padx=(2,2), pady=(2,2))

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
        side_width = int(self.layout['ctrl_width'] * zynthian_gui_config.screen_width)
        fs = min(int(0.8 * zynthian_gui_config.font_size), side_width // 16)
        info = self.get_info()
        if info:
            image = self.get_icon(info[1])
            self.info_canvas.itemconfigure(self.info_icon, image=image)
            self.info_canvas.coords(self.info_text, 0, image.height() + 2)
            self.info_canvas.itemconfigure(self.info_text, font=("sans-serif", fs), text=info[0], width=image.width())

    def get_icon(self, icon_fname):
        if not icon_fname:
            icon_fname = self.default_icon
        if icon_fname[0] == "/":
            icon_fpath = icon_fname
        else:
            icon_fpath = f"{self.ui_dir}/icons/{icon_fname}"
        try:
            if self.icons[icon_fpath][zynthian_gui_config.touch_shown]:
                return self.icons[icon_fpath][zynthian_gui_config.touch_shown]
        except:
            pass
        try:
            img = Image.open(icon_fpath)
            side_width = int(self.layout['ctrl_width'] * zynthian_gui_config.screen_width)
            icon_size = (side_width - 2, side_width - 2)
            icon = ImageTk.PhotoImage(img.resize(icon_size))
            if icon_fpath not in self.icons:
                self.icons[icon_fpath] = [None, None]
            self.icons[icon_fpath][zynthian_gui_config.touch_shown] = icon
            return icon
        except Exception as e:
            logging.error(f"Can't load info icon {icon_fpath} => {e}")
            return zynthian_gui_config.loading_imgs[0]

    def set_selector(self, zs_hidden=None):
        if zs_hidden is None:
            zs_hidden = self.zsel_hidden
        super().set_selector(zs_hidden)

    def zynpot_cb(self, i, dval):
        if i == 2:
            x0, y0, x1, y1 = self.info_canvas.bbox(self.info_text)
            w_top = self.info_canvas.bbox(self.info_icon)[3]
            w_bottom = self.info_canvas.winfo_height()
            if dval > 0 and y1 > w_bottom or dval < 0 and y0 < w_top:
                self.info_canvas.move(self.info_text, 0, dval * -10)
            return True
        return super().zynpot_cb(i, dval)

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

    # --------------------------------------------------------------------------
    # ZynVoice TTS
    # --------------------------------------------------------------------------

    def tts_info(self):
        super().tts_info()
        try:
            self.zyngui.tts.announce("Help info.", False, False, False)
            self.zyngui.tts.announce(self.list_data[self.index][3][0].replace("\n", " . "),  False, False, False)
        except:
            pass

# ------------------------------------------------------------------------------
