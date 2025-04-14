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
# Following function wrappers provide simple access for complex data types. Access with zynseq.function_name(parameters)
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
SEQ_EVENT_BPB = 5
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
SEQ_STOPPING = 2
SEQ_STARTING = 3
SEQ_STOPPINGSYNC = 4
SEQ_CHILD_PLAYING = 5 # Used to indicate a scene is stopped but some of its children are playing
SEQ_CHILD_STOPPING = 6 # Used to indicate a scene is stopped but some of its children are stopping

SEQ_MAX_COLUMNS = 8

PATTERN_EDITOR_BANK = 0     # Bank used for pattern editor
LAUNCHER_COLS = 17          # Quantity of launcher columns (16 channels + scene launchers)
SCENE_LAUNCHER_COL = LAUNCHER_COLS - 1     # Quantity of launcher columns (16 channels + scene launchers)
MIN_LAUNCHER_SLOTS = 8      # Minimum quantity of launcher slots in each channel of each bank

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
        self.progress = []
        self.seq2pad = {} # Map of [col,row] mapped by sequence (within current bank)
        self.scenes = 0

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
            self.libseq.setSwingAmount.argtypes = [ctypes.c_uint32, ctypes.c_float]
            self.libseq.getSwingAmount.restype = ctypes.c_float
            self.libseq.setHumanTime.argtypes = [ctypes.c_uint32, ctypes.c_float]
            self.libseq.getHumanTime.restype = ctypes.c_float
            self.libseq.setHumanVelo.argtypes = [ctypes.c_uint32, ctypes.c_float]
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
            self.libseq.getStateChange.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
                                                   ctypes.POINTER(ctypes.c_uint32)]
            self.libseq.getStateChange.restype = ctypes.c_uint8
            self.libseq.getProgress.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
                                                ctypes.POINTER(ctypes.c_uint16)]
            self.libseq.getProgress.restype = ctypes.c_uint8
            # Pattern functions
            self.libseq.getPattern.restype = ctypes.c_uint32
            self.libseq.getPatternAt.restype = ctypes.c_uint32

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
        self.launcher_info = []
        self.bank = None
        self.select_bank(1, True)

    # Destroy instance of shared library
    def destroy(self):
        if self.libseq:
            ctypes.dlclose(self.libseq._handle)
        self.libseq = None

    def update_state(self):
        # Get all pending states, send signals for each, update scene lauchers and send signals if necessary
        # State is represented as 4 bytes encoded as single 32-bit word: [sequence, group, mode, play state]
        # mode bits: [0..1] stop mode. [2] start mode. [7] enabled.
        states = (ctypes.c_uint32 * self.seq_in_bank)()
        count = self.libseq.getStateChange(self.bank, 0, self.seq_in_bank, states)
        if count:
            scene_changed = [False] * self.scenes
            for i in range(count):
                state = states[i] & 0xff
                mode = (states[i] >> 8) & 0xff
                group = (states[i] >> 16) & 0xff
                seq = (states[i] >> 24) & 0xff
                chan = seq % 17
                slot = seq // 17
                try:
                    self.launcher_info[slot][chan]["state"] = state
                    self.launcher_info[slot][chan]["mode"] = mode
                    self.launcher_info[slot][chan]["group"] = group
                    scene_changed[slot] = True
                except:
                    pass

                zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                            bank=self.bank, seq=seq, state=state, mode=mode, group=group)

            for slot, changed in enumerate(scene_changed):
                if not changed:
                    continue
                # Update scene summary
                if self.launcher_info[slot][SCENE_LAUNCHER_COL]["state"] not in (SEQ_STOPPED, SEQ_CHILD_PLAYING, SEQ_CHILD_STOPPING):
                    # Show scene launcher's actual state
                    continue
                scene_state = SEQ_STOPPED
                for chan in range(SCENE_LAUNCHER_COL):
                    try:
                        if self.launcher_info[slot][chan]["state"] == SEQ_STOPPING:
                            scene_state = SEQ_CHILD_STOPPING
                            break
                        elif self.launcher_info[slot][chan]["state"] not in (SEQ_STOPPED, SEQ_STARTING):
                            scene_state = SEQ_CHILD_PLAYING
                            break
                    except Exception as e:
                        logging.warning(e)
                self.launcher_info[slot][SCENE_LAUNCHER_COL]["state"] = scene_state

                zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                    bank=self.bank,
                    seq=self.launcher_info[slot][SCENE_LAUNCHER_COL]["sequence"],
                    state=self.launcher_info[slot][SCENE_LAUNCHER_COL]["state"],
                    mode=self.launcher_info[slot][SCENE_LAUNCHER_COL]["mode"],
                    group=self.launcher_info[slot][SCENE_LAUNCHER_COL]["group"]
                )
        self.update_progress()

    def update_progress(self):
        progress = (ctypes.c_uint16 * self.seq_in_bank)()
        count = self.libseq.getProgress(self.bank, 0, self.seq_in_bank, progress)
        for i in range(count):
            seq = (progress[i] >> 8) & 0xff
            prog = progress[i] & 0xff
            if prog != self.progress[i]:
                self.progress[i] = prog
                zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PROGRESS,
                               bank=self.bank, seq=seq, progress=prog)

    # Function to select a bank for edit / control
    # bank: Index of bank
    # force: True to force bank selection even if same as current bank
    def select_bank(self, bank=None, force=False):
        if self.changing_bank:
            return
        if bank is None:
            bank = self.bank
        else:
            if bank < 1 or bank == self.bank and not force:
                return
        self.changing_bank = True

        self.seq_in_bank = self.libseq.getSequencesInBank(bank)
        rows_in_bank = self.seq_in_bank // LAUNCHER_COLS
        self.bank = bank

        # Populate minimum launchers with default states
        self.launcher_info = []
        self.seq2pad = {}
        for slot in range(max(rows_in_bank, MIN_LAUNCHER_SLOTS)):
            self.append_scene()
        self.seq_in_bank = self.libseq.getSequencesInBank(bank)
        self.progress = [0] * self.seq_in_bank

        zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_REFRESH)
        self.changing_bank = False

    def update_sequence(self, chan, slot, enable=False):
        sequence = slot * LAUNCHER_COLS + chan
        if sequence >= self.seq_in_bank:
            # New sequence
            if chan == 16:
                self.set_sequence_name(self.bank, sequence, f"{chr(65 + slot)}>")
            else:
                self.set_sequence_name(self.bank, sequence, f"{chr(65 + slot)}{chan + 1}")
        if enable:
            self.libseq.setRepeat(self.bank, sequence, 1)
        state = self.libseq.getSequenceState(self.bank, sequence)
        repeat = (state >> 24) & 0xFF 
        group = (state >> 16) & 0xFF
        mode = (state >> 8) & 0xFF
        state = state & 0xFF
        follow = self.libseq.getFollowAction(self.bank, sequence)
        self.libseq.setGroup(self.bank, sequence, chan)
        if follow == 0xFFFF:
            follow_seq = -1
            follow_bank = -1
        else:
            follow_seq = follow & 0xFF
            follow_bank = follow >> 8
        pattern = self.libseq.getPattern(self.bank, sequence, 0, 0)
        if pattern == 4294967295:
            pattern = self.libseq.createPattern()
            pattern = self.libseq.addPattern(self.bank, sequence, 0, 0, pattern, True)
        bpb = self.libseq.getBeatsInPattern(pattern)
        info = {
            "title": self.get_sequence_name(self.bank, sequence),
            "bpb": bpb,
            "mode": mode,
            "repeat": repeat,
            "group": group,
            "state": state,
            "chan": chan,
            "slot": slot,
            "sequence": sequence,
            "pattern": pattern,
            "clippy": None, # Clippy processor, for clippy slots
            "tempo": None,
            "follow_seq": follow_seq,
            "follow_bank": follow_bank
        }
        if info["pattern"] == -1:
            logging.warning("No pattern!")
        try:
            self.launcher_info[slot][chan] = info
            zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                    bank=self.bank,
                    seq=sequence,
                    state=state,
                    mode=mode,
                    group=group
            )
        except Exception as e:
            logging.error(e)

    def rebuild_seq2pad(self):
        used_chan = []
        col = 0
        seq2pad = self.seq2pad
        self.seq2pad = {}
        for chain_id in self.state_manager.chain_manager.ordered_chain_ids:
            chain = self.state_manager.chain_manager.chains[chain_id]
            if chain.midi_chan is None or chain.midi_chan in used_chan:
                continue
            used_chan.append(chain.midi_chan)
            for slot in range(self.scenes):
                info = self.launcher_info[slot][chain.midi_chan]
                self.seq2pad[info["sequence"]] = [col, slot]
            col += 1
        if seq2pad != self.seq2pad:
            zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_REFRESH)

    def update_scenes(self, channel):
        """ Updates launcher info for all slots in a channel
        :channel: MIDI channel
        """

        if channel < 0:
            return #TODO: Handle ALL CHANNELS
        for slot in range(self.scenes):
            self.update_sequence(channel, slot, True)
        self.rebuild_seq2pad()

    def append_scene(self):
        """ Append a row of sequences to the current bank
        """

        slot = len(self.launcher_info)
        self.launcher_info.append([])
        for chan in range(LAUNCHER_COLS):
            self.launcher_info[slot].append({})
            self.update_sequence(chan, slot)
            self.libseq.setRepeat(self.bank, slot * 17 + 16, 1)
        self.seq_in_bank = self.libseq.getSequencesInBank(self.bank)
        self.scenes = len(self.launcher_info)
        self.progress = [0] * self.seq_in_bank
        self.rebuild_seq2pad()

    def remove_scene(self, slot):
        for chan in range(LAUNCHER_COLS):
            seq = slot * LAUNCHER_COLS + chan
            self.libseq.removeSequence(self.bank, seq)
        #TODO: Update info["slot"]
        self.scenes = len(self.launcher_info)

    def disable_channel(self, channel):
        for slot in range(len(self.launcher_info)):
            info = self.launcher_info[slot][channel]
            self.libseq.setRepeat(self.state_manager.zynseq.bank, slot * 17 + channel, 0)
            zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                    bank=self.bank,
                    seq=info["sequence"],
                    state=info["state"],
                    mode=info["mode"],
                    group=info["group"]
            )

    # Function to add / remove sequences to change bank size
    # new_columns: Quantity of columns (and rows) of new grid
    def update_bank_grid(self, new_columns):
        return # TODO: Factor out
        # To avoid odd behaviour we stop all sequences from playing before changing grid size (blunt but effective!)
        for seq in range(self.libseq.getSequencesInBank(self.bank)):
            self.libseq.setPlayState(self.bank, seq, SEQ_STOPPED)
        channels = []
        groups = []
        for column in range(new_columns):
            if column < self.LAUNCHER_COLS:
                channels.append(self.libseq.getChannel(
                    self.bank, column * self.LAUNCHER_COLS, 0))
                groups.append(self.libseq.getGroup(
                    self.bank, column * self.LAUNCHER_COLS))
            else:
                channels.append(column)
                groups.append(column)
        delta = new_columns - self.LAUNCHER_COLS
        if delta > 0:
            # Growing grid so add extra sequences
            for column in range(self.LAUNCHER_COLS):
                for row in range(self.LAUNCHER_COLS, self.LAUNCHER_COLS + delta):
                    pad = row + column * new_columns
                    self.libseq.insertSequence(self.bank, pad)
                    self.libseq.setChannel(self.bank, pad, 0, channels[column])
                    self.libseq.setGroup(self.bank, pad, groups[column])
                    self.set_sequence_name(self.bank, pad, "%s" % (pad + 1))
            for column in range(self.LAUNCHER_COLS, new_columns):
                for row in range(new_columns):
                    pad = row + column * new_columns
                    self.libseq.insertSequence(self.bank, pad)
                    self.libseq.setChannel(self.bank, pad, 0, column)
                    self.libseq.setGroup(self.bank, pad, column)
                    self.set_sequence_name(
                        self.bank, pad, "{}".format(pad + 1))
        elif delta < 0:
            # Shrinking grid so remove excess sequences
            # TODO: Lose excess columns

            # Lose exess rows
            for col in range(new_columns - 1, -1, -1):
                for row in range(self.LAUNCHER_COLS - 1, new_columns - 1, -1):
                    offset = self.LAUNCHER_COLS * col + row
                    self.libseq.removeSequence(self.bank, offset)
        self.seq_in_bank = self.libseq.getSequencesInBank(self.bank)
        self.LAUNCHER_COLS = min(8, int(sqrt(self.seq_in_bank)))
        self.progress = [0] * self.seq_in_bank
        zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_REFRESH)

    # Load a zynseq file
    # filename: Full path and filename
    def load(self, filename):
        self.libseq.load(bytes(filename, "utf-8"))
        self.select_bank(1, True)

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
    def set_sequence_name(self, bank, sequence, name):
        if self.libseq:
            self.libseq.setSequenceName(bank, sequence, bytes(name, "utf-8"))

    # Check if pattern is empty
    # Returns: True is pattern is empty
    def is_pattern_empty(self, patnum):
        if self.libseq:
            return self.libseq.isPatternEmpty(patnum)
        return False

    # Get sequence name
    # Returns: Sequence name (maximum 16 characters)
    def get_sequence_name(self, bank, sequence):
        if self.libseq:
            return self.libseq.getSequenceName(bank, sequence).decode("utf-8")
        else:
            return "%d" % (sequence)

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

    def set_midi_channel(self, bank, sequence, track, channel):
        self.libseq.setChannel(bank, sequence, track, channel)

    def set_group(self, bank, sequence, group):
        self.libseq.setGroup(bank, sequence, group)

    def set_beats_per_bar(self, bpb):
        self.libseq.setBeatsPerBar(bpb)

    def set_play_mode(self, bank, sequence, mode):
        #TODO: Playmode has changed
        self.libseq.setPlayMode(bank, sequence, mode)

    def remove_pattern(self, bank, sequence, track, time):
        self.libseq.removePattern(bank, sequence, track, time)

    def add_pattern(self, bank, sequence, track, time, pattern, force=False):
        if self.libseq.addPattern(bank, sequence, track, time, pattern, force):
            return True

    def enable_midi_learn(self, bank, sequence):
        try:
            self.libseq.enableMidiLearn(
                bank, sequence, ctypes.py_object(self), self.midi_learn_cb)
        except Exception as e:
            logging.error(e)

    def disable_midi_learn(self):
        try:
            self.libseq.enableMidiLearn(
                0, 0, ctypes.py_object(self), self.midi_learn_cb)
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

    def get_xy_from_seq(self, seq):
        """
        Get the coordinates of a sequence in the launcher grid

        :param seq: Index of sequence within currently selected bank
        :returns: [col, row] Column and row in the grid or None if not found
        .. note::
            Column is the chain position, starting from 0 at left side of mixer view
        """

        try:
            return self.seq2pad[seq]
        except:
            return None

    def get_seq_from_xy(self, col, row):
        """
        Get the sequence at a postion in the launcher grid

        :param: col: Index of column in grid (offset from left side of mixer view)
        :param: row: Index of row (slot) in grid
        :return: - Sequence number or None if not found
        """

        try:
            for seq, coord in self.seq2pad.items():
                if coord == [col, row]:
                    return seq
        except:
            pass
        return None

    def get_launcher_info_from_xy(self, col, row):
        """
        Get the launcher info at a postion in the launcher grid

        :param: col: Index of column in grid (offset from left side of mixer view)
        :param: row: Index of row (slot) in grid
        :return: - Launcher info object or None if not found
        """

        try:
            for seq, coord in self.seq2pad.items():
                if coord == [col, row]:
                    for info in self.launcher_info[row]:
                        if info["sequence"] == seq:
                            return info
        except:
            pass
        return None

# -------------------------------------------------------------------------------
