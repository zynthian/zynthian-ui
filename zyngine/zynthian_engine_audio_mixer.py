#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynmixer Python Wrapper
#
# A Python wrapper for zynmixer library
#
# Copyright (C) 2019-2024 Brian Walton <riban@zynthian.org>
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

import ctypes
import logging

from zyngine import zynthian_engine
from zyngine import zynthian_controller
from zyngine.zynthian_signal_manager import zynsigman

# -------------------------------------------------------------------------------
# Zynmixer Library Wrapper
# -------------------------------------------------------------------------------


class zynmixer(zynthian_engine):

    # Subsignals are defined inside each module. Here we define audio_mixer subsignals:
    SS_ZCTRL_SET_VALUE = 1

    # Function to initialize library
    def __init__(self):
        super().__init__()
        self.lib_zynmixer = ctypes.cdll.LoadLibrary(
            "/zynthian/zynthian-ui/zynlibs/zynmixer/build/libzynmixer.so")
        self.lib_zynmixer.init()

        self.lib_zynmixer.setLevel.argtypes = [ctypes.c_uint8, ctypes.c_float]
        self.lib_zynmixer.getLevel.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getLevel.restype = ctypes.c_float

        self.lib_zynmixer.setBalance.argtypes = [
            ctypes.c_uint8, ctypes.c_float]
        self.lib_zynmixer.getBalance.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getBalance.restype = ctypes.c_float

        self.lib_zynmixer.setMute.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.toggleMute.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getMute.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getMute.restype = ctypes.c_uint8

        self.lib_zynmixer.setMS.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getMS.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getMS.restypes = ctypes.c_uint8

        self.lib_zynmixer.setSolo.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getSolo.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getSolo.restype = ctypes.c_uint8

        self.lib_zynmixer.setMono.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getMono.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getMono.restype = ctypes.c_uint8

        self.lib_zynmixer.setPhase.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getPhase.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getPhase.restype = ctypes.c_uint8

        self.lib_zynmixer.setNormalise.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getNormalise.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getNormalise.restype = ctypes.c_uint8

        self.lib_zynmixer.reset.argtypes = [ctypes.c_uint8]

        self.lib_zynmixer.isChannelRouted.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.isChannelRouted.restype = ctypes.c_uint8

        self.lib_zynmixer.isChannelOutRouted.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.isChannelOutRouted.restype = ctypes.c_uint8

        self.lib_zynmixer.getDpm.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getDpm.restype = ctypes.c_float

        self.lib_zynmixer.getDpmHold.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getDpmHold.restype = ctypes.c_float

        self.lib_zynmixer.getDpmStates.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8, ctypes.POINTER(ctypes.c_float)]

        self.lib_zynmixer.enableDpm.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]

        self.lib_zynmixer.getMaxChannels.restype = ctypes.c_uint8

        self.MAX_NUM_CHANNELS = self.lib_zynmixer.getMaxChannels()

        # List of learned {cc:zctrl} indexed by learned MIDI channel
        self.learned_cc = [dict() for x in range(16)]

        # List of {symbol:zctrl,...} indexed by mixer strip index
        self.zctrls = []
        for i in range(self.MAX_NUM_CHANNELS):
            strip_dict = {
                'level': zynthian_controller(self, 'level', {
                    'is_integer': False,
                    'value_max': 1.0,
                    'value_default': 0.8,
                    'value': self.get_level(i),
                    'graph_path': [i, 'level']
                }),
                'balance': zynthian_controller(self, 'balance', {
                    'is_integer': False,
                    'value_min': -1.0,
                    'value_max': 1.0,
                    'value_default': 0.0,
                    'value': self.get_balance(i),
                    'graph_path': [i, 'balance']
                }),
                'mute': zynthian_controller(self, 'mute', {
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': self.get_mute(i),
                    'graph_path': [i, 'mute']
                }),
                'solo': zynthian_controller(self, 'solo', {
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': self.get_solo(i),
                    'graph_path': [i, 'solo']
                }),
                'mono': zynthian_controller(self, 'mono', {
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': self.get_mono(i),
                    'graph_path': [i, 'mono']
                }),
                'ms': zynthian_controller(self, 'm+s', {
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': self.get_ms(i),
                    'graph_path': [i, 'ms']
                }),
                'phase': zynthian_controller(self, 'phase', {
                    'is_toggle': True,
                    'value_max': 1,
                    'value_default': 0,
                    'value': self.get_phase(i),
                    'graph_path': [i, 'phase']
                })
            }
            self.zctrls.append(strip_dict)

        self.midi_learn_zctrl = None
        self.midi_learn_cb = None

    def get_controllers_dict(self, processor):
        try:
            return self.zctrls[processor.mixer_chan]
        except:
            return None

    def get_learned_cc(self, zctrl):
        for chan in range(16):
            for cc in self.learned_cc[chan]:
                if zctrl == self.learned_cc[chan][cc]:
                    return [chan, cc]

    def send_controller_value(self, zctrl):
        try:
            getattr(self, f'set_{zctrl.symbol}')(
                zctrl.graph_path[0], zctrl.value, False)
        except Exception as e:
            logging.warning(e)

    # Function to set fader level for a channel
    # channel: Index of channel
    # level: Fader value (0..+1)
    # update: True for update controller

    def set_level(self, channel, level, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setLevel(channel, ctypes.c_float(level))
        if update:
            self.zctrls[channel]['level'].set_value(level, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="level", value=level)

    # Function to set balance for a channel
    # channel: Index of channel
    # balance: Balance value (-1..+1)
    # update: True for update controller
    def set_balance(self, channel, balance, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setBalance(channel, ctypes.c_float(balance))
        if update:
            self.zctrls[channel]['balance'].set_value(balance, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="balance", value=balance)

    # Function to get fader level for a channel
    # channel: Index of channel
    # returns: Fader level (0..+1)
    def get_level(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getLevel(channel)

    # Function to get balance for a channel
    # channel: Index of channel
    # returns: Balance value (-1..+1)
    def get_balance(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getBalance(channel)

    # Function to set mute for a channel
    # channel: Index of channel
    # mute: Mute state (True to mute)
    # update: True for update controller
    def set_mute(self, channel, mute, update=False):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setMute(channel, mute)
        if update:
            self.zctrls[channel]['mute'].set_value(mute, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="mute", value=mute)

    # Function to get mute for a channel
    # channel: Index of channel
    # returns: Mute state (True if muted)
    def get_mute(self, channel, update=False):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getMute(channel)

    # Function to toggle mute of a channel
    # channel: Index of channel
    # update: True for update controller
    def toggle_mute(self, channel, update=False):
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.toggleMute(channel)
        mute = self.lib_zynmixer.getMute(channel)
        if update:
            self.zctrls[channel]['mute'].set_value(mute, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="mute", value=mute)

    # Function to set phase reversal for a channel
    # channel: Index of channel
    # phase: Phase reversal state (True to reverse)
    # update: True for update controller
    def set_phase(self, channel, phase, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setPhase(channel, phase)
        if update:
            self.zctrls[channel]['phase'].set_value(phase, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="phase", value=phase)

    # Function to get phase reversal for a channel
    # channel: Index of channel
    # returns: Phase reversal state (True if phase reversed)
    def get_phase(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getPhase(channel)

    # Function to toggle phase reversal of a channel
    # channel: Index of channel
    # update: True for update controller
    def toggle_phase(self, channel, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.togglePhase(channel)
        phase = self.lib_zynmixer.getPhase(channel)
        if update:
            self.zctrls[channel]['phase'].set_value(phase, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="phase", value=phase)

    # Function to set solo for a channel
    # channel: Index of channel
    # solo: Solo state (True to solo)
    # update: True for update controller
    def set_solo(self, channel, solo, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setSolo(channel, solo)
        if update:
            self.zctrls[channel]['solo'].set_value(solo, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="solo", value=solo)

        if channel == self.MAX_NUM_CHANNELS - 1:
            # Main strip solo clears all chain solo
            for i in range(0, self.MAX_NUM_CHANNELS - 2):
                self.zctrls[i]['solo'].set_value(solo, 0)
                zynsigman.send(
                    zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE, chan=i, symbol="solo", value=0)

    # Function to get solo for a channel
    # channel: Index of channel
    # returns: Solo state (True if solo)
    def get_solo(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getSolo(channel) == 1

    # Function to toggle mute of a channel
    # channel: Index of channel
    # update: True for update controller
    def toggle_solo(self, channel, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        if self.get_solo(channel):
            self.set_solo(channel, False)
        else:
            self.set_solo(channel, True)

    # Function to mono a channel
    # channel: Index of channel
    # mono: Mono state (True to solo)
    # update: True for update controller
    def set_mono(self, channel, mono, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setMono(channel, mono)
        if update:
            self.zctrls[channel]['mono'].set_value(mono, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="mono", value=mono)

    # Function to get mono for a channel
    # channel: Index of channel
    # returns: Mono state (True if mono)
    def get_mono(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getMono(channel) == 1

    # Function to get all mono
    # returns: List of mono states (True if mono)
    def get_all_monos(self):
        monos = (ctypes.c_bool * (self.MAX_NUM_CHANNELS))()
        self.lib_zynmixer.getAllMono(monos)
        result = []
        for i in monos:
            result.append(i)
        return result

    # Function to toggle mono of a channel
    # channel: Index of channel
    # update: True for update controller
    def toggle_mono(self, channel, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        if self.get_mono(channel):
            self.set_mono(channel, False)
        else:
            self.set_mono(channel, True)
        if update:
            self.zctrls[channel]['mono'].set_value(
                self.lib_zynmixer.getMono(channel), False)

    # Function to enable M+S mode
    # channel: Index of channel
    # enable: M+S state (True to enable)
    # update: True for update controller

    def set_ms(self, channel, enable, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        self.lib_zynmixer.setMS(channel, enable)
        if update:
            self.zctrls[channel]['ms'].set_value(enable, False)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, self.SS_ZCTRL_SET_VALUE,
                       chan=channel, symbol="ms", value=enable)

    # Function to get M+S mode
    # channel: Index of channel
    # returns: M+S mode (True if enabled)
    def get_ms(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getMS(channel) == 1

    # Function to toggle M+S mode
    # channel: Index of channel
    # update: True for update controller
    def toggle_ms(self, channel, update=True):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        if self.get_ms(channel):
            self.set_ms(channel, False)
        else:
            self.set_ms(channel, True)
        if update:
            self.zctrls[channel]['ms'].set_value(
                self.lib_zynmixer.getMS(channel), False)

    # Function to set internal normalisation of a channel when its direct output is not routed
    # channel: Index of channel
    # enable: True to enable internal normalisation
    def normalise(self, channel, enable):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS - 1:
            return  # Don't allow normalisation of main mixbus (to itself)
        self.lib_zynmixer.setNormalise(channel, enable)

    # Function to get the internal normalisation state of s channel
    # channel: Index of channel
    # enable: True to enable internal normalisation
    # update: True for update controller
    def is_normalised(self, channel):
        if channel is None:
            return False
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getNormalise(channel)

    # Function to check if channel has audio routed to its input
    # channel: Index of channel
    # returns: True if routed
    def is_channel_routed(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return (self.lib_zynmixer.isChannelRouted(channel) != 0)

    # Function to check if channel output is routed
    # channel: Index of channel
    # returns: True if routed
    def is_channel_out_routed(self, channel):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return (self.lib_zynmixer.isChannelOutRouted(channel) != 0)

    # Function to get peak programme level for a channel
    # channel: Index of channel
    # leg: 0 for A-leg (left), 1 for B-leg (right)
    # returns: Peak programme level
    def get_dpm(self, channel, leg):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getDpm(channel, leg)

    # Function to get peak programme hold level for a channel
    # channel: Index of channel
    # leg: 0 for A-leg (left), 1 for B-leg (right)
    # returns: Peak programme hold level
    def get_dpm_holds(self, channel, leg):
        if channel is None:
            return
        if channel >= self.MAX_NUM_CHANNELS:
            channel = self.MAX_NUM_CHANNELS - 1
        return self.lib_zynmixer.getDpmHold(channel, leg)

    # Function to get the dpm states for a set of channels
    # start: Index of first channel
    # end: Index of last channel
    # returns: List of tuples containing (dpm_a, dpm_b, hold_a, hold_b, mono)
    def get_dpm_states(self, start, end):
        state = (ctypes.c_float * (5 * (end - start + 1)))()
        self.lib_zynmixer.getDpmStates(start, end, state)
        result = []
        offset = 0
        for channel in range(start, end + 1):
            l = []
            for i in range(4):
                l.append(state[offset])
                offset += 1
            l.append(state[offset] != 0.0)
            offset += 1
            result.append(l)
        return result

    # Function to enable or disable digital peak meters
    # start: First mixer channel
    # end: Last mixer channel
    # enable: True to enable
    def enable_dpm(self, start, end, enable):
        if start is None or end is None:
            return
        self.lib_zynmixer.enableDpm(start, end, int(enable))

    # Function to add OSC client registration
    # client: IP address of OSC client
    def add_osc_client(self, client):
        return self.lib_zynmixer.addOscClient(ctypes.c_char_p(client.encode('utf-8')))

    # Function to remove OSC client registration
    # client: IP address of OSC client
    def remove_osc_client(self, client):
        self.lib_zynmixer.removeOscClient(
            ctypes.c_char_p(client.encode('utf-8')))

    # --------------------------------------------------------------------------
    # State management (for snapshots)
    # --------------------------------------------------------------------------

    def reset(self, strip):
        """Reset mixer strip to default values

        strip : Index of mixer strip
        """
        if not isinstance(strip, int):
            return
        if strip >= self.MAX_NUM_CHANNELS:
            strip = self.MAX_NUM_CHANNELS - 1
        self.zctrls[strip]['level'].reset_value()
        self.zctrls[strip]['balance'].reset_value()
        self.zctrls[strip]['mute'].reset_value()
        self.zctrls[strip]['mono'].reset_value()
        self.zctrls[strip]['solo'].reset_value()
        self.zctrls[strip]['phase'].reset_value()
        # for symbol in self.zctrls[strip]:
        # self.zctrls[strip][symbol].midi_unlearn()

    # Reset mixer to default state
    def reset_state(self):
        for channel in range(self.MAX_NUM_CHANNELS):
            self.reset(channel)

    def get_state(self, full=True):
        """Get mixer state as list of controller state dictionaries

        full : True to get state of all parameters or false for off-default values
        Returns : List of dictionaries describing parameter states
        """
        state = {}
        for chan in range(self.MAX_NUM_CHANNELS):
            key = 'chan_{:02d}'.format(chan)
            chan_state = {}
            for symbol in self.zctrls[chan]:
                zctrl = self.zctrls[chan][symbol]
                value = zctrl.value
                if zctrl.is_toggle:
                    value |= (zctrl.midi_cc_momentary_switch << 1)
                if value != zctrl.value_default:
                    chan_state[zctrl.symbol] = value
            if chan_state:
                state[key] = chan_state
            state["midi_learn"] = {}
            for chan in range(16):
                for cc, zctrl in self.learned_cc[chan].items():
                    state["midi_learn"][f"{chan},{cc}"] = zctrl.graph_path
        return state

    def set_state(self, state, full=True):
        """Set mixer state

        state : List of mixer channels containing dictionary of each state value
        full : True to reset parameters omitted from state
        """

        for chan, zctrls in enumerate(self.zctrls):
            key = 'chan_{:02d}'.format(chan)
            for symbol, zctrl in zctrls.items():
                try:
                    if zctrl.is_toggle:
                        zctrl.set_value(state[key][symbol] & 1, True)
                        zctrl.midi_cc_momentary_switch = state[key][symbol] >> 1
                    else:
                        zctrl.set_value(state[key][symbol], True)
                except:
                    if full:
                        zctrl.reset_value()
        if "midi_learn" in state:
            # state["midi_learn"][f"{chan},{cc}"] = zctrl.graph_path
            self.midi_unlearn_all()
            for ml, graph_path in state["midi_learn"].items():
                try:
                    chan, cc = ml.split(',')
                    zctrl = self.zctrls[graph_path[0]][graph_path[1]]
                    self.learned_cc[int(chan)][int(cc)] = zctrl
                except Exception as e:
                    logging.warning(
                        f"Failed to restore mixer midi learn: {ml} => {graph_path} ({e})")

    # --------------------------------------------------------------------------
    # MIDI Learn
    # --------------------------------------------------------------------------

    def midi_control_change(self, chan, ccnum, val):
        if self.midi_learn_zctrl and self.midi_learn_zctrl != True:
            for midi_chan in range(16):
                for midi_cc in self.learned_cc[midi_chan]:
                    if self.learned_cc[midi_chan][midi_cc] == self.midi_learn_zctrl:
                        self.learned_cc[midi_chan].pop(midi_cc)
                        break
            self.learned_cc[chan][ccnum] = self.midi_learn_zctrl
            self.disable_midi_learn()
            if self.midi_learn_cb:
                self.midi_learn_cb()
        else:
            for ch in range(16):
                try:
                    self.learned_cc[ch][ccnum].midi_control_change(val)
                    break
                except:
                    pass

    def midi_unlearn(self, zctrl):
        for chan, learned in enumerate(self.learned_cc):
            for cc, ctrl in learned.items():
                if ctrl == zctrl:
                    self.learned_cc[chan].pop(cc)
                    return

    def midi_unlearn_chan(self, chan):
        for zctrl in self.zctrls[chan].values():
            self.midi_unlearn(zctrl)

    def midi_unlearn_all(self, not_used=None):
        self.learned_cc = [dict() for x in range(16)]

    def enable_midi_learn(self, zctrl):
        self.midi_learn_zctrl = zctrl

    def disable_midi_learn(self):
        self.midi_learn_zctrl = None

    def set_midi_learn_cb(self, cb):
        self.midi_learn_cb = cb

# -------------------------------------------------------------------------------
