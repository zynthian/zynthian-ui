#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI TTS Class
#
# Copyright (C) 2026 Brian Walton <riban@zynthian.org>
#                    Fernando Moyano <jofemodo@zynthian.org>
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
from zyngine.zynthian_tts import zynthian_tts
from zyngine import zynsigman
import zynconf

# -------------------------------------------------------------------------------
# Zynthian TTS GUI Class
# Integrates zynthian_gui with TTS
# -------------------------------------------------------------------------------

class zynthian_gui_tts():
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.chain_manager = state_manager.chain_manager
        self._tts = zynthian_tts()

        # Auto configure Narrator button (temporary)
        self.tts_zynswitch_index = -1
        for i, cuias in enumerate(zynthian_gui_config.custom_switch_ui_actions):
            if cuias["L"] == "TTS_TOGGLE_ENABLE":
                self.tts_zynswitch_index = i
                break
        if self.tts_zynswitch_index >= 0:
            self.original_wiring_short = zynthian_gui_config.custom_switch_ui_actions[self.tts_zynswitch_index]["S"]
            zynthian_gui_config.custom_switch_ui_actions[self.tts_zynswitch_index]["S"] = "TTS_TOGGLE_PLAYBACK"

        zynsigman.register(zynsigman.S_STATE_MAN, zynsigman.SS_BUSY, self.busy_cb)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, self.active_chain_cb)
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_SELECT_PHRASE, self.seq_select_phrase_cb)
        zynsigman.register_queued(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE, self.zynmixer_set_value_cb)
        zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.audio_rec_cb)
        zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_MIDI_RECORDER_STATE, self.midi_rec_cb)

    def close(self):
        """ Destructor - clean-up """

        # Restore original wiring
        if self.tts_zynswitch_index >= 0:
            zynthian_gui_config.custom_switch_ui_actions[self.tts_zynswitch_index]["S"] = self.original_wiring_short

        zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, self.active_chain_cb)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_SELECT_PHRASE, self.seq_select_phrase_cb)
        zynsigman.unregister(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE, self.zynmixer_set_value_cb)
        zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_BUSY, self.busy_cb)
        zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.audio_rec_cb)
        zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_MIDI_RECORDER_STATE, self.midi_rec_cb)
        self._tts.close()
        self._tts = None

    def announce(self, text: str, replace: bool=True, urgent: bool=False, interrupt=True):
        """ Announce a TTS message
        Args:
            text: Text to announce
            replace: True to clear queue and replace with this text
            urgent: True to play next. False to append to end of queue.
            interrupt: True to interrupt currently playing message. False to finish current announcement.
        """

        try:
            self._tts.append(text, replace, urgent, interrupt)
        except Exception as e:
            logging.warning(f"TTS Error: {e}")

    def get_voice_name(self):
        """ Get the voice
            Returns: voice
        """

        voices = zynthian_tts.get_voices()
        try:
            return voices[self._tts.voice]
        except:
            logging.error("Failed to get TTS voice")
        return ""


    # ----------------------------------
    # Signal event handlers
    # ----------------------------------

    def seq_select_phrase_cb(self, phrase):
        self._tts.append(f"Phrase {phrase + 1}")

    def active_chain_cb(self, active_chain_id):
        chain = self.chain_manager.get_chain(active_chain_id)
        if not chain:
            return
        mute = ""
        if chain.zynmixer_proc:
            if chain.zynmixer_proc.controllers_dict["mute"].value:
                mute = "Mute"
            elif chain.zynmixer_proc.controllers_dict["solo"].value:
                mute = "Solo"
        if chain.chain_id:
            idx = self.chain_manager.get_chain_index(active_chain_id) + 1
            self._tts.append(f"Chain {idx}: {mute}")
        else:
            self._tts.append(f"Main chain:{mute}")

    def zynmixer_set_value_cb(self, mixbus, chan, symbol, value):
        pass
        #TODO "Should we handle zynmixer value changes for TTS here?"

    def audio_rec_cb(self, state):
        self.announce(f"Audio recorder {'started' if state else 'stopped'}")

    def midi_rec_cb(self, state):
        self.announce(f"MIDI recorder {'started' if state else 'stopped'}")

    def busy_cb(self, state):
        self._tts.set_busy(state)

# -------------------------------------------------------
# TTS Screen Class
# Provides TTS configuration view
# -------------------------------------------------------

class zynthian_gui_tts_screen(zynthian_gui_selector_info):

    def __init__(self):
        super().__init__('Action')
        self.title = self.tts_title = "Narrator options"
        self.voices = zynthian_tts.get_voices()

    def fill_list(self):

        self.list_data = []

        if self.zyngui.tts:
            self.list_data.append((self.toggle_tts, 0, f"\u2612 Enable narrator feedback",
                                   ["Toggle narrator enable", None]))
            self.list_data.append((self.set_voice, 0, f"Voice: {self.zyngui.tts.get_voice_name().split(':')[0]}",
                                   ["Select the voice", None]))
            self.list_data.append((self.set_speed, 0, f"Speed: {zynthian_gui_config.tts_speed:.1f}",
                                   ["Adjust narrator speed", None]))
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
            self.list_data.append((self.toggle_tts, 1, f"\u2610 Enable narrator feedback",
                ["Toggle narrator enable", None]))
        super().fill_list()

    def select_action(self, i, t='S'):
        if self.list_data[i][0]:
            self.list_data[i][0]()

    def toggle_tts(self):
        self.zyngui.cuia_tts_toggle_enable()

    def set_voice(self):
        self.voices = zynthian_tts.get_voices()
        try:
            voice = self.voices[self.zyngui.tts._tts.voice]
        except:
            voice = self.voices[0]
        self.enable_param_editor(self, "Voice", {
            'labels': list(self.voices.values()),
            'values': list(self.voices.keys()),
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
        self.zyngui.tts._tts.set_soundcard(soundcard)
        self.update_list()

    def hotplug(self):
        self.zyngui.screens("admin").hotplug_audio_menu()

    def set_select_path(self):
        self.select_path.set("Narrator options")
        self.update_list()

    def send_controller_value(self, zctrl):
        match zctrl.symbol:
            case "Voice":
                self.zyngui.tts._tts.set_voice(zctrl.value)
                self.update_list()
            case "Speed":
                self.zyngui.tts._tts.set_speed(zctrl.value)
                self.update_list()
            case "Volume":
                self.zyngui.tts._tts.set_volume(zctrl.value)
                self.update_list()
