#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Options Class
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

import logging
import os

# Zynthian specific modules
import zynautoconnect
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian Chain Options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_chain_options(zynthian_gui_selector_info):

    def __init__(self, parent=None, topbar=None):
        super().__init__(selcap='Option', parent=parent, topbar=topbar)
        self.index = 0
        self.chain = None
        self.set_chain()

    def set_chain(self, chain=None):
        if chain is None:
            self.chain = self.zyngui.chain_manager.active_chain
        else:
            self.chain = chain

    def build_view(self):
        if self.chain is not None:
            super().build_view()
            if self.index >= len(self.list_data):
                self.index = len(self.list_data) - 1
            return True
        else:
            return False

    def fill_list(self):
        self.list_data = []

        synth_proc_count = self.chain.get_processor_count("Synth")
        midi_proc_count = self.chain.get_processor_count("MIDI Tool")
        audio_proc_count = max(0, self.chain.get_processor_count("Audio Effect") - 1)

        self.list_data.append((None, None, "> PROCESSORS"))
        if self.chain.is_midi():
            self.list_data.append((self.midifx_add, None, "Add MIDI-FX processor",
                                    ["Add a MIDI effects processor to this the end of this chain.", "midi_processor.png"]))

        if self.chain.is_audio():
            self.list_data.append((self.audiofx_add, None, "Add Audio-FX processor",
                                    ["Add an audio effects processor to the end of this chain.", "audio_processor.png"]))

        if midi_proc_count > 0:
            self.list_data.append((self.remove_all_midifx, None, "Remove all MIDI-FX",
                                   ["Remove all MIDI-FX processors from this chain.", "delete_midi_processors.png"]))

        if audio_proc_count > 0:
            self.list_data.append((self.remove_all_audiofx, None, "Remove all Audio-FX",
                                   ["Remove all audio-FX processors from this chain.", "delete_audio_processors.png"]))

        if self.chain.get_processor_count():
            self.list_data.append((self.clear_midi_learn, None, "Clean MIDI Learn",
                                   ["Remove CC bindings from all parameters of all processors in this chain.", "delete_presets.png"]))

        self.list_data.append((None, None, "> MANAGE"))

        if self.chain.chain_id:
            self.list_data.append((self.move_chain, None, "Move chain",
                               ["Reposition the chain in the mixer view.\n\nUse knob 4 to move the chain position.", "move_left_right.png"]))

        self.list_data.append((self.rename_chain, None, "Rename chain",
                               ["Change the name of the chain. Clear name to reset to default name.", "rename.png"]))

        self.list_data.append((self.export_chain, None, "Export chain as snapshot...",
                                ["Save this chain as a snapshot.\n\nThe saved snapshot may loaded or may be imported into another snapshot.", "snapshot_chains.png"]))

        self.list_data.append((self.remove_chain, None, "Remove chain",
                               ["Remove this chain and all its processors.", "delete_chains.png"]))

        super().fill_list()

    def fill_listbox(self):
        super().fill_listbox()
        for i, val in enumerate(self.list_data):
            if val[0] == None:
                self.listbox.itemconfig(
                    i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})

    def select_action(self, i, t='S'):
        self.index = i
        try:
            self.list_data[i][0]()
        except:
            pass

    def post_action(self):
        if self.parent:
            self.build_view()
            self.show()
            self.set_select_path()
            self.parent.refresh_chain()
        else:
            self.zyngui.show_screen_reset('chain_manager')

    def clear_midi_learn(self):
        self.zyngui.show_confirm(f"Do you want to clean MIDI-learn for ALL controls in ALL processors within chain: {self.chain.get_name()}?",
            self.zyngui.chain_manager.clean_midi_learn,
            self.chain.chain_id)

    def move_chain(self):
        if self.parent:
            self.zyngui.show_screen('chain_manager')
            self.zyngui.screens["chain_manager"].start_moving_chain()
        else:
            self.zyngui.screens["chain_manager"].start_moving_chain()
            self.zyngui.show_screen_reset('chain_manager')

    def rename_chain(self):
        self.zyngui.show_keyboard(self.do_rename_chain, self.chain.title)

    def do_rename_chain(self, title):
        self.zyngui.chain_manager.set_chain_title(self.chain.chain_id, title)
        self.post_action()

    def export_chain(self):
        options = {}
        dirs = os.listdir(self.zyngui.state_manager.snapshot_dir)
        dirs.sort()
        for dir in dirs:
            if dir.startswith(".") or not os.path.isdir(f"{self.zyngui.state_manager.snapshot_dir}/{dir}"):
                continue
            options[dir] = [dir, ["Choose folder to store snapshot.", "folder.png"]]
        self.zyngui.screens['option'].config("Select location for export", options, self.name_export)
        self.zyngui.show_screen('option')

    def name_export(self, param1, param2):
        self.export_dir = param1
        self.zyngui.show_keyboard(self.confirm_export_chain, self.chain.get_title())

    def confirm_export_chain(self, title):
        path = f"{self.zyngui.state_manager.snapshot_dir}/{self.export_dir}/{title}.zss"
        if os.path.isfile(path):
            self.zyngui.show_confirm(f"File {path} already exists.\n\nOverwrite?",
                                     self.do_export_chain, path)
        else:
            self.do_export_chain(path)

    def do_export_chain(self, path):
        self.zyngui.state_manager.export_chain(path, self.chain.chain_id)

    def remove_chain(self, params=None):
        self.zyngui.show_confirm("Do you really want to remove this chain?",
                                 self.remove_chain_confirmed)

    def remove_chain_confirmed(self, params=None):
        self.zyngui.chain_manager.remove_chain(self.chain.chain_id)
        if self.parent:
            self.zyngui.show_screen_reset('root')
        else:
            self.zyngui.show_screen_reset('chain_manager')


    def add_processor(self, proc_type):
        if proc_type == "Audio Effect":
            # Try inserting just before mixer processor (pre-fader)
            try:
                slot = self.chain.zynmixer_proc.get_chain_slot()
            except:
                slot = None
        else:
            slot = None
        self.zyngui.modify_chain({
            "chain_id": self.chain.chain_id,
            "type": proc_type,
            "midi_thru": self.chain.midi_chan is not None,
            "audio_thru": proc_type == "Audio Effect",
            "slot": slot
        })

    def remove_all_procs_cb(self, type=None):
        self.state_manager.start_busy("remove_all_procs", "Removing processors")
        for processor in self.chain.get_processors(type):
            if processor.eng_code in ["MI", "MR"]:
                continue
            self.zyngui.chain_manager.remove_processor(self.chain.chain_id, processor)
        zynautoconnect.request_audio_connect(True)
        zynautoconnect.request_midi_connect(True)
        self.state_manager.end_busy("remove_all_procs")
        self.post_action()

    # Audio-FX Chain management

    def audiofx_add(self):
        self.add_processor("Audio Effect")

    def remove_all_audiofx(self):
        self.zyngui.show_confirm("Do you really want to remove all audio effects from this chain?",
                                 self.remove_all_procs_cb, "Audio Effect", autoclose=False)

    # MIDI-FX Chain management

    def midifx_add(self):
        self.add_processor("MIDI Tool")


    def remove_all_midifx(self):
        self.zyngui.show_confirm("Do you really want to remove all MIDI effects from this chain?",
                                 self.remove_all_procs_cb, "MIDI Tool", autoclose=False)

    # Select Path
    def set_select_path(self):
        title = "Chain Options"
        try:
            self.select_path.set(f"{self.chain.get_name()}/{title}")
        except:
            self.select_path.set(title)

# ------------------------------------------------------------------------------
