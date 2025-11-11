#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynseq Python Wrapper
#
# A Python wrapper for zynseq library
#
# Copyright (C) 2021-2025 Brian Walton <brian@riban.co.uk>
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
from os.path import dirname, realpath
from json import dumps, loads

from zyngine import zynthian_engine
from zyngine import zynthian_controller
from zyngine.zynthian_signal_manager import zynsigman
from zynlibs.zynaudioplayer import *

# -------------------------------------------------------------------------------
# Zynthian Step Sequencer Library Wrapper
#
# Most library functions are accessible directly by calling self.libseq.functionName(parameters)
#  ing function wrappers provide simple access for complex data types. Access with zynseq.function_name(parameters)
#
# Include the following imports to access these two library objects:
#  from zynlibs.zynseq import zynseq
#  from zynlibs.zynseq.zynseq import libseq
#
# -------------------------------------------------------------------------------

SEQ_EVENT_SCENE = 1
SEQ_EVENT_TEMPO = 2
SEQ_EVENT_CHANNEL = 3
SEQ_EVENT_GROUP = 4
SEQ_EVENT_TIMESIG = 5
SEQ_EVENT_PLAYMODE = 6
SEQ_EVENT_SEQUENCE = 7
SEQ_EVENT_LOAD = 8
SEQ_EVENT_MIDI_LEARN = 9
SEQ_EVENT_LOAD_PAT = 10

SEQ_MAX_PATTERNS = 64872

# Play modes START & END are OR'd to provide mode
# Bits 0..1 Stop mode
SEQ_MODE_END_END         = 0 # Stop at end of sequence
SEQ_MODE_END_SYNC        = 1 # Stop at next sync
SEQ_MODE_END_IMMEDIATE   = 2 # Stop immediately
# Bit 2 Start mode
SEQ_MODE_START_SYNC      = 0 # Start at next sync
SEQ_MODE_START_IMMEDIATE = 4 # Start immediately
# Bits 8..15 hold repeats. 0 for disabled.

SEQ_STOPPED = 0
SEQ_PLAYING = 1
SEQ_STARTING = 2
SEQ_STOPPING = 3
SEQ_FORCED_STOP = 4
SEQ_STOPPING_SYNC = 5
SEQ_CHILD_PLAYING = 6
SEQ_CHILD_STOPPING = 7

FOLLOW_ACTION_NONE  = 0
FOLLOW_ACTION_RELATIVE = 1
FOLLOW_ACTION_ABSOLUTE  = 2

SEQ_MAX_COLUMNS = 8

LAUNCHER_COLS = 33          # Quantity of launcher columns (16 MIDI channels 16 Clippy + phrase launchers)
PHRASE_CHANNEL = 32

# Subsignals are defined inside each module. Here we define zynseq subsignals:
SS_SEQ_PLAY_STATE = 1
SS_SEQ_REFRESH = 2
SS_SEQ_PROGRESS = 3
SS_TEMPO = 4

