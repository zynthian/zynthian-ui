#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynmixer Python Wrapper
#
# A Python wrapper for zynmixer library
#
# Copyright (C) 2019-2026 Brian Walton <riban@zynthian.org>
#
# ********************************************************************
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
# ********************************************************************

import logging
#import traceback

from zyngine import zynthian_engine
from zyngine import zynthian_controller
from zyngine.zynthian_signal_manager import zynsigman

# -------------------------------------------------------------------------------
# zynmixer channel strip engine
# -------------------------------------------------------------------------------


class zynthian_engine_audio_mixer(zynthian_engine):

    # Controller Screens
    _ctrl_screens = [
        ['level', ['gain', 'level', 'balance']],
        ['toggles', ['mute', 'solo', 'pfl', 'ab_mixgroup']],
        ['signal', ['mono', 'phase', 'ms']],
        ['recorder', ['record']],
    ]

    # Function to initialize library
    def __init__(self, state_manager):
        super().__init__(state_manager)
        self.type = "Audio Effect"
        self.name = "Mixer"
        self.nickname = "MI"
        self.MAX_NUM_CHANNELS = 0
        zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynsigman.SS_AUDIO_RECORDER_STATE, self.audio_recorder_cb)

    def start(self):
        pass

    def get_controllers_dict(self, processor):
        if not processor.controllers_dict:
            processor.controllers_dict = {
                'gain': zynthian_controller(self, 'gain', {
                    'is_integer': True,
                    'value_min': -40,
                    'value_max': 40,
                    'value_default': 0,
                    'labels': ["0dB" if x==0 else f"{x:+d}dB" for x in range(-40, 41)],
                    'value': processor.zynmixer.get_gain(processor.mixer_chan),
                    'processor': processor
                }),
                'level': zynthian_controller(self, 'level', {
                    'is_integer': False,
                    'value_max': 1.0,
                    'value_default': 0.8,
                    'value': processor.zynmixer.get_level(processor.mixer_chan),
                    'processor': processor
                }),
                'balance': zynthian_controller(self, 'balance', {
                    'is_integer': False,
                    'value_min': -1.0,
                    'value_max': 1.0,
                    'value_default': 0.0,
                    'value': processor.zynmixer.get_balance(processor.mixer_chan),
                    'processor': processor
                }),
                'mute': zynthian_controller(self, 'mute', {
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_mute(processor.mixer_chan),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'solo': zynthian_controller(self, 'solo', {
                    'name': "S",
                    'short_name': "solo",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_solo(processor.mixer_chan),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'pfl': zynthian_controller(self, 'pfl', {
                    'name': "PFL",
                    'short_name': "pfl",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_pfl(processor.mixer_chan),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'mono': zynthian_controller(self, 'mono', {
                    'name': "M",
                    'short_name': "mono",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_mono(processor.mixer_chan),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'ms': zynthian_controller(self, 'ms', {
                    'name': "MS",
                    'short_name': "M+S",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_ms(processor.mixer_chan),
                    'labels': ['off', 'on'],
                    'processor': processor,
                    'name': "M+S"
                }),
                'phase': zynthian_controller(self, 'phase', {
                    'name': "Ø",
                    'short_name': "phase",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_phase(processor.mixer_chan),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'record': zynthian_controller(self, 'record', {
                    'name': "R",
                    'short_name': "record",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': 0,
                    'processor': processor,
                    'labels': ['off', 'on']
                })
            }
            if processor.eng_code == "MI":
                processor.controllers_dict['ab_mixgroup'] = zynthian_controller(self, 'ab_mixgroup', {
                    'name': "A/B",
                    'short_name': "A/B mix",
                    'is_integer': True,
                    'value_max': 2,
                    'value_default': 0,
                    'value': processor.zynmixer.get_ab_mixgroup(processor.mixer_chan),
                    'processor': processor,
                    'labels': ['none', 'A', 'B']
                })
            elif processor.chain.chain_id == 0:
                processor.controllers_dict |= {
                'aux_level': zynthian_controller(self, 'aux_level', {
                    'name': "aux level",
                    'is_integer': False,
                    'value_max': 1.0,
                    'value_default': 0.8,
                    'value': processor.zynmixer.get_level(1),
                    'processor': processor
                }),
                'aux_balance': zynthian_controller(self, 'aux_balance', {
                    'name': "aux balance",
                    'is_integer': False,
                    'value_min': -1.0,
                    'value_max': 1.0,
                    'value_default': 0.0,
                    'value': processor.zynmixer.get_balance(1),
                    'processor': processor
                }),
                'aux_mute': zynthian_controller(self, 'aux_mute', {
                    'name': "aux mute",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_mute(1),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'aux_solo': zynthian_controller(self, 'aux_solo', {
                    'name': "aux solo",
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': processor.zynmixer.get_solo(1),
                    'processor': processor,
                    'labels': ['off', 'on']
                }),
                'global_xfader': zynthian_controller(self, 'global_xfader', {
                    'name': "Crossfader A/B",
                    'is_integer': False,
                    'value_max': 1.0,
                    'value_min': 0.0,
                    'value_default': 0.0,
                    'value': self.state_manager.zynmixer_chan.get_global_xfader(),
                    'processor': processor,
                }),
                'pfl_level': zynthian_controller(self, 'pfl_level', {
                    'name': "PFL Level",
                    'is_integet': False,
                    'value_max': 1.0,
                    'value_min': 0.0,
                    'value_default': 1.0,
                    'value': processor.zynmixer.get_pfl_level(),
                    'processor': processor
                })}
        return processor.controllers_dict

    def add_processor(self, processor):
        self.processors.append(processor)
        if processor.eng_code == "MR":
            processor.zynmixer = self.state_manager.zynmixer_bus
            processor.jackname = "zynmixer_bus"
            if processor.chain_id:
                # Aux Mixbus
                processor.mixer_chan = self.state_manager.zynmixer_bus.add_strip()
                send = self.state_manager.zynmixer_chan.add_send()
                processor.name = f"Aux Mixbus {send}"
                self._ctrl_screens = [
                    ['level', ['gain', 'level', 'balance']],
                    ['toggles', ['mute', 'solo', 'pfl']],     # TODO => 'ab_mixgroup'
                    ['signal', ['mono', 'phase', 'ms']],
                    ['recorder', ['record']]
                ]
            else:
                # Main mixbus
                processor.mixer_chan = 0
                processor.name = "Main Mixbus"
                self._ctrl_screens = [
                    ['level', ['gain', 'level', 'balance']],
                    ['toggles', ['mute', 'solo', 'pfl']],
                    ['signal', ['mono', 'phase', 'ms']],
                    ['global', ['global_xfader', 'pfl_level']],
                    ['aux', ['aux_level', 'aux_balance', 'aux_mute', 'aux_solo']],
                    ['recorder', ['record']]
                ]
        else:
            # Normal audio mixer strip
            processor.zynmixer = self.state_manager.zynmixer_chan
            processor.jackname = "zynmixer_chan"
            processor.mixer_chan = self.state_manager.zynmixer_chan.add_strip()
            processor.name = f"Mixer Channel {processor.mixer_chan + 1}"
        processor.refresh_controllers()
        return

    def remove_processor(self, processor):
        processor.zynmixer.set_mute(processor.mixer_chan, 1)
        super().remove_processor(processor)
        processor.zynmixer.remove_strip(processor.mixer_chan)
        if processor.zynmixer == self.state_manager.zynmixer_bus:
            send = processor.mixer_chan
            self.state_manager.zynmixer_chan.remove_send(send)

    def send_controller_value(self, zctrl):
        try:
            if zctrl.symbol.startswith("send"):
                getattr(zctrl.processor.zynmixer, f"set_{zctrl.graph_path[0]}")(
                    zctrl.processor.mixer_chan, zctrl.graph_path[1], zctrl.value)
            elif zctrl.symbol == "solo":
                if zctrl.processor.chain_id == 0:
                    for chain in self.state_manager.chain_manager.chains.values():
                        if chain.zynmixer_proc:
                            chain.zynmixer_proc.controllers_dict["solo"].set_value(0)
                    zctrl.processor.controllers_dict["aux_solo"].set_value(0)
                else:
                    getattr(zctrl.processor.zynmixer, f'set_{zctrl.symbol}')(zctrl.processor.mixer_chan, zctrl.value)
                glob_solo = self.state_manager.zynmixer_chan.get_global_solo()
                self.state_manager.zynmixer_bus.set_solo(0, glob_solo)
            elif zctrl.symbol.startswith("aux_"):
                getattr(zctrl.processor.zynmixer, f'set_{zctrl.symbol[4:]}')(1, zctrl.value)
            elif zctrl.symbol.startswith("global_"):
                getattr(self.state_manager.zynmixer_chan, f'set_{zctrl.symbol}')(zctrl.value)
            elif zctrl.symbol == "pfl_level":
                zctrl.processor.zynmixer.set_pfl_level(zctrl.value)
            else:
                getattr(zctrl.processor.zynmixer, f'set_{zctrl.symbol}')(zctrl.processor.mixer_chan, zctrl.value)
        except Exception as e:
            logging.error(e)
            #logging.exception(traceback.format_exc())

    def get_path(self, processor):
        return processor.name
        if processor.chain_id:
            if processor.eng_code == "MR":
                return f"Aux Mixbus {processor.chain_id}"
            else:
                return f"Mixer Channel {processor.chain_id}"
        return f"Main Mixbus"

    def audio_recorder_cb(self, state):
        for processor in self.processors:
            processor.controllers_dict["record"].set_readonly(state)

# -------------------------------------------------------------------------------
