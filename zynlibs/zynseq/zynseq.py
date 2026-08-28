#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynseq Python Wrapper
#
# A Python wrapper for zynseq library
#
# Copyright (C) 2021-2026 Brian Walton <brian@riban.co.uk>
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
from json import dump, dumps, load, loads

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

MIDI_NOTE_OFF = 0x80
MIDI_NOTE_ON = 0x90
MIDI_POLY_PRESSURE = 0xA0
MIDI_CONTROL = 0xB0
MIDI_PROGRAM = 0xC0
MIDI_CHAN_PRESSURE = 0xD0
MIDI_PITCHBEND = 0xE0
MIDI_SYSEX_START = 0xF0
MIDI_TIMECODE = 0xF1
MIDI_POSITION = 0xF2
MIDI_SONG = 0xF3
MIDI_TUNE = 0xF6
MIDI_SYSEX_END = 0xF7
MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_CONTINUE = 0xFB
MIDI_STOP = 0xFC
MIDI_ACTIVE_SENSE = 0xFE
MIDI_RESET = 0xFF

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

# Bit 0 indicates playing
SEQ_STOPPED = 0
SEQ_PLAYING = 1
SEQ_STARTING = 2
SEQ_STOPPING = 3
SEQ_FORCED_STOP = 4
SEQ_STOPPING_SYNC = 5
SEQ_CHILD_PLAYING = 6
SEQ_CHILD_STOPPING = 8

FOLLOW_ACTION_NONE  = 0
FOLLOW_ACTION_RELATIVE = 1
FOLLOW_ACTION_ABSOLUTE  = 2

SEQ_MAX_COLUMNS = 8

LAUNCHER_COLS = 33          # Quantity of launcher columns (16 MIDI channels 16 Clippy + phrase launchers)
PHRASE_CHANNEL = 32

CHANNEL_CHARS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'
                 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'Γ', 'Δ', 'Λ', 'Π', 'Σ', 'Ω']
                 # 'Θ', 'Ξ', 'Φ', 'Ψ',

PATTERN_PARAMS = [
    "step", # Step within pattern
    "duration", # Duration of event
    "offset", # Offset from start of step
    "command", # MIDI command
    "val1Start", # MIDI value 1 at start of event
    "val1End", # MIDI value 1 at end of event
    "val2Start", # MIDI value 2 at start of event
    "val2End", # MIDI value 2 at end of event
    "chance", # Probability % of event triggering
    "stutSpd", # Stutter speed (retriggers/beat)
    "stutVfx" # Stutter velocity FX value
]

# Maximum number of steps in a pattern
MAX_STEPS_PATTERN = 256 * 12 * 96

class event_data(ctypes.Structure):
    _pack_ = 1                              # Crucial for matching C's packing
    _fields_ = [
        ("position", ctypes.c_uint32),      # Start position of event in steps
        ("offset", ctypes.c_float),         # Offset of event position in steps
        ("duration", ctypes.c_float),       # Duration of event in steps
        ("command", ctypes.c_uint8),        # MIDI command without channel
        ("val1_start", ctypes.c_uint8),     # MIDI value 1 at start of event
        ("val2_start", ctypes.c_uint8),     # MIDI value 2 at start of event
        ("val1_end", ctypes.c_uint8),       # MIDI value 1 at end of event
        ("val2_end", ctypes.c_uint8),       # MIDI value 2 at end of event
        ("stut_speed", ctypes.c_uint8),     # Stutter speed in "retriggers every 2 steps"
        ("stut_velfx", ctypes.c_uint8),     # Stutter velocity FX (none=0, fade-out=1, fade-in=2)
        ("stut_ramp", ctypes.c_uint8),      # Stutter speed ramp FX (none=0, ramp-up=1, ramp-down=2)
        ("play_freq", ctypes.c_uint8),      # Play/Skip note each N loops: last bit => play/skip, higher bits => loop count
                                            # Can be used for enabling/disabling the event: 0 => play never, 1 => play on every loop
        ("stut_freq", ctypes.c_uint8),      # Play/Skip stutter each N loops: last bit => play/skip, higher bits => loop count
        ("play_chance", ctypes.c_float),    # Probability of playing (0 = not played, 0.5 = plays with 50%, 1.0 = always plays)
        ("stut_chance", ctypes.c_float)     # Probability of stutter (0 = not stutter, 0.5 = stutters with 50%, 1.0 = always stutters)
    ]

    def set_values(self, pos, os, dur, cmd, v1s, v2s, v1e, v2e, sspd, svfx, srmp, pf, sf, pc, sc):
        self.position = pos
        self.osffset = os
        self.duration = dur
        self.command = cmd
        self.val1_start = v1s
        self.val2_start = v2s
        self.val1_end = v1e
        self.val2_end = v2e
        self.stut_speed = sspd
        self.stut_velfx = svfx
        self.stut_ramp = srmp
        self.play_freq = pf
        self.stut_freq = sf
        self.play_chance = pc
        self.stut_chance = sc

    def get_key(self):
        return self.val1_start * MAX_STEPS_PATTERN + self.position

    def __str__(self):
        return f"""(position={self.position}, offset={self.offset}, duration={self.duration}, command={self.command},
    val1_start={self.val1_start}, val2_start={self.val2_start}, val1_end={self.val1_end}, val2_end={self.val2_end},
    stut_speed={self.stut_speed}, stut_velfx={self.stut_velfx}, stut_ramp={self.stut_ramp},
    play_freq={self.play_freq}, stut_freq={self.stut_freq},
    play_chance={self.play_chance}, stut_chance={self.stut_chance})"""


