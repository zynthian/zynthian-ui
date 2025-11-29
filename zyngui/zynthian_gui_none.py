# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI None Class
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

# Zynthian specific modules
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian None GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_none:

    def __init__(self):
        self.shown = False
        self.zyngui = zynthian_gui_config.zyngui

    def build_view(self):
        return True

    def hide(self):
        self.shown = False

    def show(self):
        self.shown = True

    def zynpot_cb(self, i, dval):
        return True

    def refresh_loading(self):
        pass

    def switch_select(self, t='S'):
        pass

# -------------------------------------------------------------------------------
