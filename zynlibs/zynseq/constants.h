/**    Define constants used by step sequencer library */
#pragma once
#include <cstdint>

#define DEFAULT_TEMPO    120 // March time (120 BPM)

// Play mode
#define DISABLED        0 // Does not start, stops immediately
#define ONESHOT         1 // Play once, stops immediately - Should it reset to zero when stopped?
#define LOOP            2 // Loop whole sequence restarting immediately at end of sequence, stop at end of sequence
#define ONESHOTALL      3 // Play once all way to end, stop at end of sequence
#define LOOPALL         4 // Play whole sequence then start again at next sync point, stop at end of sequence
#define ONESHOTSYNC     5 // Play once until sync point truncating if necessary, stop at sync point
#define LOOPSYNC        6 // Play sequence looping at sync point, truncating if necessary, stop at sync point
#define LASTPLAYMODE    6

// Play status
#define STOPPED         0 // Sequence is stopped
#define PLAYING         1 // Sequence is playing
#define STOPPING        2 // Sequence is playing waiting to stop
#define STARTING        3 // Sequence is paused waiting to start
#define RESTARTING      4 // Sequence is paused waiting to start or play (on next clock cycle)
#define LASTPLAYSTATUS  4

// MIDI commands
#define MIDI_POSITION   0xF2
#define MIDI_SONG       0xF3
#define MIDI_CLOCK      0xF8
#define MIDI_START      0xFA
#define MIDI_CONTINUE   0xFB
#define MIDI_STOP       0xFC
#define MIDI_NOTE_OFF   0x80
#define MIDI_NOTE_ON    0x90
#define MIDI_CONTROL    0xB0

struct MIDI_MESSAGE {
    uint8_t command = 0;
    uint8_t value1 = 0;
    uint8_t value2 = 0;
};

