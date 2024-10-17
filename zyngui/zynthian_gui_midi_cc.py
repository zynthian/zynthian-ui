# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Midi-CC Selector Class
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

import ctypes
import logging

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian CC number selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_cc(zynthian_gui_selector):

    def __init__(self):
        self.chain = None
        self.zmop_index = None
        self.cc_route = None
        super().__init__('CC', True)

    def set_chain(self, chain):
        if chain.zmop_index is not None and chain.zmop_index >= 0:
            self.chain = chain
            self.zmop_index = chain.zmop_index
        else:
            self.chain = None
            self.zmop_index = None

    def build_layout(self):
        if self.chain:
            return super().build_layout()
        else:
            return False

    def fill_list(self):
        self.list_data = []

        self.cc_route = (ctypes.c_uint8 * 128)()
        lib_zyncore.zmop_get_cc_route(self.zmop_index, self.cc_route)

        for ccnum, enabled in enumerate(self.cc_route):
            if enabled:
                self.list_data.append(
                    (str(ccnum), ccnum, "\u2612 CC {}".format(str(ccnum).zfill(2))))
            else:
                self.list_data.append(
                    (str(ccnum), ccnum, "\u2610 CC {}".format(str(ccnum).zfill(2))))
        super().fill_list()

    def select_action(self, i, t='S'):
        ccnum = self.list_data[i][1]
        if self.cc_route[ccnum]:
            self.cc_route[ccnum] = 0
            bullet = "\u2610"
        else:
            self.cc_route[ccnum] = 1
            bullet = "\u2612"
        cctext = f"{bullet} CC {str(ccnum).zfill(2)}"
        self.list_data[i] = (str(ccnum), ccnum, cctext)
        self.listbox.delete(i)
        self.listbox.insert(i, cctext)
        self.select(i)
        # Set CC route state in zyncore
        lib_zyncore.zmop_set_cc_route(self.zmop_index, self.cc_route)

    def set_select_path(self):
        self.select_path.set("Routed CCs")

# ------------------------------------------------------------------------------
