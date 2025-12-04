#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#                         Oscar Acena <oscaracena@gmail.com>
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

import signal
import logging
import traceback
from time import sleep
import multiprocessing as mp

mp.set_start_method('fork')

import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman
from zynlibs.zynmixer.zynmixer import SS_ZYNMIXER_SET_VALUE
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Control device base class
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_base:

    dev_ids = []			# String list that could identify the device
    dev_id = None  			# String that identifies the device
    fb_dev_id = None		# Index of zmop connected to controller input
    dev_zynpad = False		# Can act as a zynpad trigger device
    dev_zynmixer = False    # Can act as an audio mixer controller device
    dev_pated = False		# Can act as a pattern editor device
    enabled = False			# True if device driver is enabled
    autoload_flag = True    # False to prevent autoloading the driver when device is detected
    # True if input device must be unrouted from chains when driver is loaded
    # Alternately specific MIDI channels can be unrouted by specifying a bitwise mask,
    # For instance, use "0b0000000000001111" to unroute MIDI channels 0 to 3.
    unroute_from_chains = True

    driver_name = None
    driver_description = None

    @classmethod
    def get_autoload_flag(cls):
        return cls.autoload_flag

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.state_manager = state_manager
        self.chain_manager = state_manager.chain_manager
        # Slot index where the input device is connected, starting from 1 (0 = None)
        self.idev = idev_in
        # Slot index where the output device (feedback), if any, is connected, starting from 1 (0 = None)
        self.idev_out = idev_out
        # OPTIONAL: real-time MIDI processor (jack client), inserted between the input device and zmip
        self.midiproc_jackname = None
        self.midiproc = None

    # Returns the driver name
    @classmethod
    def get_driver_name(cls):
        if cls.driver_name is None:
            return cls.__name__[17:]
        else:
            return cls.driver_name

    # Returns the driver description
    @classmethod
    def get_driver_description(cls):
        return cls.driver_description

    # Send SysEx universal inquiry.
    # It's answered by some devices with a SysEx message.
    def send_sysex_universal_inquiry(self):
        if self.idev_out > 0:
            msg = bytes.fromhex("F0 7E 7F 06 01 F7")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

    # Initialize control device: setup, register signals, etc
    # It *SHOULD* be implemented by child class
    def init(self):
        self.init_midiproc()
        self.refresh()

    # End control device: restore initial state, unregister signals, etc
    # It *SHOULD* be implemented by child class
    def end(self):
        self.end_midiproc()

    # Spawn midiproc task using multiprocessing API
    def init_midiproc(self):
        midiproc_task = getattr(self, "midiproc_task", None)
        if callable(midiproc_task):
            try:
                self.midiproc_jackname = "midiproc_" + self.get_driver_name()
                self.midiproc = mp.Process(target=midiproc_task, args=(self.midiproc_jackname,))
                self.midiproc.start()
                zynautoconnect.request_midi_connect()
            except Exception as e:
                self.midiproc = None
                self.midiproc_jackname = None
                logging.exception(traceback.format_exc())
                #logging.error(e)

    # Terminate middings process
    def end_midiproc(self):
        if self.midiproc:
            try:
                self.midiproc.terminate()
                self.midiproc.join()
                sleep(0.1)
                self.midiproc = None
                zynautoconnect.request_midi_connect()
            except Exception as e:
                logging.error(e)

    # The midiproc task itself. It runs in a spawned process.
    # It must call self._midiproc_task() to reset signal handlers
    # *COULD* be implemented by child class
    # def midiproc_task(self):
    #    self.midiproc_task_reset_signal_handlers()
    #    # Implementation goes here!

    # Reset process signal handlers.
    # It *MUST* be called from midiproc_task, running in a spawned process.
    @staticmethod
    def midiproc_task_reset_signal_handlers():
        signal.signal(signal.SIGHUP, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGQUIT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    # Refresh full device status (LED feedback, etc)
    # *COULD* be implemented by child class
    def refresh(self):
        pass
        #logging.debug(f"Refresh LEDs for {type(self).__name__}: NOT IMPLEMENTED!")

    # Device MIDI event handler
    # *COULD* be implemented by child class
    def midi_event(self, ev):
        return False
        #logging.debug(f"MIDI EVENT for '{type(self).__name__}'")

    # Light-Off LEDs
    # *COULD* be implemented by child class
    def light_off(self):
        pass
        #logging.debug(f"Lighting Off LEDs for {type(self).__name__}: NOT IMPLEMENTED!")

    # Sleep On
    # *COULD* be improved by child class
    def sleep_on(self):
        self.light_off()

    # Sleep Off
    # *COULD* be improved by child class
    def sleep_off(self):
        self.refresh()

    # Return driver's state dictionary
    # *COULD* be implemented by child class
    def get_state(self):
        return None

    # Restore driver's state
    # *COULD* be implemented by child class
    def set_state(self, state):
        pass


# ------------------------------------------------------------------------------------------------------------------
# Zynpad control device base class
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_zynpad(zynthian_ctrldev_base):

    dev_zynpad = True		# Can act as a zynpad trigger device

    def __init__(self, state_manager, idev_in, idev_out=None):
        self.cols = 8
        self.rows = 8
        self.scroll_v = 0  # Offset of first row of pads
        self.zynseq = state_manager.zynseq
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        super().init()
        # Register for zynseq updates
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.update_seq_state)
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.refresh)
        # Register for chain add/remove
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_ADD_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
        # Register for snapshot loading
        zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_SNAPSHOT, self.refresh)

    def end(self):
        # Unregister for snapshot loading
        zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_SNAPSHOT, self.refresh)
        # Unregister from processor tree changes
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_ADD_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
        # Unregister from zynseq updates
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.update_seq_state)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.refresh)
        # Light off
        self.light_off()
        super().end()

    def update_seq_state(self, phrase, chan):
        """Update hardware indicators for a sequence (pad): playing state etc.
        *SHOULD* be implemented by child class

        phrase - phrase index (row)
        chan - chan index (col)
        state - sequence's state
        mode - sequence's mode
        """
        logging.debug(f"Update sequence playing state for {type(self).__name__}: NOT IMPLEMENTED!")

    def pad_off(self, col, row):
        """Light-Off the pad specified with column & row
        *SHOULD* be implemented by child class
        """
        pass

    def refresh(self):
        """Refresh full device status (LED feedback, etc)
        *COULD* be implemented by child class
        """
        if self.idev_out is None:
            return
        self.light_off()
        for row in range(self.rows):
            phrase = row + self.scroll_v
            for col in range(self.cols):
                chan = self.zynseq.get_chan_from_col(col)
                self.update_seq_state(phrase, chan)
            self.update_seq_state(phrase, zynseq.PHRASE_CHANNEL)