class zynseq(zynthian_engine):

    # Initiate library - performed by zynseq module
    def __init__(self, state_manager=None):
        self.state_manager = state_manager

        try:
            self.libseq = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynseq.so")
            self.libseq.getSequenceName.restype = ctypes.c_char_p
            self.libseq.addNote.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float,
                                            ctypes.c_float]
            self.libseq.getNoteDuration.restype = ctypes.c_float
            self.libseq.changeDurationAll.argtypes = [ctypes.c_float]
            self.libseq.getNoteOffset.restype = ctypes.c_float
            self.libseq.setNoteOffset.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_float]
            self.libseq.addControl.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
                                               ctypes.c_float, ctypes.c_float]
            self.libseq.getControlDuration.restype = ctypes.c_float
            self.libseq.getControlOffset.restype = ctypes.c_float
            self.libseq.setControlOffset.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_float]
            self.libseq.setSwingAmount.argtypes = [ctypes.c_float]
            self.libseq.getSwingAmount.restype = ctypes.c_float
            self.libseq.setSwingDiv.argtypes = [ctypes.c_uint32]
            self.libseq.getSwingDiv.restype = ctypes.c_uint32
            self.libseq.setHumanTime.argtypes = [ctypes.c_float]
            self.libseq.getHumanTime.restype = ctypes.c_float
            self.libseq.setHumanVelo.argtypes = [ctypes.c_float]
            self.libseq.getHumanVelo.restype = ctypes.c_float
            self.libseq.setPlayChance.argtypes = [ctypes.c_float]
            self.libseq.getPlayChance.restype = ctypes.c_float
            self.libseq.getTempo.restype = ctypes.c_double
            self.libseq.setTempo.argtypes = [ctypes.c_double]
            self.libseq.getTempoAt.restype = ctypes.c_float
            self.libseq.getTempoAt.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint16]
            self.libseq.addTempoEvent.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float, ctypes.c_uint16,
                                                  ctypes.c_uint16]
            self.libseq.getMetronomeVolume.restype = ctypes.c_float
            self.libseq.setMetronomeVolume.argtypes = [ctypes.c_float]
            self.libseq.getStateChange.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
            self.libseq.getStateChange.restype = ctypes.c_uint32
            self.libseq.getProgress.restype = ctypes.POINTER(ctypes.c_uint8)
            # Pattern functions
            self.libseq.getPattern.restype = ctypes.c_uint32
            self.libseq.getPatternAt.restype = ctypes.c_uint32
            # Sequence functions
            self.libseq.setSequenceFollowAction.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
            self.libseq.getSequenceFollowAction.restype = ctypes.c_uint8
            self.libseq.setSequenceFollowParam.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_int16]
            self.libseq.getSequenceFollowParam.restype = ctypes.c_int16

            self.libseq.convertToJson.restype = ctypes.c_char_p
            self.libseq.getState.restype = ctypes.c_char_p

            self.libseq.init(bytes("zynseq", "utf-8"))
        except Exception as e:
            self.libseq = None
            print("Can't initialise zynseq library: %s" % str(e))

        self.zctrl_tempo = zynthian_controller(self, 'bpm', {  # It was changed from 'tempo'
            'name': 'BPM',
            'is_integer': False,
            'value_min': 10.0,
            'value_max': 420,
            'value': self.libseq.getTempo(),
            'nudge_factor': 1.0
        })

        # Cache sequence info for launchers to reduce access to libseq
        self.phrases = 0  # Quantity of launcher slots/rows/phrases
        self.scene = 0  # Currently selected scene
        self.chan = 0 # Currently selected channel
        self.phrase = 0 # Currently selected phrase
        self.seq_in_scene = 0  # Quantity of sequence in the selected scene
        self.pause_update = False
        self.progress = [0] * LAUNCHER_COLS
        self.chan2col = [None] * LAUNCHER_COLS # Maps MIDI channel to launcher column
        self.reset()

    # Destroy instance of shared library
    def destroy(self):
        if self.libseq:
            ctypes.dlclose(self.libseq._handle)
        self.libseq = None

    def reset(self):
        self.libseq.reset()
        self.refresh_state()

    def update_state(self):
        # Get all pending states, send signals for each, update phrase lauchers and send signals if necessary
        # State is represented as 4 bytes encoded as single 32-bit word: [sequence, group, mode, play state]
        # mode bits: [0..1] stop mode. [2] start mode. [7] enabled.

        size = self.phrases * 33
        states = (ctypes.c_uint32 * size)()
        count = self.libseq.getStateChange(states, size)
        for i in range(count):
            if self.pause_update:
                return  # Stop processing updates if changing structure
            phrase = (states[i] >> 24) & 0xff
            chan = min((states[i] >> 16) & 0xff, 32)
            mode = (states[i] >> 8) & 0xff
            state = states[i] & 0xff
            try:
                if chan == PHRASE_CHANNEL:
                    info = self.state["scenes"][self.scene]["phrases"][phrase]
                else:
                    info = self.state["scenes"][self.scene]["phrases"][phrase]["sequences"][chan]
            except:
                logging.warning(f"No launcher info for sequence ({phrase},{chan})")
                continue
            info["state"] = state
            info["mode"] = mode
            zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE, phrase=phrase, chan=chan, state=state, mode=mode)
        # Update progress
        progress = self.libseq.getProgress()
        for i in range(33):
            self.progress[i] = progress[i]  # TODO: Can we just point at getProgress()?

    def enable_channel(self, channel, enable):
        self.libseq.enableChannel(channel, enable)
        self.refresh_state()

    def insert_phrase(self, scene, phrase=None):
        """ Insert a row of sequences to the current scene

        :phrase: Index of phrase to insert (Default: append)
        """

        if phrase is None:
            phrase = self.phrases
        self.libseq.insertPhrase(scene, phrase)
        self.refresh_state()

    def remove_phrase(self, scene, phrase):
        if self.phrases < 2:
            return  # TODO: What should be the minimum quantity of launchers?
        self.libseq.removePhrase(scene, phrase)
        self.refresh_state()

    def swap_phrase(self, scene, phrase1, phrase2):
        self.libseq.swapPhrase(scene, phrase1, phrase2)
        self.refresh_state()

    # Load a zynseq file
    # filename: Full path and filename

    def load(self, filename):
        self.libseq.load(bytes(filename, "utf-8"))

    # Load a zynseq pattern file
    # patnum: Pattern number
    # filename: Full path and filename
    def load_pattern(self, patnum, filename):
        self.libseq.load_pattern(int(patnum), bytes(filename, "utf-8"))

    # Save a zynseq file
    # filename: Full path and filename
    # Returns: True on success
    def save(self, filename):
        if self.libseq:
            return self.libseq.save(bytes(filename, "utf-8"))
        return None

    # Save a zynseq pattern file
    # patnum: Pattern number
    # filename: Full path and filename
    # Returns: True on success
    def save_pattern(self, patnum, filename):
        if self.libseq:
            return self.libseq.save_pattern(int(patnum), bytes(filename, "utf-8"))
        return None

    # Check if pattern is empty
    # Returns: True is pattern is empty
    def is_pattern_empty(self, patnum):
        if self.libseq:
            return self.libseq.isPatternEmpty(patnum)
        return False

    # Get sequence name
    # Returns: Sequence name (maximum 16 characters)
    def get_sequence_name(self, scene, phrase, sequence):
        if self.libseq:
            return self.libseq.getSequenceName(scene, phrase, sequence).decode("utf-8")
        else:
            return f"{sequence}"

    # Request JACK transport start
    # client: Name to register with transport to avoid other clients stopping whilst in use
    def transport_start(self, client):
        if self.libseq:
            self.libseq.transportStart(bytes(client, "utf-8"))

    # Request JACK transport stop
    # client: Name registered with transport when started
    # Note: Transport stops when all registered clients have requested stop
    def transport_stop(self, client):
        if self.libseq:
            self.libseq.transportStop(bytes(client, "utf-8"))

    # Toggle JACK transport
    # client: Name to register or was previously registered with transport when started

    def transport_toggle(self, client):
        if self.libseq:
            self.libseq.transportToggle(bytes(client, "utf-8"))

    def set_tempo(self, tempo):
        self.zctrl_tempo.set_value(tempo)
        zynaudioplayer.set_tempo(tempo)

    def get_tempo(self):
        return self.libseq.getTempo()

    def nudge_tempo(self, offset):
        self.zctrl_tempo.nudge(offset)

    def send_controller_value(self, zctrl):
        if zctrl == self.zctrl_tempo:
            self.libseq.setTempo(zctrl.value)
            #self.state_manager.audio_player.engine.player.set_tempo(zctrl.value)
            zynsigman.send(zynsigman.S_STEPSEQ, SS_TEMPO, tempo=zctrl.value)

    def set_midi_channel(self, chan, sequence, track, channel):
        self.libseq.setChannel(chan, sequence, track, channel)
        self.refresh_state()

    def remove_pattern(self, chan, sequence, track, time):
        self.libseq.removePattern(chan, sequence, track, time)

    def add_pattern(self, chan, sequence, track, time, pattern, force=False):
        if self.libseq.addPattern(chan, sequence, track, time, pattern, force):
            return True

    def enable_midi_learn(self, chan, sequence):
        try:
            self.libseq.enableMidiLearn(chan, sequence, ctypes.py_object(self), self.midi_learn_cb)
        except Exception as e:
            logging.error(e)

    def disable_midi_learn(self):
        try:
            self.libseq.enableMidiLearn(0, 0, ctypes.py_object(self), self.midi_learn_cb)
        except Exception as e:
            logging.error(e)

    def refresh_state(self):
        self.state = loads(self.libseq.getState().decode("utf-8"))
        self.libseq.freeState()
        self.phrases = len(self.state["scenes"][self.scene]["phrases"])
        self.refresh_chan2col()

    def refresh_chan2col(self):
        self.chan2col = [None] * LAUNCHER_COLS
        col = 0
        for id in self.state_manager.chain_manager.ordered_chain_ids:
            midi_chan = self.state_manager.chain_manager.chains[id].midi_chan
            if midi_chan is not None and self.chan2col[midi_chan] is None:
                self.chan2col[midi_chan] = col
                col += 1

    def set_state(self, state):
        result = self.libseq.setState(bytes(dumps(state), "utf-8"))
        if not result:
            for chain in self.state_manager.chain_manager.chains.values():
                if chain.midi_chan is not None:
                    self.libseq.enableChannel(chain.midi_chan, True)
        self.refresh_state()
        return result

    def set_sequence_param(self, scene, phrase, sequence, param, value):
        """ Set a sequence parameter
        
        scene: Index of scene
        phrase: Index of phrase
        sequence: Index of sequence
        param: Name of parameter (camelCase)
        value: Value to set parameter

        param may be: mode, group, name, repeat, followaction, followParam
        """

        try:
            if sequence == PHRASE_CHANNEL:
                state_seq = self.state["scenes"][scene]["phrases"][phrase]
            else:
                state_seq = self.state["scenes"][scene]["phrases"][phrase]["sequences"][sequence]
            fn_name = f"setSequence{param[0].upper()}{param[1:]}"
            fn = getattr(self.libseq, fn_name)
            if type(value) is str:
                fn(scene, phrase, sequence, bytes(value, "utf-8"))
            else:
                fn(scene, phrase, sequence, value)
            state_seq[param] = value
        except Exception as e:
            logging.warning(f"Failed to set sequence parameter {param}={value}: {e}")
            return False

    def select_phrase(self, phrase):
        """
        Select a phrase

        :param: phrase Index of phrase
        """

        if (phrase >= self.phrases):
            phrase = self.phrases - 1
        if (phrase < 0):
            phrase = 0
        if phrase == self.phrase:
            return False
        self.phrase = phrase
        zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_REFRESH)


    def get_pad_coords(self, phrase, chan):
        """
        Get the coordinates of a sequence in the displayed launcher grid

        :param phrase: Index of phrase (row)
        :param chan: MIDI channel of sequence
        :returns: [row, col] Row and column in the grid or None if not found
        .. note::
            Column is the chain position, starting from 0 at left side of mixer view
            Row is same as phrase - should be changed to offer scroll position
        """

        try:
            #TODO: Lookup horizontal and vertical scroll poisition
            row = phrase
            return row, self.chan2col[chan]
        except:
            return None

    def get_chan_from_col(self, col):
        """
        Get the MIDI channel of a column of launchers
        
        :param col: Index of column on hardware launcher (display order, MIDI chains only)
        :returns: MIDI channel or None if invalid
        """

        try:
            return self.chan2col.index(col)
        except:
            return None


# -------------------------------------------------------------------------------
