# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI MIDI CC range config class
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
from zyngine import zynthian_controller
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian MIDI key-range GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_cc_range(zynthian_gui_base):

    def __init__(self):
        super().__init__()

        self.zctrl = None

        self.text_color = zynthian_gui_config.color_tx
        self.plot_color = zynthian_gui_config.color_on
        self.axis_color = zynthian_gui_config.color_hl
        #self.font_axis = ("sans", zynthian_gui_config.font_size)
        self.font_axis = (zynthian_gui_config.font_family, int(1.0 * zynthian_gui_config.font_size))

        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # Plot canvas
        self.plot_width = int(3 * self.width / 4)
        self.plot_height = self.height
        self.mgx = self.plot_width // 10
        self.mgy = self.plot_height // 10
        self.plot_canvas = tkinter.Canvas(self.main_frame,
                                           width=self.plot_width,
                                           height=self.plot_height,
                                           bd=0,
                                           highlightthickness=0,
                                           bg="#000000")
        if zynthian_gui_config.layout['columns'] == 3:
            self.plot_canvas.grid(row=0, column=0, rowspan=2, columnspan=2)
        else:
            self.plot_canvas.grid(row=0, column=0, rowspan=4, columnspan=1)
        self.plot_canvas.bind("<Button-1>", self.cb_plot_press)
        self.plot_canvas.bind("<B1-Motion>", self.on_plot_motion)

        # Create and plot controllers
        self.zgui_ctrls = [None, None, None, None]
        # Slots 1 & 2 are empty
        for j in range(0, 2):
            i = zynthian_gui_config.layout['ctrl_order'][j]
            self.zgui_ctrls[i] = zynthian_gui_controller(i, self.main_frame, None)
        # Slot 3 => Val1
        i = zynthian_gui_config.layout['ctrl_order'][2]
        self.v1_zctrl = zynthian_controller(self, 'Value at Min')
        self.v1_zgui_ctrl = zynthian_gui_controller(i, self.main_frame, self.v1_zctrl)
        self.zgui_ctrls[i] = self.v1_zgui_ctrl
        # Slot 4 => Val2
        i = zynthian_gui_config.layout['ctrl_order'][3]
        self.v2_zctrl = zynthian_controller(self, 'Value at Max')
        self.v2_zgui_ctrl = zynthian_gui_controller(i, self.main_frame, self.v2_zctrl)
        self.zgui_ctrls[i] = self.v2_zgui_ctrl
        # Display widgets
        if zynthian_gui_config.layout['columns'] == 3:
            self.v1_zgui_ctrl.configure(height=self.height // 2, width=self.width // 4)
            self.v2_zgui_ctrl.configure(height=self.height // 2, width=self.width // 4)
            self.v1_zgui_ctrl.grid(row=0, column=2, pady=(0, 1))
            self.v2_zgui_ctrl.grid(row=1, column=2, pady=(1, 0))
        else:
            for i in range(0, 4):
                self.zgui_ctrls[i].configure(height=self.height // 4, width=self.width // 4)
                self.zgui_ctrls[i].grid(row=i, column=2, pady=(1, 1))

        self.plot()
        self.replot = True

    def build_view(self):
        self.replot = True
        if not self.shown:
            zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
        return True

    def hide(self):
        if self.shown:
            zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
        super().hide()

    def config(self, zctrl):
        self.zctrl = zctrl
        self.setup_zctrls()
        self.replot = True
        self.set_select_path()

    def setup_zctrls(self):
        self.v1_zctrl.set_options({
            'value_min': self.zctrl.value_min,
            'value_max': self.zctrl.value_max,
            'value': self.zctrl.midi_cc_val1})
        self.v1_zgui_ctrl.config(self.v1_zctrl)
        self.v1_zgui_ctrl.setup_zynpot()

        self.v2_zctrl.set_options({
            'value_min': self.zctrl.value_min,
            'value_max': self.zctrl.value_max,
            'value': self.zctrl.midi_cc_val2})
        self.v2_zgui_ctrl.config(self.v2_zctrl)
        self.v2_zgui_ctrl.setup_zynpot()

    def cb_load_zs3(self, zs3_id):
        """Handle LOAD_ZS3 signal

        zs3_id : ID of loaded zs3
        """

        self.v1_zgui_ctrl.is_dirty = True
        self.v2_zgui_ctrl.is_dirty = True
        self.replot = True

    def plot_zctrls(self):
        if self.replot:
            for zgui_ctrl in self.zgui_ctrls:
                if zgui_ctrl and zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty:
                    zgui_ctrl.calculate_plot_values()
                    zgui_ctrl.plot_value()
                    zgui_ctrl.zctrl.is_dirty = False
            self.update_plot()
            self.replot = False

    def switch_select(self, t='S'):
        self.zyngui.close_screen()

    def zynpot_cb(self, i, dval):
        try:
            self.zgui_ctrls[i].zynpot_cb(dval)
            return True
        except:
            return False

    def zynpot_abs(self, i, val):
        try:
            self.zgui_ctrls[i].zynpot_abs(val)
            return True
        except:
            return False

    def send_controller_value(self, zctrl):
        if self.shown and self.zctrl is not None:
            if zctrl == self.v1_zctrl:
                self.zctrl.midi_cc_val1 = zctrl.value
                self.zctrl._configure()
                #logging.debug("SETTING MIDI CC VAL1: {}".format(zctrl.value))
                self.replot = True
            elif zctrl == self.v2_zctrl:
                self.zctrl.midi_cc_val2 = zctrl.value
                self.zctrl._configure()
                #logging.debug("SETTING MIDI CC VAL2: {}".format(zctrl.value))
                self.replot = True

    def set_select_path(self):
        try:
            self.select_path.set(f"CC Value Range: {self.zctrl.name}")
        except:
            self.select_path.set("CC Value Range")

    def plot(self):
        y0 = self.plot_height - self.mgy
        x0 = self.mgx - zynthian_gui_config.font_size
        x1 = self.plot_width - self.mgx

        # Vertical lines
        self.plot_canvas.create_line(self.mgx, y0, self.mgx, self.mgy,
                                     fill=self.axis_color, tags="axis")
        self.plot_canvas.create_line(x1, y0, x1, self.mgy,
                                     fill=self.axis_color, tags="axis")

        # Horizontal lines & Y-labels
        n_ticks = 4
        for i in range(0, n_ticks + 1):
            y = y0 + int(i * (self.mgy - y0) / n_ticks)
            self.plot_canvas.create_line(x0, y, x1, y,
                                        fill=self.axis_color, tags="axis")
            self.plot_canvas.create_text(x0, y, anchor=tkinter.E, text=str(int(i * 128 / n_ticks)),
                                        fill=self.text_color, font=self.font_axis, tags="axis")

    def update_plot(self):
        # Delete "replot" elements
        self.plot_canvas.delete("replot")

        # Do some maths
        if self.zctrl.value_range == 0:
            return
        k = (self.plot_width - 2 * self.mgx) / self.zctrl.value_range
        x1 = self.mgx + int(self.zctrl.midi_cc_val1 * k)
        x2 = self.mgx + int(self.zctrl.midi_cc_val2 * k)
        y0 = self.plot_height - self.mgy
        dash = self.mgx // 4

        # Plot value 1 dashed line
        self.plot_canvas.create_line(x1, y0, x1, self.mgy,
                                     fill=self.axis_color, dash=(dash, dash), tags="replot")
        # Plot value 2 dashed line
        self.plot_canvas.create_line(x2, y0, x2, self.mgy,
                                     fill=self.axis_color, dash=(dash, dash), tags="replot")
        # Plot linear value range representation
        self.plot_canvas.create_line(x1, y0, x2, self.mgy,
                                     fill=self.plot_color, width=3, tags="replot")

        # X Axis labels
        y0 += zynthian_gui_config.font_size
        if self.zctrl.midi_cc_val1 < self.zctrl.midi_cc_val2:
            a1 = tkinter.NE
            a2 = tkinter.NW
        else:
            a1 = tkinter.NW
            a2 = tkinter.NE
        self.plot_canvas.create_text(x1, y0, anchor=a1, text=self.v1_zgui_ctrl.format_print.format(self.zctrl.midi_cc_val1),
                                     fill=self.text_color, font=self.font_axis, tags="replot")
        self.plot_canvas.create_text(x2, y0, anchor=a2, text=self.v2_zgui_ctrl.format_print.format(self.zctrl.midi_cc_val2),
                                     fill=self.text_color, font=self.font_axis, tags="replot")


    def cb_plot_press(self, event):
        pass

    def on_plot_motion(self, event):
        pass

# ------------------------------------------------------------------------------
