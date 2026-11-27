# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_audio2midi)
#
# zynthian_engine implementation for the Audio to MIDI converter (global processor)
#
# Copyright (C) 2026 Brian Walton <riban@zynthian.org>
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

import os
import ctypes
import logging

from zyngine.zynthian_engine import zynthian_engine

# ------------------------------------------------------------------------------
# Audio to MIDI Engine Class
# ------------------------------------------------------------------------------

LIB_PATH = "/zynthian/zynthian-ui/zynlibs/zynaudio2midi/build/libzynaudio2midi.so"
JACK_CLIENT_NAME = "audio2midi"  # Ports: "input" (audio), "midi_out" (MIDI)


class zynthian_engine_audio2midi(zynthian_engine):
    """Converts the notes played into an audio input to MIDI note on/off and optional pitch bend (channel 1).

    The converter (JACK client) only runs while enabled (start/stop), so it costs nothing when disabled.
    Its MIDI output is a MIDI input device, like a hardware port.
    """

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    _ctrls = [
        ["onset", {
            "name": "onset threshold",
            "short_name": "onset",
            "value_min": -80,
            "value_max": 0,
            "value_default": -40,
            "is_integer": True
        }],
        ["release", {
            "name": "release threshold",
            "short_name": "release",
            "value_min": -90,
            "value_max": 0,
            "value_default": -50,
            "is_integer": True
        }],
        ["polyphonic", {
            "name": "mode",
            "labels": ["mono", "poly"],
            "ticks": [0, 1],
            "value_min": 0,
            "value_max": 1,
            "value_default": 0
        }],
        ["noise", {
            "name": "noise filter",
            "short_name": "noise filter",
            "value_min": 0,
            "value_max": 100,
            "value_default": 50,
            "is_integer": True
        }],
        ["pitchbend", {
            "name": "pitch bend",
            "labels": ["off", "on"],
            "ticks": [0, 1],
            "value_min": 0,
            "value_max": 1,
            "value_default": 0
        }],
        ["bend_range", {
            "name": "bend range",
            "value_min": 1,
            "value_max": 24,
            "value_default": 2,
            "is_integer": True
        }]
    ]

    _ctrl_screens = [
        ["Audio ➔ MIDI", ["onset", "release", "polyphonic", "noise"]],
        ["Pitch bend", ["pitchbend", "bend_range"]]
    ]

    # ----------------------------------------------------------------------------
    # ZynAPI variables
    # ----------------------------------------------------------------------------

    zynapi_instance = None

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    def __init__(self, state_manager=None, proc=None):
        super().__init__(state_manager)

        self.type = "Audio to MIDI"
        self.name = "Audio ➔ MIDI"
        self.nickname = "AM"
        self.processor = proc

        # Help page of the control view (the default would be named after the processor's name)
        help_dir = os.environ.get('ZYNTHIAN_HELP_DIR', "/zynthian/zynthian-help")
        self.custom_gui_help_fpath = f"{help_dir}/common/audio2midi.html"

        self.audio_out = []
        self.options['midi_chan'] = False
        self.options['replace'] = False

        self.lib = None
        try:
            self.lib = ctypes.cdll.LoadLibrary(LIB_PATH)
            self.lib.start.restype = ctypes.c_uint8
            self.lib.isRunning.restype = ctypes.c_uint8
            for fn in ("setOnsetThreshold", "setReleaseThreshold", "setNoiseFilter", "setBendRange"):
                getattr(self.lib, fn).argtypes = [ctypes.c_float]
            for fn in ("setPolyphonic", "setPitchBend"):
                getattr(self.lib, fn).argtypes = [ctypes.c_uint8]
        except Exception as e:
            logging.error(f"Can't load audio to MIDI library => {e}")
            self.lib = None

    def stop(self):
        self.stop_converter()
        super().stop()

    # ---------------------------------------------------------------------------
    # Converter (JACK client) control
    # ---------------------------------------------------------------------------

    def start_converter(self):
        """Start the converter. Returns True on success."""

        if self.lib is None:
            return False
        # Apply the current controller values before the first audio is processed
        for processor in self.processors:
            for zctrl in processor.controllers_dict.values():
                self.send_controller_value(zctrl)
        if self.lib.start():
            return True
        logging.error("Can't start audio to MIDI converter")
        return False

    def stop_converter(self):
        if self.lib is not None:
            self.lib.stop()

    def is_running(self):
        return self.lib is not None and bool(self.lib.isRunning())

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def get_path(self, processor):
        return self.name

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
        if processor is None:
            return {}
        zctrls = super().get_controllers_dict(processor)
        for zctrl in zctrls.values():
            self.send_controller_value(zctrl)
        return zctrls

    def send_controller_value(self, zctrl):
        if self.lib is None:
            return
        if zctrl.symbol == "onset":
            self.lib.setOnsetThreshold(zctrl.value)
        elif zctrl.symbol == "release":
            self.lib.setReleaseThreshold(zctrl.value)
        elif zctrl.symbol == "polyphonic":
            self.lib.setPolyphonic(1 if zctrl.value else 0)
        elif zctrl.symbol == "noise":
            self.lib.setNoiseFilter(zctrl.value)
        elif zctrl.symbol == "pitchbend":
            self.lib.setPitchBend(1 if zctrl.value else 0)
        elif zctrl.symbol == "bend_range":
            self.lib.setBendRange(zctrl.value)


# ******************************************************************************
