#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI XY-Controller Class
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

import math
import tkinter
import logging
from datetime import datetime
from time import monotonic
import tkinter.font as tkfont

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_fullscreen_modal import zynthian_gui_fullscreen_modal

# ------------------------------------------------------------------------------
# Zynthian X-Y Controller GUI Class
# ------------------------------------------------------------------------------

# TODO: Derive control_xy from gui base class?


class zynthian_gui_control_xy(zynthian_gui_fullscreen_modal):

    def __init__(self):
        super().__init__()
        self.canvas = None
        self.hline = None
        self.vline = None
        self.zyngui = zynthian_gui_config.zyngui

        # Init X vars
        self.padx = 24
        self.x0 = self.padx
        self.x1 = zynthian_gui_config.display_width - self.padx
        self.width = zynthian_gui_config.display_width - 2 * self.padx
        self.x = self.width / 2
        self.xvalue = 64

        # Init Y vars
        self.pady = 18
        self.y0 = self.pady
        self.y1 = zynthian_gui_config.display_height - self.pady
        self.height = zynthian_gui_config.display_height - 2 * self.pady
        self.y = self.height / 2
        self.yvalue = 64

        self.last_motion_ts = None

        # Create Canvas
        self.canvas = tkinter.Canvas(self,
                                     # bd=0,
                                     highlightthickness=0,
                                     relief='flat',
                                     bg=zynthian_gui_config.color_bg)
        self.canvas.grid(sticky="news")

        # Setup Canvas Callbacks
        self.canvas.bind("<B1-Motion>", self.cb_canvas)
        self.last_tap = 0
        self.tap_count = 0
        self.canvas.bind("<Button-1>", self.cb_press)

        # Create text
        self.text = self.canvas.create_text(
            zynthian_gui_config.display_width//2,
            int(0.98 * zynthian_gui_config.display_height),
            anchor=tkinter.S,
            justify=tkinter.CENTER,
            font=zynthian_gui_config.font_topbar,
            fill=zynthian_gui_config.color_ctrl_bg_off,
            text="Tap 3 times to exit"
        )

        self.text_x = self.canvas.create_text(
            self.x0 + 5,
            self.y0 + 5,
            anchor=tkinter.NW,
            justify=tkinter.LEFT,
            font=zynthian_gui_config.font_topbar,
            fill=zynthian_gui_config.color_ctrl_bg_off,
            text=""
        )
        font = tkfont.Font(family=zynthian_gui_config.font_family, size=zynthian_gui_config.topbar_fs)
        text_height = font.metrics("linespace")

        self.text_y = self.canvas.create_text(
            self.x0 + 5,
            self.y0 + 10 + text_height,
            anchor=tkinter.NW,
            justify=tkinter.LEFT,
            font=zynthian_gui_config.font_topbar,
            fill=zynthian_gui_config.color_ctrl_bg_off,
            text=""
        )

        # Create Cursor
        self.hline = self.canvas.create_line(
            0,
            self.y,
            zynthian_gui_config.display_width,
            self.y,
            fill=zynthian_gui_config.color_on)
        self.vline = self.canvas.create_line(
            self.x,
            0,
            self.x,
            zynthian_gui_config.display_width,
            fill=zynthian_gui_config.color_on)

    def build_view(self):
        try:
            # Check zctrl are valid
            # TODO: Could use these values to show info of which parameters are being controlled
            self.zyngui.state_manager.zctrl_x.symbol
            self.zyngui.state_manager.zctrl_y.symbol
        except:
            return False
        return True

    def show(self):
        if not self.shown:
            super().show()
            self.get_controller_values()
            self.refresh()

    def get_controller_values(self):
        if self.zyngui.state_manager.zctrl_x.value != self.xvalue:
            self.xvalue = self.zyngui.state_manager.zctrl_x.value
            if self.zyngui.state_manager.zctrl_x.value_range == 0:
                self.x = 0
            elif self.zyngui.state_manager.zctrl_x.is_logarithmic:
                self.x = int(self.width * math.log10((9 * self.zyngui.state_manager.zctrl_x.value - (10 * self.zyngui.state_manager.zctrl_x.value_min -
                             self.zyngui.state_manager.zctrl_x.value_max)) / self.zyngui.state_manager.zctrl_x.value_range))
            else:
                self.x = int(self.width * (self.xvalue - self.zyngui.state_manager.zctrl_x.value_min) /
                             self.zyngui.state_manager.zctrl_x.value_range)
            self.canvas.coords(self.vline, self.x, self.y0, self.x, self.y1)

        if self.zyngui.state_manager.zctrl_y.value != self.yvalue:
            self.yvalue = self.zyngui.state_manager.zctrl_y.value
            if self.zyngui.state_manager.zctrl_y.value_range == 0:
                self.y = 0
            elif self.zyngui.state_manager.zctrl_y.is_logarithmic:
                self.y = int(self.width * math.log10((9 * self.zyngui.state_manager.zctrl_y.value - (10 * self.zyngui.state_manager.zctrl_y.value_min -
                             self.zyngui.state_manager.zctrl_y.value_max)) / self.zyngui.state_manager.zctrl_y.value_range))
            else:
                self.y = int(self.height * (self.yvalue - self.zyngui.state_manager.zctrl_y.value_min) /
                             self.zyngui.state_manager.zctrl_y.value_range)
            self.canvas.coords(self.hline, self.x0, self.y, self.x1, self.y)

    def refresh(self):
        self.canvas.coords(self.hline, self.x0, self.y, self.x1, self.y)
        self.canvas.coords(self.vline, self.x, self.y0, self.x, self.y1)

        if self.zyngui.state_manager.zctrl_x.is_logarithmic:
            xv = (math.pow(10, (self.x - self.x0) / self.width) * self.zyngui.state_manager.zctrl_x.value_range + (10 *
                  self.zyngui.state_manager.zctrl_x.value_min - self.zyngui.state_manager.zctrl_x.value_max)) / 9
        else:
            xv = self.zyngui.state_manager.zctrl_x.value_min + (self.x - self.x0) * \
                self.zyngui.state_manager.zctrl_x.value_range / self.width

        if self.zyngui.state_manager.zctrl_x.is_integer:
            xv = int(xv)

        if xv != self.xvalue:
            self.xvalue = xv
            self.zyngui.state_manager.zctrl_x.set_value(self.xvalue, True)
            self.canvas.itemconfig(self.text_x, text=f"{self.zyngui.state_manager.zctrl_x.name}: {self.xvalue:.3f}")

        if self.zyngui.state_manager.zctrl_y.is_logarithmic:
            yv = (math.pow(10, (self.y - self.y0) / self.height) * self.zyngui.state_manager.zctrl_y.value_range + (10 *
                  self.zyngui.state_manager.zctrl_y.value_min - self.zyngui.state_manager.zctrl_y.value_max)) / 9
        else:
            yv = self.zyngui.state_manager.zctrl_y.value_min + (self.y - self.y0) * \
                self.zyngui.state_manager.zctrl_y.value_range / self.height

        if self.zyngui.state_manager.zctrl_y.is_integer:
            yv = int(yv)

        if yv != self.yvalue:
            self.yvalue = yv
            self.zyngui.state_manager.zctrl_y.set_value(self.yvalue, True)
            self.canvas.itemconfig(self.text_y, text=f"{self.zyngui.state_manager.zctrl_y.name}: {self.yvalue:.3f}")

    def cb_canvas(self, event):
        # logging.debug("XY controller => %s, %s" % (event.x, event.y))
        self.x = min(self.x1, max(self.x0, event.x))
        self.y = min(self.y1, max(self.y0, event.y))
        self.refresh()
        self.last_motion_ts = datetime.now()

    def cb_press(self, event):
        now = monotonic()
        if now > self.last_tap + 0.05 and now < self.last_tap + 0.5:
            self.tap_count += 1
            if self.tap_count > 1:
                self.tap_count = 0
                self.zyngui.cuia_back()
        else:
            self.tap_count = 0
        self.last_tap = now

    def zynpot_cb(self, i, dval):
        # Wait 0.1 seconds after last motion for start reading encoders again
        if self.last_motion_ts is None or (datetime.now() - self.last_motion_ts).total_seconds() > 0.1:
            self.last_motion_ts = None
            if i == 2:
                zctrl = self.zyngui.state_manager.zctrl_y
            elif i == 3:
                zctrl = self.zyngui.state_manager.zctrl_x
            else:
                return False
            if i < zynthian_gui_config.num_zynpots and self.zyngui.zynpot_pr_state[i] > 0:
                self.zyngui.zynpot_pr_state[i] += 1
                fine = True
            else:
                fine = self.alt_mode
            res = zctrl.nudge(dval, fine=fine)
            if res:
                self.get_controller_values()
                return res
        return False

    def refresh_loading(self):
        pass

    def switch_select(self, t='S'):
        pass

    def get_alt_mode(self):
        return self.alt_mode



# ------------------------------------------------------------------------------
