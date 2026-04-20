#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI TTS Class
#
# Copyright (C) 2026 Fernando Moyano <jofemodo@zynthian.org>
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
import zynautoconnect
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# -------------------------------------------------------------------------------
# Zynthian TTS GUI Class
# -------------------------------------------------------------------------------

class zynthian_gui_tts(zynthian_gui_selector_info):

    def __init__(self):
        super().__init__('Action')
        self.title = "Narration options"
        self.tts = self.zyngui.state_manager._tts

    def fill_list(self):

        self.list_data = []

        if self.tts.is_running():
            self.list_data.append((self.toggle_tts, 0, f"\u2612 Enable Narration feedback",
                                   ["Toggle narration enable", None]))
            self.list_data.append((self.set_voice, 0, f"Voice: {self.tts.get_voice_name().split(':')[0]}",
                                   ["Select the Voice", None]))
            self.list_data.append((self.set_speed, 0, f"Speed: {zynthian_gui_config.tts_speed:.1f}",
                                   ["Adjust speed of narration", None]))
            self.list_data.append((self.set_volume, 0, f"Volume: {zynthian_gui_config.tts_volume}%"))
            self.list_data.append((None, 0, "Soundcard"))
            soundcards = zynautoconnect.get_alsa_audio_devices(True, "tts")
            if soundcards:
                for soundcard in soundcards:
                    if zynthian_gui_config.tts_soundcard == soundcard:
                        self.list_data.append((self.set_soundcard, soundcard, f"\u2612 {soundcard}",
                            ["Select soundcard for narrator output", None]))
                    else:
                        self.list_data.append((self.set_soundcard, soundcard, f"\u2610 {soundcard}",
                            ["Select soundcard for narrator output", None]))
            else:
                self.list_data.append((self.hotplug, 0, "No soundcards - check hotplug USB"))
        else:
            self.list_data.append((self.toggle_tts, 1, f"\u2610 Enable Narration feedback",
                ["Toggle narration enable", None]))
        super().fill_list()

    def select_action(self, i, t='S'):
        if self.list_data[i][0]:
            self.list_data[i][0]()
        self.update_list()

    def toggle_tts(self):
        if self.tts.is_running():
            self.tts.disable()
        else:
            self.tts.enable()

    def set_voice(self):
        voices = self.tts.voices
        voice = self.tts.get_voice_name()
        self.enable_param_editor(self, "Voice", {
            'labels': list(voices.values()),
            'values': list(voices.keys()),
            'value': voice})

    def set_speed(self):
        self.enable_param_editor(self, "Speed", {
            'value_min': 0.6,
            'value_max': 2.0,
            'nudge_factor': 0.2,
            'value': zynthian_gui_config.tts_speed})

    def set_volume(self):
        self.enable_param_editor(self, "Volume", {
            'value_min': 0,
            'value_max': 100,
            'value': zynthian_gui_config.tts_volume})

    def set_soundcard(self):
        soundcard = self.list_data[self.index][1]
        self.tts.set_soundcard(soundcard)
        self.update_list()

    def hotplug(self):
        self.zyngui.screens("admin").hotplug_audio_menu()

    def set_select_path(self):
        self.select_path.set("Narrator options")
        self.update_list()

    def send_controller_value(self, zctrl):
        match zctrl.symbol:
            case "Voice":
                self.tts.set_voice(zctrl.value)
                self.update_list()
            case "Speed":
                self.tts.set_speed(zctrl.value)
                self.update_list()
            case "Volume":
                self.tts.set_volume(zctrl.value)
                self.update_list()
