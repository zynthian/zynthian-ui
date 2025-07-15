/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020-2023 Brian Walton <brian@riban.co.uk>
 *
 * ******************************************************************
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * For a full copy of the GNU General Public License see the LICENSE.txt file.
 *
 * ******************************************************************

    Define constants used by step sequencer library
*/

#pragma once
#include <cstdint>

#define DEFAULT_TEMPO 120 // March time (120 BPM)

// Play modes START, END and ENABLED are OR'd to provide mode
// Bits 0..1 Stop mode
#define MODE_END_END 0       // Stop at end of sequence
#define MODE_END_SYNC 1      // Stop at next sync
#define MODE_END_IMMEDIATE 2 // Stop immediately
// Bit 2 Start mode
#define MODE_START_SYNC 0      // Start at next sync
#define MODE_START_IMMEDIATE 4 // Start immediately
// Bit 7 Enable mode
#define MODE_ENABLE 128 // Bit 7 set if sequence enabled

// Play status
#define STOPPED 0       // Sequence is stopped
#define PLAYING 1       // Sequence is playing
#define STOPPING 2      // Sequence is playing waiting to stop
#define STARTING 3      // Sequence is paused waiting to start
#define STOPPING_SYNC 4 // Sequence is playing waiting to stop at next sync point

// Follow action
enum FOLLOW_ACTION {
    FOLLOW_ACTION_NONE,
    FOLLOW_ACTION_LOOP,
    FOLLOW_ACTION_NEXT,
    FOLLOW_ACTION_PREV,
    FOLLOW_ACTION_JUMP
};

// MIDI commands
#define MIDI_NOTE_OFF 0x80
#define MIDI_NOTE_ON 0x90
#define MIDI_POLY_PRESSURE 0xA0
#define MIDI_CONTROL 0xB0
#define MIDI_PROGRAM 0xC0
#define MIDI_CHAN_PRESSURE 0xD0
#define MIDI_PITCHBEND 0xE0
#define MIDI_SYSEX_START 0xF0
#define MIDI_TIMECODE 0xF1
#define MIDI_POSITION 0xF2
#define MIDI_SONG 0xF3
#define MIDI_TUNE 0xF6
#define MIDI_SYSEX_END 0xF7
#define MIDI_CLOCK 0xF8
#define MIDI_START 0xFA
#define MIDI_CONTINUE 0xFB
#define MIDI_STOP 0xFC
#define MIDI_ACTIVE_SENSE 0xFE
#define MIDI_RESET 0xFF

struct MIDI_MESSAGE {
    uint8_t command = 0;
    uint8_t value1 = 0;
    uint8_t value2 = 0;
};
