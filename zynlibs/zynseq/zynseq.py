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
from math import sqrt
from os.path import dirname, realpath

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

SEQ_EVENT_BANK = 1
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

CHANNEL_TYPE_DISABLED = 0
CHANNEL_TYPE_MIDI = 1
CHANNEL_TYPE_CLIPPY = 2

SEQ_MAX_COLUMNS = 8

PATTERN_EDITOR_BANK = 0     # Bank used for pattern editor
LAUNCHER_BANK = 1           # Bank used for launchers
LAUNCHER_COLS = 16          # Quantity of launcher columns (16 channels + scene launchers)
SCENE_CHANNEL = 16

# Subsignals are defined inside each module. Here we define zynseq subsignals:
SS_SEQ_PLAY_STATE = 1
SS_SEQ_REFRESH = 2
SS_SEQ_PROGRESS = 3
SS_TEMPO = 4

class zynseq(zynthian_engine):

    # Initiate library - performed by zynseq module
    def __init__(self, state_manager=None):
        self.state_manager = state_manager
        self.changing_bank = False

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
            self.libseq.getTempoAt.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint16]
            self.libseq.addTempoEvent.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float, ctypes.c_uint16,
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
            self.libseq.setFollowAction.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_int16]
            self.libseq.getFollowAction.restype = ctypes.c_uint8
            self.libseq.getFollowActionParam.restype = ctypes.c_int16

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
        self.launcher_info = []  # List of list launcher info, indexed by [slot][channel] - always 17 channels wide: MIDI chan 0..15 + scene launcher 16
        self.sequence_info = {}  # Map of launcher info, mapped by sequence (within current bank) - reverse linking for optimisation
        self.scenes = 8  # Quantity of launcher slots/rows/scenes
        self.bank = 0  # Currently selected bank
        self.seq_in_bank = 0  # Quantity of sequence in the selected bank
        self.pause_update = False
        self.progress = [0] * LAUNCHER_COLS
        self.reset()

    # Destroy instance of shared library
    def destroy(self):
        if self.libseq:
            ctypes.dlclose(self.libseq._handle)
        self.libseq = None

    def reset(self):
        self.libseq.reset()
        self.rebuild_all_launcher_info()

    def update_state(self):
        # Get all pending states, send signals for each, update scene lauchers and send signals if necessary
        # State is represented as 4 bytes encoded as single 32-bit word: [sequence, group, mode, play state]
        # mode bits: [0..1] stop mode. [2] start mode. [7] enabled.

        size = self.scenes * 17
        states = (ctypes.c_uint32 * size)()
        count = self.libseq.getStateChange(states, size)
        for i in range(count):
            if self.pause_update:
                return  # Stop processing updates if changing structure
            scene = (states[i] >> 24) & 0xff
            chan = min((states[i] >> 16) & 0xff, 16)
            mode = (states[i] >> 8) & 0xff
            state = states[i] & 0xff
            try:
                info = self.launcher_info[scene][chan]
            except Exception as e:
                # This sequence is not used by a launcher
                logging.warning(e)
                continue
            info["state"] = state
            info["mode"] = mode
            zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE, scene=scene, chan=chan, state=state, mode=mode)
        # Update progress
        progress = self.libseq.getProgress()
        for i in range(17):
            self.progress[i] = progress[i]  # TODO: Can we just point at getProgress()?

    def rebuild_all_launcher_info(self):
        self.pause_update = True
        self.launcher_info = []
        self.sequence_info = {}
        self.scenes = self.libseq.getNumScenes()
        self.seq_in_bank = self.scenes * 16
        for chan in range(17):
            for slot in range(self.scenes):
                self.rebuild_launcher_info(slot, chan)
            try:
                clippy = self.launcher_info[0][chan]["clippy"]
                if clippy:
                    clippy.engine.update_controllers(clippy)
            except Exception as e:
                logging.warning(f"Error getting clippy for channel {chan}: {e}")
        self.progress = [0] * 17
        self.pause_update = False

    def rebuild_launcher_info(self, scene, chan):
        """
        Build a dictionary of info for a launcher

        :slot: Index of scene
        :chan: MIDI chan
        """

        state = self.libseq.getSequenceState(scene, chan)
        repeat = (state >> 24) & 0xFF 
        mode = (state >> 8) & 0xFF
        state = state & 0xFF
        follow_action = self.libseq.getFollowAction(scene, chan)
        if follow_action == FOLLOW_ACTION_NONE:
            follow_param = 0
        else:
            follow_param = self.libseq.getFollowActionParam(scene, chan)
        pattern = self.libseq.getPattern(scene, chan, 0, 0)
        empty = self.libseq.isEmpty(scene, chan)
        title = self.get_sequence_name(scene, chan)
        # TODO: A lot of duplicated info. Much of this data optimises reverse lookup, e.g. from seq or position but it also repeats much channel data for each slot.
        info = {
            "title": title,
            "mode": mode,
            "repeat": repeat,
            "state": state,
            "chan": chan,
            "scene": scene,
            "pad_column": None,
            "chains": [],  # Used when drawing launcher pads
            "pattern": pattern,
            "empty": empty,
            "clippy": None,  # Clippy processor, for clippy slots
            "follow_action": follow_action,
            "follow_param": follow_param  # Jump offset (rel or abs, dep on action)
        }
        # Scene launcher
        if chan == 16:
            info["timesig"] = self.libseq.getTimeSigAt(scene, chan, 1, 0)
            info["tempo"] = self.libseq.getTempoAt(scene, chan, 1, 0)

        # Update pad position and list of chains this sequence belongs
        used_chan = []
        col = 0
        for chain_id in self.state_manager.chain_manager.ordered_chain_ids:
            chain = self.state_manager.chain_manager.chains[chain_id]
            if chain.midi_chan is None:
                continue
            if chain.midi_chan == chan:
                try:
                    processor = chain.get_processors("MIDI Synth")[0]
                    if processor.engine.nickname == "CL":
                        info["clippy"] = processor
                except:
                    pass
                info["chains"].append(chain_id)
                if info["pad_column"] is None:
                    info["pad_column"] = col
            if chain.midi_chan not in used_chan:
                col += 1
                used_chan.append(chain.midi_chan)

        if info["pattern"] == -1:
            logging.warning("No pattern!")
        self.sequence_info[scene * 17 + chan] = info  # TODO: Can we lose one of these maps?
        while len(self.launcher_info) <= scene:
            self.launcher_info.append([{"state": 0} for i in range(LAUNCHER_COLS + 1)])
        self.launcher_info[scene][chan] = info
        zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
            scene=scene,
            chan=chan,
            state=state,
            mode=mode
        )

    def insert_scene(self, scene=None):
        """ Insert a row of sequences to the current bank

        :scene: Index of scene to insert (Default: append)
        """

        if scene is None:
            scene = self.scenes
        self.libseq.insertScene(scene)
        self.rebuild_all_launcher_info()

    def remove_scene(self, scene):
        if self.scenes < 2:
            return  # TODO: What should be the minimum quantity of launchers?
        self.libseq.removeScene(scene)
        self.rebuild_all_launcher_info()

    def swap_scene(self, scene1, scene2):
        self.libseq.swapScene(scene1, scene2)
        self.rebuild_all_launcher_info()

    def enable_channel(self, channel, enable=True):
        """
        Enable or disable sequences in channel

        :channel: MIDI channel
        :enable: True to enable, False to disable
        """

        if channel is None or channel > 15:
            return
        repeat = 1 if enable else 0
        for scene in range(len(self.launcher_info)):
            info = self.launcher_info[scene][channel]
            self.libseq.setRepeat(scene, channel, repeat)
            zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                    scene=scene,
                    chan=info["chan"],
                    state=info["state"],
                    mode=info["mode"]
            )

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

    # Set sequence name
    # name: Sequence name (truncates at 16 characters)
    def set_sequence_name(self, scene, chan, name):
        try:
            self.libseq.setSequenceName(scene, chan, bytes(name, "utf-8"))
            self.launcher_info[scene][chan]["title"] = name
        except Exception as e:
            logging.error(f"Error setting sequence name: {e}")

    # Check if pattern is empty
    # Returns: True is pattern is empty
    def is_pattern_empty(self, patnum):
        if self.libseq:
            return self.libseq.isPatternEmpty(patnum)
        return False

    # Get sequence name
    # Returns: Sequence name (maximum 16 characters)
    def get_sequence_name(self, scene, sequence):
        if self.libseq:
            return self.libseq.getSequenceName(scene, sequence).decode("utf-8")
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

    def update_tempo(self):
        self.set_tempo(self.libseq.getTempo())

    def nudge_tempo(self, offset):
        self.zctrl_tempo.nudge(offset)

    def send_controller_value(self, zctrl):
        if zctrl == self.zctrl_tempo:
            self.libseq.setTempo(zctrl.value)
            #self.state_manager.audio_player.engine.player.set_tempo(zctrl.value)
            zynsigman.send(zynsigman.S_STEPSEQ, SS_TEMPO, tempo=zctrl.value)

    def set_midi_channel(self, chan, sequence, track, channel):
        self.libseq.setChannel(chan, sequence, track, channel)

    def set_play_mode(self, chan, sequence, mode):
        self.libseq.setPlayMode(chan, sequence, mode)

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

    def get_riff_data(self):
        fpath = "/tmp/snapshot.zynseq"
        try:
            # Save to tmp
            self.save(fpath)
            # Load binary data
            with open(fpath, "rb") as fh:
                riff_data = fh.read()
                logging.info("Loading RIFF data...\n")
            return riff_data

        except Exception as e:
            logging.error("Can't get RIFF data! => {}".format(e))
            return None

    def restore_riff_data(self, riff_data):
        fpath = "/tmp/snapshot.zynseq"
        try:
            # Save RIFF data to tmp file
            with open(fpath, "wb") as fh:
                fh.write(riff_data)
                logging.info("Restoring RIFF data...\n")
            # Load from tmp file
            if self.load(fpath):
                self.filename = "snapshot"
                return True

        except Exception as e:
            logging.error("Can't restore RIFF data! => {}".format(e))
            return False

    def get_pad_coords(self, seq):
        """
        Get the coordinates of a sequence in the displayed launcher grid

        :param seq: Index of sequence within currently selected bank
        :returns: [col, row] Column and row in the grid or None if not found
        .. note::
            Column is the chain position, starting from 0 at left side of mixer view
        """

        try:
            col = self.sequence_info[seq]["pad_column"]
            row = self.sequence_info[seq]["scene"]
            if col is None or row is None:
                return None
            return col, row
        except:
            return None

    def get_launcher_info(self, col, slot):
        """
        Get the launcher info for a pad in the displayed launcher grid

        :param: col: Index of column in grid (offset from left side of mixer view)
        :param: slot: Index of slot in grid
        :return: - Launcher info object or None if not found
        """

        #TODO: Optimise this
        try:
            for seq, info in self.sequence_info.items():
                if col == info["pad_column"] and slot == info["scene"]:
                    return info
        except:
            pass
        return None

# -------------------------------------------------------------------------------
