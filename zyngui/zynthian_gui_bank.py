#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Bank Selector Class
#
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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

import copy
import logging

# Zynthian specific modules
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_bank(zynthian_gui_selector_info):

    def __init__(self):
        self.processor = None
        super().__init__('Bank', default_icon="presets_bank.png")

    def fill_list(self):
        if not self.processor:
            logging.error("Can't fill bank list for None processor!")
            return
        # self.list_data = self.processor.bank_list
        # TODO: Can't optimize because of setBfree / Aeolus "bank anomaly"
        self.list_data = self.processor.get_bank_list()
        super().fill_list()

    def build_view(self):
        self.processor = self.zyngui.get_current_processor()
        if self.processor:
            self.processor.preset_subdir_info = None
            self.index = self.processor.get_bank_index()
            if self.processor.get_show_fav_presets():
                if len(self.processor.get_preset_favs()) > 0:
                    self.index = 0
                else:
                    self.processor.set_show_fav_presets(False)
            return super().build_view()
        else:
            return False

    def show(self):
        if len(self.list_data) > 0:
            super().show()

    def browse_root(self):
        if self.processor and self.processor.bank_subdir_info:
            self.index = self.processor.bank_subdir_info[1]
            self.processor.bank_subdir_info = None
            self.processor.preset_subdir_info = None
            self.set_select_path()
            self.update_list()
            self.select_listbox(self.index)
            return True
        return False

    def browse_back(self):
        if self.processor and self.processor.bank_subdir_info:
            self.index = self.processor.bank_subdir_info[1]
            self.processor.bank_subdir_info = self.processor.bank_subdir_info[3]
            self.processor.preset_subdir_info = None
            self.set_select_path()
            self.update_list()
            self.select_listbox(self.index)
            return True
        return False

    def select_action(self, i, t='S'):
        if self.list_data and self.list_data[i][0] == '*FAVS*':
            self.processor.set_show_fav_presets(True)
        else:
            if self.processor.set_bank(i) is None:
                # More setup stages to progress
                self.set_select_path()
                self.build_view()
                return
            self.processor.set_show_fav_presets(False)

        # If only one bank, show to preset list
        if len(self.list_data) <= 1:
            self.zyngui.replace_screen('preset')
        else:
            self.zyngui.show_screen('preset')
        self.zyngui.screens["preset"].autoselect()

    def topbar_bold_touch_action(self):
        self.zyngui.zynswitch_defered('B', 1)

    def show_bank_options(self):
        options = {}
        engine = self.processor.engine
        bank = copy.deepcopy(self.list_data[self.index])
        bank_name = bank[2]
        title_user = False
        if engine.is_preset_user(bank):
            if hasattr(engine, "rename_user_bank"):
                options["Rename"] = [bank, ["Rename bank", "rename.png"]]
                title_user = True
            if hasattr(engine, "delete_user_bank"):
                options["Delete"] = [bank, ["Delete bank", "folder_delete.png"]]
                title_user = True
        if hasattr(engine, "create_user_bank"):
            options["Global"] = None
            options["Create new bank"] = ["new bank", ["Create an empty bank", "folder_new.png"]]
        if not options:
            options["No bank options!"] = None
        if title_user:
            title = f"Bank options: {bank_name}"
        else:
            title = "Bank options"
        self.zyngui.screens['option'].config(
            title, options, self.bank_options_cb)
        self.zyngui.show_screen('option')

    def show_menu(self):
        self.show_bank_options()

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.current_screen == "option":
            self.close_screen()

    def bank_options_cb(self, option, bank):
        self.options_bank_index = self.index
        if option == "New":
            self.zyngui.show_keyboard(self.create_bank, bank)
        elif option == "Rename":
            self.zyngui.show_keyboard(self.rename_bank, bank[2])
        elif option == "Delete":
            self.zyngui.show_confirm("Do you really want to remove bank '{}' and delete all of its presets?".format(
                bank[2]), self.delete_bank, bank)

    def create_bank(self, bank_name):
        self.processor.engine.create_user_bank(bank_name)
        self.zyngui.close_screen()

    def rename_bank(self, bank_name):
        self.processor.engine.rename_user_bank(
            self.list_data[self.options_bank_index], bank_name)
        self.zyngui.close_screen()

    def delete_bank(self, bank):
        self.processor.engine.delete_user_bank(bank)
        self.zyngui.close_screen()

    # Function to handle *all* switch presses.
    # swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    # t: Press type ["S"=Short, "B"=Bold, "L"=Long]
    # returns True if action fully handled or False if parent action should be triggered
    def switch(self, swi, t='S'):
        if swi == 2:
            if t == 'S':
                self.zyngui.show_favorites()
                return True
        elif swi == 3:
            if t == 'B':
                self.show_bank_options()
                return True
        return False

    def set_selector(self, zs_hidden=False):
        super().set_selector(zs_hidden)

    def set_select_path(self):
        if self.processor:
            self.select_path.set(self.processor.get_basepath_subdir())

# -------------------------------------------------------------------------------
