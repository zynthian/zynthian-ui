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
from zyngine.zynthian_signal_manager import zynsigman

# -------------------------------------------------------------------------------
# Zynmixer Library Wrapper and processor
# -------------------------------------------------------------------------------

# Subsignals are defined inside each module. Here we define audio_mixer subsignals:
SS_ZYNMIXER_SET_VALUE = 1

class ZynMixer():
    """
    A class representing an instance of a zynmixer, audio mixer library.
    """

    # Function to initialize library
    def __init__(self, is_mixbus=False):
        self.mixbus = is_mixbus
        if is_mixbus:
            self.lib_zynmixer = ctypes.cdll.LoadLibrary(
                f"/zynthian/zynthian-ui/zynlibs/zynmixer/build/libzynmixer_mixbus.so")
        else:
            self.lib_zynmixer = ctypes.cdll.LoadLibrary(
                f"/zynthian/zynthian-ui/zynlibs/zynmixer/build/libzynmixer.so")

        self.lib_zynmixer.addStrip.restype = ctypes.c_int8
        self.lib_zynmixer.removeStrip.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.removeStrip.restype = ctypes.c_int8

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

        self.lib_zynmixer.setMono.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getMono.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getMono.restype = ctypes.c_uint8

        self.lib_zynmixer.setPhase.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getPhase.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getPhase.restype = ctypes.c_uint8

        self.lib_zynmixer.setSendMode.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getSendMode.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getSendMode.restype = ctypes.c_uint8

        self.lib_zynmixer.addSend.restype = ctypes.c_int

        self.lib_zynmixer.removeSend.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.removeSend.restype = ctypes.c_uint8

        self.lib_zynmixer.setSend.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float]
        self.lib_zynmixer.getSend.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getSend.restype = ctypes.c_float

        self.lib_zynmixer.setNormalise.argtypes = [
            ctypes.c_uint8]
        self.lib_zynmixer.getNormalise.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getNormalise.restype = ctypes.c_uint8

        self.lib_zynmixer.reset.argtypes = [ctypes.c_uint8]

        self.lib_zynmixer.getDpm.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getDpm.restype = ctypes.c_float

        self.lib_zynmixer.getDpmHold.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getDpmHold.restype = ctypes.c_float

        self.lib_zynmixer.getDpmStates.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8, ctypes.POINTER(ctypes.c_float)]

        self.lib_zynmixer.enableDpm.argtypes = [
            ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]

        self.lib_zynmixer.getMaxChannels.restype = ctypes.c_uint8

        self.MAX_NUM_CHANNELS = self.lib_zynmixer.getMaxChannels()

    def add_strip(self):
        """
        Adds a mixer strip to the mixer

        Returns
        -------
        int
            Index of strip or -1 on failure

        """
        
        return self.lib_zynmixer.addStrip()

    def remove_strip(self, chan):
        """
        Removes a mixer channel strip from the mixer
        
        Parameters
        ----------
        chan : int
            Index of the mixer channel strip to remove
        
        Returns
        -------
        int
            Index of strip or -1 on failure
        """

        return self.lib_zynmixer.removeStrip(chan)

    def add_send(self):
        """
        Adds an effect send to the mixer

        Returns
        -------
        int
            Index of send or -1 on failure

        """
        
        return self.lib_zynmixer.addSend()

    def remove_send(self, send):
        """
        Removes an effect send from the mixer
        
        Parameters
        ----------
        send : int
            Index of the effect send to remove
        
        Returns
        -------
        int
            Index of send or -1 on failure
        """

        return self.lib_zynmixer.removeSend(send)

    def get_send_count(self):
        """
        Get the quantity of effect sends
        
        Returns
        -------
        int
            Qauntity of effect sends
        """

        return self.lib_zynmixer.getSendCount()

    def set_level(self, channel, level):
        """
        Sets the fader level of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        level : float
            Value of level (0..1.0)
        """

        if channel is None:
            return
        self.lib_zynmixer.setLevel(channel, ctypes.c_float(level))
        zynsigman.send(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE,
            mixbus=self.mixbus, chan=channel, symbol="level", value=level)

    def get_level(self, channel):
        """
        Gets the fader level of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        float
            Fader level (0..1.0)
        """

        if channel is None:
            return
        return self.lib_zynmixer.getLevel(channel)

    def set_balance(self, channel, balance):
        """
        Sets the balance of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        balance : float
            Value of balance (-1.0..1.0)
        """

        if channel is None:
            return
        self.lib_zynmixer.setBalance(channel, balance)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE,
            mixbus=self.mixbus, chan=channel, symbol="balance", value=balance)

    def get_balance(self, channel):
        """
        Gets the balance of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        float
            Balance level (-1.0..1.0)
        """
        if channel is None:
            return
        return self.lib_zynmixer.getBalance(channel)

    def set_mute(self, channel, mute):
        """
        Sets the mute of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        mute : bool
            True to mute, False to unmute
        """

        if channel is None:
            return
        self.lib_zynmixer.setMute(channel, mute)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE,
            mixbus=self.mixbus, chan=channel, symbol="mute", value=mute)

    # Function to get mute for a channel
    # channel: Index of channel
    # returns: Mute state (True if muted)
    def get_mute(self, channel):
        """
        Gets the mute state of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        bool
            True if mute enabled, False if disabled
        """

        if channel is None:
            return
        return self.lib_zynmixer.getMute(channel)

    def toggle_mute(self, channel):
        """
        Toggle the mute state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of of the mixer strip
        """

        self.lib_zynmixer.toggleMute(channel)

    def set_phase(self, channel, phase):
        """
        Sets the phase reverse of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        phase : bool
            True to phase reverse, False for normal
        """

        if channel is None:
            return
        self.lib_zynmixer.setPhase(channel, phase)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE,
            mixbus=self.mixbus, chan=channel, symbol="phase", value=phase)

    def get_phase(self, channel):
        """
        Gets the phase reverse state of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        bool
            True if phase reverse enabled, False if disabled
        """

        if channel is None:
            return
        return self.lib_zynmixer.getPhase(channel)

    def toggle_phase(self, channel):
        """
        Toggle the phase reverse state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of of the mixer strip
        """

        if channel is None:
            return
        self.lib_zynmixer.togglePhase(channel)

    def set_send_mode(self, channel, send, mode):
        """
        Sets the effect send mode of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        send : int
            Index of the send
        mode : int
            0: post fader, 1: pre fader
        """

        if channel is None or 0 >= mode > 1:
            return
        self.lib_zynmixer.setSendMode(channel, send, mode)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE,
            mixbus=self.mixbus, chan=channel, symbol="send_mode", value=mode)

    def get_send_mode(self, channel, send):
        """
        Gets the effect send mode of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        send : int
            Index of the send
        
        Returns
        -------
        int
            0: post fader, 1: pre fader
        """

        if channel is None:
            return
        return self.lib_zynmixer.getSendMode(channel, send)

    def set_mono(self, channel, mono):
        """
        Sets the mono state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        mono : bool
            True to for mono, False for stereo
        """

        if channel is None:
            return
        self.lib_zynmixer.setMono(channel, mono)
        zynsigman.send(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE,
            mixbus=self.mixbus, chan=channel, symbol="mono", value=mono)

    def get_mono(self, channel):
        """
        Gets the mono state of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        bool
            True if mono, False if stereo
        """

        if channel is None:
            return
        return self.lib_zynmixer.getMono(channel)

    def get_all_monos(self):
        """
        Gets the mono state of all mixer strips
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        list
            A list of bools indicating the mono state of each strip
        """
        monos = (ctypes.c_bool * (self.MAX_NUM_CHANNELS))()
        self.lib_zynmixer.getAllMono(monos)
        result = []
        for i in monos:
            result.append(i)
        return result

    def toggle_mono(self, channel):
        """
        Toggle the mono state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of of the mixer strip
        """

        if channel is None:
            return
        if self.get_mono(channel):
            self.set_mono(channel, False)
        else:
            self.set_mono(channel, True)

    def set_ms(self, channel, enable):
        """
        Sets the M+S state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        enable : bool
            True to enable M+S, False to disable
        """

        if channel is None:
            return
        self.lib_zynmixer.setMS(channel, enable)

    def get_ms(self, channel):
        """
        Gets the M+S state of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        bool
            True if M+S enabled, False if disabled
        """
        if channel is None:
            return
        return self.lib_zynmixer.getMS(channel) == 1

    def toggle_ms(self, channel):
        """
        Toggle the M+S state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of of the mixer strip
        """

        if channel is None:
            return
        self.set_ms(channel, not self.get_ms(channel))

    def set_send(self, channel, send, level):
        """
        Sets an effect send level of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        send : int
            Index of the effect send
        level : float
            Value of level (0..1.0)
        """

        if channel is None or send is None:
            return
        self.lib_zynmixer.setSend(channel, send, level)

    def get_send(self, channel, send):
        """
        Gets a send level of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        send : int
            Index of the send
        
        Returns
        -------
        float
            Value of the send level (0..1.0)
        """

        if channel is None or send is None:
            return
        return self.lib_zynmixer.getSend(channel, send)

    def normalise(self, channel, enable):
        """
        Sets the internal normalisation to strip 0 of a mixer strip (only on buses)

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        enable : bool
            True to internally route strip to strip 0 (main mixbus), False to disable this normalisation
        """

        if channel is None:
            return
        self.lib_zynmixer.setNormalise(channel, enable)

    def is_normalised(self, channel):
        """
        Gets the internal normalised routig state of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        
        Returns
        -------
        bool
            True if normalised routing to strip 0 (main mixbus), False if disabled
        """

        if channel is None:
            return False
        return self.lib_zynmixer.getNormalise(channel) == 1

    def get_dpm(self, channel, leg):
        """
        Gets peak programme level of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        leg : int
            0 for A-leg (left), 1 for B-leg (right)
        
        Returns
        -------
        float
            Peak programme level (dBFS)
        """

        if channel is None:
            return
        return self.lib_zynmixer.getDpm(channel, leg)

    def get_dpm_holds(self, channel, leg):
        """
        Gets peak programme hold level of a mixer strip
        
        Parameters
        ----------
        channel : int
            Index of the mixer strip
        leg : int
            0 for A-Leg (left), 1 for B-leg (right)
        
        Returns
        -------
        float
            Peak progamme hold level (dBFS)
        """

        if channel is None:
            return
        return self.lib_zynmixer.getDpmHold(channel, leg)

    def get_dpm_states(self, start, end):
        """
        Gets peak programme level state of a range of mixer strips
        
        Parameters
        ----------
        start : int
            Index of the first mixer strip
        end : int
            Index of the last mixer strip
        
        Returns
        -------
        list
            A list of tuples containing (dpm_a, dpm_b, hold_a, hold_b, mono)
        """

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

    def enable_dpm(self, start, end, enable):
        """
        Enable or disable peak programme meter of a range of mixer strips

        Parameters
        ----------
        start : int
            Index of the first mixer strip
        end : int
            Index of the last mixer strip
        enable : bool
            True to enable DPM, False to disable
        """

        if start is None or end is None:
            return
        self.lib_zynmixer.enableDpm(start, end, enable, int(enable))

    # Function to add OSC client registration
    # client: IP address of OSC client
    def add_osc_client(self, client):
        return self.lib_zynmixer.addOscClient(ctypes.c_char_p(client.encode('utf-8')))

    # Function to remove OSC client registration
    # client: IP address of OSC client
    def remove_osc_client(self, client):
        self.lib_zynmixer.removeOscClient(
            ctypes.c_char_p(client.encode('utf-8')))

    def reset(self):
        for channel in range(self.MAX_NUM_CHANNELS):
            self.lib_zynmixer.reset(channel, False)
            self.lib_zynmixer.reset(channel, True)

# -------------------------------------------------------------------------------
