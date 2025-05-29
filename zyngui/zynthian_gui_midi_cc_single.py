# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Midi-CC Single Selector Class
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

import logging

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian single CC number selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_cc_single(zynthian_gui_selector):

    def __init__(self):
        self.cb_func = None
        self.cc_num = None
        self.param = None
        super().__init__('CC', True)

    def config(self, cb_func, cc_num, param=None):
        self.cb_func = cb_func
        self.cc_num = cc_num
        self.param = param

    def fill_list(self):
        self.list_data = []
        for ccnum in range(1, 128):
            self.list_data.append((str(ccnum), ccnum, f"{str(ccnum).zfill(2)}"))
        if isinstance(self.cc_num, int) and 0 < self.cc_num < 128:
            self.index = self.cc_num - 1
        super().fill_list()

    def select_action(self, i, t='S'):
        self.cc_num = self.list_data[i][1]
        self.zyngui.close_screen()
        self.cb_func(self.cc_num, self.param)

    def set_select_path(self):
        self.select_path.set("CC")

# ------------------------------------------------------------------------------
