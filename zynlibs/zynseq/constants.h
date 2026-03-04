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

#define DEFAULT_TEMPO 120.0 // March time (120 BPM)
#define DEFAULT_BPB 4  // Default time signature (Beats Per Bar)
#define PHRASE_CHANNEL 32 // Phrase launcher channel

// Play modes START & END are OR'd to provide mode
// Bits 0..1 Stop mode
#define MODE_END_END 0       // Stop at end of sequence
#define MODE_END_SYNC 1      // Stop at next sync
#define MODE_END_IMMEDIATE 2 // Stop immediately
// Bit 2 Start mode
#define MODE_START_SYNC 0      // Start at next sync
#define MODE_START_IMMEDIATE 4 // Start immediately

// Clock trigger flags
#define CLOCK_TRIG_MIDI 1    // Clock has triggered a MIDI event
#define CLOCK_TRIG_TEMPO 2   // Clock has triggered a tempo change
#define CLOCK_TRIG_TIMESIG 4 // Clock has triggered a time signature change
#define CLOCK_TRIG_SEQEND 8  // Clock has triggered a sequence end
#define CLOCK_TRIG_PHRASE 16 // Clock has triggered a phrase change

// Clock rates
#define PPQN_INTERNAL 1920  // Quantity of sequencer clock pulses in each beat
#define PPQN_MIDI 24        // Quantity of MIDI clock pulses in each beat

// Play status (bit 0 = playing)
#define STOPPED 0       // Sequence is stopped
#define PLAYING 1       // Sequence is playing
#define STARTING 2      // Sequence is paused waiting to start
#define STOPPING 3      // Sequence is playing waiting to stop
#define FORCED_STOP 4   // Sequence is stopped immediately
#define STOPPING_SYNC 5 // Sequence is playing waiting to stop at next sync point
#define CHILD_PLAYING 6 // Child (of phrase launcher) sequence is playing
#define CHILD_STOPPING 8 // Child (of phrase launcher) sequence is stopping

// Metronome modes
enum METRO_MODES {
    METRO_MODE_OFF,         // Disable metronome
    METRO_MODE_TRANSPORT,   // Play metronome only when transport running
    METRO_MODE_ON,          // Play metronome
    METRO_MODE_INTRO,       // Play metronome only when trasport stopped
    METRO_MODE_NO_PEEP,     // Play metronome without accent
    METRO_MODE_SILENT,      // Play transport but don't play metronome
    METRO_MODE_LAST         // Dummy - used for range check
};

// Jack transport modes
enum JTRANS_MODES {
    JTRANS_MODE_OFF,        // Disable jack transport
    JTRANS_MODE_LOCK,       // Lock jack transport to internal transport
    JTRANS_MODE_TRIG,       // Trigger jack transport start from internal transport start, don't auto stop
    JTRANS_MODE_ON,          // Enable jack transport running continually
    JTRANS_MODE_LAST        // Dummy - usef for range check
};

// Local transport flags
#define TRANSPORT_CLIENT_ZYNSEQ   1
#define TRANSPORT_CLIENT_METRO    2

// Follow action
enum FOLLOW_ACTION {
    FOLLOW_ACTION_NONE,
    FOLLOW_ACTION_RELATIVE,
    FOLLOW_ACTION_ABSOLUTE
};

// MIDI commands
static const uint8_t MIDI_NOTE_OFF = 0x80;
static const uint8_t MIDI_NOTE_ON = 0x90;
static const uint8_t MIDI_POLY_PRESSURE = 0xA0;
static const uint8_t MIDI_CONTROL = 0xB0;
static const uint8_t MIDI_PROGRAM = 0xC0;
static const uint8_t MIDI_CHAN_PRESSURE = 0xD0;
static const uint8_t MIDI_PITCHBEND = 0xE0;
static const uint8_t MIDI_SYSEX_START = 0xF0;
static const uint8_t MIDI_TIMECODE = 0xF1;
static const uint8_t MIDI_POSITION = 0xF2;
static const uint8_t MIDI_SONG = 0xF3;
static const uint8_t MIDI_TUNE = 0xF6;
static const uint8_t MIDI_SYSEX_END = 0xF7;
static const uint8_t MIDI_CLOCK = 0xF8;
static const uint8_t MIDI_START = 0xFA;
static const uint8_t MIDI_CONTINUE = 0xFB;
static const uint8_t MIDI_STOP = 0xFC;
static const uint8_t MIDI_ACTIVE_SENSE = 0xFE;
static const uint8_t MIDI_RESET = 0xFF;

struct MIDI_MESSAGE {
    uint8_t command = 0;
    uint8_t value1 = 0;
    uint8_t value2 = 0;
};
