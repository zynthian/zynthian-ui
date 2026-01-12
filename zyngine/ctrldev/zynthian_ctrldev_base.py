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

    SCROLL_MODE_CTRL    = 0
    SCROLL_MODE_GUI_SEL = 1
    SCROLL_MODE_GUI_VIEW = 2
    SCROLL_MODE_NONE    = 3

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
        """Returns autoload flag value"""

        return cls.autoload_flag

    def __init__(self, state_manager, idev_in, idev_out=None):
        """Class Constructor

        state_manager - state manager object
        idev_in - integer
        idev_out - integer
        """

        self.state_manager = state_manager
        self.chain_manager = state_manager.chain_manager
        self.zynseq = state_manager.zynseq

        # Slot index where the input device is connected, starting from 1 (0 = None)
        self.idev = idev_in
        # Slot index where the output device (feedback), if any, is connected, starting from 1 (0 = None)
        self.idev_out = idev_out
        # Filtered chain list
        self.chain_ids_filtered = []
        self.chain_type_filter = []  # List of chain types to include (empty for all) => [midi, audio, synth, generator]
        # OPTIONAL: real-time MIDI processor (jack client), inserted between the input device and zmip
        self.midiproc_jackname = None
        self.midiproc = None
        self.cols = 0 # Quantity of columns of controllers, usually mapped to chains
        self.rows = 0 # Quantity of rows of controllers, usually mapped to phrases
        self.scroll_h = 0 # Offset of first column / chain
        self.scroll_v = 0 # Offset of first phrase / row of pads
        self.set_scroll_mode(self.SCROLL_MODE_GUI_SEL)
        self.scroll_bank_mode = False # TODO: Implement ctrl scrolls by whole banks of cols/rows

    @classmethod
    def get_driver_name(cls):
        """Returns the driver name"""

        if cls.driver_name is None:
            return cls.__name__[17:]
        else:
            return cls.driver_name

    @classmethod
    def get_driver_description(cls):
        """Returns the driver description"""

        return cls.driver_description

    def send_sysex_universal_inquiry(self):
        """Send SysEx universal inquiry.
        It's answered by some devices with a SysEx message."""

        if self.idev_out > 0:
            msg = bytes.fromhex("F0 7E 7F 06 01 F7")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

    def init(self):
        """Initialize control device: setup, register signals, etc
        It *SHOULD* be implemented by child class"""

        self.init_midiproc()
        self.refresh()

        # Register for chain add/remove
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_ADD_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)
        # Register for snapshot loading
        zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_SNAPSHOT, self.refresh)

    def end(self):
        """End control device: restore initial state, unregister signals, etc
        It *SHOULD* be implemented by child class"""

        # Unregister for snapshot loading
        zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_LOAD_SNAPSHOT, self.refresh)
        # Unregister from processor tree changes
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_ADD_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_CHAIN, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_REMOVE_ALL_CHAINS, self.refresh)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.refresh)

        self.end_midiproc()

    def init_midiproc(self):
        """Spawn midiproc task using multiprocessing API"""

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

    def end_midiproc(self):
        """Terminate middings process"""

        if self.midiproc:
            try:
                self.midiproc.terminate()
                self.midiproc.join()
                sleep(0.1)
                self.midiproc = None
                zynautoconnect.request_midi_connect()
            except Exception as e:
                logging.error(e)

    # def midiproc_task(self):
    #    """The midiproc task itself. It runs in a spawned process.
    #    It must call self._midiproc_task() to reset signal handlers
    #    *COULD* be implemented by child class"""
    #
    #    self.midiproc_task_reset_signal_handlers()
    #    # Implementation goes here!

    @staticmethod
    def midiproc_task_reset_signal_handlers():
        """Reset process signal handlers.
        It *MUST* be called from midiproc_task, running in a spawned process."""

        signal.signal(signal.SIGHUP, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGQUIT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    def get_num_filtered_chains(self):
        return len(self.chain_ids_filtered)

    def get_filtered_chain_id_by_index(self, index):
        """Get filtered chain ID by index

        index - Index in filtered chain list
        return: integer
        """

        try:
            return self.chain_ids_filtered[index]
        except:
            return None

    def get_filtered_chain_by_index(self, index):
        """Get filtered chain by index

        index - Index in filtered chain list
        return: chain
        """

        try:
            return self.chain_manager.chains[self.chain_ids_filtered[index]]
        except:
            return None

    def get_filtered_index_by_chain(self, chain):
        """Get index of chain in the filtered chain list

        chain - chain to find in filtered list
        return: integer
        """
        try:
            return self.chain_ids_filtered.index(chain.chain_id)
        except:
            return -1

    def get_filtered_index_by_chain_id(self, chain_id):
        """Get index of chain in the filtered chain list

        chain - chain to find in filtered list
        return: integer
        """
        try:
            return self.chain_ids_filtered.index(chain_id)
        except:
            return -1

    def get_filtered_midi_chan_by_index(self, index):
        """Get filtered chain MIDI channel by index"""
        try:
            return self.chain_manager.chains[self.chain_ids_filtered[index]].midi_chan
        except:
            return None

    def refresh(self):
        """Refresh full device status (LED feedback, etc)
        *COULD* be implemented by child class
        """

        self.chain_ids_filtered = self.chain_manager.get_chain_ids_filtered(self.chain_type_filter)
        logging.debug(f"Filtered Chains {self.chain_type_filter}: {self.chain_ids_filtered}")

    def midi_event(self, ev):
        """Device MIDI event handler
        *COULD* be implemented by child class
        """

        return False
        #logging.debug(f"MIDI EVENT for '{type(self).__name__}'")

    def light_off(self):
        """Light-Off LEDs
        *COULD* be implemented by child class
        """

        pass
        #logging.debug(f"Lighting Off LEDs for {type(self).__name__}: NOT IMPLEMENTED!")

    def sleep_on(self):
        """Sleep On
        *COULD* be improved by child class
        """

        self.light_off()

    def sleep_off(self):
        """Sleep Off
        *COULD* be improved by child class
        """

        self.refresh()

    def get_state(self):
        """Return driver's state dictionary
        *COULD* be implemented by child class"""

        return None

    def set_state(self, state):
        """Restore driver's state
        *COULD* be implemented by child class"""

        pass

    def get_scroll_mode(self):
        return self._scroll_mode

    def set_scroll_mode(self, mode):
        """Set the chain and phrase scroll mode
        mode - New scroll mode"""

        if mode < 0 or mode > 3:
            return

        self._scroll_mode = mode
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.on_active_chain)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.on_active_phrase)
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_VIEW_POS, self.on_gui_view_pos)

        match mode:
            case self.SCROLL_MODE_GUI_SEL:
                zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.on_active_chain)
                zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_SELECT_PHRASE, self.on_active_phrase)
            case self.SCROLL_MODE_GUI_VIEW:
                zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_VIEW_POS, self.on_gui_view_pos)
            case self.SCROLL_MODE_CTRL:
                pass
            case self.SCROLL_MODE_NONE:
                self.scroll_h = self.scroll_v = 0
            case _:
                return

    def on_active_chain(self, active_chain_id):
        """Handle active chain selection
        *COULD* be implemented by child class"""

        if active_chain_id == 0:
            return
        pos = self.chain_manager.get_chain_index(active_chain_id)
        if pos < self.scroll_h:
            self.scroll_h = pos
        elif pos >= self.scroll_h + self.cols:
            self.scroll_h = max(0, min(pos - self.cols + 1, len(self.chain_ids_filtered) - self.cols))
        else:
            return
        self.refresh()

    def on_active_phrase(self, phrase):
        """Handle active phrase selection
        *COULD* be impleented by child class"""

        if phrase < self.scroll_v:
            self.scroll_v = phrase
        elif phrase >= self.scroll_v + self.rows:
            self.scroll_v = max(0, min(self.zynseq.phrases - self.rows, phrase - self.rows + 1))
        else:
            return
        self.refresh()

    def on_gui_view_pos(self, left_chain=None, top_phrase=None):
        """Update GUI scroll position
        *COULD* be implemented by child class"""

        if self._scroll_mode != self.SCROLL_MODE_GUI_VIEW:
            return False
        refresh = False
        if self.scroll_h != left_chain:
            self.scroll_h = left_chain
            refresh = True
        if self.scroll_v != top_phrase:
            self.scroll_v = top_phrase
            refresh = True
        if refresh:
            self.refresh()
        return True

