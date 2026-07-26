#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Add Chain Selector Grid Class
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


class zynthian_gui_add_chain(zynthian_gui_selector_grid):
    """
    Add Chain Selector presented as a grid of buttons.
    """
    def __init__(self):
        super().__init__()

        self.columns = 3
        self.pos = 0
        self.title = "Add Chain..."
        self.reset_config()

    def reset_config(self):
        self.config = [{
                "title": "Instrument",
                "icon": "midi_instrument.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "MIDI Synth", "midi_thru": False, "audio_thru": False, "pos": self.pos}]
            }, {
                "title": "Audio Input",
                "icon": "microphone.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "Audio Effect", "midi_thru": False, "audio_thru": True, "pos": self.pos}]
            }, {
                "title": "Clip Launcher",
                "icon": "zynthian_logo.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "Audio Generator", "midi_thru": False, "audio_thru": False, "engine": "CL", "midi_chan": None, "pos": self.pos}]
            }, {
                "title": "MIDI",
                "icon": "midi_logo.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "MIDI Tool", "midi_thru": True, "audio_thru": False, "pos": self.pos}]
            }, {
                "title": "MIDI\n+\nAudio",
                "icon": "midi_audio.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "Audio Effect", "midi_thru": True, "audio_thru": True, "pos": self.pos}]
            }, {
                "title": "Audio Generator",
                "icon": "audio_generator.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "Audio Generator", "midi_thru": False, "audio_thru": False, "pos": self.pos}]
            }, {
                "title": "Special",
                "icon": "special_chain.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "Special", "midi_thru": True, "audio_thru": True, "pos": self.pos}]
            }, {
                "title": "Mixbus",
                "icon": "effects_loop.png",
                "action": self.zyngui.modify_chain,
                "action_params": [{"type": "Audio Effect", "midi_thru": False, "audio_thru": True, "mixbus": True, "pos": self.pos}]
            }]
        if self.zyngui.chain_manager.get_processor_count(eng_code="CL") > 15:
            self.config[2] = {
                "title": "Clip Launcher\nMax. 16 reached!",
                "icon": "audio.png",
                "action": None
            }

    # Setup position and reset
    def set_chain_pos(self, pos):
        self.pos = pos

    def build_view(self):
        self.reset_config()
        return super().build_view()
