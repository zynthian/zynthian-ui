#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI ZS3 screen
#
# Copyright (C) 2018-2023 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian Sub-SnapShot (ZS3) GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_zs3(zynthian_gui_selector):

    def __init__(self):
        super().__init__('Program', True)

        self.zs3_waiting_label = tkinter.Label(self.main_frame,
                                               text='Waiting for MIDI Program Change...',
                                               font=(
                                                   zynthian_gui_config.font_family, zynthian_gui_config.font_size-2),
                                               fg=zynthian_gui_config.color_ml,
                                               bg=zynthian_gui_config.color_panel_bg
                                               )

    def show_waiting_label(self):
        if self.wide:
            padx = (0, 2)
        else:
            padx = (2, 2)
        self.zs3_waiting_label.grid(
            row=zynthian_gui_config.layout['list_pos'][0] + 4, column=zynthian_gui_config.layout['list_pos'][1], padx=padx, sticky='ew')

    def hide_waiting_label(self):
        self.zs3_waiting_label.grid_forget()

    def build_view(self):
        if super().build_view():
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.zyngui.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.register_queued(
                zynsigman.S_STATE_MAN, self.zyngui.state_manager.SS_SAVE_ZS3, self.cb_save_zs3)
            return True
        else:
            return False

    def hide(self):
        if self.shown:
            self.disable_midi_learn()
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, self.zyngui.state_manager.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.unregister(
                zynsigman.S_STATE_MAN, self.zyngui.state_manager.SS_SAVE_ZS3, self.cb_save_zs3)
            super().hide()

    def fill_list(self):
        self.list_data = []
        self.list_data.append(("SAVE_ZS3", None, "Save as new ZS3"))
        idx = 2
        try:
            self.list_data.append(
                ("zs3-0", self.zyngui.state_manager.zs3["zs3-0"], "Undo changes to current ZS3"))
            idx += 1
        except:
            pass

        # Add list of programs
        if len(self.zyngui.state_manager.zs3) > 1:
            self.list_data.append((None, None, "> SAVED ZS3s"))
        for id, state in self.zyngui.state_manager.zs3.items():
            if id in ["last_zs3", "zs3-0"]:
                continue
            elif id.startswith("zs3"):
                title = f"{state['title']}"
            else:
                parts = id.split('/')
                if len(parts) > 1:
                    if parts[0] == "*":
                        title = f"{state['title']} -> PR#{parts[1]}"
                    else:
                        title = f"{state['title']} -> CH#{parts[0]}:PR#{parts[1]}"
                else:
                    title = f"{state['title']} ({id})"
            self.list_data.append((id, state, title))
            if 'last_zs3' in self.zyngui.state_manager.zs3:
                if id == self.zyngui.state_manager.zs3['last_zs3']:
                    self.index = idx
                idx += 1

        super().fill_list()

    def cb_load_zs3(self, zs3_id):
        if self.shown:
            for i, row in enumerate(self.list_data):
                if row[0] == zs3_id:
                    self.select(i)
                    break

    def cb_save_zs3(self, zs3_id):
        if self.shown:
            self.update_list()
            self.disable_midi_learn()
            self.cb_load_zs3(zs3_id)

    def select_action(self, i, t='S'):
        zs3_index = self.list_data[i][0]
        if zs3_index == "SAVE_ZS3":
            self.zyngui.state_manager.disable_learn_pc()
            self.zyngui.state_manager.save_zs3()
            return True
        else:
            if t == 'S':
                self.zyngui.state_manager.disable_learn_pc()
                self.zyngui.state_manager.load_zs3(zs3_index)
                self.zyngui.close_screen()
                return True
            elif t == 'B':
                self.show_menu()
                return True

    def status_bold_touch_action(self):
        self.zyngui.callable_ui_action('screen_snapshot')

    def show_menu(self):
        try:
            zs3_index = self.list_data[self.index][0]
            if zs3_index == "SAVE_ZS3":
                return
            self.zyngui.state_manager.disable_learn_pc()
            self.zyngui.screens['zs3_options'].config(zs3_index)
            self.zyngui.show_screen('zs3_options')
        except:
            pass

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.current_screen == "zs3_options":
            self.close_screen()

    def enable_midi_learn(self):
        self.zyngui.state_manager.enable_learn_pc()
        self.show_waiting_label()

    def disable_midi_learn(self):
        self.zyngui.state_manager.disable_learn_pc()
        self.hide_waiting_label()

    def back_action(self):
        self.zyngui.state_manager.disable_learn_pc()
        return False

    def set_select_path(self):
        self.select_path.set("ZS3 (SubSnapShots)")

# -------------------------------------------------------------------------------