# ------------------------------------------------------------------------------------------------------------------
# Zynmixer control device base class
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_zynmixer(zynthian_ctrldev_base):

    dev_zynmixer = True		# Can act as a zynmixer trigger device

    def __init__(self, state_manager, idev_in, idev_out=None):
        self.zynmixer = state_manager.zynmixer_chan
        self.zynmixer_bus = state_manager.zynmixer_bus
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        super().init()
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_mixer_active_chain)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_mixer_strip)

    def end(self):
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_mixer_active_chain)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_AUDIO_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_mixer_strip)
        self.light_off()
        super().end()

    def update_mixer_strip(self, chan, symbol, value, mixbus=False):
        """Update hardware indicators for a mixer strip: mute, solo, level, balance, etc.
        *SHOULD* be implemented by child class

        chan - Mixer strip index
        symbol - Control name
        value - Control value
        mixbus - True for mixbus mixer. False for chain mixer. (Default: False)
        """
        logging.debug(f"Update mixer strip for {type(self).__name__}: NOT IMPLEMENTED!")

    def update_mixer_active_chain(self, active_chain):
        """Update hardware indicators for active_chain
        *SHOULD* be implemented by child class

        active_chain - Active chain
        """
        logging.debug(f"Update mixer active chain for {type(self).__name__}: NOT IMPLEMENTED!")

    def set_mixer_param(self, param, pos, value):
        """Set a mixer parameter value

        param - Symbol name of the parameter
        pos - Chain display position (-1 for main chain)
        value - Parameter value
        """

        if pos < 0:
            chain = self.chain_manager.chains[0]
        else:
            chain = self.chain_manager.get_chain_by_position(pos, midi=False)
        if chain:
            try:
                chain.zynmixer_proc.controllers_dict[param].set_value(value)
            except:
                logging.warning(f"Failed to set {param} to {value}")

    def get_mixer_param(self, param, pos):
        """Get a mixer parameter value

        param - Symbol name of the parameter
        pos - Chain display position (-1 for main chain)
        Returns - Parameter value
        """

        if pos < 0:
            chain = self.chain_manager.chains[0]
        else:
            chain = self.chain_manager.get_chain_by_position(pos, midi=False)
        if chain:
            try:
                return chain.zynmixer_proc.controllers_dict[param].get_value()
            except:
                logging.warning(f"Failed to get {param}")
        return 0

    def toggle_mixer_param(self, param, pos):
        """Toggle chain mute

        param - Symbol name of the parameter
        pos - Chain display position (-1 for main chain)
        return - mute state
        """
        if pos < 0:
            chain = self.chain_manager.chains[0]
        else:
            chain = self.chain_manager.get_chain_by_position(pos, midi=False)
        if chain:
            try:
                chain.zynmixer_proc.controllers_dict[param].toggle()
                return chain.zynmixer_proc.controllers_dict[param].value
            except:
                logging.warning(f"Failed to toggle {param}")
        return 0

# --------------------------------------------------------------------------
