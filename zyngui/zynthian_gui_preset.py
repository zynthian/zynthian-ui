#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Preset Selector Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
from zyngui.zynthian_gui_save_preset import zynthian_gui_save_preset

# -------------------------------------------------------------------------------
# Zynthian Preset/Instrument Selection GUI Class
# -------------------------------------------------------------------------------


class zynthian_gui_preset(zynthian_gui_selector_info, zynthian_gui_save_preset):

    def __init__(self):
        self.processor = None
        super().__init__('Preset', default_icon="preset.png")

    def fill_list(self):
        if not self.processor:
            logging.error("Can't fill preset list for None processor!")
            return
        self.processor.load_preset_list()
        self.list_data = self.processor.preset_list
        super().fill_list()

    def build_view(self):
        self.processor = self.zyngui.get_current_processor()
        if self.processor:
            return super().build_view()
        else:
            return False

    def show(self):
        if len(self.list_data) > 0:
            super().show()

    def select_action(self, i, t='S'):
        if t == 'S':
            # Allow animation
            self.icon_canvas.grid_remove()
            self.loading_canvas.grid(rowspan=1)
            self.zyngui.state_manager.start_busy("set preset")
            # Set preset
            self.zyngui.get_current_processor().set_preset(i)
            self.zyngui.state_manager.end_busy("set preset")
            self.zyngui.purge_screen_history("bank")
            # Stop animation and restore icon canvas
            self.loading_canvas.grid_remove()
            self.icon_canvas.grid()
            # Close
            self.zyngui.replace_screen("control")

    def show_preset_options(self):
        options = {}
        engine = self.processor.engine
        try:
            preset = copy.deepcopy(self.list_data[self.index])
            if preset[2][0] == "❤":
                preset[2] = preset[2][1:]
            preset_name = preset[2]
            title = f"Preset: {preset_name}"
        except:
            preset = None
            title = "Preset Options"
            pass
        if preset:
            if self.processor.engine.is_preset_fav(preset):
                options["\u2612 Favourite"] = [preset, ["Remove from favorites list", "favorite_remove.png"]]
            else:
                options["\u2610 Favourite"] = [preset, ["Add to favorites list", "favorite_add.png"]]
            if engine.is_preset_user(preset):
                if hasattr(engine, "rename_preset"):
                    options["Rename"] = [preset, ["Rename preset", "rename.png"]]
                if hasattr(engine, "delete_preset"):
                    options["Delete"] = [preset, ["Delete preset", "file_delete.png"]]
        global_options = {}
        if hasattr(engine, "save_preset"):
            global_options["Save new preset"] = [True, ["Save as new preset", "file_save.png"]]
        if self.processor.eng_code.startswith("JV/"):
            global_options["Scan for new presets"] = [True, ["Scan new presets, e.g. added via webconf", "reload.png"]]
        if global_options:
            options["Global"] = None
            options.update(global_options)
        self.zyngui.screens['option'].config(title, options, self.preset_options_cb)
        self.zyngui.show_screen('option')

    def show_menu(self):
        self.show_preset_options()

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.current_screen == "option":
            self.close_screen()

    def preset_options_cb(self, option, preset):
        if option.endswith("Favourite"):
            self.processor.toggle_preset_fav(preset)
            self.processor.load_preset_list()
            self.show_preset_options()
        elif option == "Rename":
            self.zyngui.show_keyboard(self.rename_preset, preset[2])
        elif option == "Delete":
            self.delete_preset(preset)
        elif option == "Save new preset":
            super().save_preset()
        elif option == "Scan for new presets":
            self.scan_presets()

    def rename_preset(self, new_name):
        preset = self.list_data[self.index]
        new_name = new_name.strip()
        if new_name != preset[2]:
            try:
                # TODO: Confirm rename if overwriting existing preset or duplicate name
                self.processor.engine.rename_preset(self.processor.bank_info, preset, new_name)
                if preset[0] == self.processor.preset_info[0]:
                    #TODO: This is not updating the display name of the current preset which is what I think it should be doing
                    self.zyngui.state_manager.start_busy("set preset")
                    self.processor.set_preset_by_id(preset[0])
                    self.zyngui.state_manager.end_busy("set preset")
                self.fill_list()
            except Exception as e:
                logging.error("Failed to rename preset => {}".format(e))

    def delete_preset(self, preset):
        self.zyngui.show_confirm("Do you really want to delete '{}'?".format(
            preset[2]), self.delete_preset_confirmed, preset)

    def delete_preset_confirmed(self, preset):
        try:
            count = self.processor.engine.delete_preset(self.processor.bank_info, preset)
            self.processor.remove_preset_fav(preset)
            self.fill_list()
            if count == 0:
                self.zyngui.close_screen()
        except Exception as e:
            logging.error("Failed to delete preset => {}".format(e))

    def scan_presets(self):
        self.zyngui.chain_manager.reload_engine_preset_info(self.processor.eng_code)
        self.zyngui.cuia_bank_preset(self.processor)

    # Function to handle *all* switch presses.
    # swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    # t: Press type ["S"=Short, "B"=Bold, "L"=Long]
    # returns True if action fully handled or False if parent action should be triggered
    def switch(self, swi, t='S'):
        if swi == 1:
            if t == 'S':
                if len(self.processor.get_bank_list()) > 1:
                    self.zyngui.replace_screen('bank')
                    return True
        elif swi == 2:
            if t == 'S':
                self.zyngui.toggle_favorites()
                return True
        elif swi == 3:
            if t == 'B':
                self.show_preset_options()
                return True
        return False

    def cuia_toggle_play(self, params=None):
        try:
            if self.processor.engine.nickname == "AP":
                self.click_listbox()
        except:
            pass

    def set_selector(self, zs_hidden=False):
        super().set_selector(zs_hidden)

    def preselect_action(self):
        self.zyngui.state_manager.start_busy("preselect preset")
        res = self.processor.preload_preset(self.index)
        self.zyngui.state_manager.end_busy("preselect preset")
        return res

    def restore_preset(self):
        return self.processor.restore_preset()

    def set_select_path(self):
        if self.processor:
            if self.processor.show_fav_presets:
                self.select_path.set(self.processor.get_basepath() + " > Favorites")
            else:
                self.select_path.set(self.processor.get_bankpath())

# ------------------------------------------------------------------------------
