#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for Akai MPK mini MK3
# A mode enforcer implemented as a python jack client.
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

import logging
import multiprocessing as mp

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base

# Following from: https://github.com/Carlborg/hardpush/blob/master/hardpush.ino
# All scales seem to work as 12-semitone scales. (otherwise they would need the octave-distance at the end)
# Define scales in the form 'semitones added to tonic'
_MODES = {
    "Chromatic":          [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "Major":              [0, 2, 4, 5, 7, 9, 11],
    "Minor":              [0, 2, 3, 5, 7, 8, 10],
    "Dorian":             [0, 2, 3, 5, 7, 9, 10],
    "Mixolydian":         [0, 2, 4, 5, 7, 9, 10],
    "Lydian":             [0, 2, 4, 6, 7, 9, 11],
    "Phrygian":           [0, 1, 3, 5, 7, 8, 10],
    "Locrian":            [0, 1, 3, 4, 7, 8, 10],
    "Diminished":         [0, 1, 3, 4, 6, 7, 9, 10],
    "Whole-Half":         [0, 2, 3, 5, 6, 8, 9, 11],
    "Whole Tone":         [0, 2, 4, 6, 8, 10],
    "Minor Blues":        [0, 3, 5, 6, 7, 10],
    "Minor Pentatonic":   [0, 3, 5, 7, 10],
    "Major Pentatonic":   [0, 2, 4, 7, 9],
    "Harmonic Minor":     [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor":      [0, 2, 3, 5, 7, 9, 11],
    "Super Locrian":      [0, 1, 3, 4, 6, 8, 10],
    "Bhairav":            [0, 1, 4, 5, 7, 8, 11],
    "Hungarian Minor":    [0, 2, 3, 6, 7, 8, 11],
    "Minor Gypsy":        [0, 1, 4, 5, 7, 8, 10],
    "Hirojoshi":          [0, 2, 3, 7, 8],
    "In-Sen":             [0, 1, 5, 7, 10],
    "Iwato":              [0, 1, 5, 6, 10],
    "Kumoi":              [0, 2, 3, 7, 9],
    "Pelog":              [0, 1, 3, 4, 7, 8],
    "Spanish":            [0, 1, 3, 4, 5, 6, 8, 10]
}

_MODE_BANKS = {
    "notes": [
        # Bank A
        "Chromatic",
        "Major",
        "Minor",
        "Dorian",
        "Mixolydian",
        "Lydian",
        "Phrygian",
        "Locrian",
        # Bank B
        "Chromatic",
        "Harmonic Minor",
        "Melodic Minor",
        "Super Locrian",
        "Bhairav",
        "Hungarian Minor",
        "Minor Gypsy",
        None
    ],
    "CCs": [
        # Bank A
        "Chromatic",
        "Minor Pentatonic",
        "Major Pentatonic",
        "Hirojoshi",
        "In-Sen",
        "Iwato",
        "Kumoi",
        None,
        # Bank B
        "Chromatic",
        "Diminished",
        "Whole-Half",
        "Spanish",
        "Whole Tone",
        "Minor Blues",
        "Pelog",
        None
    ]
}

_WHITE_NOTES_OFFSET = [0, None, 1, None, 2, 3, None, 4, None, 5, None, 6]
_BLACK_NOTES_OFFSET = [None, 0, None, 1, None, None, 2, None, 3, None, 4, None]
_6_NOTES_OFFSET = [0, None, 1, None, 2, 3, None, 4, None, 5, None, None]
_8_NOTES_OFFSET = [0, None, 1, 2, 3, 4, None, 5, None, 6, None, 7]

# ------------------------------------------------------------------------------------------------------------------
# Mode enforcer for the Akai MPK mini MK3
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_akai_mpk_moder(zynthian_ctrldev_base):

    dev_ids = ["MPK mini 3 IN 1"]
    driver_description = "Mode enforcer. Use pads notes & CCs to change mode:\n"\
                         "+ Notes / Bank A (White Keys): Chromatic, Major, Minor, Dorian, Mixolydian, Lydian, Phrygian, Locrian\n"\
                         "+ Notes / Bank B (White Keys): Chromatic, Harmonic Minor, Melodic Minor, Super Locrian, Bhairav, Hungarian Minor, Minor Gypsy\n"\
                         "+ CC / Bank A (Black Keys): Chromatic, Minor Pentatonic, Major Pentatonic, Hirojoshi, In-Sen, Iwato, Kumoi\n"\
                         "+ CC / Bank B (Custom Keys): Chromatic, Diminished, Whole-Half, Spanish, While Tone, Minor Blues, Pelog"

    unroute_from_chains = 0b0000001000000000  # Unroute channel 10 (akai MPK mini's pads)
    autoload_flag = False

    # IPC => multiprocessing.Value() object to share an integer variable (mode  index) across processes
    mode_keys = list(_MODES.keys())
    mode_values = list(_MODES.values())
    mode_index = mp.Value('i', 0)

    def midiproc_task(self):
        self.midiproc_task_reset_signal_handlers()

        import jack
        import struct
        from threading import Event

        # First 4 bits of status byte:
        NOTEON = 0x9
        NOTEOFF = 0x8

        client = jack.Client(self.midiproc_jackname)
        inport = client.midi_inports.register('in_1')
        outport = client.midi_outports.register('out_1')
        event = Event()

        @client.set_process_callback
        def process(frames):
            # Get mode info
            mode_notes = self.mode_values[self.mode_index.value]
            n_notes = len(mode_notes)
            # Process MIDI data
            outport.clear_buffer()
            for offset, indata in inport.incoming_midi_events():
                if len(indata) == 3:
                    status, pitch, vel = struct.unpack('3B', indata)
                    # Process notes from all channels except channel 10
                    if (status & 0xF) != 9 and status >> 4 in (NOTEON, NOTEOFF):
                        # Translate key to mode note
                        note_offset = pitch % 12
                        pitch_base = pitch - note_offset
                        # 7-notes modes
                        if n_notes == 7:
                            # Use only white notes =>
                            note_offset = _WHITE_NOTES_OFFSET[note_offset]
                            if note_offset is not None:
                                pitch = pitch_base + mode_notes[note_offset]
                            else:
                                continue
                        # 5-notes modes
                        elif n_notes == 5:
                            # Use only black notes =>
                            note_offset = _BLACK_NOTES_OFFSET[note_offset]
                            if note_offset is not None:
                                pitch = pitch_base + mode_notes[note_offset]
                            else:
                                continue
                        # 6-notes modes
                        elif n_notes == 6:
                            # Use white notes except B =>
                            note_offset = _6_NOTES_OFFSET[note_offset]
                            if note_offset is not None:
                                pitch = pitch_base + mode_notes[note_offset]
                            else:
                                continue
                        # 8-notes modes
                        elif n_notes == 8:
                            # Use white notes + black D# =>
                            note_offset = _8_NOTES_OFFSET[note_offset]
                            if note_offset is not None:
                                pitch = pitch_base + mode_notes[note_offset]
                            else:
                                continue
                        # Other modes? => Currently no modes in this category!
                        elif n_notes < 12:
                            # Use only notes in mode, disable notes out of mode
                            if note_offset in mode_notes:
                                pass
                            else:
                                continue
                        # Chromatic
                        else:
                            pass
                        try:
                            outport.write_midi_event(offset, (status, pitch, vel))
                        except:
                            pass
                        continue

                    # Pass through
                    outport.write_midi_event(offset, indata)

        @client.set_shutdown_callback
        def shutdown(status, reason):
            logging.debug('JACK-CLIENT shutdown:', reason, status)
            event.set()

        with client:
            event.wait()

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F
        # Use the Akai MPK mini's pads (channel 10) for selecting the chord =>
        if evchan == 9:
            # Pad Notes, Bank A & B:
            if evtype == 0x9:
                note = ev[1] & 0x7F
                if 36 <= note <= 51:
                    mode_key = _MODE_BANKS["notes"][note - 36]
                    try:
                        self.mode_index.value = self.mode_keys.index(mode_key)
                    except:
                        pass
                    logging.debug(f"MODE => {mode_key} ({self.mode_index.value})")
                    return True
            # Pad CCs, Bank A & B:
            elif evtype == 0xB:
                ccnum = ev[1] & 0x7F
                ccval = ev[2] & 0x7F
                if ccval > 0 and 16 <= ccnum <= 31:
                    mode_key = _MODE_BANKS["CCs"][ccnum - 16]
                    try:
                        self.mode_index.value = self.mode_keys.index(mode_key)
                    except:
                        pass
                    logging.debug(f"MODE => {mode_key} ({self.mode_index.value})")
                    return True

# ------------------------------------------------------------------------------
