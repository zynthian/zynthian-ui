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

import zynautoconnect
from zyngine.zynthian_engine import zynthian_engine

# ------------------------------------------------------------------------------
# Audio to MIDI Engine Class
# ------------------------------------------------------------------------------

LIB_PATH = "/zynthian/zynthian-ui/zynlibs/zynaudio2midi/build/libzynaudio2midi.so"
JACK_CLIENT_NAME = "audio2midi"  # Ports: "input", "input_2" (audio), "midi_out", "midi_out_2" (MIDI)
NUM_OUTPUTS = 2
AUDIO_IN_SYMBOLS = ("audio_in", "audio_in_2")  # Audio input controller of each channel
DETECTION_SYMBOLS = ("onset", "release", "noise")  # Detection settings of channel 1 (channel 2: with "_2" suffix)


class zynthian_engine_audio2midi(zynthian_engine):
    """Converts the notes played into an audio input to MIDI note on/off and optional pitch bend (channel 1).

    The converter (JACK client) always runs but only analyses what is used: an output routed to a chain (active),
    fed by a connected audio input. It has 2 channels: converter input 1 feeds output 1, input 2 feeds output 2.
    A channel without an input sends nothing. When both channels use the same audio input with the same detection
    settings, it is analysed once (one detector feeds both outputs).
    Its MIDI outputs are MIDI input devices, like hardware ports. Each output has its own mode (mono / poly,
    pitch bend). Each channel has an audio input controller: the physical audio input of its converter input.
    The control view shows the pages of one channel (set_channel).
    """

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    # Each channel has its own detection parameters, audio input and output mode. Output 1 defaults to pitch bend
    # (e.g. lead synths), output 2 to none (e.g. pianos).
    _ctrls = []
    for _output, _bend in ((1, 1), (2, 0)):
        _sfx = "" if _output == 1 else f"_{_output}"
        _ctrls += [
            # Detection parameters of the channel's input. With one input feeding both outputs, those of the channel
            # with the input apply.
            [f"onset{_sfx}", {
                "name": f"channel {_output} onset threshold",
                "short_name": "onset",
                "value_min": -80,
                "value_max": 0,
                "value_default": -60,
                "is_integer": True
            }],
            [f"release{_sfx}", {
                "name": f"channel {_output} release threshold",
                "short_name": "release",
                "value_min": -90,
                "value_max": 0,
                "value_default": -66,
                "is_integer": True
            }],
            [f"noise{_sfx}", {
                "name": f"channel {_output} noise filter",
                "short_name": "noise filter",
                "value_min": 0,
                "value_max": 100,
                "value_default": 15,
                "is_integer": True
            }],
            # Physical audio input of the channel's converter input (0: none). Labels follow the audio inputs found.
            # Its value is state_manager.audio2midi_in (saved in the MIDI capture state), not restored from here.
            [f"audio_in{_sfx}", {
                "name": f"channel {_output} audio input",
                "short_name": "audio input",
                "labels": ["none", "1", "2"],
                "ticks": [0, 1, 2],
                "value_min": 0,
                "value_max": 2,
                "value_default": 0
            }],
            [f"polyphonic{_sfx}", {
                "name": f"output {_output} mode",
                "short_name": "mode",
                "labels": ["mono", "poly"],
                "ticks": [0, 1],
                "value_min": 0,
                "value_max": 1,
                "value_default": 0
            }],
            [f"pitchbend{_sfx}", {
                "name": f"output {_output} pitch bend",
                "short_name": "pitch bend",
                "labels": ["off", "on"],
                "ticks": [0, 1],
                "value_min": 0,
                "value_max": 1,
                "value_default": _bend
            }],
            [f"bend_range{_sfx}", {
                "name": f"output {_output} bend range",
                "short_name": "bend range",
                "value_min": 1,
                "value_max": 24,
                "value_default": 2,
                "is_integer": True
            }]
        ]
    del _output, _bend, _sfx

    # Pages of the control view: those of the channel set by set_channel()
    _ctrl_screens = None

    # Controller symbol => (library setter, channel / output index)
    _ctrl_fn = {}
    for _channel in range(2):
        _sfx = "" if _channel == 0 else f"_{_channel + 1}"
        for _symbol, _fn in (("onset", "setOnsetThreshold"), ("release", "setReleaseThreshold"),
                             ("noise", "setNoiseFilter"), ("polyphonic", "setPolyphonic"),
                             ("pitchbend", "setPitchBend"), ("bend_range", "setBendRange")):
            _ctrl_fn[_symbol + _sfx] = (_fn, _channel)
    del _channel, _sfx, _symbol, _fn

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

        self.channel = 0
        self._ctrl_screens = self.get_channel_screens(0)

        self.lib = None
        try:
            self.lib = ctypes.cdll.LoadLibrary(LIB_PATH)
            self.lib.start.restype = ctypes.c_uint8
            self.lib.isRunning.restype = ctypes.c_uint8
            for fn in ("setOnsetThreshold", "setReleaseThreshold", "setNoiseFilter"):
                getattr(self.lib, fn).argtypes = [ctypes.c_uint8, ctypes.c_float]
            for fn in ("setPolyphonic", "setPitchBend", "setOutputActive", "setOutputSource"):
                getattr(self.lib, fn).argtypes = [ctypes.c_uint8, ctypes.c_uint8]
            self.lib.setBendRange.argtypes = [ctypes.c_uint8, ctypes.c_float]
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
                self.send_lib_value(zctrl)
        self.update_output_sources()
        if self.lib.start():
            return True
        logging.error("Can't start audio to MIDI converter")
        return False

    def stop_converter(self):
        if self.lib is not None:
            self.lib.stop()

    def is_running(self):
        return self.lib is not None and bool(self.lib.isRunning())

    def set_output_active(self, output, active):
        """Activate an output (0..NUM_OUTPUTS-1). Only active outputs are analysed (cost CPU)."""
        if self.lib is not None:
            self.lib.setOutputActive(output, 1 if active else 0)

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        super().add_processor(processor)
        processor.name = self.get_channel_name()

    def get_path(self, processor):
        return self.name

    # ---------------------------------------------------------------------------
    # Channels
    # ---------------------------------------------------------------------------

    def get_channel_name(self):
        """Name of the channel shown in the control view (its title), as its MIDI output, e.g. "Audio ➔ MIDI 2"."""
        return f"{self.name} {self.channel + 1}"

    @staticmethod
    def get_channel_screens(channel):
        """Control view pages of a channel (0..NUM_OUTPUTS-1): its audio input and detection settings, then its
        MIDI output"""

        sfx = "" if channel == 0 else f"_{channel + 1}"
        return [
            ["Audio", [f"audio_in{sfx}", f"onset{sfx}", f"release{sfx}", f"noise{sfx}"]],
            ["MIDI", [f"polyphonic{sfx}", f"pitchbend{sfx}", f"bend_range{sfx}"]]
        ]

    def set_channel(self, channel):
        """Show the pages of a channel (0..NUM_OUTPUTS-1) in the control view"""

        if channel not in range(NUM_OUTPUTS):
            return
        self.channel = channel
        self._ctrl_screens = self.get_channel_screens(channel)
        self.refresh_audio_in_ctrls()
        for processor in self.processors:
            processor.name = self.get_channel_name()
            processor.init_ctrl_screens()

    def refresh_audio_in_ctrls(self):
        """Update the audio input controllers from the audio inputs found and the converter's audio inputs
        (state_manager.audio2midi_in), without changing them"""

        try:
            n_inputs = len(zynautoconnect.get_audio_capture_ports())
        except Exception:
            n_inputs = 2
        values = self.get_audio_inputs()
        for processor in self.processors:
            for channel, symbol in enumerate(AUDIO_IN_SYMBOLS):
                zctrl = processor.controllers_dict.get(symbol)
                if zctrl is None:
                    continue
                value = values[channel]
                n = max(n_inputs, value, 1)  # Keep the selected input, and at least 2 options
                zctrl.set_options({
                    "labels": ["none"] + [str(i) for i in range(1, n + 1)],
                    "ticks": list(range(n + 1))
                })
                zctrl.set_value(value, False)
                zctrl.is_dirty = True  # Redraw: the labels may change without the value
        self.update_output_sources()

    def get_audio_inputs(self):
        """Audio input (1.., 0 for none) of each channel, from state_manager.audio2midi_in"""

        values = []
        for channel in range(NUM_OUTPUTS):
            try:
                audio_in = self.state_manager.audio2midi_in[channel]
                values.append(audio_in[0] if audio_in else 0)
            except (AttributeError, IndexError, TypeError):
                values.append(0)
        return values

    def is_detection_shared(self):
        """True if both channels can share one detector: same audio input and same detection settings (one detector
        can only analyse with one set of settings)"""

        audio_in = self.get_audio_inputs()
        if not audio_in[0] or audio_in[0] != audio_in[1]:
            return False
        for processor in self.processors:
            zctrls = processor.controllers_dict
            for symbol in DETECTION_SYMBOLS:
                try:
                    if zctrls[symbol].value != zctrls[f"{symbol}_2"].value:
                        return False
                except KeyError:
                    return False
        return True

    def update_output_sources(self):
        """Feed output 2 from channel 1's detector while both channels share one (analysed once), else from its own"""

        if self.lib is not None:
            self.lib.setOutputSource(1, 0 if self.is_detection_shared() else 1)

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
            self.send_lib_value(zctrl)
        self.refresh_audio_in_ctrls()
        return zctrls

    def send_controller_value(self, zctrl):
        if zctrl.symbol in AUDIO_IN_SYMBOLS:
            # The user selected a channel's audio input. Not when restoring a state: the MIDI capture state holds it.
            if not zctrl.processor or not zctrl.processor.set_state_flag:
                self.state_manager.set_audio2midi_input(AUDIO_IN_SYMBOLS.index(zctrl.symbol), int(zctrl.value))
            return
        self.send_lib_value(zctrl)
        if zctrl.symbol.split("_")[0] in DETECTION_SYMBOLS:
            self.update_output_sources()  # Sharing a detector needs the same settings

    def send_lib_value(self, zctrl):
        """Send a controller value to the library (not the audio input controllers)"""

        if self.lib is None:
            return
        try:
            fn, output = self._ctrl_fn[zctrl.symbol]
        except KeyError:
            return
        value = zctrl.value
        if fn in ("setPolyphonic", "setPitchBend"):
            value = 1 if value else 0
        getattr(self.lib, fn)(output, value)


# ******************************************************************************