# Buffer to select pattern events (event indexes)
event_key_buffer_size = 10000
event_key_buffer = (ctypes.c_uint32 * event_key_buffer_size)()


class zynseq(zynthian_engine):

    # Initiate library - performed by zynseq module
    def __init__(self, state_manager=None, proc=None):
        self.state_manager = state_manager
        self.proc = proc
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_tempo.py"

        try:
            self.libseq = ctypes.cdll.LoadLibrary(dirname(realpath(__file__))+"/build/libzynseq.so")
            self.libseq.getSequenceName.restype = ctypes.c_char_p

            self.libseq.addNote.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float, ctypes.c_float]
            self.libseq.pastePatternBuffer.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_float, ctypes.c_int8, ctypes.c_bool]
            self.libseq.getPatternSelectionKeys.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32,
                                                            ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint8, ctypes.c_uint8]
            self.libseq.getEventDataAt.argtypes = [ctypes.c_uint32, ctypes.POINTER(event_data)]
            self.libseq.getBufferEventDataAt.argtypes = [ctypes.c_uint32, ctypes.POINTER(event_data)]
            self.libseq.getNoteData.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.POINTER(event_data)]
            self.libseq.setNoteData.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.POINTER(event_data)]
            #self.libseq.getNoteData.restype = ctypes.c_int32
            self.libseq.getNoteDuration.restype = ctypes.c_float

            self.libseq.changeDurationAll.argtypes = [ctypes.c_float]
            self.libseq.changeVelocityAll.argtypes = [ctypes.c_float]
            self.libseq.changeDurationList.argtypes = [ctypes.c_float, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
            self.libseq.changeVelocityList.argtypes = [ctypes.c_float, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]

            self.libseq.getNoteOffset.restype = ctypes.c_float
            self.libseq.setNoteOffset.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_float]

            self.libseq.addControl.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float, ctypes.c_float]
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

            self.libseq.setNotePlayChance.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_float]
            self.libseq.getNotePlayChance.argtypes = [ctypes.c_uint32, ctypes.c_uint8]
            self.libseq.getNotePlayChance.restype = ctypes.c_float

            self.libseq.setNoteStutterChance.argtypes = [ctypes.c_uint32, ctypes.c_uint8, ctypes.c_float]
            self.libseq.getNoteStutterChance.argtypes = [ctypes.c_uint32, ctypes.c_uint8]
            self.libseq.getNoteStutterChance.restype = ctypes.c_float

            self.libseq.getTempo.restype = ctypes.c_double
            self.libseq.setTempo.argtypes = [ctypes.c_double]
            self.libseq.getTempoAt.restype = ctypes.c_float
            self.libseq.getTempoAt.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint16]
            self.libseq.addTempoEvent.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float, ctypes.c_uint16, ctypes.c_uint16]
            self.libseq.getMetronomeVolume.restype = ctypes.c_float
            self.libseq.setMetronomeVolume.argtypes = [ctypes.c_float]
            self.libseq.getStateChange.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32]
            self.libseq.getStateChange.restype = ctypes.c_uint32
            self.libseq.getProgress.restype = ctypes.POINTER(ctypes.c_uint8)

            # Pattern functions
            self.libseq.getPattern.restype = ctypes.c_uint32
            self.libseq.getPatternAt.restype = ctypes.c_uint32
            self.libseq.convertPattern.argtypes = [ctypes.c_char_p]
            self.libseq.convertPattern.restype = ctypes.c_char_p

            # Sequence functions
            self.libseq.setSequenceTempo.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_float]
            self.libseq.getSequenceTempo.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
            self.libseq.getSequenceTempo.restype = ctypes.c_float
            self.libseq.setSequenceBpb.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
            self.libseq.getSequenceBpb.restype = ctypes.c_uint8
            self.libseq.setSequenceFollowAction.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
            self.libseq.getSequenceFollowAction.restype = ctypes.c_uint8
            self.libseq.setSequenceFollowParam.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_int16]
            self.libseq.getSequenceFollowParam.restype = ctypes.c_int16
            self.libseq.setSequencePlayFlags.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint32]
            self.libseq.getSequencePlayFlags.restype = ctypes.c_uint32
            self.libseq.setSequenceFollowRepeat.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
            self.libseq.getSequenceFollowRepeat.restype = ctypes.c_uint8

            self.libseq.convertToJson.restype = ctypes.c_char_p
            self.libseq.getState.restype = ctypes.c_char_p

            self.PPQN = self.libseq.getPPQN()
            self.libseq.init(bytes("zynseq", "utf-8"))

        except Exception as e:
            self.libseq = None
            print("Can't initialise zynseq library: %s" % str(e))

        self.zctrl_tempo = zynthian_controller(self, 'bpm', {
            'name': 'BPM',
            'is_integer': False,
            'value_min': 10.0,
            'value_max': 420.0,
            'value': self.libseq.getTempo(),
            'nudge_factor': 1.0
        })
        self.zctrl_metro_mode = zynthian_controller(self, 'metronome_enable', {
            'name': 'Metronome Mode',
            'labels': ['OFF', 'AUTO', 'ON', 'INTRO', "NO ACCENT", "SILENT"],
            'value': self.libseq.getMetronomeMode()
        })
        self.zctrl_metro_volume = zynthian_controller(self, 'metronome_volume', {
            'name': 'Metronome Volume',
            'value_min': 0,
            'value_max': 100,
            'value': int(100 * self.libseq.getMetronomeVolume())
        })
        self.zctrl_ppqn = zynthian_controller(self, 'ppqn', {
            'name': 'Clock PPQN',
            'value_min': 1,
            'value_max': 48,
            'value_default': 24,
            'value': self.libseq.getExtClockPPQN()
        })

        # Cache sequence info for launchers to reduce access to libseq
        self.phrases = 0  # Quantity of launcher slots/rows/phrases
        self.scene = 0  # Currently selected scene
        self.chan = 0 # Currently selected channel
        self.phrase = 0 # Currently selected phrase
        self.seq_in_scene = 0  # Quantity of sequence in the selected scene
        self.playing_sequences = 0 # Quantity of playing sequences
        self.pause_update = False
        self.progress = [0] * LAUNCHER_COLS
        self.bpb = 4
        self.beat = 0 # Current beat of bar
        self.clippy = None # Clippy engine object
        self.reset()

    # Destroy instance of shared library
    def destroy(self):
        if self.libseq:
            ctypes.dlclose(self.libseq._handle)
        self.libseq = None

    def reset(self):
        self.libseq.reset()
        self.refresh_state()

    # Load a zynseq file
    # filename: Full path and filename
    def load(self, filename):
        self.libseq.load(bytes(filename, "utf-8"))

    # -------------------------------------------------------------------
    # Channel management
    # -------------------------------------------------------------------

    def set_midi_channel(self, chan, sequence, track, channel):
        self.libseq.setChannel(chan, sequence, track, channel)
        self.refresh_state()

    def enable_channel(self, channel, enable, refresh=False):
        self.libseq.enableChannel(channel, enable)
        self.refresh_state(refresh)

    # -------------------------------------------------------------------
    # Miscelaneous
    # -------------------------------------------------------------------

    # Get sequence name
    # Returns: Sequence name (maximum 16 characters)
    def get_sequence_name(self, scene, phrase, sequence):
        name = self.libseq.getSequenceName(scene, phrase, sequence).decode("utf-8")
        if not name:
            name = f"{CHANNEL_CHARS[sequence]}{phrase + 1}"
        return name

    # -------------------------------------------------------------------
    # Phrase Management
    # -------------------------------------------------------------------

    def insert_phrase(self, scene, phrase=None):
        """ Insert a row of sequences to the current scene

        :phrase: Index of phrase to insert (Default: append)
        """

        if phrase is None:
            phrase = self.phrases
        self.libseq.insertPhrase(scene, phrase)
        if scene == self.scene and self.clippy:
            self.clippy.insert_phrase(phrase)
        self.refresh_state()

    def duplicate_phrase(self, scene, phrase=None):
        """ Insert a row of sequences to the current scene

        :phrase: Index of phrase to insert (Default: append)
        """

        if phrase is None:
            phrase = self.phrases
        self.libseq.duplicatePhrase(scene, phrase)
        if scene == self.scene and self.clippy:
            self.clippy.duplicate_phrase(phrase)
        self.refresh_state()

    def remove_phrase(self, scene, phrase):
        if self.phrases < 2:
            return  # TODO: What should be the minimum quantity of launchers?
        self.libseq.removePhrase(scene, phrase)
        if scene == self.scene and self.clippy:
            self.clippy.remove_phrase(phrase)
        if self.phrase == phrase:
            self.phrase = max(0, self.phrase - 1)
        self.refresh_state()

    def nudge_phrase(self, scene, phrase, forward):
        """ Move a phrase forward or backward by one position
        Args:
            scene: Index of scene
            phrase: Index of phrase
            forward: True to move forward, else move backwards
        """

        self.libseq.nudgePhrase(scene, phrase, forward)
        if self.clippy and scene == self.scene:
            self.clippy.nudge_phrase(phrase, forward)
        phrase2 = phrase + 1 if forward else phrase - 1
        if self.phrase == phrase:
            self.phrase = phrase2
        elif self.phrase == phrase2:
            self.phrase = phrase
        self.refresh_state()

    def select_phrase(self, phrase, force=False):
        """
        Select a phrase

        :param: phrase Index of phrase
        :param: force True to select phrase even if same as currently selected
        """

        if (phrase >= self.phrases):
            phrase = self.phrases - 1
        if (phrase < 0):
            phrase = 0
        if not force and phrase == self.phrase:
            return False
        self.phrase = phrase
        zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_SELECT_PHRASE, phrase=phrase)
        
    def get_phrase_loop_info(self, phrase=None):
        """ Get info for loop that this phrase is within
        Args:
            phrase: Index of phrase to check
        Returns: Tuple of phrase loop info (loop_end_phrase, loop_length, repeat_count) or None if not in loop
        """

        if phrase == None:
            phrase = self.phrase
        i = phrase
        while True:
            # Iterate until exceed quantity of phrases in scene
            try:
                info = self.state["scenes"][self.scene]["phrases"][i]
            except:
                return None
            if info["followAction"] == FOLLOW_ACTION_RELATIVE and info["followParam"] < 0:
                # If current phrase is inside the next loop, return the loop count
                loop_from = i + info["followParam"]
                if phrase >= loop_from:
                    return (i, -info["followParam"], info["followRepeat"])
                # else loop count is 0 (current phrase not in the next loop)
                else:
                    return None
            i += 1

    def get_phrase_loop_info_all(self, phrase=None):
        """ Get info for *ALL* nested loops that this phrase is within
        Args:
            phrase: Index of phrase to check
        Returns: List of tuples of phrase loop info (loop_end_phrase, loop_length, repeat_count) or None if not in loop
        """

        if phrase == None:
            phrase = self.phrase
        i = phrase
        res = []
        while True:
            # Iterate until exceed quantity of phrases in scene
            try:
                info = self.state["scenes"][self.scene]["phrases"][i]
            except:
                return res
            if info["followAction"] == FOLLOW_ACTION_RELATIVE and info["followParam"] < 0:
                # If current phrase is inside the next loop, return the loop count
                loop_from = i + info["followParam"]
                if phrase >= loop_from:
                    res.append((i, -info["followParam"], info["followRepeat"]))
            i += 1
        return res

    # -------------------------------------------------------------------
    # Pattern and event management
    # -------------------------------------------------------------------

    # Load a zynseq pattern file
    # patnum: Pattern number
    # filename: Full path and filename
    def load_pattern(self, patnum, filename):
        try:
            with open(filename, "r") as f:
                state = load(f)
                patn = state["patn"]
                patn_str = dumps(patn)
        except:
            try:
                # Legacy binary file format
                patn_str = self.libseq.convertPattern(bytes(filename, "utf-8")).decode("utf-8")
                self.libseq.freeState()
                patn = loads(patn_str)
            except:
                return
        if patn:
            self.libseq.setPattern(patnum, bytes(patn_str, "utf-8"))
            self.state["patns"][str(patnum)] = patn

    # Save a zynseq pattern file
    # patnum: Pattern number
    # filename: Full path and filename
    # Returns: True on success
    def save_pattern(self, patnum, filename):
        try:
            state = {
                "schema_version": self.state_manager.get_schema(),
                "patn": self.state["patns"][str(patnum)]
            }
            with open(filename, "w") as f:
                dump(state, f)
                return True
        except:
            pass

    # Check if pattern is empty
    # Returns: True is pattern is empty
    def is_pattern_empty(self, patnum):
        if self.libseq:
            return self.libseq.isPatternEmpty(patnum)
        return False

    def remove_pattern(self, chan, sequence, track, time):
        self.libseq.removePattern(chan, sequence, track, time)

    def add_pattern(self, chan, sequence, track, time, pattern, force=False):
        if self.libseq.addPattern(chan, sequence, track, time, pattern, force):
            return True

    def get_note_data(self, step, note, cp_buffer=False):
        """ Get note full data searching by step & note number in the currently loaded pattern

        step: Step index in the current pattern
        note: Note number
        cp_buffer: Note number
        Returns: A data struct with event data
        """

        evdata = event_data()
        res = self.libseq.getNoteData(step, note, evdata, cp_buffer)
        if res >= 0:
            #logging.debug(f"Note ({step}, {note}) data => {evdata}")
            return evdata

    def set_note_data(self, step, note, evdata):
        """ Set note data searching by step & note number in the currently loaded pattern.
            All event data is overwritten except: position, offset duration, command and val1_start,

        step: Step index in the current pattern
        note: Note number
        evdata: event_data object
        Returns: A data struct with event data
        """

        return self.libseq.setNoteData(step, note, evdata)

    def get_pattern_selection(self, pattern, step1, step2, note1, note2):
        """ Get event indexes from pattern in the specified step & note range.

        pattern: Pattern index
        step1: Start of step range
        step2: End of step range
        note1: Start of note range
        note2: End of note range
        Returns: A list of event indexes
        """

        # Initially, event keys (step+note) are copied into a ctypes buffer array
        n = self.libseq.getPatternSelectionKeys(pattern, event_key_buffer, event_key_buffer_size,
                                               step1, step2, note1, note2)

        # Then copy and return in a dictionary
        res = {}
        for i in range(n):
            res[event_key_buffer[i]] = True
        return res

    # -------------------------------------------------------------------
    # MIDI transport & clock settings
    # -------------------------------------------------------------------

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

    def tap_tempo(self):
        self.libseq.tapTempo()

    # -------------------------------------------------------------------
    # Zynseq Zctrls management
    # -------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        if zctrl == self.zctrl_tempo:
            self.libseq.setTempo(zctrl.value)
            #self.state_manager.audio_player.engine.player.set_tempo(zctrl.value)
            zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, tempo=zctrl.value)
        elif zctrl == self.zctrl_metro_mode:
            self.libseq.setMetronomeMode(zctrl.value)
            zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_METRO, mode=zctrl.value, volume=self.zctrl_metro_volume.value)
        elif zctrl == self.zctrl_metro_volume:
            self.libseq.setMetronomeVolume(zctrl.value / 100.0)
            zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_METRO, mode=self.zctrl_metro_mode.value, volume=zctrl.value)
        elif zctrl == self.zctrl_ppqn:
            self.libseq.setExtClockPPQN(zctrl.value)

    # -------------------------------------------------------------------
    # Zynseq MIDI learn ==> Is this still used?
    # -------------------------------------------------------------------

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

    # -------------------------------------------------------------------
    # State management
    # -------------------------------------------------------------------

    def update_state(self):
        # Get all pending states, send signals for each, update phrase lauchers and send signals if necessary
        # State is represented as 4 bytes encoded as single 32-bit word: [sequence, group, mode, play state]
        # mode bits: [0..1] stop mode. [2] start mode. [7] enabled.

        self.beat = self.libseq.getBeat()
        tempo = self.libseq.getTempo()
        if tempo != self.zctrl_tempo.value:
            self.zctrl_tempo.set_value(tempo)
        size = self.phrases * 33
        states = (ctypes.c_uint32 * size)()
        count = self.libseq.getStateChange(states, size)
        if count:
            self.playing_sequences = self.libseq.getPlayingSequences()
            bpb = self.libseq.getBpb()
            if bpb != self.bpb:
                self.bpb = bpb
                zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TIMESIG, bpb=bpb)
            # Iterate state changes
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
                zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_PLAY_STATE, phrase=phrase, chan=chan)

    def update_progress(self):
        self.progress = self.libseq.getProgress()
        #progress = self.libseq.getProgress()
        #for i in range(33):
        #    self.progress[i] = progress[i]

    def refresh_state(self, send=True):
        self.state = loads(self.libseq.getState().decode("utf-8"))
        self.libseq.freeState()
        try:
            self.state["scenes"][0]["phrases"][0]
        except:
            logging.warning("Invalid zynseq - rebuilding default")
            self.libseq.reset()
            self.state = loads(self.libseq.getState().decode("utf-8"))
            self.libseq.freeState()
        self.phrases = len(self.state["scenes"][self.scene]["phrases"])
        try:
            if self.state["tempo"] != self.zctrl_tempo.value:
                self.zctrl_tempo.set_value(self.state["tempo"])
        except:
            logging.warning("Failed to set tempo")
        try:
            if self.state["bpb"] != self.bpb:
                self.bpb = self.state["bpb"]
                zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TIMESIG, bpb=self.bpb)
        except:
            logging.warning("Failed to set bpb")
        if send:
            zynsigman.send(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_STATE)

    def set_state(self, state):
        result = self.libseq.setState(bytes(dumps(state), "utf-8"))
        if not result:
            for chain in self.state_manager.chain_manager.chains.values():
                if chain.midi_chan is not None:
                    self.libseq.enableChannel(chain.midi_chan, True)
        self.refresh_state()
        return result

    def set_sequence_param(self, scene, phrase, sequence, param, value):
        """ Set a sequence parameter value

        scene: Index of scene
        phrase: Index of phrase
        sequence: Index of sequence
        param: Name of parameter (camelCase)
        value: Parameter value
        Return: True on success

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
            return True
        except Exception as e:
            logging.warning(f"Failed to set sequence parameter {param}={value}: {e}")
        return False

    def get_sequence_param(self, scene, phrase, sequence, param):
        """ Get a sequence parameter value

        scene: Index of scene
        phrase: Index of phrase
        sequence: Index of sequence
        param: Name of parameter (camelCase)
        Returns: Parameter value

        param may be: mode, group, name, repeat, followaction, followParam
        """

        try:
            if sequence == PHRASE_CHANNEL:
                return self.state["scenes"][scene]["phrases"][phrase][param]
            else:
                state_seq = self.state["scenes"][scene]["phrases"][phrase]["sequences"][sequence][param]
        except Exception as e:
            logging.warning(f"Failed to get sequence parameter {param}: {e}")
        return 0

    def get_pattern(self, scene, phrase, sequence, track, pos):
        """ Get the index of a pattern within a sequence

        scene: Index of scene
        phrase: Index of phrase
        sequence: Index of sequence
        track: Index of track
        pos: Position within track
        Returns: Pattern index or None on failure
        """

        try:
            return self.state["scenes"][scene]["phrases"][phrase]["sequences"][sequence]["tracks"][track]["patns"][str(pos)]
        except Exception as e:
            logging.warning(f"Failed to get pattern: {e}")
        return None

    def get_pattern_event(self, pattern, event, param):
        """ Get a pattern event parameter from the state cache

        pattern: Index of pattern
        event: Index of event
        param: Name of parameter
        Returns: Parameter value
        """

        try:
            idx = PATTERN_PARAMS.index(param)
            return self.state["patns"][str(pattern)]["events"][event][idx]
        except Exception as e:
            logging.warning(f"Failed to get pattern event parameter {param}")


# -------------------------------------------------------------------------------
