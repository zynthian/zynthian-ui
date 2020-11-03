/**	Define constants used by step sequencer library */
#pragma once
#include <cstdint>

#define DEFAULT_TEMPO	120 // March time (120 BPM)
#define DEFAULT_TIMESIG	0x0404 // Common time (4/4)

// Play mode
#define DISABLED		0
#define ONESHOT			1
#define LOOP			2
#define ONESHOTALL		3
#define LOOPALL			4
#define ONESHOTSYNC		5
#define LOOPSYNC		6
#define LASTPLAYMODE	6

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

struct MIDI_MESSAGE {
	uint8_t command = 0;
	uint8_t value1 = 0;
	uint8_t value2 = 0;
};

