#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Save Preset helper Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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

# ------------------------------------------------------------------------------
# Zynthian Save Preset GUI Class
# ------------------------------------------------------------------------------
# This helper class must be inheritated by a GUI selector class!!
# ------------------------------------------------------------------------------


class zynthian_gui_save_preset():

    def save_preset(self):
        if self.processor:
            self.save_preset_create_bank_name = None
            self.save_preset_bank_info = None
            bank_list = self.processor.get_bank_list()
            # if not bank_list or not bank_list[0][0] or self.processor.auto_save_bank:
            if not bank_list or self.processor.auto_save_bank:
                self.save_preset_select_name_cb()
                return
            options = {}
            index = self.processor.get_bank_index()
            if callable(getattr(self.processor.engine, "create_user_bank", None)):
                options["***New bank***"] = "NEW_BANK"
                index += 1
            for bank in bank_list:
                if bank[0] == "*FAVS*":
                    index -= 1
                elif bank[0]:
                    options[bank[2]] = bank
                else:
                    options["None"] = ["", None, "None", None]
            if len(options) > 0:
                self.zyngui.screens['option'].config("Select bank...", options, self.save_preset_select_bank_cb)
                self.zyngui.show_screen('option')
                self.zyngui.screens['option'].select(index)
            else:
                self.save_preset_select_name_cb()

    def save_preset_select_bank_cb(self, bank_name, bank_info):
        self.save_preset_bank_info = bank_info
        if bank_info == "NEW_BANK":
            self.zyngui.show_keyboard(self.save_preset_select_name_cb, "NewBank")
        else:
            self.save_preset_select_name_cb()

    def save_preset_select_name_cb(self, create_bank_name=None):
        if create_bank_name is not None:
            create_bank_name = create_bank_name.strip()
        self.save_preset_create_bank_name = create_bank_name
        if self.processor.preset_name:
            self.zyngui.show_keyboard(self.save_preset_cb, self.processor.preset_name + " COPY")
        else:
            self.zyngui.show_keyboard(self.save_preset_cb, "New Preset")

    def save_preset_cb(self, preset_name):
        preset_name = preset_name.strip()
        if preset_name:
            # If must create new bank, calculate URID
            if self.save_preset_create_bank_name:
                create_bank_urid = self.processor.engine.get_user_bank_urid(self.save_preset_create_bank_name)
                self.save_preset_bank_info = (create_bank_urid, None, self.save_preset_create_bank_name, None)
            if self.processor.engine.preset_exists(self.save_preset_bank_info, preset_name):
                self.zyngui.show_confirm(f"Do you want to overwrite preset '{preset_name}'?",
                                        self.do_save_preset, preset_name)
            else:
                self.do_save_preset(preset_name)

    def do_save_preset(self, preset_name):
        preset_name = preset_name.strip()
        self.zyngui.state_manager.start_busy("Save Preset", f"Saving preset {preset_name}")

        try:
            # Save preset
            preset_uri = self.processor.engine.save_preset(self.save_preset_bank_info, preset_name)

            if preset_uri:
                # If must create new bank, do it!
                if self.save_preset_create_bank_name:
                    self.processor.engine.create_user_bank(self.save_preset_create_bank_name)
                    logging.info(f"Created new bank '{self.save_preset_create_bank_name}' => {self.save_preset_bank_info[0]}")
                if self.save_preset_bank_info:
                    self.processor.set_bank_by_id(self.save_preset_bank_info[0])
                self.processor.load_preset_list()
                self.processor.set_preset_by_id(preset_uri)
                self.index = self.processor.get_preset_index()
            else:
                logging.error(f"Can't save preset '{preset_name}' to bank '{self.save_preset_bank_info[2]}'")

        except Exception as e:
            logging.error(e)

        self.save_preset_create_bank_name = None
        self.zyngui.state_manager.end_busy("Save Preset")
        self.zyngui.close_screen()

# ------------------------------------------------------------------------------
