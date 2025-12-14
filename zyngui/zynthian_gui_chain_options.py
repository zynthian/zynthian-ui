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
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian Chain Options GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_chain_options(zynthian_gui_selector_info):

    def __init__(self):
        super().__init__('Option')
        self.index = 0
        self.chain = self.zyngui.chain_manager.active_chain

    def fill_list(self):
        self.list_data = []

        synth_proc_count = self.chain.get_processor_count("Synth")
        midi_proc_count = self.chain.get_processor_count("MIDI Tool")
        audio_proc_count = max(0, self.chain.get_processor_count("Audio Effect") - 1)

        if not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]) and self.chain.get_processor_count():
            self.list_data.append((self.midi_learn, None, "MIDI Learn",
                                   ["Enter MIDI-learning mode for processor parameters.", "midi_learn.png"]))

        # TODO: Catch signal for Audio Recording status change
        if self.chain.chain_id == 0 and not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
            if self.zyngui.state_manager.audio_recorder.status:
                self.list_data.append(
                    (self.zyngui.state_manager.audio_recorder.toggle_recording, None, "■ Stop Audio Recording", ["Stop audio recording", "audio_recorder.png"]))
            else:
                self.list_data.append(
                    (self.zyngui.state_manager.audio_recorder.toggle_recording, None, "⬤ Start Audio Recording", ["Start audio recording", "audio_recorder.png"]))

        self.list_data.append((self.add_chain, None, "Insert new chain",
                               ["Create a new chain.",
                                "midi_instrument.png"]))

        if self.chain.chain_id != 0:
            self.list_data.append((self.export_chain, None, "Export chain as snapshot...",
                                   ["Save the selected chain as a snapshot which may then be imported into another snapshot.", "snapshot_chains.png"]))
            if synth_proc_count * midi_proc_count + audio_proc_count == 0:
                self.list_data.append((self.remove_chain, None, "Remove chain",
                                       ["Remove this chain and all its processors.", "delete_chains.png"]))
            else:
                self.list_data.append((self.remove_cb, None, "Remove...",
                                       ["Remove chain or processors.", "delete_chains.png"]))
        elif audio_proc_count > 0:
            self.list_data.append((self.remove_all_audiofx, None, "Remove all Audio-FX",
                                   ["Remove all audio-FX processors in this chain.", "delete_audio_processors.png"]))

        self.list_data.append((self.rename_chain, None, "Rename chain",
                               ["Rename the chain. Clear name to reset to default name.", "rename.png"]))
        if self.chain.chain_id:
            if len(self.zyngui.chain_manager.ordered_chain_ids) > 1:
                self.list_data.append((self.move_chain, None, "Move chain",
                                       ["Reposition the chain in the mixer view.", "move_left_right.png"]))
        super().fill_list()

    def fill_listbox(self):
        super().fill_listbox()
        for i, val in enumerate(self.list_data):
            if val[0] == None:
                self.listbox.itemconfig(
                    i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})

    def build_view(self):
        self.chain = self.zyngui.chain_manager.active_chain
        if self.chain is not None:
            super().build_view()
            if self.index >= len(self.list_data):
                self.index = len(self.list_data) - 1
            return True
        else:
            return False

    def select_action(self, i, t='S'):
        self.index = i
        if self.list_data[i][0] is None:
            pass
        elif self.list_data[i][1] is None:
            self.list_data[i][0]()
        else:
            self.list_data[i][0](self.list_data[i][1], t)

    def midi_learn(self):
        options = {}
        options['Enter MIDI-learn'] = "enable_midi_learn"
        options['Enter Global MIDI-learn'] = "enable_global_midi_learn"
        options['Clear chain MIDI-learn'] = "clean_chain"
        self.zyngui.screens['option'].config(
            "MIDI-learn", options, self.midi_learn_menu_cb)
        self.zyngui.show_screen('option')

    def midi_learn_menu_cb(self, options, params):
        if params == 'enable_midi_learn':
            self.zyngui.replace_screen("control")
            self.zyngui.cuia_toggle_midi_learn()
        elif params == 'enable_global_midi_learn':
            self.zyngui.replace_screen("control")
            self.zyngui.cuia_toggle_midi_learn()
            self.zyngui.cuia_toggle_midi_learn()
        elif params == 'clean_chain':
            self.zyngui.show_confirm(
                f"Do you want to clean MIDI-learn for ALL controls in ALL processors within chain {self.chain.chain_id:02d}?", self.zyngui.chain_manager.clean_midi_learn, self.chain.chain_id)

    def move_chain(self):
        if "chain_manager" in self.zyngui.screen_history:
            self.zyngui.screens["chain_manager"].moving_chain = True
            self.zyngui.show_screen_reset('chain_manager')
        else:
            self.zyngui.screens["audio_mixer"].moving_chain = True
            self.zyngui.show_screen_reset('root')

    def rename_chain(self):
        self.zyngui.show_keyboard(self.do_rename_chain, self.chain.title)

    def do_rename_chain(self, title):
        self.chain.title = title
        self.zyngui.show_screen_reset('root')

    def export_chain(self):
        options = {}
        dirs = os.listdir(self.zyngui.state_manager.snapshot_dir)
        dirs.sort()
        for dir in dirs:
            if dir.startswith(".") or not os.path.isdir(f"{self.zyngui.state_manager.snapshot_dir}/{dir}"):
                continue
            options[dir] = [dir, ["Choose folder to store snapshot.", "folder.png"]]
        self.zyngui.screens['option'].config(
            "Select location for export", options, self.name_export)
        self.zyngui.show_screen('option')

    def name_export(self, param1, param2):
        self.export_dir = param1
        self.zyngui.show_keyboard(self.confirm_export_chain, self.chain.get_title())

    def confirm_export_chain(self, title):
        path = f"{self.zyngui.state_manager.snapshot_dir}/{self.export_dir}/{title}.zss"
        if os.path.isfile(path):
            self.zyngui.show_confirm(f"File {path} already exists.\n\nOverwrite?", self.do_export_chain, path)
        else:
            self.do_export_chain(path)

    def do_export_chain(self, path):
        self.zyngui.state_manager.export_chain(path, self.chain.chain_id)

    # Remove submenu

    def remove_cb(self):
        options = {}
        if self.chain.synth_slots and self.chain.get_processor_count("MIDI Tool"):
            options['Remove All MIDI-FXs'] = "midifx"
        if self.chain.get_processor_count("Audio Effect") > 1:
            options['Remove All Audio-FXs'] = "audiofx"
        if self.chain.chain_id != 0:
            options['Remove Chain'] = "chain"
        self.zyngui.screens['option'].config(
            "Remove...", options, self.remove_all_cb)
        self.zyngui.show_screen('option')

    def remove_all_cb(self, options, params):
        if params == 'midifx':
            self.remove_all_midifx()
        elif params == 'audiofx':
            self.remove_all_audiofx()
        elif params == 'chain':
            self.remove_chain()

    def remove_chain(self, params=None):
        self.zyngui.show_confirm(
            "Do you really want to remove this chain?", self.chain_remove_confirmed)

    def chain_remove_confirmed(self, params=None):
        self.zyngui.chain_manager.remove_chain(self.chain.chain_id)
        self.zyngui.show_screen_reset('root')

    def add_chain(self, params=None):
        config = []
        config.append({
            "title": "Synth",
            "icon": "midi_instrument.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "MIDI Synth", "midi_thru": False, "audio_thru": False}]
        })
        config.append({
            "title": "Audio",
            "icon": "microphone.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "Audio Effect", "midi_thru": False, "audio_thru": True}]
        })
        config.append({
            "title": "Clip",
            "icon": "audio.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "Audio Generator", "midi_thru": False, "audio_thru": False, "engine": "CL", "midi_chan": None}]
        })
        config.append({
            "title": "Mixbus",
            "icon": "effects_loop.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "Audio Effect", "midi_thru": False, "audio_thru": True, "mixbus": True}]
        })
        config.append({
            "title": "MIDI",
            "icon": "midi_logo.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "MIDI Tool", "midi_thru": True, "audio_thru": False}]
        })
        config.append({
            "title": "MIDI\n+\nAudio",
            "icon": "midi_audio.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "Audio Effect", "midi_thru": True, "audio_thru": True}]
        })
        config.append({
            "title": "Audio Generator",
            "icon": "audio_generator.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "Audio Generator", "midi_thru": False, "audio_thru": False}]
        })
        config.append({
            "title": "Special",
            "icon": "special_chain.png",
            "action": self.zyngui.modify_chain,
            "action_params": [{"type": "Special", "midi_thru": True, "audio_thru": True}]
        })
        self.zyngui.screens["selector_grid"].setup(config)
        self.zyngui.show_screen("selector_grid")

    # FX-Chain management

    def audiofx_add(self):
        self.zyngui.modify_chain(
            {"type": "Audio Effect", "chain_id": self.chain.chain_id})

    def remove_all_audiofx(self):
        self.zyngui.show_confirm(
            "Do you really want to remove all audio effects from this chain?", self.remove_all_procs_cb, "Audio Effect")

    def remove_all_procs_cb(self, type=None):
        for processor in self.chain.get_processors(type):
            if processor.eng_code in ["MI", "MR"]:
                continue
            self.zyngui.chain_manager.remove_processor(
                self.chain.chain_id, processor)
        self.build_view()
        self.show()

    # MIDI-Chain management

    def midifx_add(self):
        self.zyngui.modify_chain(
            {"type": "MIDI Tool", "chain_id": self.chain.chain_id})

    def remove_all_midifx(self):
        self.zyngui.show_confirm(
            "Do you really want to remove all MIDI effects from this chain?", self.remove_all_procs_cb, "MIDI Tool")

    # Select Path
    def set_select_path(self):
        try:
            self.select_path.set(f"Chain Options: {self.chain.get_name()}")
        except:
            self.select_path.set("Chain Options")

# ------------------------------------------------------------------------------
