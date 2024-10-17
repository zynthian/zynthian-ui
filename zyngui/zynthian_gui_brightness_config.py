#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Brightness config
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

import os
import glob
import tkinter
import logging

# Zynthian specific modules
import zynconf
from zyncoder.zyncore import lib_zyncore
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller


# ------------------------------------------------------------------------------
# Zynthian Brightness config GUI Class
# ------------------------------------------------------------------------------
class zynthian_gui_brightness_config(zynthian_gui_base):

    backlight_sysctrl_dir = "/sys/class/backlight"

    def __init__(self):
        super().__init__()

        self.zgui_ctrls = []
        self.display_brightness_zctrl = None
        self.display_brightness_gui_ctrl = None
        self.wsleds_brightness_zctrl = None
        self.wsleds_brightness_gui_ctrl = None

        # self.brightness_sysctrl_fpath = "/sys/class/backlight/rpi_backlight/brightness"
        self.brightness_sysctrl_fpath = self.get_backlight_sysctrl_fpath()

        self.init_ctrls()

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

    def get_backlight_sysctrl_fpath(self):
        if os.path.isdir(self.backlight_sysctrl_dir):
            try:
                # Search brightness system control files
                brightness_files = list(glob.iglob(
                    f"{self.backlight_sysctrl_dir}/*/brightness"))
                # Return the first one
                if len(brightness_files) > 0:
                    logging.debug(
                        f"Display brightness control file: {brightness_files[0]}")
                    return brightness_files[0]
                else:
                    logging.debug(
                        f"Can't find a display brightness control file")
            except Exception as e:
                logging.error(e)
        return None

    def init_ctrls(self):
        if self.brightness_sysctrl_fpath:
            try:
                val = int(os.environ.get("ZYNTHIAN_DISPLAY_BRIGHTNESS", "100"))
            except:
                val = 100
                logging.warning(
                    "Can't get init value for display brightness. Using default value.")
            try:
                val = int(val * 255 / 100)
                self.set_display_brightness(val)
                logging.info("Setting display brightness to {}.".format(val))
                # Create display brightness control
                if not self.display_brightness_gui_ctrl:
                    self.display_brightness_zctrl = zynthian_controller(self, 'display_brightness', {
                                                                        'name': 'Display', 'value_min': 0, 'value_max': 100, 'is_integer': True, 'nudge_factor': 1, 'value': val})
                    self.display_brightness_gui_ctrl = zynthian_gui_controller(
                        0, self.main_frame, self.display_brightness_zctrl)
                    self.zgui_ctrls.append(self.display_brightness_gui_ctrl)
            except:
                logging.warning("Can't set display brightness!")

        if self.zyngui.wsleds:
            try:
                val = int(os.environ.get("ZYNTHIAN_WSLEDS_BRIGHTNESS", "100"))
            except:
                val = 100
                logging.warning(
                    "Can't get init value for LED brightness. Using default value.")
            val = val / 100.0
            self.zyngui.wsleds.set_brightness(val)
            logging.info("Setting LED brightness to {}.".format(val))
            # Create LEDs brightness control
            if not self.wsleds_brightness_gui_ctrl:
                self.wsleds_brightness_zctrl = zynthian_controller(self, 'wsleds_brightness', {
                                                                   'name': 'LEDs', 'value_min': 0, 'value_max': 100, 'is_integer': True, 'nudge_factor': 1, 'value':  val})
                self.wsleds_brightness_gui_ctrl = zynthian_gui_controller(
                    1, self.main_frame, self.wsleds_brightness_zctrl)
                self.zgui_ctrls.append(self.wsleds_brightness_gui_ctrl)

    def get_num_zctrls(self):
        return len(self.zgui_ctrls)

    def get_display_brightness(self):
        if self.brightness_sysctrl_fpath:
            with open(self.brightness_sysctrl_fpath, "r") as fd:
                return int(fd.readline())
        return 255

    def set_display_brightness(self, val):
        if self.brightness_sysctrl_fpath:
            with open(self.brightness_sysctrl_fpath, "w") as fd:
                fd.write(str(val))

    def setup_zctrls(self):
        try:
            if self.display_brightness_gui_ctrl:
                val = int(self.get_display_brightness() * 100 / 255)
                logging.debug("DISPLAY BRIGHTNESS => {}".format(val))
                self.display_brightness_zctrl.set_value(val)
                self.replot = True

            if self.zyngui.wsleds:
                if self.wsleds_brightness_gui_ctrl:
                    val = int(self.zyngui.wsleds.get_brightness() * 100)
                    logging.debug("LED BRIGHTNESS => {}".format(val))
                    self.wsleds_brightness_zctrl.set_value(val)
                    self.replot = True
        except:
            pass

        self.setup_zctrls_layout()

    def send_controller_value(self, zctrl):
        if self.shown:
            if zctrl == self.display_brightness_zctrl:
                # logging.debug("Display Brightness => {}".format(zctrl.value))
                self.set_display_brightness(int(zctrl.value * 255 / 100))
                self.replot = True

            elif zctrl == self.wsleds_brightness_zctrl:
                # logging.debug("LEDs Brightness => {}".format(zctrl.value))
                if self.zyngui.wsleds:
                    self.zyngui.wsleds.set_brightness(zctrl.value / 100.0)
                self.replot = True

    def hide(self):
        if self.shown:
            config = {}
            if self.display_brightness_zctrl:
                config["ZYNTHIAN_DISPLAY_BRIGHTNESS"] = str(
                    self.display_brightness_zctrl.value)
            if self.wsleds_brightness_zctrl:
                config["ZYNTHIAN_WSLEDS_BRIGHTNESS"] = str(
                    self.wsleds_brightness_zctrl.value)
            if len(config) > 0:
                zynconf.save_config(config)

        super().hide()

    def set_select_path(self):
        self.select_path.set("Brightness")

    # -------------------------------------------------------------------------
    # Generic code (it should be abstracted to a base class
    # -------------------------------------------------------------------------

    def setup_zctrls_layout(self):
        for zgui_ctrl in self.zgui_ctrls:
            i = zgui_ctrl.index
            zgui_ctrl.setup_zynpot()
            zgui_ctrl.erase_midi_bind()
            zgui_ctrl.configure(
                height=self.height // zynthian_gui_config.layout['rows'], width=self.width // 4)
            zgui_ctrl.grid(
                row=zynthian_gui_config.layout['ctrl_pos'][i][0], column=zynthian_gui_config.layout['ctrl_pos'][i][1])

    def plot_zctrls(self):
        if self.replot:
            for zgui_ctrl in self.zgui_ctrls:
                if zgui_ctrl.zctrl.is_dirty:
                    zgui_ctrl.calculate_plot_values()
                    zgui_ctrl.plot_value()
                    zgui_ctrl.zctrl.is_dirty = False
            self.replot = False

    def build_view(self):
        self.setup_zctrls()
        return True

    def zynpot_cb(self, i, dval):
        if i < len(self.zgui_ctrls):
            self.zgui_ctrls[i].zynpot_cb(dval)
            return True
        else:
            return False

    def switch_select(self, t='S'):
        self.zyngui.close_screen()

# ------------------------------------------------------------------------------