# ------------------------------------------------------------------------------------------------------------------
# Zynpad control device base class
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_zynpad(zynthian_ctrldev_base):

    dev_zynpad = True		# Can act as a zynpad trigger device

    def __init__(self, state_manager, idev_in, idev_out=None):
        self.cols = 8 # Quatity of columns of physical launcher buttons
        self.rows = 8 # Quatity of rows of physical launcher buttons
        self.phrase_launcher_col = self.cols # Index of column used as phrase launcher
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        super().init()
        # Register for zynseq updates
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.update_seq_state)
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_STATE, self.refresh)

    def end(self):
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
        chan - zynseq's midi chan
        """
        #logging.debug(f"UPDATE SEQ STATE {phrase}, {chan}")
        if chan is None or self.idev_out is None:
            return
        row = phrase - self.scroll_v
        if row < 0 or row >= self.rows:
            return
        # Phrase launcher
        if chan == 32:
            col = self.phrase_launcher_col
            try:
                pad_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]
            except:
                pad_info = None
            self.update_pad(row, col, pad_info)
        # Sequence/Clip launcher
        else:
            try:
                pad_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][chan]
            except IndexError:
                pad_info = None
            for idx in self.chain_manager.get_pos_by_midi_chan(chan):
                col = idx - self.scroll_h
                if 0 <= col < self.cols:
                    self.update_pad(row, col, pad_info)

    def update_pad(self, row, col, pad_info):
        """Update the pad at row,col
        *SHOULD* be implemented by child class

        row - row
        col - column
        chan - zynseq's midi chan
        pad_info - dictionary with the pad info
        """
        pass

    def pad_off(self, col, row):
        """Light-Off the pad specified with column & row
        *SHOULD* be implemented by child class
        """
        pass

    def refresh(self):
        """Refresh full device status (LED feedback, etc)
        *COULD* be implemented by child class
        """
        super().refresh()
        if self.idev_out is None:
            return
        self.light_off()
        for row in range(self.rows):
            phrase = row + self.scroll_v
            for chan in range(32):
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
        self.scroll_h = 0
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        super().init()
        # Register for audio mixer changes
        zynsigman.register_queued(zynsigman.S_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_mixer_strip)

    def end(self):
        # Unregister for audio mixer changes
        zynsigman.unregister(zynsigman.S_MIXER, SS_ZYNMIXER_SET_VALUE, self.update_mixer_strip)
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

    def update_mixer_active_chain(self, active_chain_id):
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
            chain = self.get_filtered_chain_by_index(pos)
        if chain and chain.zynmixer_proc:
            try:
                zctrl = chain.zynmixer_proc.controllers_dict[param]
                if zctrl.value != value:
                    zctrl.set_value(value)
            except:
                logging.warning(f"Failed to set {param} to {value}")

    def nudge_mixer_param(self, param, pos, value):
        """Set a mixer parameter value

        param - Symbol name of the parameter
        pos - Chain display position (-1 for main chain)
        value - Parameter value
        """

        if pos < 0:
            chain = self.chain_manager.chains[0]
        else:
            chain = self.get_filtered_chain_by_index(pos)
        if chain and chain.zynmixer_proc:
            try:
                zctrl = chain.zynmixer_proc.controllers_dict[param]
                zctrl.nudge(value)
            except:
                logging.warning(f"Failed to nudge {param} by {value}")

    def get_mixer_param(self, param, pos):
        """Get a mixer parameter value

        param - Symbol name of the parameter
        pos - Chain display position (-1 for main chain)
        Returns - Parameter value
        """

        if pos < 0:
            chain = self.chain_manager.chains[0]
        else:
            chain = self.get_filtered_chain_by_index(pos)
        if chain and chain.zynmixer_proc:
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
            chain = self.get_filtered_chain_by_index(pos)
        if chain and chain.zynmixer_proc:
            try:
                chain.zynmixer_proc.controllers_dict[param].toggle()
                return chain.zynmixer_proc.controllers_dict[param].value
            except:
                logging.warning(f"Failed to toggle {param}")
        return 0


# --------------------------------------------------------------------------
