# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Details Class
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

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base

# ------------------------------------------------------------------------------
# Zynthian Details GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_details(zynthian_gui_base):

    def __init__(self):
        super().__init__()
        self.title = ""

        # Textarea
        self.textarea = tkinter.Text(self.main_frame,
                                     width=int(
                                         zynthian_gui_config.display_width/(zynthian_gui_config.font_size + 5)),
                                     height=int(
                                         zynthian_gui_config.display_height/(zynthian_gui_config.font_size + 8)),
                                     font=(zynthian_gui_config.font_family,
                                           zynthian_gui_config.font_size, "normal"),
                                     wrap='word',
                                     # justify=tkinter.LEFT,
                                     bd=0,
                                     highlightthickness=0,
                                     relief=tkinter.FLAT,
                                     bg=zynthian_gui_config.color_bg,
                                     fg=zynthian_gui_config.color_tx)
        self.textarea.bind("<ButtonRelease-1>", self.cb_push)
        self.textarea.grid(row=0, column=0, padx=zynthian_gui_config.font_size,
                           pady=zynthian_gui_config.font_size // 2)

    def setup(self, title, text):
        self.title = title
        self.set_select_path()
        self.textarea.delete(1.0, tkinter.END)
        self.textarea.insert(tkinter.END, text)
        self.textarea.see(tkinter.END)

    def zynpot_cb(self, i, dval):
        # TODO: Scroll textarea
        return True

    def switch_select(self, t='S'):
        self.zyngui.back_screen()

    def back_action(self):
        return False

    def cb_push(self, event):
        self.zyngui.cuia_back()

    def cb_motion(self, event):
        # TODO: Scroll textarea
        pass

    def set_select_path(self):
        self.select_path.set(self.title)

# -------------------------------------------------------------------------------
