#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Main Menu Grid Class
#
# Copyright (C) 2025 Fernando Moyano <jofemodo@zynthian.org>
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

from zyngui.zynthian_gui_selector_grid import zynthian_gui_selector_grid


class zynthian_gui_main_menu(zynthian_gui_selector_grid):
    """
    Fast menu presented as a grid of buttons.
    """
    def __init__(self):
        super().__init__()

        self.columns = 3
        self.title = "Main Menu"
        self.config = [{
            "title": "Add\nChain",
            "icon": "add_chain.png",
            "action": self.zyngui.cuia_add_chain
        }, {
            "title": "Snapshots",
            "icon": "snapshot.png",
            "action": self.zyngui.cuia_screen_snapshot
        }, {
            "title": "Clean",
            "icon": "delete.png",
            "action": self.clean
        }, {
            "title": "Tempo",
            "icon": "metronome.png",
            "action": self.zyngui.cuia_tempo
        }, {
            "title": "Audio\nPlayer",
            "icon": "audio_recorder.png",
            "action": self.zyngui.cuia_screen_audio_player
        }, {
            "title": "MIDI\nPlayer",
            "icon": "midi_recorder.png",
            "action": self.zyngui.cuia_screen_midi_recorder
        }, {
            "title": "Admin",
            "icon": "settings.png",
            "action": self.zyngui.cuia_screen_admin
        }, {
            "title": "Audio\nLevels",
            "icon": "audio_options.png",
            "action": self.zyngui.cuia_screen_alsa_mixer
        }, {
            "title": "Power",
            "icon": "poweroff.png",
            "action": self.zyngui.cuia_power
         }
    ]

    def clean(self):
        self.zyngui.screens["grid_sel"].setup("Confirm Clean", [
                {"icon": "delete_chains.png", "title": "Clean All Chains", "action": self.clean_chains_confirmed},
                {"icon": "delete_sequences.png", "title": "Clean All Sequences", "action": self.clean_sequences_confirmed},
                {"icon": "delete_all.png", "title": "Clean All Chains & Sequences", "action": self.clean_all_confirmed},
                None, None, None,
                {"icon": "cancel.png", "title": "Cancel", "action": self.zyngui.close_screen}
        ])
        self.zyngui.screens["grid_sel"].selected_node = 2
        self.zyngui.show_screen("grid_sel")

    def clean_chains_confirmed(self, params=None):
        self.zyngui.clean_chains()
        self.zyngui.show_screen_reset('mixer')

    def clean_sequences_confirmed(self, params=None):
        self.zyngui.clean_sequences()
        self.zyngui.show_screen_reset('launcher')

    def clean_all_confirmed(self, params=None):
        self.zyngui.clean_all()
        self.zyngui.show_screen_reset('root')
