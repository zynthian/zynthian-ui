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

FOLLOW_ACTION_NONE  = 0
FOLLOW_ACTION_LOOP = 1
FOLLOW_ACTION_NEXT  = 2
FOLLOW_ACTION_PREV  = 3
FOLLOW_ACTION_JUMP  = 4

SEQ_MAX_COLUMNS = 8

PATTERN_EDITOR_BANK = 0     # Bank used for pattern editor
LAUNCHER_BANK = 1           # Bank used for launchers
LAUNCHER_COLS = 17          # Quantity of launcher columns (16 channels + scene launchers)
SCENE_LAUNCHER_COL = LAUNCHER_COLS - 1     # Index of scene launcher column

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
            self.libseq.getTempoAt.argtypes = [ctypes.c_uint8, ctypes.c_uint32, ctypes.c_uint16, ctypes.c_uint16]
            self.libseq.addTempoEvent.argtypes = [ctypes.c_uint8, ctypes.c_uint32, ctypes.c_float, ctypes.c_uint16,
                                                  ctypes.c_uint16]
            self.libseq.getMetronomeVolume.restype = ctypes.c_float
            self.libseq.setMetronomeVolume.argtypes = [ctypes.c_float]
            self.libseq.getStateChange.argtypes = [ctypes.c_uint8, ctypes.c_uint32, ctypes.c_uint32,
                                                   ctypes.POINTER(ctypes.c_uint32)]
            self.libseq.getStateChange.restype = ctypes.c_uint8
            self.libseq.getProgress.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
            # Pattern functions
            self.libseq.getPattern.restype = ctypes.c_uint32
            self.libseq.getPatternAt.restype = ctypes.c_uint32
            # Sequence functions
            self.libseq.setFollowAction.argtypes = [ctypes.c_uint8, ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint32]
            self.libseq.getFollowAction.restype = ctypes.c_uint8
            self.libseq.getFollowActionParam.restype = ctypes.c_uint32

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
        self.launcher_info = [] # List of list launcher info, indexed by [slot][channel] - always 17 channels wide: MIDI chan 0..15 + scene launcher 16
        self.sequence_info = {} # Map of launcher info, mapped by sequence (within current bank) - reverse linking for optimisation
        self.slots = 8 # Quantity of launcher slots/rows/scenes
        self.bank = None # Currently selected bank
        self.seq_in_bank = 0 # Quantity of sequence in the selected bank
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
        self.select_bank(1)
        self.rebuild_all_launcher_info()

    def update_state(self):
        # Get all pending states, send signals for each, update scene lauchers and send signals if necessary
        # State is represented as 4 bytes encoded as single 32-bit word: [sequence, group, mode, play state]
        # mode bits: [0..1] stop mode. [2] start mode. [7] enabled.

        if self.bank is None:
            return
        states = (ctypes.c_uint32 * self.seq_in_bank)()
        count = self.libseq.getStateChange(self.bank, 0, self.seq_in_bank, states)
        if count:
            scene_changed = [False] * self.slots
            for i in range(count):
                if self.pause_update:
                    return # Stop processing updates if changing structure
                state = states[i] & 0xff
                mode = (states[i] >> 8) & 0xff
                group = (states[i] >> 16) & 0xff
                seq = (states[i] >> 24) & 0xff
                try:
                    info = self.sequence_info[seq]
                except Exception as e:
                    # This sequence is not used by a launcher
                    logging.warning(e)
                    continue
                if info["slot"] >= self.slots:
                    continue
                info["state"] = state
                info["mode"] = mode
                info["group"] = group
                scene_changed[info["slot"]] = True
                zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                            bank=self.bank, seq=seq, state=state, mode=mode, group=group)

            # Update scene summary
            for slot, changed in enumerate(scene_changed):
                if not changed:
                    continue
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

                try:
                    zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
                        bank=self.bank,
                        seq=self.launcher_info[slot][SCENE_LAUNCHER_COL]["sequence"],
                        state=self.launcher_info[slot][SCENE_LAUNCHER_COL]["state"],
                        mode=self.launcher_info[slot][SCENE_LAUNCHER_COL]["mode"],
                        group=self.launcher_info[slot][SCENE_LAUNCHER_COL]["group"]
                    )
                except Exception as e:
                    logging.warning(e)

        self.update_progress()

    def update_progress(self):
        progress = (ctypes.c_uint8 * LAUNCHER_COLS)()
        self.libseq.getProgress(progress)
        for grp in range(LAUNCHER_COLS):
            self.progress[grp] = progress[grp]

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
        self.slots = self.seq_in_bank // LAUNCHER_COLS
        self.bank = bank

        if bank == 1 and self.slots == 0:
            self.slots = 8
            # Create default launchers
            for seq in range(LAUNCHER_COLS * self.slots):
                self.libseq.getSequenceState(bank, seq)

        self.rebuild_all_launcher_info()

        zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_REFRESH)
        self.changing_bank = False

    def rebuild_all_launcher_info(self):
        self.pause_update = True
        self.launcher_info = []
        self.sequence_info = {}
        self.seq_in_bank = self.libseq.getSequencesInBank(self.bank)
        self.slots = self.seq_in_bank // LAUNCHER_COLS
        clippy_engine = None
        for sequence in range(self.slots * LAUNCHER_COLS):
            info = self.rebuild_launcher_info(sequence)
            if clippy_engine is None and info["clippy"]:
                clippy_engine = info["clippy"].engine
        #if clippy_engine:
        #    clippy_engine.set_slots(self.slots)
        self.progress = [0] * self.seq_in_bank
        self.pause_update = False

    def rebuild_launcher_info(self, sequence):
        """
        Build a dictionary of info for a launcher

        :seqeunce: Index of seqeunce
        :returns: info object
        :note:
            Sequence numbers always start at 0 for slot 0, channel 0 and increment by channel (0..15) plus launcher (16)
            before wrapping to next slot (17..33, etc.). Manipulating sequence position requires copying.
            So sequence number can be deduced by channel & slot. Channel 0..15 are MIDI channels. Channel 16 is scene (row) launcher.
        """

        chan = sequence % LAUNCHER_COLS
        slot = sequence // LAUNCHER_COLS
        if chan < 16 and not self.state_manager.chain_manager.midi_chan_2_chain_ids[chan]:
            self.libseq.setRepeat(self.bank, sequence, 0)
        state = self.libseq.getSequenceState(self.bank, sequence)
        repeat = (state >> 24) & 0xFF 
        group = chan
        mode = (state >> 8) & 0xFF
        state = state & 0xFF
        self.libseq.setGroup(self.bank, sequence, group)
        follow_action = self.libseq.getFollowAction(self.bank, sequence)
        follow_param = self.libseq.getFollowActionParam(self.bank, sequence)
        pattern = self.libseq.getPattern(self.bank, sequence, 0, 0)
        if pattern == 4294967295:
            pattern = self.libseq.createPattern()
            self.libseq.addPattern(self.bank, sequence, 0, 0, pattern, True)
        bpb = self.libseq.getBeatsInPattern(pattern)
        #TODO: A lot of duplicated info. Much of this data optimises reverse lookup, e.g. from seq or position but it also repeats much channel data for each slot.
        info = {
            "title": self.get_sequence_name(self.bank, sequence), # Not used
            "bpb": bpb, # Used by scene launcher
            "mode": mode,
            "repeat": repeat,
            "group": group,
            "state": state,
            "chan": chan,
            "slot": slot,
            "pad_column": None,
            "chains": [], # Not used?
            "sequence": sequence,
            "pattern": pattern,
            "clippy": None, # Clippy processor, for clippy slots
            "tempo": None,
            "follow_action": follow_action,
            "follow_param": follow_param # For jump action, this is the follow scene not sequence as used by libzynseq
        }
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
                        self.libseq.setGroup(0, processor.stop_seq, group)

                except:
                    pass
                info["chains"].append(chain_id)
                if info["pad_column"] is None:
                    info["pad_column"] = col
            if chain.midi_chan not in used_chan:
                col +=1
                used_chan.append(chain.midi_chan)

        if info["pattern"] == -1:
            logging.warning("No pattern!")
        self.sequence_info[sequence] = info # TODO: Can we lose one of these maps?
        while len(self.launcher_info) <= slot:
            self.launcher_info.append([{"state": 0} for i in range(LAUNCHER_COLS)])
        self.launcher_info[slot][chan] = info
        zynsigman.send(zynsigman.S_STEPSEQ, SS_SEQ_PLAY_STATE,
            bank=self.bank,
            seq=sequence,
            state=state,
            mode=mode,
            group=group
        )
        return info

    def add_channel(self, chan):
        """
        Add the launchers for a new channel

        :chan: MIDI channel
        """
        for slot in range(self.slots):
            try:
                sequence = self.launcher_info[slot][chan]["sequence"]
                self.set_sequence_name(self.bank, sequence, f"{chr(65 + slot)}{chan + 1}")
                self.libseq.setChannel(self.bank, sequence, 0, chan)
                self.libseq.setRepeat(self.bank, sequence, 1)
                #self.rebuild_launcher_info(sequence)
            except Exception as e:
                logging.warning(e)
        self.rebuild_all_launcher_info()

    def add_scene(self, slot=None):
        """ Add a row of sequences to the current bank

        :slot: Index of slot to insert (Default: append)
        """

        if slot is None:
            slot = self.slots
        for sequence in range(self.seq_in_bank - 1, slot * LAUNCHER_COLS - 1, -1):
            self.libseq.moveSequence(self.bank, sequence, self.bank, sequence + LAUNCHER_COLS)
        for sequence in range(slot * LAUNCHER_COLS, (slot + 1) * LAUNCHER_COLS):
            chan = sequence % LAUNCHER_COLS
            if chan == 16:
                self.set_sequence_name(self.bank, sequence, f"{chr(65 + slot)}")
                self.libseq.setFollowAction(self.bank, sequence, FOLLOW_ACTION_NONE, 0)
            else:
                self.set_sequence_name(self.bank, sequence, f"{chr(65 + slot)}{chan + 1}")
        #self.rebuild_all_launcher_info()

        clippy = self.get_clippy()
        if clippy:
            clippy.insert_slot(slot)
        self.rebuild_all_launcher_info()

    def remove_scene(self, slot):
        if self.slots < 2:
            return # TODO: What should be the minimum quantity of launchers?
        if slot + 1 >= self.slots:
            for seq in range(slot * LAUNCHER_COLS, self.seq_in_bank):
                self.libseq.removeSequence(self.bank, seq)
        else:
            for seq in range((slot + 1) * LAUNCHER_COLS, self.seq_in_bank):
                self.libseq.moveSequence(self.bank, seq, self.bank, seq - LAUNCHER_COLS)
        clippy = self.get_clippy()
        if clippy:
            clippy.remove_slot(slot)
        self.rebuild_all_launcher_info()

    def move_scene(self, slot, offset):
        new_slot = slot + offset
        if new_slot >= self.slots:
            new_slot = self.slots - 1
        if new_slot < 0:
            new_slot = 0
        if new_slot == slot:
            return slot
        if new_slot > slot:
            for i in range(slot, new_slot):
                src_seq = i * LAUNCHER_COLS
                dst_seq = (i + 1) * LAUNCHER_COLS
                for i in range(17):
                    self.libseq.swapSequence(self.bank, src_seq + i, self.bank, dst_seq + i)
        else:
            for i in range(slot, new_slot, -1):
                src_seq = i * LAUNCHER_COLS
                dst_seq = (i - 1) * LAUNCHER_COLS
                for i in range(17):
                    self.libseq.swapSequence(self.bank, src_seq + i, self.bank, dst_seq + i)
        clippy = self.get_clippy()
        if clippy:
            clippy.move_slot(slot, offset)
        self.rebuild_all_launcher_info()
        return new_slot

    def get_clippy(self):
        #TODO: We only need one global clippy engine instance
        for a in self.launcher_info:
            try:
                proc = a[0]["clippy"]
                if proc:
                    return proc.engine
            except:
                pass
        return None

    def disable_channel(self, channel):
        """
        Disable sequences in channel

        :channel: MIDI channel
        """

        if channel is None or channel > 16:
            return
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
        self.libseq.setPlayMode(bank, sequence, mode)

    def remove_pattern(self, bank, sequence, track, time):
        self.libseq.removePattern(bank, sequence, track, time)

    def add_pattern(self, bank, sequence, track, time, pattern, force=False):
        if self.libseq.addPattern(bank, sequence, track, time, pattern, force):
            return True

    def enable_midi_learn(self, bank, sequence):
        try:
            self.libseq.enableMidiLearn(bank, sequence, ctypes.py_object(self), self.midi_learn_cb)
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
            row = self.sequence_info[seq]["slot"]
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
                if col == info["pad_column"] and slot == info["slot"]:
                    return info
        except:
            pass
        return None

# -------------------------------------------------------------------------------
