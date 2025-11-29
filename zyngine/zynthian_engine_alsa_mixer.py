# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_alsa_mixer)
#
# zynthian_engine implementation for Alsa Mixer
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

import os
import re
import copy
import numpy
import logging
import alsaaudio
from subprocess import check_output

from zyncoder.zyncore import lib_zyncore
from . import zynthian_engine
from . import zynthian_controller

# ------------------------------------------------------------------------------
# ALSA Mixer Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_alsa_mixer(zynthian_engine):

    sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR', "/zynthian/zynthian-sys")
    soundcard_name = os.environ.get('SOUNDCARD_NAME', "Unknown")

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    _ctrl_screens = []

    # ----------------------------------------------------------------------------
    # Config variables
    # ----------------------------------------------------------------------------

    volume_units_percent_devices = []

    # ---------------------------------------------------------------------------
    # Translations by device
    # ---------------------------------------------------------------------------

    device_overrides = {}

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    _ctrl_screens = []

    # ----------------------------------------------------------------------------
    # ZynAPI variables
    # ----------------------------------------------------------------------------

    zynapi_instance = None

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    def __init__(self, state_manager=None, proc=None):
        super().__init__(state_manager)

        self.type = "Mixer"
        self.name = "Audio Levels"
        self.nickname = "MX"

        self.processor = proc

        self.audio_out = []
        self.options['midi_chan'] = False
        self.options['replace'] = False

        self.zctrls = None
        self.stereo_controls = [] # list of alsa controls that can be controlled as stereo pairs
        self.stereo_channels = 0 # Quantity of optional switchable stereo channels
        self.get_soundcard_config()

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

    def is_headphone_amp_interface_available(self):
        try:
            return callable(lib_zyncore.set_hpvol)
        except:
            return False

    def allow_rbpi_headphones(self):
        try:
            if not self.is_headphone_amp_interface_available() and self.rbpi_device_name and self.device_name != self.rbpi_device_name:
                return True
            else:
                return False
        except:
            logging.error("Error checking RBPi headphones")
            return False

    def get_controllers_dict(self, processor=None, ctrl_list=None):
        if ctrl_list == "*":
            ctrl_list = None
        elif ctrl_list is None:
            ctrl_list = copy.copy(self.ctrl_list)

        logging.debug(f"MIXER CTRL LIST: {ctrl_list}")

        ctrls = self.get_mixer_zctrls(self.device_name, ctrl_list)

        # Add HP amplifier interface if available
        try:
            if self.is_headphone_amp_interface_available():
                ctrls["Headphone"] = {
                    'name': "Headphone",
                    'graph_path': lib_zyncore.set_hpvol,
                    'value': lib_zyncore.get_hpvol(),
                    'value_min': 0,
                    'value_max': lib_zyncore.get_hpvol_max(),
                    'is_integer': True,
                    'group_symbol': "output",
                    'group_name': "Output levels"
                }
                logging.debug("Added zyncore Headphones Amplifier volume control")
        except Exception as e:
            logging.debug(f"Can't add zyncore Headphones Amplifier: {e}")

        # Add RBPi headphones if enabled and available...
        if self.allow_rbpi_headphones() and self.state_manager and self.state_manager.get_zynthian_config("rbpi_headphones"):
            try:
                hp_ctrls = self.get_mixer_zctrls(self.rbpi_device_name, ["Headphone", "PCM"])
                if len(hp_ctrls) > 0:
                    ctrls |= hp_ctrls
                else:
                    raise Exception("RBPi Headphone volume control not found!")
            except Exception as e:
                logging.error(f"Can't configure RBPi headphones volume control: {e}")

        if processor:
            self.zctrls = processor.controllers_dict
            # Remove controls that are no longer used
            for symbol in list(self.zctrls):
                d = True
                for ctrl in ctrls:
                    if symbol == ctrl:
                        d = False
                        break
                if d:
                    del self.zctrls[symbol]
        else:
            self.zctrls = {}

        # Add new controllers or reconfigure existing ones
        for symbol, config in ctrls.items():
            if symbol in self.zctrls:
                self.zctrls[symbol].set_options(config)
            else:
                self.zctrls[symbol] = zynthian_controller(self, symbol, config)

        # Generate control screens
        self._ctrl_screens = None
        self.generate_ctrl_screens(self.zctrls)

        return self.zctrls

    def get_mixer_zctrls(self, device_name=None, ctrl_list=[]):
        _ctrls = {}
        if device_name:
            device = f"hw:{device_name}"
        else:
            device = self.device

        try:
            is_log = False
            mixer_ctrl_names = sorted(set(alsaaudio.mixers(device=device)))
            for ctrl_name in mixer_ctrl_names:
                idx = 0  # ALSA array index
                try:
                    alsaaudio.Mixer(ctrl_name, 1, -1, device)
                    ctrl_array = True
                except:
                    ctrl_array = False
                while True:
                    # Iterate through all elements of array
                    try:
                        mixer_ctrl = alsaaudio.Mixer(ctrl_name, idx, -1, device)
                        switch_cap = mixer_ctrl.switchcap()  # May be arbitrary switch, not necessarily mute
                        level_cap = mixer_ctrl.volumecap()  # May be arbitrary level, not necessarily volume
                        enum_vals = mixer_ctrl.getenum()
                    except Exception as e:
                        break  # exceeded index in array of controls
                    io_num = idx + 1
                    if level_cap and switch_cap:
                        switch_suffix = "_switch"
                    else:
                        switch_suffix = ""
                    if (level_cap or switch_cap) and enum_vals:
                        enum_suffix = "_enum"
                    else:
                        enum_suffix = ""

                    if "Playback Volume" in level_cap:
                        # Control supports control of an output level parameter
                        levels = mixer_ctrl.getvolume(alsaaudio.PCM_PLAYBACK, self.volume_units)
                        ctrl_multi = ctrl_array or len(levels) > 1
                        for chan, val in enumerate(levels):
                            ctrl_range = mixer_ctrl.getrange(alsaaudio.PCM_PLAYBACK, self.volume_units)
                            if ctrl_multi:
                                name = f"{ctrl_name} {io_num}"
                            else:
                                name = ctrl_name
                            is_toggle = mixer_ctrl.getrange(alsaaudio.PCM_PLAYBACK)[1] == 1
                            if is_toggle:
                                labels = ["off", "on"]
                            else:
                                labels = None
                            symbol = f"{ctrl_name.replace(' ', '_')}"
                            if ctrl_array:
                                symbol += f"_{idx}"
                            if len(levels) > 1:
                                symbol += f"_{chan}"
                            if ctrl_list:
                                try:
                                    display_priority = 10000 - ctrl_list.index(symbol)
                                except:
                                    io_num += 1
                                    continue
                            else:
                                display_priority = 10000 - io_num
                            if ctrl_name == "Headphone":
                                io_num = 0  # Clumsey but we are only guestimating here
                            _ctrls[symbol] = {
                                'name': name,
                                'graph_path': [ctrl_name, idx, chan, "playback_level", ctrl_array],
                                'value': val,
                                'value_min': ctrl_range[0],
                                'value_max': ctrl_range[1],
                                'is_toggle': is_toggle,
                                'is_integer': True,
                                'is_logarithmic': is_log,
                                'labels': labels,
                                'processor': self.processor,
                                'group_symbol': "output",
                                'group_name': "Output levels",
                                'display_priority': display_priority
                            }
                            io_num += 1
                    elif "Capture Volume" in level_cap:
                        # Control supports control of an input level parameter
                        levels = mixer_ctrl.getvolume(alsaaudio.PCM_CAPTURE, self.volume_units)
                        ctrl_multi = ctrl_array or len(levels) > 1
                        for chan, val in enumerate(levels):
                            ctrl_range = mixer_ctrl.getrange(alsaaudio.PCM_CAPTURE, self.volume_units)
                            if ctrl_multi:
                                name = f"{ctrl_name} {io_num}"
                            else:
                                name = f"{ctrl_name}"
                            is_toggle = mixer_ctrl.getrange(alsaaudio.PCM_CAPTURE)[1] == 1
                            if is_toggle:
                                labels = ["off", "on"]
                            else:
                                labels = None
                            symbol = f"{ctrl_name.replace(' ', '_')}"
                            if ctrl_array:
                                symbol += f"_{idx}"
                            if len(levels) > 1:
                                symbol += f"_{chan}"
                            if ctrl_list:
                                try:
                                    display_priority = 10000 - ctrl_list.index(symbol)
                                except:
                                    io_num += 1
                                    continue
                            else:
                                display_priority = 10000 - io_num
                            _ctrls[symbol] = {
                                'name': name,
                                'graph_path': [ctrl_name, idx, chan, "capture_level", ctrl_array],
                                'value': val,
                                'value_min': ctrl_range[0],
                                'value_max': ctrl_range[1],
                                'is_toggle': is_toggle,
                                'is_integer': True,
                                'is_logarithmic': is_log,
                                'labels': labels,
                                'processor': self.processor,
                                'group_symbol': "input",
                                'group_name': "Input levels",
                                'display_priority': display_priority
                            }
                            io_num += 1
                    elif "Volume" in level_cap:
                        # Control supports control of a misc? level parameter
                        levels = mixer_ctrl.getvolume(alsaaudio.PCM_PLAYBACK, self.volume_units)
                        ctrl_multi = ctrl_array or len(levels) > 1
                        for chan, val in enumerate(levels):
                            ctrl_range = mixer_ctrl.getrange(alsaaudio.PCM_PLAYBACK, self.volume_units)
                            if ctrl_multi:
                                name = f"{ctrl_name} {io_num}"
                            else:
                                name = f"{ctrl_name}"
                            is_toggle = mixer_ctrl.getrange(alsaaudio.PCM_PLAYBACK)[1] == 1
                            if is_toggle:
                                labels = ["off", "on"]
                            else:
                                labels = None
                            symbol = f"{ctrl_name.replace(' ', '_')}"
                            if ctrl_array:
                                symbol += f"_{idx}"
                            if len(levels) > 1:
                                symbol += f"_{chan}"
                            if ctrl_list:
                                try:
                                    display_priority = 10000 - ctrl_list.index(symbol)
                                except:
                                    io_num += 1
                                    continue
                            else:
                                display_priority = 10000 - io_num
                            _ctrls[symbol] = {
                                'name': name,
                                'graph_path': [ctrl_name, idx, chan, "playback_level", ctrl_array],
                                'value': val,
                                'value_min': ctrl_range[0],
                                'value_max': ctrl_range[1],
                                'is_toggle': is_toggle,
                                'is_integer': True,
                                'is_logarithmic': is_log,
                                'labels': labels,
                                'processor': self.processor,
                                'group_symbol': "other",
                                'group_name': "Other controls",
                                'display_priority': display_priority
                            }
                            io_num += 1
                    io_num = idx + 1
                    if "Playback Mute" in switch_cap:
                        # Control supports control of an ouput switch parameter
                        mutes = mixer_ctrl.getmute()
                        ctrl_multi = ctrl_array or len(mutes) > 1
                        for chan, val in enumerate(mutes):
                            if ctrl_multi:
                                name = f"{ctrl_name} {io_num}"
                            else:
                                name = ctrl_name
                            symbol = f"{ctrl_name.replace(' ', '_')}"
                            if ctrl_array:
                                symbol += f"_{idx}"
                            symbol += switch_suffix
                            if ctrl_list:
                                try:
                                    display_priority = 10000 - ctrl_list.index(symbol)
                                except:
                                    io_num += 1
                                    continue
                            else:
                                display_priority = 10000 - io_num
                            _ctrls[symbol] = {
                                'name': name,
                                'graph_path': [ctrl_name, idx, chan, "switch", ctrl_array],
                                'value': val,
                                'value_min': 0,
                                'value_max': 1,
                                'is_toggle': True,
                                'is_integer': True,
                                'labels': ["off", "on"],
                                'processor': self.processor,
                                'group_symbol': "output",
                                'group_name': "Output levels",
                                'display_priority': display_priority
                            }
                            io_num += 1
                    elif "Capture Mute" in switch_cap:
                        # Control supports control of an output switch parameter
                        mutes = mixer_ctrl.getrec()
                        ctrl_multi = ctrl_array or len(mutes) > 1
                        for chan, val in enumerate(mutes):
                            if ctrl_multi:
                                name = f"{ctrl_name} {io_num}"
                            else:
                                name = ctrl_name
                            symbol = f"{ctrl_name.replace(' ', '_')}"
                            if ctrl_array:
                                symbol += f"_{idx}"
                            symbol += switch_suffix
                            if ctrl_list:
                                try:
                                    display_priority = 10000 - ctrl_list.index(symbol)
                                except:
                                    io_num += 1
                                    continue
                            else:
                                display_priority = 10000 - io_num
                            _ctrls[symbol] = {
                                'name': name,
                                'graph_path': [ctrl_name, idx, chan, "switch", ctrl_array],
                                'value': val,
                                'value_min': 0,
                                'value_max': 1,
                                'is_toggle': True,
                                'is_integer': True,
                                'labels': ["off", "on"],
                                'processor': self.processor,
                                'group_symbol': "input",
                                'group_name': "Input levels",
                                'display_priority': display_priority
                            }
                            io_num += 1
                    elif "Mute" in switch_cap:
                        # Control supports control of a misc? switch parameter
                        mutes = mixer_ctrl.getmute()
                        ctrl_multi = ctrl_array or len(mutes) > 1
                        for chan, val in enumerate(mutes):
                            if ctrl_multi:
                                name = f"{ctrl_name} {io_num}"
                            else:
                                name = ctrl_name
                            symbol = f"{ctrl_name.replace(' ', '_')}"
                            if ctrl_array:
                                symbol += f"_{idx}"
                            symbol += switch_suffix
                            if ctrl_list:
                                try:
                                    display_priority = 10000 - ctrl_list.index(symbol)
                                except:
                                    idx += 1
                                    continue
                            else:
                                display_priority = 10000 - io_num
                            _ctrls[symbol] = {
                                'name': name,
                                'graph_path': [ctrl_name, idx, chan, "switch", ctrl_array],
                                'value': val,
                                'value_min': 0,
                                'value_max': 1,
                                'is_toggle': True,
                                'is_integer': True,
                                'labels': ["off", "on"],
                                'processor': self.processor,
                                'group_symbol': "other",
                                'group_name': "Other controls",
                                'display_priority': display_priority
                            }
                            io_num += 1
                    io_num = idx + 1
                    if enum_vals:
                        # Control allows selection from a list
                        if ctrl_array:
                            name = f"{ctrl_name} {io_num}"
                        else:
                            name = ctrl_name
                        symbol = f"{ctrl_name.replace(' ', '_')}"
                        symbol += enum_suffix
                        if ctrl_array:
                            symbol += f"_{idx}"
                        if ctrl_list:
                            try:
                                display_priority = 10000 - ctrl_list.index(symbol)
                            except:
                                idx += 1
                                continue
                        else:
                            display_priority = 10000 - io_num
                        _ctrls[symbol] = {
                            'name': name,
                            'graph_path': [ctrl_name, idx, 0, "enum", ctrl_array],
                            'labels': enum_vals[1],
                            'ticks': list(range(len(enum_vals[1]))),
                            'value': enum_vals[1].index(enum_vals[0]),
                            'value_min': 0,
                            'value_max': len(enum_vals[1]) - 1,
                            'is_toggle': False,
                            'is_integer': True,
                            'processor': self.processor,
                            'group_symbol': "other",
                            'group_name': "Other controls",
                            'display_priority': display_priority
                        }
                        io_num += 1
                    idx += 1

        except Exception as err:
            logging.error(err)

        # Apply soundcard specific overrides
        if self.device_name in self.device_overrides:
            for ctrl in self.device_overrides[self.device_name]:
                try:
                    _ctrls[ctrl] |= self.device_overrides[self.device_name][ctrl]
                except:
                    pass  # There may be hidden controls

        for i in range(self.stereo_channels):
            a = i * 2
            b = a + 1
            symbol = f"stereo_{i}"
            _ctrls[symbol] = {
                'graph_path': self.set_stereo,
                'name': f"Stereo {a+1}+{b+1}",
                'labels': ["mono", "stereo"],
                'is_toggle': True,
                'is_integer': True,
                'processor': self.processor,
                'group_symbol': "stereo",
                'group_name': "Stereo",
                "display_priority": 100
            }
        return _ctrls

    def set_stereo(self, value):
        pass

    def send_controller_value(self, zctrl):
        try:
            if callable(zctrl.graph_path):
                zctrl.graph_path(zctrl.value)
            else:
                name = zctrl.graph_path[0]
                idx = zctrl.graph_path[1]
                chan = zctrl.graph_path[2]
                type = zctrl.graph_path[3]
                array = zctrl.graph_path[4]
                if type == "playback_level":
                    alsaaudio.Mixer(name, idx, -1, self.device).setvolume(zctrl.value, chan, alsaaudio.PCM_PLAYBACK, self.volume_units)
                    try:
                        if name in self.stereo_controls and self.zctrls[f"stereo_{chan // 2}"].value:
                            parts = zctrl.symbol.split("_")
                            index = int(parts[-1])
                            if index % 2:
                                parts[-1] = str(index - 1)
                            else:
                                parts[-1] = str(index + 1)
                        self.zctrls["_".join(parts)].set_value(zctrl.value)
                    except:
                        pass # No stereo controller for this channel
                elif type == "capture_level":
                    alsaaudio.Mixer(name, idx, -1, self.device).setvolume(zctrl.value, chan, alsaaudio.PCM_CAPTURE, self.volume_units)
                elif type == "switch":
                    alsaaudio.Mixer(name, idx, -1, self.device).setmute(zctrl.value, chan)
                elif type == "enum":
                    alsaaudio.Mixer(name, idx, -1, self.device).setenum(zctrl.value)
                #logging.debug(f"Sending value '{zctrl.value}' for zctrl '{zctrl.symbol}' => IS_DIRTY: {zctrl.is_dirty}, OBJECT => {zctrl}")
        except Exception as err:
            logging.error(f"Can't send value '{zctrl.value}' for zctrl '{zctrl.symbol}' => {err}")

    # --------------------------------------------------------------------------
    # Special
    # --------------------------------------------------------------------------

    def get_soundcard_config(self):
        try:
            jack_opts = os.environ.get('JACKD_OPTIONS')
            res = re.compile(r" hw:(\S+) ").search(jack_opts)
            self.device_name = res.group(1)
        except:
            self.device_name = "0"
        self.device = f"hw:{self.device_name}"

        try:
            cmd = self.sys_dir + "/sbin/get_rbpi_audio_device.sh"
            self.rbpi_device_name = check_output(cmd, shell=True).decode("utf-8")
        except:
            self.rbpi_device_name = None

        try:
            scmix = os.environ.get('SOUNDCARD_MIXER', "").replace("\\n", "")
            self.ctrl_list = [item.strip() for item in scmix.split(',')]
        except:
            self.ctrl_list = None

        if self.device_name in self.volume_units_percent_devices:
            self.volume_units = alsaaudio.VOLUME_UNITS_PERCENTAGE
        else:
            self.volume_units = alsaaudio.VOLUME_UNITS_RAW

        if self.device_name == "sndrpihifiberry":
            self.set_sndrpihifiberry_overrides()
        elif self.device_name == "US16x08":
            self.set_US16x08_overrides()

    # ---------------------------------------------------------------------------
    # Overrides
    # ---------------------------------------------------------------------------

    def set_sndrpihifiberry_overrides(self):
        mylog = [0, 28, 44, 55, 64, 72, 78, 83, 88, 92, 96, 99, 103, 106, 108, 111, 113,
                 116, 118, 120, 122, 124, 125, 127, 129, 130, 132, 133, 135, 136, 137]
        output_level_labels = list(map(str, range(0, 101)))
        output_level_ticks = mylog + list(range(138, 208))
        # HifiBerry / ZynADAC
        self.device_overrides["sndrpihifiberry"] = {
            "Digital_0": {"name": f"Output 1 level", "labels":  output_level_labels, "ticks": output_level_ticks},
            "Digital_1": {"name": f"Output 2 level", "labels":  output_level_labels, "ticks": output_level_ticks},
            "Digital_0_switch": {"name": f"Output 1 mute"},
            "Digital_1_switch": {"name": f"Output 2 mute"},
            "ADC_0": {"name": f"Input 1 Level"},
            "ADC_1": {"name": f"Input 2 Level"},
            "PGA_Gain_Left": {"name": f"Input 1 Gain", "group_symbol": "input", 'group_name': "Input levels"},
            "PGA_Gain_Right": {"name": f"Input 2 Gain", "group_symbol": "input", 'group_name': "Input levels"},
            "ADC_Left_Input": {"name": f"Input 1 Mode", "labels": ["Disabled", "Unbalanced Mono TS",
                               "Unbalanced Mono TR", "Stereo TRS to Mono", "Balanced Mono TRS"],
                               "group_symbol": "input", 'group_name': "Input levels"},
            "ADC_Right_Input": {"name": f"Input 2 Mode", "labels": ["Disabled", "Unbalanced Mono TS",
                                "Unbalanced Mono TR", "Stereo TRS to Mono", "Balanced Mono TRS"], 
                                "group_symbol": "input", 'group_name': "Input levels"}
        }

        # ZynADAC fix
        if self.soundcard_name == "ZynADAC":
            self.device_overrides["sndrpihifiberry"]["ADC_Left_Input"]["labels"] =\
                ["Disabled", "Unbalanced Mono TR", "Unbalanced Mono TS", "Stereo TRS to Mono", "Balanced Mono TRS"]
            self.device_overrides["sndrpihifiberry"]["ADC_Right_Input"]["labels"] = \
                ["Disabled", "Unbalanced Mono TR", "Unbalanced Mono TS", "Stereo TRS to Mono", "Balanced Mono TRS"]

    def set_US16x08_overrides(self):
        # Tascam US-16x08
        overrides = {}
        overrides[f"DSP_Bypass"] = {"name": "DSP enable", "group_name": "Global"}
        self.stereo_controls = ["Compressor", "Compressor Threshold", "Compressor Ratio", "Compressor Attack", "Compressor Release", "EQ", "EQ High", "EQ High Frequencey", "EQ Low", "EQ Low Frequency", "EQ MidHigh", "EQ MidHigh Frequency", "EQ MidHigh Q", "EQ MidLow", "EQ MidLow Frequency", "EQ MidLow Q", "Line", "Mute", "Pan Left-Right", "Phase"]
        self.stereo_channels = 8
        for i in range(16):
            overrides[f"Compressor_{i}_switch"] = {"name": f"Compressor {i + 1} disable", "group_symbol": f"comp{i}", "group_name": f"Compressor {i + 1}", "labels": ["enabled", "disabled"], "display_priority": 70}
            overrides[f"Compressor_Threshold_{i}"] = {"name": f"Compressor {i + 1} threshold", "group_symbol": f"comp{i}", "group_name": f"Compressor {i + 1}", "labels": [f"{j} dB" for j in range(-32, 1)], "display_priority": 69}
            overrides[f"Compressor_Ratio_{i}"] = {"name": f"Compressor {i + 1} ratio", "group_symbol": f"comp{i}", "group_name": f"Compressor {i + 1}", "labels": ["1:1", "1.1:1", "1.3:1", "1.5:1", "1.7:1", "2:1", "2.5:1", "3:1", "3.5:1", "4:1", "5:1", "6:1", "8:1", "16:1", "inf:1"], "display_priority": 68}
            overrides[f"Compressor_Attack_{i}"] = {"name": f"Compressor {i + 1} attack", "group_symbol": f"comp{i}", "group_name": f"Compressor {i + 1}", "labels": [f"{j} ms" for j in range(2, 201)], "display_priority": 67}
            overrides[f"Compressor_Release_{i}"] = {"name": f"Compressor {i + 1} release", "group_symbol": f"comp{i}", "group_name": f"Compressor {i + 1}", "labels": [f"{j} ms" for j in range(10, 1010, 10)], "display_priority": 66}
            overrides[f"Compressor_{i}"] = {"name": f"Compressor {i + 1} gain", "group_symbol": f"comp{i}", "group_name": f"Compressor {i + 1}", "labels": [f"{j} dB" for j in range(21)], "display_priority": 65}
            overrides[f"EQ_{i}"] = {"name": f"EQ {i + 1} disable", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": ["enabled", "disabled"], "display_priority": 50}
            for j, param in enumerate(["Low", "MidLow", "MidHigh", "High"]):
                overrides[f"EQ_{param}_{i}"] = {"name": f"EQ {i + 1} {param.lower()}", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": [f"{j} dB" for j in range(-12, 13)], "display_priority": 10 + j * 10}
            overrides[f"EQ_High_Frequency_{i}"] = {"name": f"EQ {i + 1} high freq", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": [f"{j:.1f} kHz" for j in numpy.geomspace(1.7, 18, num=32)], "display_priority": 41}
            overrides[f"EQ_MidHigh_Frequency_{i}"] = {"name": f"EQ {i + 1} midhigh freq", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": [f"{int(j)} Hz" for j in numpy.geomspace(32, 18000, num=64)], "display_priority": 32}
            overrides[f"EQ_MidHigh_Q_{i}"] = {"name": f"EQ {i + 1} midhigh Q", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": ["0.25", "0.5", "1", "2", "4", "8", "16"], "display_priority": 31}
            overrides[f"EQ_MidLow_Frequency_{i}"] = {"name": f"EQ {i + 1} midlow freq", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": [f"{int(j)} Hz" for j in numpy.geomspace(32, 18000, num=64)], "display_priority": 23}
            overrides[f"EQ_MidLow_Q_{i}"] = {"name": f"EQ {i + 1} midlow Q", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": ["0.25", "0.5", "1", "2", "4", "8", "16"], "display_priority": 22}
            overrides[f"EQ_Low_Frequency_{i}"] = {"name": f"EQ {i + 1} low freq", "group_symbol": f"eq{i}", "group_name": f"EQ {i + 1}", "labels": [f"{int(j)} Hz" for j in numpy.geomspace(32, 16000, num=32)], "display_priority": 10}
            overrides[f"Line_Out_{i}"] = {"group_symbol": "output"}
            overrides[f"Line_{i}"] = {"name": f"Fader {i + 1}", "group_symbol": f"mixer{i}", "group_name": f"Mixer {i + 1}", "labels": [f"{j} dB" for j in range(-127, 7)], "display_priority": 4}
            overrides[f"Pan_Left-Right_{i}"] = {"name": f"Pan {i + 1}", "group_symbol": f"mixer{i}", "group_name": f"Mixer {i + 1}", "labels": [f"{j}" for j in range(-127, 128)], "display_priority": 3}
            overrides[f"Phase_{i}"] = {"name": f"Phase {i + 1}", "group_symbol": f"mixer{i}", "group_name": f"Mixer {i + 1}", "labels": ["on", "off"], "display_priority": 1}
            overrides[f"Mute_{i}"] = {"name": f"Mute {i + 1}", "group_symbol": f"mixer{i}", "group_name": f"Mixer {i + 1}", "labels": ["mute", "unmute"], "display_priority": 2}
            #overrides[f"Level_Meter_{i}"] = {"name": f"Meter {i + 1}", "group_symbol": f"mixer{i}", "group_name": f"Mixer {i + 1}"}
        overrides["Buss_Out"] = {"name": "Mixdown", "group_symbol": "mixer_main", "group_name": "Mixer Main", "display_priority": 7}
        overrides["Master"] = {"name": "Main Fader", "group_symbol": "mixer_main", "group_name": "Mixer Main", "labels": ["on", "off"], "labels": [f"{j} dB" for j in range(-127, 7)], "display_priority": 6}
        overrides["Master_Mute"] = {"name": "Main Mute", "group_symbol": "mixer_main", "group_name": "Mixer Main", "labels": ["mute", "unmute"], "display_priority": 5}
        self.device_overrides["US16x08"] = overrides

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    @classmethod
    def init_zynapi_instance(cls):
        if not cls.zynapi_instance:
            cls.zynapi_instance = cls(None)
        else:
            logging.debug("\n\n********** REUSING INSTANCE ***********")

    @classmethod
    def refresh_zynapi_instance(cls):
        if cls.zynapi_instance:
            cls.zynapi_instance.stop()
            cls.zynapi_instance = cls(None)

    @classmethod
    def zynapi_get_controllers(cls, ctrl_list="*"):
        return cls.zynapi_instance.get_controllers_dict(None, ctrl_list)

    @classmethod
    def zynapi_get_device_name(cls):
        return cls.zynapi_instance.device_name

    @classmethod
    def zynapi_get_rbpi_device_name(cls):
        return cls.zynapi_instance.rbpi_device_name

# ******************************************************************************
