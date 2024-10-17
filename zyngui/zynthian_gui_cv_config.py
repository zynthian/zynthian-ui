#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI CV config
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
from ctypes import c_float

# Zynthian specific modules
import zynconf
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian CV config GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_cv_config(zynthian_gui_base):

    def __init__(self):
        super().__init__()

        self.zgui_ctrls = []
        self.cvin_scale_gui_ctrl = None
        self.cvin_offset_gui_ctrl = None
        self.cvout_scale_gui_ctrl = None
        self.cvout_offset_gui_ctrl = None

        self.info_canvas = tkinter.Canvas(self.main_frame,
                                          height=1,
                                          width=1,
                                          bg=zynthian_gui_config.color_panel_bg,
                                          bd=0,
                                          highlightthickness=0)
        self.main_frame.rowconfigure(2, weight=1)
        if zynthian_gui_config.layout['columns'] == 3:
            self.info_canvas.grid(row=0, column=1, rowspan=2,
                                  padx=(2, 2), sticky='news')
            self.main_frame.columnconfigure(1, weight=1)
        else:
            self.info_canvas.grid(row=0, column=0, rowspan=4,
                                  padx=(0, 2), sticky='news')
            self.main_frame.columnconfigure(0, weight=1)

        self.replot = True

    def set_zctrls(self):
        if not self.cvin_scale_gui_ctrl:
            lib_zyncore.zynaptik_cvin_get_volts_octave.restype = c_float
            val = lib_zyncore.zynaptik_cvin_get_volts_octave()
            logging.debug("CVIN SCALE => {}".format(val))
            self.cvin_scale_zctrl = zynthian_controller(self, 'cvin_scale', {
                                                        'name': 'CVin Volts/Octave', 'value_min': 0.1, 'value_max': 5.0, 'is_integer': False, 'nudge_factor': 0.01, 'value':  val})
            self.cvin_scale_gui_ctrl = zynthian_gui_controller(
                0, self.main_frame, self.cvin_scale_zctrl)
            self.zgui_ctrls.append(self.cvin_scale_gui_ctrl)

        if not self.cvin_offset_gui_ctrl:
            self.cvin_offset_zctrl = zynthian_controller(self, 'cvin_offset', {
                                                         'name': 'CVin Offset', 'value_min': 0, 'value_max': 127, 'is_integer': True, 'nudge_factor': 1, 'value':  lib_zyncore.zynaptik_cvin_get_note0()})
            self.cvin_offset_gui_ctrl = zynthian_gui_controller(
                1, self.main_frame, self.cvin_offset_zctrl)
            self.zgui_ctrls.append(self.cvin_offset_gui_ctrl)

        if not self.cvout_scale_gui_ctrl:
            lib_zyncore.zynaptik_cvout_get_volts_octave.restype = c_float
            val = lib_zyncore.zynaptik_cvout_get_volts_octave()
            logging.debug("CVOUT SCALE => {}".format(val))
            self.cvout_scale_zctrl = zynthian_controller(self, 'cvout_scale', {
                                                         'name': 'CVout Volts/Octave', 'value_min': 0.1, 'value_max': 5.0, 'is_integer': False, 'nudge_factor': 0.01, 'value':  val})
            self.cvout_scale_gui_ctrl = zynthian_gui_controller(
                2, self.main_frame, self.cvout_scale_zctrl)
            self.zgui_ctrls.append(self.cvout_scale_gui_ctrl)

        if not self.cvout_offset_gui_ctrl:
            self.cvout_offset_zctrl = zynthian_controller(self, 'cvout_offset', {
                                                          'name': 'CVout Offset', 'value_min': 0, 'value_max': 127, 'is_integer': True, 'nudge_factor': 1, 'value':  lib_zyncore.zynaptik_cvout_get_note0()})
            self.cvout_offset_gui_ctrl = zynthian_gui_controller(
                3, self.main_frame, self.cvout_offset_zctrl)
            self.zgui_ctrls.append(self.cvout_offset_gui_ctrl)

        layout = zynthian_gui_config.layout
        for zgui_ctrl in self.zgui_ctrls:
            i = zgui_ctrl.index
            zgui_ctrl.setup_zynpot()
            zgui_ctrl.erase_midi_bind()
            zgui_ctrl.configure(height=self.height //
                                layout['rows'], width=self.width // 4)
            zgui_ctrl.grid(row=layout['ctrl_pos'][i]
                           [0], column=layout['ctrl_pos'][i][1])

    def plot_zctrls(self):
        if self.replot:
            for zgui_ctrl in self.zgui_ctrls:
                if zgui_ctrl.zctrl.is_dirty:
                    zgui_ctrl.calculate_plot_values()
                    zgui_ctrl.plot_value()
                    zgui_ctrl.zctrl.is_dirty = False
            self.replot = False

    def build_view(self):
        self.set_zctrls()
        return True

    def zynpot_cb(self, i, dval):
        if i < 4:
            self.zgui_ctrls[i].zynpot_cb(dval)
            return True
        else:
            return False

    def send_controller_value(self, zctrl):
        if self.shown:
            if zctrl == self.cvin_scale_zctrl:
                logging.debug("CVin scale => {}".format(zctrl.value))
                try:
                    lib_zyncore.zynaptik_cvin_set_volts_octave(
                        c_float(zctrl.value))
                except Exception as e:
                    logging.error(e)
                self.replot = True

            elif zctrl == self.cvin_offset_zctrl:
                logging.debug("CVin offset => {}".format(zctrl.value))
                lib_zyncore.zynaptik_cvin_set_note0(zctrl.value)
                self.replot = True

            elif zctrl == self.cvout_scale_zctrl:
                logging.debug("CVout scale => {}".format(zctrl.value))
                try:
                    lib_zyncore.zynaptik_cvout_set_volts_octave(
                        c_float(zctrl.value))
                except Exception as e:
                    logging.error(e)
                self.replot = True

            elif zctrl == self.cvout_offset_zctrl:
                logging.debug("CVout offset => {}".format(zctrl.value))
                lib_zyncore.zynaptik_cvout_set_note0(zctrl.value)
                self.replot = True

    def switch_select(self, t='S'):
        self.zyngui.close_screen()

    def set_select_path(self):
        self.select_path.set("CV Settings")


# ------------------------------------------------------------------------------
