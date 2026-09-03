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

import math
import ctypes
import logging

from zyngine.zynthian_signal_manager import zynsigman

# -------------------------------------------------------------------------------
# Zynmixer Library Wrapper and processor
# -------------------------------------------------------------------------------

MIN_GAIN = -120.0
MAX_GAIN = 40.0

class DPM(ctypes.Structure):
    _fields_ = [
        ("a", ctypes.c_float),
        ("b", ctypes.c_float),
        ("a_hold", ctypes.c_float),
        ("b_hold", ctypes.c_float),
        ("mono", ctypes.c_uint8)
    ]

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

        self.lib_zynmixer.setGain.argtypes = [ctypes.c_uint8, ctypes.c_float]
        self.lib_zynmixer.getGain.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getGain.restype = ctypes.c_float

        self.lib_zynmixer.setBalance.argtypes = [ctypes.c_uint8, ctypes.c_float]
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

        if not self.mixbus:
            self.lib_zynmixer.setGlobalXFader.argtypes = [ctypes.c_float]
            self.lib_zynmixer.getGlobalXFader.restype = ctypes.c_float
            self.lib_zynmixer.setABMixGroup.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
            self.lib_zynmixer.getABMixGroup.argtypes = [ctypes.c_uint8]
            self.lib_zynmixer.getABMixGroup.restype = ctypes.c_uint8
        else:
            self.lib_zynmixer.setPflLevel.argtypes = [ctypes.c_float]
            self.lib_zynmixer.getPflLevel.restype = ctypes.c_float

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

        self.lib_zynmixer.setNormalise.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getNormalise.argtypes = [ctypes.c_uint8]
        self.lib_zynmixer.getNormalise.restype = ctypes.c_uint8

        self.lib_zynmixer.reset.argtypes = [ctypes.c_uint8]

        self.lib_zynmixer.getDpm.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getDpm.restype = ctypes.c_float

        self.lib_zynmixer.getDpmHold.argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        self.lib_zynmixer.getDpmHold.restype = ctypes.c_float

        self.lib_zynmixer.updateDpmStates.argtypes = [ctypes.POINTER(DPM), ctypes.c_uint8]

        self.lib_zynmixer.getMaxChannels.restype = ctypes.c_uint8

        self.MAX_NUM_CHANNELS = self.lib_zynmixer.getMaxChannels()
        self.dpm = (DPM * self.MAX_NUM_CHANNELS)()

    def norm_to_db(self, value: float):
        """ Convert linear normalized range to dB range.
        Args:
            value: Linear normalized value
        Returns:
            Value in dB (0.0 maps to MIN_GAIN not -inf)
        """

        if value <= 0.0:
            return MIN_GAIN
        db = 20.0 * math.log10(value)
        return max(db, MIN_GAIN)

    def db_to_norm(self, db: float):
        """ Convert dB to linear normalized range
        Args:
            db: Value in dB
        Returns:
            Normalised value, e.g. 0dB == 1.0.
        """

        if db <= MIN_GAIN:
            return 0.0
        return 10.0 ** (db / 20.0)

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

    def set_gain(self, channel, gain):
        """
        Sets the gain of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        level : float
            Value of gain in +/-dB
        """

        if channel is None:
            return
        gain = self.db_to_norm(gain)

        self.lib_zynmixer.setGain(channel, ctypes.c_float(gain))
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="gain", value=gain, mixbus=self.mixbus)

    def get_gain(self, channel):
        """
        Gets the gain of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip

        Returns
        -------
        float
            Gain in +/-dB
        """

        if channel is None:
            return

        gain = self.lib_zynmixer.getGain(channel)
        return self.norm_to_db(gain)

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="level", value=level, mixbus=self.mixbus)

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="balance", value=balance, mixbus=self.mixbus)

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="mute", value=mute, mixbus=self.mixbus)

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

    def set_solo(self, channel, solo):
        """
        Sets the solo of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        solo : bool
            True to solo, False to unsolo
        """

        if channel is None:
            return
        self.lib_zynmixer.setSolo(channel, solo)
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="solo", value=solo, mixbus=self.mixbus)

    def get_solo(self, channel):
        """
        Gets the solo state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip

        Returns
        -------
        bool
            True if solo enabled, False if disabled
        """

        if channel is None:
            return
        return self.lib_zynmixer.getSolo(channel)

    def toggle_solo(self, channel):
        """
        Toggle the solo state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of of the mixer strip
        """

        self.lib_zynmixer.toggleSolo(channel)

    def clear_solo(self):
        self.lib_zynmixer.clearSolo()

    def get_global_solo(self):
        return self.lib_zynmixer.getGlobalSolo()

    def set_pfl(self, channel, pfl):
        """
        Sets the PFL of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip
        pfl : bool
            True to PFL, False to unPFL
        """

        if channel is None:
            return
        self.lib_zynmixer.setPfl(channel, pfl)
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="pfl", value=pfl, mixbus=self.mixbus)

    def get_pfl(self, channel):
        """
        Gets the PFL state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of the mixer strip

        Returns
        -------
        bool
            True if PFL enabled, False if disabled
        """

        if channel is None:
            return
        return self.lib_zynmixer.getPfl(channel)

    def toggle_pfl(self, channel):
        """
        Toggle the PFL state of a mixer strip

        Parameters
        ----------
        channel : int
            Index of of the mixer strip
        """

        self.lib_zynmixer.togglePfl(channel)

    def clear_pfl(self):
        self.lib_zynmixer.clearPfl()

    def set_pfl_level(self, level):
        """ Set the volumne level of PFL output
        Args:
        level: Normalised volume level factor
        """

        if self.mixbus:
            self.lib_zynmixer.setPflLevel(level)

    def get_pfl_level(self):
        """ Get the volumne level of PFL output
        Returns: Normalised volume level factor
        """

        if self.mixbus:
            return self.lib_zynmixer.getPflLevel()
        return 0

    def get_global_pfl(self):
        return self.lib_zynmixer.getGlobalPfl()

    def set_global_xfader(self, val):
        if not self.mixbus:
            self.lib_zynmixer.setGlobalXFader(val)
            zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                        chan=0, symbol="global_xfader", value=val, mixbus=self.mixbus)
        else:
            logging.warning("Function not implemented in MixBuses!")

    def get_global_xfader(self):
        if not self.mixbus:
            return self.lib_zynmixer.getGlobalXFader()
        else:
            logging.warning("Function not implemented in MixBuses!")
            return 0.0

    def set_ab_mixgroup(self, channel, abmix):
        if not self.mixbus:
            self.lib_zynmixer.setABMixGroup(channel, abmix)
            zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                        chan=channel, symbol="ab_mixgroup", value=abmix, mixbus=self.mixbus)
        else:
            logging.warning("Function not implemented in MixBuses!")

    def get_ab_mixgroup(self, channel):
        if not self.mixbus:
            return self.lib_zynmixer.getABMixGroup(channel)
        else:
            logging.warning("Function not implemented in MixBuses!")
            return 0

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="phase", value=phase, mixbus=self.mixbus)

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

    def set_record(self, channel, record):
        # State handled entirely by zctrl
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
            chan=channel, symbol="record", value=record, mixbus=self.mixbus)

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="send_mode", value=mode, mixbus=self.mixbus)

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="mono", value=mono, mixbus=self.mixbus)

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
        zynsigman.send(zynsigman.S_MIXER, zynsigman.SS_ZYNMIXER_SET_VALUE,
                       chan=channel, symbol="ms", value=enable, mixbus=self.mixbus)

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

    def set_send_level(self, channel, send, level):
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

    def get_send_level(self, channel, send):
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

    def update_dpm_states(self, count=0):
        """
        Updates peak programme level state of a range of mixer strips

        Parameters
        ----------
        count : int
            Quantity of mixer strips (default: 0 for all)
        """

        self.lib_zynmixer.updateDpmStates(self.dpm, count)

    def enable_dpm(self, enable):
        """
        Enable or disable peak programme meter

        Parameters
        ----------
        enable : bool
            True to enable DPM, False to disable
        Note: Main mixbus is always enabled
        """

        self.lib_zynmixer.enableDpm(int(enable))

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
