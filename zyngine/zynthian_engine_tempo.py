# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_tempo)
#
# zynthian_engine implementation for Tempo control
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
from time import monotonic
from collections import deque

from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_engine import zynthian_engine
from zyngine.zynthian_controller import zynthian_controller

# ------------------------------------------------------------------------------
# Tempo Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_tempo(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    _ctrl_screens = [
        ["Tempo", ["bpm", "metro_enable", "metro_volume"]]
    ]

    # ----------------------------------------------------------------------------
    # ZynAPI variables
    # ----------------------------------------------------------------------------

    zynapi_instance = None

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    NUM_TAPS = 4

    def __init__(self, state_manager=None, proc=None):
        super().__init__(state_manager)

        self.type = "Tempo"
        self.name = "Tempo"
        self.nickname = "TP"
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_tempo.py"
        self.processor = proc

        self.audio_out = []
        self.options['midi_chan'] = False
        self.options['replace'] = False

        self.zctrls = None

        self.tap_buf = None
        self.last_tap_ts = 0

        self.buttonbar_config = [
            ("toggle_audio_play", "Play\nAudio"),
            ("toggle_audio_record", "Record\nAudio"),
            ("toggle_midi_play", "Play\nMIDI"),
            ("toggle_midi_record", "Record\nMIDI")
        ]

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def get_path(self, processor):
        return self.name

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    # ----------------------------------------------------------------------------
    # Bank Managament
    # ----------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return [("", None, "", None)]

    def set_bank(self, processor, bank):
        return True

    # ----------------------------------------------------------------------------
    # Preset Managament
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank, processor=None):
        return [("", None, "", None)]

    def set_preset(self, processor, preset, preload=False):
        return True

    def cmp_presets(self, preset1, preset2):
        return True

    # ----------------------------------------------------------------------------
    # Controllers Managament
    # ----------------------------------------------------------------------------

    def get_controllers_dict(self, processor=None, ctrl_list=None):
        if processor:
            if not processor.controllers_dict:
                processor.controllers_dict = {
                    "bpm": self.state_manager.zynseq.zctrl_tempo,
                    "metro_enable": self.state_manager.zynseq.zctrl_metro_enable,
                    "metro_volume": self.state_manager.zynseq.zctrl_metro_volume
                }
            return processor.controllers_dict
        return  {
            "bpm": self.state_manager.zynseq.zctrl_tempo,
            "metro_enable": self.state_manager.zynseq.zctrl_metro_enable,
            "metro_volume": self.state_manager.zynseq.zctrl_metro_volume
        }

    def send_controller_value(self, zctrl):
        pass

    # ----------------------------------------------------------------------------
    # Special
    # ----------------------------------------------------------------------------

    def tap(self):
        now = monotonic()
        if self.state_manager.zynseq.libseq.getClockSource() == 2:
            lib_zyncore.zynstep_send_clock()
            logging.debug("TAP SYNCING (BEAT + TEMPO)!")
        else:
            tap_dur = now - self.last_tap_ts
            self.last_tap_ts = now
            if tap_dur < 0.14285 or tap_dur > 2:
                # Too slow or too fast so reset
                self.tap_buf = deque(maxlen=self.NUM_TAPS)
            else:
                self.tap_buf.append(tap_dur)
                logging.debug(f"TAP TEMPO BUFFER: {self.tap_buf}")
                bpm = 60 * len(self.tap_buf) / sum(self.tap_buf)
                self.state_manager.zynseq.set_tempo(bpm)
                logging.debug(f"SETTING TAP TEMPO BPM: {bpm}")

# ******************************************************************************
