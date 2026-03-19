#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Fast Menu Grid Class
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


class zynthian_gui_fast_menu(zynthian_gui_selector_grid):
    """
    Fast menu presented as a grid of buttons.
    """
    def __init__(self):
        super().__init__()

        self.columns = 3
        self.title = "Fast Menu"
        self.config = [{
            "title": "Chain\nManager",
            "icon": None,
            "action": self.zyngui.cuia_screen_chain_manager
        }, {
            "title": "Snapshots",
            "icon": "snapshot.png",
            "action": self.zyngui.cuia_screen_snapshot
        }, {
            "title": "ZS3",
            "icon": "zs3.png",
            "action": self.zyngui.cuia_screen_zs3
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
            "icon": None,
            "action": self.zyngui.cuia_screen_admin
        }, {
            "title": "Soundcard\nLevels",
            "icon": "audio.png",
            "action": self.zyngui.cuia_screen_alsa_mixer
        }, {
            "title": "Power",
            "icon": "poweroff.png",
            "action": self.zyngui.cuia_power
         }
    ]

