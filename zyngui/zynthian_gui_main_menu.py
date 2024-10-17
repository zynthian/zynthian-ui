#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Main Menu Class
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

import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian App Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_main_menu(zynthian_gui_selector):

    def __init__(self):
        super().__init__('Menu', True)

    def fill_list(self):
        self.list_data = []

        # Chain & Sequence Management
        self.list_data.append((None, 0, "> ADD CHAIN"))
        self.list_data.append(
            (self.add_synth_chain, 0, "Add Instrument Chain"))
        self.list_data.append((self.add_audiofx_chain, 0, "Add Audio Chain"))
        self.list_data.append((self.add_midifx_chain, 0, "Add MIDI Chain"))
        self.list_data.append(
            (self.add_midiaudiofx_chain, 0, "Add MIDI+Audio Chain"))
        self.list_data.append(
            (self.add_generator_chain, 0, "Add Audio Generator Chain"))
        self.list_data.append((self.add_special_chain, 0, "Add Special Chain"))

        self.list_data.append((None, 0, "> REMOVE"))
        self.list_data.append((self.remove_sequences, 0, "Remove Sequences"))
        self.list_data.append((self.remove_chains, 0, "Remove Chains"))
        self.list_data.append((self.remove_all, 0, "Remove All"))

        # Add list of Apps
        self.list_data.append((None, 0, "> MAIN"))
        self.list_data.append((self.snapshots, 0, "Snapshots"))
        self.list_data.append((self.step_sequencer, 0, "Sequencer"))
        self.list_data.append((self.audio_recorder, 0, "Audio Recorder"))
        self.list_data.append((self.midi_recorder, 0, "MIDI Recorder"))
        self.list_data.append((self.tempo_settings, 0, "Tempo Settings"))
        self.list_data.append((self.audio_levels, 0, "Audio Levels"))
        self.list_data.append((self.audio_mixer_learn, 0, "Mixer Learn"))

        # Add list of System / configuration views
        self.list_data.append((None, 0, "> SYSTEM"))
        self.list_data.append((self.admin, 0, "Admin"))
        self.list_data.append(
            (self.all_sounds_off, 0, "PANIC! All Sounds Off"))

        super().fill_list()

    def select_action(self, i, t='S'):
        if self.list_data[i][0]:
            self.last_action = self.list_data[i][0]
            self.last_action(t)

    def add_synth_chain(self, t='S'):
        self.zyngui.modify_chain(
            {"type": "MIDI Synth", "midi_thru": False, "audio_thru": False})

    def add_audiofx_chain(self, t='S'):
        self.zyngui.modify_chain(
            {"type": "Audio Effect", "midi_thru": False, "audio_thru": True})

    def add_midifx_chain(self, t='S'):
        self.zyngui.modify_chain(
            {"type": "MIDI Tool", "midi_thru": True, "audio_thru": False})

    def add_midiaudiofx_chain(self, t='S'):
        self.zyngui.modify_chain(
            {"type": "Audio Effect", "midi_thru": True, "audio_thru": True})

    def add_generator_chain(self, t='S'):
        self.zyngui.modify_chain(
            {"type": "Audio Generator", "midi_thru": False, "audio_thru": False})

    def add_special_chain(self, t='S'):
        self.zyngui.modify_chain(
            {"type": "Special", "midi_thru": True, "audio_thru": True})

    def snapshots(self, t='S'):
        logging.info("Snapshots")
        self.zyngui.show_screen("snapshot")

    def remove_all(self, t='S'):
        self.zyngui.show_confirm(
            "Do you really want to remove ALL chains & sequences?", self.remove_all_confirmed)

    def remove_all_confirmed(self, params=None):
        self.index = 0
        self.zyngui.clean_all()

    def remove_chains(self, t='S'):
        self.zyngui.show_confirm(
            "Do you really want to remove ALL chains?", self.remove_chains_confirmed)

    def remove_chains_confirmed(self, params=None):
        self.index = 0
        self.zyngui.clean_chains()

    def remove_sequences(self, t='S'):
        self.zyngui.show_confirm(
            "Do you really want to remove ALL sequences?", self.remove_sequences_confirmed)

    def remove_sequences_confirmed(self, params=None):
        self.index = 0
        self.zyngui.clean_sequences()

    def step_sequencer(self, t='S'):
        logging.info("Step Sequencer")
        self.zyngui.show_screen('zynpad')

    def audio_recorder(self, t='S'):
        logging.info("Audio Recorder/Player")
        self.zyngui.show_screen("audio_player")

    def midi_recorder(self, t='S'):
        logging.info("MIDI Recorder/Player")
        self.zyngui.show_screen("midi_recorder")

    def audio_mixer_learn(self, t='S'):
        logging.info("Audio Mixer Learn")
        self.zyngui.screens["audio_mixer"].midi_learn_menu()

    def audio_levels(self, t='S'):
        logging.info("Audio Levels")
        self.zyngui.show_screen("alsa_mixer")

    def tempo_settings(self, t='S'):
        logging.info("Tempo Settings")
        self.zyngui.show_screen("tempo")

    def admin(self, t='S'):
        logging.info("Admin")
        self.zyngui.show_screen("admin")

    def all_sounds_off(self, t='S'):
        logging.info("All Sounds Off")
        self.zyngui.callable_ui_action("all_sounds_off")

    def set_select_path(self):
        self.select_path.set("Main")

# ------------------------------------------------------------------------------
