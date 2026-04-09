#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Control class
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

import logging

# Zynthian specific modules
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman

from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_side_chain import zynthian_side_chain

from zyngui.zynthian_gui_control import zynthian_gui_control
from zyngui.zynthian_gui_chain_options import zynthian_gui_chain_options
#from zyngui.zynthian_gui_processor_options import zynthian_gui_processor_options
from zyngui.zynthian_gui_midi_config import zynthian_gui_midi_config
from zyngui.zynthian_gui_audio_in import zynthian_gui_audio_in
from zyngui.zynthian_gui_audio_out import zynthian_gui_audio_out

# ------------------------------------------------------------------------------
# Zynthian Chain control GUI Class
# ------------------------------------------------------------------------------

class zynthian_gui_chain_control(zynthian_gui_base):

    def __init__(self, selcap='Chain Control'):
        super().__init__()

        # Attach static methods to main frame
        # => Grid a subscreen frame in the main frame's second column
        self.main_frame.grid_main = lambda frame: frame.grid(row=0, column=1, sticky='NEWS')

        self.chain = None
        self.chain_id = None
        self.chain_shown = False
        # Create chain frame, only in 2 columns layouts
        if zynthian_gui_config.layout['columns'] == 2:
            self.chain_width = 0.20
            self.chain_canvas = zynthian_side_chain(self)
        else:
            self.chain_width = 0.0
            self.chain_canvas = None

        self.subscreens = {}
        self.subscreens['control'] = zynthian_gui_control(parent=self)
        self.subscreens['chain_options'] = zynthian_gui_chain_options(parent=self)
        self.subscreens['midi_config'] = zynthian_gui_midi_config(parent=self)
        self.subscreens['audio_out'] = zynthian_gui_audio_out(parent=self)
        self.subscreens['audio_in'] = zynthian_gui_audio_in(parent=self)

        self.subscreen_name = None
        self.subscreen_key = None
        self.subscreen = None
        self.config_subscreen("control")

        self.update_layout()

    def update_layout(self):
        super().update_layout()
        # Reconfigure side chain canvas
        if self.chain_canvas:
            _chwidth = int(self.chain_width * self.width)
            chwidth = _chwidth * self.chain_shown
            self.chain_canvas.configure(width=_chwidth, height=self.height)
            #self.chain_canvas.update_layout()
        else:
            self.chain_shown = False
            chwidth = 0
        # Reconfigure subscreen
        self.subscreen_width = self.width - chwidth
        self.subscreen.configure(width=self.subscreen_width, height=self.height)
        # Reconfigure main frame columns
        self.main_frame.columnconfigure(0, minsize=chwidth, weight=int(self.chain_shown))
        self.main_frame.columnconfigure(1, minsize=self.subscreen_width, weight=1)

    def show_chain(self, show):
        if not self.chain_canvas:
            return
        if show:
            self.chain_shown = True
            self.update_layout()
            self.chain_canvas.grid(row=0, column=0, padx=(0, 2), pady=(0, 0), sticky="NEWS")
        else:
            self.chain_shown = False
            self.update_layout()
            self.chain_canvas.grid_remove()

    def toggle_chain(self):
        self.show_chain(not self.chain_shown)

    def refresh_chain(self):
        self.chain_canvas.build_graph()

    def build_view(self):
        super().build_view()

        if not self.shown:
            zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.cb_set_active_chain)

        self.set_chain()
        self.subscreen.show()
        return True

    def hide(self):
        if self.shown:
            zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.cb_set_active_chain)

        if self.chain_canvas:
            self.chain_canvas.hide()
        self.subscreen.hide()
        super().hide()

    def set_chain(self, chain_id=None):
        if chain_id is None:
            self.chain_id = self.chain_manager.active_chain.chain_id
        else:
            self.chain_id = chain_id
        self.chain = self.chain_manager.chains[self.chain_id]
        self.zyngui.current_processor = self.chain.current_processor

        if self.chain_canvas:
            self.chain_canvas.set_chain(self.chain_id)
            self.chain_canvas.build_view()
        else:
            self.config_subscreen()
            self.subscreen.build_view()

    def cb_set_active_chain(self, active_chain_id):
        self.set_chain(active_chain_id)

    def config_subscreen(self, ssname=None):
        if ssname is not None:
            self.subscreen_name = ssname
        try:
            match self.subscreen_name:
                case "chain_options":
                    self.subscreen_key = self.subscreen_name
                    self.subscreen = self.subscreens[self.subscreen_key]
                    self.subscreen.set_chain(self.chain)
                case "midi_input":
                    self.subscreen_key = "midi_config"
                    self.subscreen = self.subscreens[self.subscreen_key]
                    self.subscreen.set_chain(self.chain)
                    self.subscreen.midi_input = True
                case "midi_output":
                    self.subscreen_key = "midi_config"
                    self.subscreen = self.subscreens[self.subscreen_key]
                    self.subscreen.set_chain(self.chain)
                    self.subscreen.midi_input = False
                case _:
                    self.subscreen_key = self.subscreen_name
                    self.subscreen = self.subscreens[self.subscreen_key]
        except Exception as e:
            logging.error(e)
            self.subscreen_name = self.subscreen_key = "control"
            self.subscreen = self.subscreens[self.subscreen_key]

    def show_subscreen(self, ssname, proc=None, force=False):
        # Avoid ugly flickering by hiding the old screen after displaying the new one
        if ssname != self.subscreen_name:
            old_screen = self.subscreen
        else:
            old_screen = None
        if old_screen or force:
            self.config_subscreen(ssname)
            self.subscreen.configure(width=self.subscreen_width, height=self.height)
            self.subscreen.build_view()
            self.subscreen.show()
            if old_screen:
                old_screen.hide()
        elif self.subscreen_name == "control" and proc:
            self.subscreen.select_processor(proc)

    def select_subscreen(self, ssname, proc=None, show_chain=True):
        if ssname == "control":
            self.chain_canvas.select_node(proc=proc, action=True)
        else:
            self.chain_canvas.select_node(proc=ssname, action=True)
        self.show_chain(show_chain)

    # --------------------------------------------------------------------------
    # Zynpot & zynswitch callbacks
    # --------------------------------------------------------------------------

    # Function to handle *all* switch presses.
    #  swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    #  t: Press type ["S"=Short, "B"=Bold, "L"=Long]
    #  returns True if action fully handled or False if parent action should be triggered
    def switch(self, swi, t='S'):
        if self.subscreen.switch(swi, t):
            return True
        if swi == 0:
            if t == 'S':
                self.chain_manager.rotate_chain()
                return True
            elif t == "B":
                self.zyngui.cuia_bank_preset()
                return True

    def switch_select(self, t):
        if t == 'S':
            self.subscreen.switch_select(t)
            if self.subscreen_name == "control":
                if self.subscreen.mode == "select":
                    self.show_chain(True)
                else:
                    self.show_chain(False)
            return True
        elif t == 'B':
            return self.subscreen.switch_select(t)

    def back_action(self):
        if self.subscreen and self.subscreen.back_action():
            return True
        if self.chain_shown:
            self.show_chain(False)
            self.chain_canvas.select_current_processor(action=True)
            self.subscreen.set_mode_control()
            return True
        return False

    def zynpot_abs(self, i, val):
        return self.subscreen.zynpot_abs(i, val)

    def zynpot_cb(self, i, dval):
        if self.chain_shown and i == 2:
            if dval > 0:
                self.chain_canvas.arrow_down()
            elif dval < 0:
                self.chain_canvas.arrow_up()
            return True
        if self.subscreen.zynpot_cb(i, dval):
            if i == 3 and self.subscreen_name == "control":
               self.chain_canvas.select_current_processor()
            return True

    def plot_zctrls(self, force=False):
        return self.subscreen.plot_zctrls(force)

    # --------------------------------------------------------------------------
    # CUIA & LEDs
    # --------------------------------------------------------------------------

    def callable_ui_action(self, cuia, params=None):
        logging.debug("CUIA '{}' => {}".format(cuia, params))
        # First, try subscreen-defined catch-all cuia function
        cuia_func = getattr(self.subscreen, "callable_ui_action", None)
        if callable(cuia_func) and cuia_func(cuia, params):
            return True
        else:
            # Second, try subscreen-defined specific cuia function
            cuia_func_name = "cuia_" + cuia.lower()
            cuia_func = getattr(self.subscreen, cuia_func_name, None)
            if callable(cuia_func) and cuia_func(params):
                return True
            else:
                # Third, call default CUIA function (defined in this class)
                cuia_func = getattr(self, cuia_func_name, None)
                if callable(cuia_func):
                    return cuia_func(params)
        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if self.chain_shown:
            if i == 2:
                if self.chain_canvas:
                    self.chain_canvas.switch_select(t)
                return True
            elif i == 3:
                self.switch_select(t)
                return True
        return self.subscreen.cuia_v5_zynpot_switch(params)

    def cuia_arrow_up(self, params=None):
        self.subscreen.arrow_up()
        if self.subscreen_name == "control":
            self.chain_canvas.select_current_processor()
        return True

    def cuia_arrow_down(self, params=None):
        self.subscreen.arrow_down()
        if self.subscreen_name == "control":
            self.chain_canvas.select_current_processor()
        return True

    def cuia_arrow_right(self, params=None):
        self.chain_manager.next_chain()
        return True

    def cuia_arrow_left(self, params=None):
        self.chain_manager.previous_chain()
        return True

    def update_wsleds(self, leds):
        try:
            self.subscreen.update_wsleds(leds)
        except (AttributeError, TypeError):
            pass

    # --------------------------------------------------------------------------
    # Options Menu
    # --------------------------------------------------------------------------

    def show_menu(self):
        if not self.chain_shown:
            self.show_chain(True)
            try:
                self.subscreen.set_mode_select()
            except:
                pass
        else:
            zynthian_gui_config.zyngui.show_screen('chain_manager')

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.get_current_screen().endswith("_options"):
            self.zyngui.close_screen()

# ------------------------------------------------------------------------------
