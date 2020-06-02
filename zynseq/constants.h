/**	Define constants used by step sequencer library */
#pragma once
#include <cstdint>

// Play mode
#define DISABLED		0
#define ONESHOT			1
#define LOOP			2
#define ONESHOTALL		3
#define LOOPALL			4
#define LASTPLAYMODE	4

// Play status
#define STOPPED			0
#define PLAYING			1
#define STOPPING		2
#define STARTING		3
#define LASTPLAYSTATUS	3

// MIDI commands
#define MIDI_POSITION	0xF2
#define MIDI_SONG		0xF3
#define MIDI_CLOCK		0xF8
#define MIDI_START		0xFA
#define MIDI_CONTINUE	0xFB
#define MIDI_STOP		0xFC
#define MIDI_NOTE_OFF	0x80
#define MIDI_NOTE_ON	0x90
#define MIDI_CONTROL	0xB0

// Master track event types
#define MASTER_EVENT_TEMPO 1

struct MIDI_MESSAGE {
	uint8_t command;
	uint8_t value1;
	uint8_t value2;
};
