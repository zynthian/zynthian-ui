
/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020-2026 Brian Walton <brian@riban.co.uk>
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
 */

#include <cstring> // provides strcmp
#include <set>
#include <string>
#include <vector>
#include <array>

#include <jack/jack.h>      // provides JACK interface
#include <jack/midiport.h>  // provides JACK MIDI interface
#include <stdio.h>          // provides printf
#include <stdlib.h>         // provides exit
#include <thread>           // provides thread for timer
#include <cmath>            // provides sqrt
#include <nlohmann/json.hpp> // provides json

#include "metronome.h"       // metronome wav data
#include "pattern.h"         // provides pattern objects
#include "sequencemanager.h" // provides management of sequences, patterns, events, etc
#include "timebase.h"        // provides timebase event map
#include "zynseq.h"          // exposes library methods as c functions

#define FILE_VERSION 11

#define DPRINTF(fmt, args...)                                                                                                                                  \
    if (g_bDebug)                                                                                                                                              \
    fprintf(stderr, fmt, ##args)

// Structure to capture live recorded MIDI events
struct ev_start {
    uint32_t start;
    uint8_t velocity;
    float offset;
};
static struct ev_start startEvents[128];

jack_port_t* g_pInputPort;            // Pointer to the JACK MIDI input port
jack_port_t* g_pClockInputPort;       // Pointer to the JACK MIDI clock input port
jack_port_t* g_pOutputPort;           // Pointer to the JACK MIDI output port
jack_port_t* g_pClockOutputPort;      // Pointer to the JACK MIDI clock output port
jack_port_t* g_pClippyOutputPort;     // Pointer to the JACK MIDI output port feeding clippy
jack_port_t* g_pMetronomePort;        // Pointer to the JACK metronome audio output port
jack_client_t* g_pJackClient = NULL;  // Pointer to the JACK client
jack_nframes_t g_nSampleRate = 48000; // Quantity of samples per second
uint32_t g_nXruns = 0;

std::multimap<uint32_t, SEQ_EVENT*> g_mSchedule;    // Schedule of sequence events (queue for sending), indexed by scheduled play time (ticks since tick epoch)
SequenceManager g_seqMan;                           // Instance of sequence manager
bool g_naHeldNote[16][128];                         // Array of flags indicating a note has been played on a MIDI channel
uint8_t g_nScene                    = 0;            // Index of currently selected scene
Pattern* g_pPattern                 = NULL;         // Pointer to currently edited pattern
uint16_t g_nPhrase                  = 0;            // Index of currently edited phrase
uint16_t g_nSequence                = 0;            // Index of currently edited sequence
bool g_bMutex                       = false;        // Mutex lock for access to g_mSchedule
bool g_bDebug                       = false;        // True to output debug info
bool g_bPatternModified             = false;        // True if pattern has changed since last check
bool g_bDirty                       = false;        // True if anything has been modified
uint32_t g_nTransportClients        = 0;            // Bitwise flags indicating which clients have requested local transport
uint8_t g_nTransportState           = STOPPED;      // State of local (non-jack) transport
bool g_bTransportRolling            = false;        // True if (arranger) transport rolling forward bars
bool g_bMidiRecord                  = false;        // True to add notes to current pattern from MIDI input
uint8_t g_nSustainValue             = 0;            // Last sustain pedal value during note input (recording)
uint32_t g_nSustainStart            = 0;            // Step when sustain pedal was last pressed
uint32_t g_nLastStepCC              = 0;            // Step when last => WARNING!! Doesn't work if capturing several CC at once!
uint8_t g_nPlayingSequences         = 0;            // Bitwise flga of playing/starting sequences

char g_sName[256];                                  // Buffer to hold sequence name so that it can be sent back for Python to parse
uint8_t g_nInputRest                = 0xFF;         // MIDI note number that creates rest in pattern
uint16_t g_nVerticalZoom            = 16;           // Quantity of rows to show in pattern and arranger view
uint16_t g_nHorizontalZoom          = 16;           // Quantity of beats to show in arranger view

// Patter copy/paste buffer
Pattern* g_pPatternBuffer           = NULL;         // Pointer to pattern copy/paste buffer

// Transport variables apply to next period
uint32_t g_nDefaultBpb                = DEFAULT_BPB; // Default quantity of beats (quater notes) in each bar
uint32_t g_nBeatsPerBar               = DEFAULT_BPB; // Current quantity of beats (quater notes) in each bar (sync point division)
uint32_t g_nBeatType                  = 4;           // Time signature denominator (not used)
double g_dTempo                       = 120.0;
double g_dFramesPerTick;                           // Quantity of frames in each sequence clock cycle (tick)
bool g_bTimebaseChanged               = false;     // True to trigger recalculation of timebase parameters
Timebase* g_pTimebase                 = NULL;      // Pointer to the timebase object for selected song
uint32_t g_nBar                       = 1;         // Current bar
uint32_t g_nBeat                      = 1;         // Current beat within bar
uint32_t g_nTick                      = 0;         // Current tick within bar
uint32_t g_nBarStartTick              = 0;         // Quantity of ticks from start of song to start of current bar
uint32_t g_nExtClockPPQN              = PPQN_MIDI; // Quantity of PPQN of the external clock

float g_fSwingAmount = 0.0; // Swing amount, range from 0 to 1, but values over 0.5 are not "MPC swing"
float g_fHumanTime = 0.0;   // Timing Humanization, range from 0 to FLOAT_MAX
float g_fHumanVelo = 0.0;   // Velocity Humanization, range from 0 to FLOAT_MAX
float g_fPlayChance = 1.0;  // Probability for playing notes (0 = Notes are not played, 0.5 = Notes plays with prob.50%, 1 = All notes play always)

size_t g_nMetronomePtr = -1;   // Position within metronome click wav data (-1 if not playing, e.g. between beats)
float g_fMetronomeLevel = 1.0; // Factor to scale metronome level (volume)
uint8_t g_nMetronomeMode = 0;  // Metonome play mode
struct metro_wav_t g_metro_pip;
struct metro_wav_t g_metro_peep;
struct metro_wav_t* g_pMetro = &g_metro_pip; // Pointer to the current metronome sound (pip/peep)

char* g_pState = nullptr; // Pointer used for temporary transfer of state string

using json = nlohmann::ordered_json;

// ** Internal (non-public) functions  (not delcared in header so need to be in correct order in source file) **

// Enable / disable debug output
void enableDebug(bool bEnable) {
    fprintf(stderr, "libseq setting debug mode %s\n", bEnable ? "on" : "off");
    g_bDebug = bEnable;
}

// Convert tempo to frames per clock
void updateClockTiming() {
    g_dFramesPerTick = 60.0 * g_nSampleRate / (g_dTempo * PPQN_INTERNAL);
}

void onJackConnect(jack_port_id_t source, jack_port_id_t dest, int connect, void* args) {
    if (jack_port_by_id(g_pJackClient, dest) == g_pClockInputPort) {
        setTempo(g_dTempo);
        DPRINTF("%u connections to MIDI clock port\n", jack_port_connected(g_pClockInputPort));
    }
}

// Handle timebase change
void onJackTimebase(jack_transport_state_t nState, jack_nframes_t nFramesInPeriod, jack_position_t* pPosition, int bUpdate, void* pArgs) {
    pPosition->bar = g_nBar;
    pPosition->beat = g_nBeat;
    pPosition->tick = g_nTick;
    pPosition->bar_start_tick = g_nBarStartTick;
    pPosition->beats_per_minute = g_dTempo;
    pPosition->beats_per_bar = g_nBeatsPerBar;
    pPosition->ticks_per_beat = PPQN_INTERNAL;
    pPosition->valid = JackPositionBBT;
}

/*  Process jack period
    nFrames: Quantity of frames in this period
    pArgs: Parameters passed to function by main thread (not used here)

    [For info]
    jack_last_frame_time() returns the quantity of samples since JACK started until start of this period
    jack_midi_event_write sends MIDI message at sample time sequence within this period

    [Process]
    Process incoming MIDI events
    Iterate through events scheduled to trigger within this process period
    For each event, add MIDI events to the output buffer at appropriate frame offset
    Remove events from schedule

    Schedule holds events, indexed by their scheduled execution time in frames since jack epoch.
*/
int onJackProcess(jack_nframes_t nFrames, void* pArgs) {
    // Transport & Clock
    static uint64_t nNow = 0;
    static jack_nframes_t nLastNow32 = 0;
    static uint64_t nLastExtClockFrame = 0; // Frames since jack epoch of last external clock
    static double dNextIntClockFrame = 0.0; // Frames since jack epoch of next internal clock
    static uint32_t nExtClk = 0; // Count of external clocks in this beat (wrap at PPQN)
    static uint32_t nTickTime = 0; // Quantity of elapsed ticks since tick epoch that next event will be processed
    static uint32_t nBeatsPerBar = g_nBeatsPerBar; // Sequencer's live beats per bar, updated from g_nBeatsPerBar on bar boundary
    static int64_t nNextBeatTime = 0; // Tick time of next beat
    static bool bRolling = g_bTransportRolling; // Transport rolling bars, updates g_bTranportRolling on next bar

    // Populate 64-bit monotonic frame clock (to avoid 24 hour overflow)
    jack_nframes_t nNow32 = jack_last_frame_time(g_pJackClient);
    if (nNow32 < nLastNow32)
        nNow += 0x100000000ULL;
    nNow = (nNow & 0xFFFFFFFF00000000ULL) | nNow32;

    // Metronome audio output buffer
    jack_default_audio_sample_t* pOutMetronome = (jack_default_audio_sample_t*)jack_port_get_buffer(g_pMetronomePort, nFrames);
    memset(pOutMetronome, 0, sizeof(jack_default_audio_sample_t) * nFrames);

    // MIDI output buffers
    void* pOutputBuffer = jack_port_get_buffer(g_pOutputPort, nFrames);
    void* pClockBuffer = jack_port_get_buffer(g_pClockOutputPort, nFrames);
    void* pClippyBuffer = jack_port_get_buffer(g_pClippyOutputPort, nFrames);
    jack_midi_clear_buffer(pOutputBuffer);
    jack_midi_clear_buffer(pClockBuffer);
    jack_midi_clear_buffer(pClippyBuffer);

    // Get mutex lock to protect access to MIDI output schedule
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;

    std::vector<jack_nframes_t> vTicks; // Vector of internal tick offsets within this jack period

    // Process MIDI input
    jack_midi_event_t midiEvent;
    void* pInputBuffer;

    // Ensure next clock frame is not in the past
    if (dNextIntClockFrame < nNow)
        dNextIntClockFrame = nNow;

    // MIDI Clock input
    pInputBuffer = jack_port_get_buffer(g_pClockInputPort, nFrames);
    for (jack_nframes_t i = 0; i < jack_midi_get_event_count(pInputBuffer); ++i) {
        if (jack_midi_event_get(&midiEvent, pInputBuffer, i))
            continue;

        switch (midiEvent.buffer[0]) {
            case MIDI_CLOCK: {
                uint32_t nExpectedTicksBeforeClk = midiEvent.time / g_dFramesPerTick;
                // First update tempo to get current clock period
                double dTempo = 60.0 * g_nSampleRate / (double(g_nExtClockPPQN) * (nNow + midiEvent.time - nLastExtClockFrame));
                setTempo(dTempo);
                nLastExtClockFrame = nNow + midiEvent.time;
                uint32_t nTicksBeforeClk = midiEvent.time / g_dFramesPerTick;
                int32_t nTickDelta = nTicksBeforeClk - nExpectedTicksBeforeClk;
                nNextBeatTime += nTickDelta;
                break;
            }
            case MIDI_START: {
                // Rx start on clock port so restart any playing sequences - this may cause disruption to playback - as expected
                g_nBar = 1;
                g_nBeat = 1;
                nExtClk = 0;
                g_nBarStartTick = 0;
                fprintf(stderr, "START\n");
                break;
            }
            case MIDI_POSITION: {
                // Rx song position on clock port - reset to bar boundary, e.g. used by bar clock signal
                uint16_t pos = midiEvent.buffer[1] + (midiEvent.buffer[2] << 7);
                if (pos == 0) {
                    fprintf(stderr, "MIDI SONG POSITION %u\n", pos);
                    g_nBeat = 1;
                }
                break;
            }
        }
    }

    // Populate remaining ticks in this period, at current tempo
    for (; dNextIntClockFrame < nNow + nFrames; dNextIntClockFrame += g_dFramesPerTick) {
        vTicks.push_back(dNextIntClockFrame - nNow);
    }

    // Process normal MIDI input (ignore MIDI CLOCK)
    pInputBuffer = jack_port_get_buffer(g_pInputPort, nFrames);
    jack_nframes_t nCount = jack_midi_get_event_count(pInputBuffer);
    uint8_t bPatternRecording = (g_bMidiRecord && g_pPattern);
    for (jack_nframes_t i = 0; i < nCount; i++) {
        if (jack_midi_event_get(&midiEvent, pInputBuffer, i))
            continue;
        // Process MIDI RT-events => clock/tranport events
        switch (midiEvent.buffer[0]) {
            case MIDI_STOP:
                // Rx stop on any port - stops transport rolling on next bar
                bRolling = false;
                break;
            case MIDI_START:
                // Rx start on any port - starts transport rolling on next bar
                bRolling = true; //!@todo Use bRolling to acutally start rolling
                //!@todo reset to start of bar
                break;
            case MIDI_CONTINUE:
                // Rx continue on any port - starts jack transport on next bar
                bRolling = true;
                break;
            /*
            case MIDI_POSITION:
            {
                //!@todo Should we let Jack timebase master manage MIDI position changes?
                uint32_t nPos = (midiEvent.buffer[1] + (midiEvent.buffer[2] << 7)) * 6;
                DPRINTF("StepJackClient POSITION %d (clocks)\n", nPos);
                break;
            }
            */
            case MIDI_SONG: {
                // MIDI song selection will change selected sequencer scene
                uint8_t nSong = midiEvent.buffer[1];
                DPRINTF("StepJackClient Select song %u\n", nSong);
                if (nSong < g_seqMan.getNumScenes())
                    setScene(nSong); //!@todo Restricted to existing scenes but may want to allow creating new scene
                break;
            }
            default:
                break;
        }

        // Handle MIDI events for programming patterns from MIDI input
        if (bPatternRecording) {
            uint32_t nStep = getPatternPlayhead();
            uint8_t nPlayState = g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayState();
            uint8_t nCommand = midiEvent.buffer[0] & 0xF0;
            uint8_t nNum1 = midiEvent.buffer[1];
            uint8_t nNum2 = midiEvent.buffer[2];

            // Real Time Capture (while playing)
            if (nPlayState) {
                // Note on event
                if (nCommand == MIDI_NOTE_ON && nNum2 > 0) {
                    // Current event time minus the latency delay (1 period = nFrames), converted to clocks
                    int fpos = int(midiEvent.time) - nFrames;
                    double dclk = double(fpos) / g_dFramesPerTick;
                    uint32_t nPlayPos = g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayPosition() + int(dclk);
                    //fprintf(stderr, "START NOTE %d => %d (DCLK = %f)\n", nNum1, nPlayPos, dclk);
                    startEvents[nNum1].start = nPlayPos;
                    startEvents[nNum1].velocity = nNum2;
                }
                // Note off event
                else if ((nCommand == MIDI_NOTE_ON && nNum2 == 0) || nCommand == MIDI_NOTE_OFF) {
                    if (startEvents[nNum1].start != -1) {
                        // Current event time minus the latency delay (1 period = nFrames), converted to clocks
                        int fpos = int(midiEvent.time) - nFrames;
                        double dclk = double(fpos) / g_dFramesPerTick;
                        uint32_t nPlayPos = g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayPosition() + int(dclk);
                        //fprintf(stderr, "END NOTE %d => %d (DCLK = %f)\n", nNum1, nPlayPos, dclk);
                        uint32_t nClocksPerStep = g_pPattern->getClocksPerStep();
                        uint32_t nStart = startEvents[nNum1].start / nClocksPerStep;
                        float fOffset = double(startEvents[nNum1].start % nClocksPerStep) / nClocksPerStep;
                        float fDuration = double(int(nPlayPos) - int(startEvents[nNum1].start)) / nClocksPerStep;
                        // Constrain duration
                         if (fDuration < 0.0)
                            fDuration += g_pPattern->getSteps();
                        if (fDuration < 1.0)
                            fDuration = 1.0;

                       // Add note to pattern
                        g_pPattern->addNote(nStart, nNum1, startEvents[nNum1].velocity, fDuration, fOffset);
                        //fprintf(stderr, "Captured Note %d at %d + %f with duration %f\n", nNum1, nStart, fOffset, fDuration);
                        // Reset note in event buffer
                        startEvents[nNum1].start = -1;
                        // Flag pattern as modified
                        setPatternModified(g_pPattern, true, false);
                    }
                }
                // CC event
                else if (nCommand == MIDI_CONTROL) {
                    // Manage sustain pedal (CC64)
                    if (nNum1 == 64) {
                        if (nNum2 > 0 && g_nSustainValue == 0) {
                            g_nSustainValue = nNum2;
                            g_nSustainStart = nStep;
                            // Add new pedal press
                            g_pPattern->addControl(g_nSustainStart, 64, g_nSustainValue, g_nSustainValue);
                            setPatternModified(g_pPattern, true, false);
                        } else if (nNum2 == 0) {
                            if (g_nSustainValue > 0) {
                                // Add pedal release
                                g_pPattern->addControl(nStep, 64, 0, 0);
                                // The next should be improved to be functional!
                                // Remove old pedals => "Overdubbing" sustain pedal is a mess!
                                //g_pPattern->removeControlInterval(0, g_pPattern->getSteps() - 1, 64);
                                setPatternModified(g_pPattern, true, false);
                            }
                            g_nSustainValue = 0;
                        }
                        // else => Other cases must be bouncing or pedal "artifacts" that we ignore
                        // Manage rest of CCs
                    } else {
                        // Remove old CCs => "Overdubbing" CC is a mess!
                        if (g_nLastStepCC < nStep)
                            g_pPattern->removeControlInterval(g_nLastStepCC + 1, nStep, nNum1);
                        // Add new CC event
                        g_pPattern->addControl(nStep, nNum1, nNum2, nNum2);
                        g_nLastStepCC = nStep;
                        setPatternModified(g_pPattern, true, false);
                    }
                }
            }
            // Step capture
            else {
                bool bAdvance = false;
                // Use sustain pedal for advance step
                if (nCommand == MIDI_CONTROL && nNum1 == 64) {
                    if (nNum2 > 0)
                        g_nSustainValue = nNum2;
                    else {
                        g_nSustainValue = 0;
                        bAdvance = true;
                    }
                }
                // Note on event
                else if (nCommand == MIDI_NOTE_ON && nNum2) {
                    setPatternModified(g_pPattern, true, false);
                    uint32_t nDuration = getNoteDuration(nStep, nNum1);
                    if (g_nSustainValue > 0)
                        g_pPattern->addNote(nStep, nNum1, nNum2, nDuration + 1);
                    else {
                        bAdvance = true;
                        if (nDuration)
                            g_pPattern->removeNote(nStep, nNum1);
                        else if (nNum1 != g_nInputRest)
                            g_pPattern->addNote(nStep, nNum1, nNum2, 1);
                    }
                }
                // Advance step
                if (bAdvance && g_nTransportState != PLAYING) {
                    if (++nStep >= g_pPattern->getSteps())
                        nStep = 0;
                    g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->setPlayPosition(nStep * g_pPattern->getClocksPerStep());
                    // printf("libzynseq advancing to step %d\n", nStep);
                }
            }
        }
    }

    // Reset pedal if pattern recording is off
    if (!bPatternRecording && g_nSustainValue > 0) {
        g_nSustainValue = 0;
    }

    // Send MIDI output aligned with first sample of frame resulting in similar latency to audio
    //!@todo Interpolate events across frame, e.g. CC variations

    // Process clock ticks in this period
    jack_nframes_t nMetronomeFrame = 0; // Position within this period of next metronome sample
    uint32_t nPeriodStartTick = nTickTime; // Store the first tick of this period
    for (const auto& nFrame: vTicks) {
        // Iterate clocks within this jack period to prepare MIDI output schedule events

        /* Schedule events in this period
        Pass clock time and schedule to pattern manager so it can populate with events.
        Pass sync pulse so that it can synchronise its sequences, e.g. start zynpad sequences
        */

        bool bBeat = false; // True if start of beat
        bool bSync = false; // True if at start of bar

        // Update local (internal) transport
        if (g_nTransportState == STARTING) {
            g_nTransportState = PLAYING;
            nNextBeatTime = nTickTime + PPQN_INTERNAL;
            g_nBeat = 1;
            bSync = true;
            bBeat = true;
            jack_transport_start(g_pJackClient);
        } else if (g_nTransportState == STOPPING) {
            if (g_nBeat == 1) {
                g_nTransportState = STOPPED;
                jack_transport_stop(g_pJackClient);
                jack_transport_locate(g_pJackClient, 0);
                g_seqMan.resetFollowRepeat();
            }
        }

        if (g_nTransportState == PLAYING) {
            if (nTickTime >= nNextBeatTime) {
                // Beat
                nNextBeatTime = nTickTime + PPQN_INTERNAL;
                nMetronomeFrame = nFrame;
                bBeat = true;
                DPRINTF("Beat at tick %d, frame %u (%llu)\n", nTickTime, nFrame, nNow + nFrame);
                if (++g_nBeat > nBeatsPerBar) {
                    // Bar
                    g_nBeat = 1;
                    bSync = true;
                    if (g_bTransportRolling) {
                        ++g_nBar;
                    }
                }
            }

            // *** THIS IS WHERE THE SEQUENCES ARE CLOCKED ***
            //!@todo Optimise to reduce rate calling clock especially if we increase the clock rate from 24 to 96 or above. Maybe return the time until next check
            uint8_t nPlayingSequences = g_seqMan.clock(nTickTime, &g_mSchedule, bSync);

            // Check for sequenced timebase changes (from patterns)
            if (g_seqMan.isTempoChanged()) {
                float tempo = g_seqMan.getTempo();
                setTempo(tempo);
            }
            if (g_seqMan.isTimeSigChanged()) {
                uint8_t newBpb = g_seqMan.getTimeSig(true);
                if (newBpb > 1) {
                    g_nBeatsPerBar = newBpb;
                }
            }

            if (bSync) { // Bar boundary actions
                // Update time signature
                if (bSync && nBeatsPerBar != g_nBeatsPerBar) {
                    nBeatsPerBar = g_nBeatsPerBar;
                    g_seqMan.setTimeSig(nBeatsPerBar);
                }
                // Stop transport
                if (g_nPlayingSequences != nPlayingSequences) {
                    g_nPlayingSequences = nPlayingSequences;
                    if (!g_nPlayingSequences) {
                        DPRINTF("No sequences playing now: %u clock: %u beat: %u tick: %u\n", nNow, nTickTime, g_nBeat, g_nTick);
                        transportStop(TRANSPORT_CLIENT_ZYNSEQ);
                    }
                }
            }

            // Update transport parameters
            g_nBarStartTick = g_nTick;
        }

        // Send MIDI CLOCK...
        if (nTickTime % (PPQN_INTERNAL / PPQN_MIDI) == 0) {
            // Add a MIDI_CLOCK message to the schedule
            g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(nTickTime, new SEQ_EVENT({nTickTime, 0, MIDI_MESSAGE{MIDI_CLOCK, 0, 0}})));
        }


        if (bBeat) {
            if (g_nMetronomeMode == METRO_MODE_ON ||
            g_nMetronomeMode == METRO_MODE_TRANSPORT && (g_nTransportState == PLAYING || g_bTransportRolling) ||
            g_nMetronomeMode == METRO_MODE_INTRO && !(g_nPlayingSequences & 1)) {
                // Start metronome
                g_nMetronomePtr = 0;
                g_pMetro = bSync ? &g_metro_peep : &g_metro_pip;
            } else if (g_nMetronomeMode == METRO_MODE_NO_PEEP) {
                g_nMetronomePtr = 0;
                g_pMetro = &g_metro_pip;
            }
        }

        ++nTickTime;
    }

    // Play metronome sound
    if (g_nMetronomePtr >= 0) {
        for (int n = nMetronomeFrame; n < nFrames; ++n) {
            if (g_nMetronomePtr < g_pMetro->size) {
                pOutMetronome[n] = g_pMetro->data[g_nMetronomePtr++] * g_fMetronomeLevel;
            } else {
                g_nMetronomePtr = -1;
                break;
            }
        }
    }

    // Process events scheduled to be sent to MIDI output
    size_t nTickIdx = 0;
    auto it = g_mSchedule.begin();
    // Iterate the ticks in this period and events for each tick
    while (it != g_mSchedule.end() && nTickIdx < vTicks.size()) {
        // it->first is the scheduled tickTime of the event
        if (it->first > nPeriodStartTick + nTickIdx)
            ++nTickIdx;
        else {
            // Iterate events scheduled for this tick
            size_t nSize = 1;
            bool bSkip = false;
            if (it->second->msg.command < 0xF4) {
                uint8_t nType = it->second->msg.command;
                if (nType < 0xF0)
                    nType &= 0xF0;
                switch (nType) {
                case MIDI_PROGRAM:
                case MIDI_CHAN_PRESSURE:
                case MIDI_TIMECODE:
                case MIDI_SONG:
                    nSize = 2;
                    break;
                case MIDI_CONTROL:
                    // Skip sustain events if recording and sustain is pressed
                    if (it->second->msg.value1 == 64 && g_nSustainValue > 0)
                        bSkip = true;
                    nSize = 3;
                    break;
                case MIDI_NOTE_ON:
                    g_naHeldNote[it->second->msg.command & 0x0f][it->second->msg.value1] = it->second->msg.value2;
                    nSize = 3;
                    break;
                case MIDI_NOTE_OFF:
                    g_naHeldNote[it->second->msg.command & 0x0f][it->second->msg.value1] = 0;
                    nSize = 3;
                    break;
                default:
                    nSize = 3;
                }
            }
            jack_nframes_t nFrame = vTicks[nTickIdx];
            if (it->second->msg.command >= 0xF8 && it->second->msg.command <= 0xFC) {
                unsigned char* pBuffer = jack_midi_event_reserve(pClockBuffer, nFrame, nSize);
                if (pBuffer == NULL)
                    break; // Exceeded buffer size (or other issue)
                pBuffer[0] = it->second->msg.command;
            } else if (!bSkip) {
               unsigned char* pBuffer = jack_midi_event_reserve(it->second->output == 0xfe ? pClippyBuffer : pOutputBuffer, nFrame, nSize);
                if (pBuffer == NULL)
                    break; // Exceeded buffer size (or other issue)
                pBuffer[0] = it->second->msg.command;
                if (nSize > 1)
                    pBuffer[1] = it->second->msg.value1;
                if (nSize > 2)
                    pBuffer[2] = it->second->msg.value2;
                DPRINTF("Sending MIDI event %x,%x,%x at %llu\n", pBuffer[0], pBuffer[1], pBuffer[2], nNow + nFrame);
            }
            delete it->second;
            it->second = NULL;
        ++it;
        }
        g_mSchedule.erase(g_mSchedule.begin(), it);
    }
    g_bMutex = false;
    return 0;
}

int onJackSampleRateChange(jack_nframes_t nFrames, void* pArgs) {
    DPRINTF("zynseq: Jack sample rate: %u\n", nFrames);
    if (nFrames == 0)
        return 0;
    g_nSampleRate = nFrames;
    updateClockTiming();
    return 0;
}

int onJackXrun(void* pArgs) {
    DPRINTF("zynseq detected XRUN %u\n", ++g_nXruns);
    // g_bTimebaseChanged = true; // Discontinuity so need to recalculate timebase parameters
    return 0;
}

void end() {
    DPRINTF("zynseq exit\n");
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    g_bMutex = true;
    for (auto it : g_mSchedule) {
        delete it.second;
    }
    g_bMutex = false;
    freeState();
}

// ** Library management functions **

__attribute__((constructor)) void zynseq(void) { fprintf(stderr, "Started libzynseq\n"); }

void init(char* name) {
    //!@todo Invalid name triggers seg fault

    g_metro_pip.data = metronome_pip;
    g_metro_pip.size = sizeof(metronome_pip) / sizeof(float);
    g_metro_peep.data = metronome_peep;
    g_metro_peep.size = sizeof(metronome_peep) / sizeof(float);

    // Register with Jack server
    // fprintf(stderr, "**zynseq initialising as %s**\n", name);
    char* sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;

    if (g_pJackClient) {
        fprintf(stderr, "libzynseq already initialised\n");
        return; // Already initialised
    }

    if ((g_pJackClient = jack_client_open(name, nOptions, &nStatus, sServerName)) == 0) {
        fprintf(stderr, "libzynseq failed to start jack client: %d\n", nStatus);
        return;
    }

    // Create input ports
    if (!(g_pInputPort = jack_port_register(g_pJackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0))) {
        fprintf(stderr, "libzynseq cannot register input port\n");
        return;
    }
    if (!(g_pClockInputPort = jack_port_register(g_pJackClient, "clock_in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0))) {
        fprintf(stderr, "libzynseq cannot register clock input port\n");
        return;
    }

    // Create output ports
    if (!(g_pOutputPort = jack_port_register(g_pJackClient, "output", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libzynseq cannot register output port\n");
        return;
    }
    if (!(g_pClockOutputPort = jack_port_register(g_pJackClient, "clock", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libzynseq cannot register MIDI clock output port\n");
        return;
    }
    if (!(g_pClippyOutputPort = jack_port_register(g_pJackClient, "clippy", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libzynseq cannot register clippy output port\n");
        return;
    }

    // Create metronome output port
    if (!(g_pMetronomePort = jack_port_register(g_pJackClient, "metronome", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "linzynseq cannot register metronome port\n");
        return;
    }

    g_nSampleRate = jack_get_sample_rate(g_pJackClient);
    updateClockTiming();

    // Register JACK callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    jack_set_sample_rate_callback(g_pJackClient, onJackSampleRateChange, 0);
    jack_set_port_connect_callback(g_pJackClient, onJackConnect, 0);
    //jack_set_xrun_callback(g_pJackClient, onJackXrun, 0);

    if (jack_activate(g_pJackClient)) {
        fprintf(stderr, "libzynseq cannot activate client\n");
        return;
    }

    // Register the cleanup function to be called when program exits
    atexit(end);

    if (jack_set_timebase_callback(g_pJackClient, 0, onJackTimebase, NULL))
        fprintf(stderr, "ERROR: Failed to become timebase master\n");
    jack_transport_locate(g_pJackClient, 0);
    selectPattern(1);
    setTempo(120.0);
}

bool isModified() { return g_bDirty; }

// Write a single signed byte
int fileWrite8(int8_t value, FILE* pFile) {
    int nResult = fwrite(&value, 1, 1, pFile);
    return 1;
}

// Write a single unsigned byte
int fileWrite8u(uint8_t value, FILE* pFile) {
    int nResult = fwrite(&value, 1, 1, pFile);
    return 1;
}

// Write a 16-bit signed word as 2 bytes
int fileWrite16(int16_t value, FILE* pFile) {
    for (int i = 1; i >= 0; --i)
        fileWrite8u((value >> i * 8), pFile);
    return 2;
}

// Write a 16-bit unsigned word as 2 bytes
int fileWrite16u(uint16_t value, FILE* pFile) {
    for (int i = 1; i >= 0; --i)
        fileWrite8u((value >> i * 8), pFile);
    return 2;
}

// Write a 32-bit signed word as 4 bytes
int fileWrite32(int32_t value, FILE* pFile) {
    for (int i = 3; i >= 0; --i)
        fileWrite8u((value >> i * 8), pFile);
    return 4;
}

// Write a 32-bit unsigned word as 4 bytes
int fileWrite32u(uint32_t value, FILE* pFile) {
    for (int i = 3; i >= 0; --i)
        fileWrite8u((value >> i * 8), pFile);
    return 4;
}

int fileWrite32f(float value, FILE* pFile) {
    uint8_t* p = (uint8_t*)&value;
    for (int i = 3; i >= 0; --i)
        fileWrite8u(*(p + i), pFile);
    return 4;
}

// Read a single signed byte
int8_t fileRead8(FILE* pFile) {
    int8_t nResult = 0;
    fread(&nResult, 1, 1, pFile);
    return nResult;
}

// Read a single unsigned byte
uint8_t fileRead8u(FILE* pFile) {
    uint8_t nResult = 0;
    fread(&nResult, 1, 1, pFile);
    return nResult;
}

// Read a 2-byte signed word
int16_t fileRead16(FILE* pFile) {
    int16_t nResult = 0;
    for (int i = 1; i >= 0; --i) {
        uint8_t nValue = fileRead8u(pFile);
        nResult |= (nValue << (i * 8));
    }
    return nResult;
}

// Read a 2-byte unsigned word
uint16_t fileRead16u(FILE* pFile) {
    uint16_t nResult = 0;
    for (int i = 1; i >= 0; --i) {
        uint8_t nValue = fileRead8u(pFile);
        nResult |= (nValue << (i * 8));
    }
    return nResult;
}

// Read a 4-byte signed word
int32_t fileRead32(FILE* pFile) {
    int32_t nResult = 0;
    for (int i = 3; i >= 0; --i) {
        uint8_t nValue = fileRead8u(pFile);
        nResult |= (nValue << (i * 8));
    }
    return nResult;
}

// Read a 4-byte unsigned word
uint32_t fileRead32u(FILE* pFile) {
    uint32_t nResult = 0;
    for (int i = 3; i >= 0; --i) {
        uint8_t nValue = fileRead8u(pFile);
        nResult |= (nValue << (i * 8));
    }
    return nResult;
}

// Read a 4-byte float
float fileRead32f(FILE* pFile) {
    float fResult = 0.0;
    uint8_t* p = (uint8_t*)&fResult;
    for (int i = 3; i >= 0; --i)
        *(p + i) = fileRead8u(pFile);
    return fResult;
}

// Read a BCD (Binary-Coded Decimal) value from a 4 byte word
float fileReadBCD(FILE* f) {
    return float(fileRead16u(f)) / 10000 + fileRead16(f);
}

/* Check if there is sufficient data left in a block to process next stanza. If not, consume remaining bytes. */
bool checkBlock(FILE* pFile, uint32_t nActualSize, uint32_t nExpectedSize) {
    if (nActualSize < nExpectedSize) {
        for (size_t i = 0; i < nActualSize; ++i)
            fileRead8u(pFile);
        return true;
    }
    return false;
}

void reset() {
    g_nPhrase = 0;
    g_nSequence = 0;
    g_seqMan.init();
    g_nScene = 0;
    g_nBar = 1;
    g_nBarStartTick = g_nTick;
    g_nBeat = 1;
    g_nDefaultBpb = DEFAULT_BPB;
    g_nBeatsPerBar = DEFAULT_BPB;
    // Create default phrases
    for (uint8_t phrase = 0; phrase < 8; ++phrase)
        insertPhrase(g_nScene, phrase);
}

const char* convertToJson(const char* filename) {
    uint32_t nVersion = 0;
    FILE* pFile;
    pFile = fopen(filename, "r");
    if (pFile == NULL)
        return "{}";
    char sHeader[4];
    int bs;
    json j;

    // Iterate each block within IFF file
    while (fread(sHeader, 4, 1, pFile) == 1) {
        uint32_t nBlockSize = fileRead32(pFile);
        if (memcmp(sHeader, "vers", 4) == 0) {
            if (nBlockSize != 16) {
                fclose(pFile);
                // printf("Error reading vers block from sequence file\n");
                return "{}";
            }
            nVersion = fileRead32(pFile);
            if (nVersion < 4 || nVersion > 10) {
                fclose(pFile);
                printf("Unsupported sequence file version %d. Not loading file.\n", nVersion);
                return "{}";
            }
            j["tempo"] = fileRead16(pFile); //!@todo save and load tempo as fraction of BPM
            j["bpb"] = fileRead16(pFile);
            fileRead8u(pFile); // No longer use trigger channel
            fileRead8u(pFile); // No longer use trigger input
            fileRead8u(pFile); // No longer use trigger output
            fileRead8(pFile); // padding
            fileRead16u(pFile); // No longer use vertical zoom
            fileRead16u(pFile); // No longer use horizontal zoom
            // printf("Version:%u Tempo:%0.2lf Beats per bar:%u Zoom V:%u H:%u\n", nVersion, g_dTempo, g_nBeatsPerBar, g_nVerticalZoom, g_nHorizontalZoom);
        } else if (memcmp(sHeader, "patn", 4) == 0) {
            if (nVersion > 8) {
                if (checkBlock(pFile, nBlockSize, 32))
                    continue;
            } else if (nVersion > 4) {
                if (checkBlock(pFile, nBlockSize, 14))
                    continue;
            } else {
                if (checkBlock(pFile, nBlockSize, 12))
                    continue;
            }
            json patj;
            uint32_t nPattern = fileRead32(pFile);
            uint32_t beats = fileRead32(pFile);
            uint16_t spb = fileRead16(pFile);
            patj["steps"] = beats * spb;
            patj["beats"] = beats;
            patj["scale"] = fileRead8u(pFile);
            patj["tonic"] = fileRead8u(pFile);
            if (nVersion > 4) {
                patj["refNote"] = fileRead8u(pFile); //!@todo What is this?
                nBlockSize -= 1;
            }
            if (nVersion > 8) {
                patj["quantize"] = fileRead8u(pFile);
                patj["swingDiv"] = fileRead8u(pFile);
                patj["swing"] = fileReadBCD(pFile);
                patj["humanTime"] = fileReadBCD(pFile);
                patj["humanVel"] = fileReadBCD(pFile);
                patj["chance"] = int(fileReadBCD(pFile) * 100);
                nBlockSize -= 18;
            }
            if (nVersion > 4) {
                fileRead8(pFile); // padding
                nBlockSize -= 1;
            }
            nBlockSize -= 12;
            // printf("Pattern:%u Beats:%u StepsPerBeat:%u Scale:%u Tonic:%u\n", nPattern, pPattern->getBeatsInPattern(), pPattern->getStepsPerBeat(),
            // pPattern->getScale(), pPattern->getTonic());
            while (nBlockSize) {
                if (nVersion > 8) {
                    if (checkBlock(pFile, nBlockSize, 21))
                        break;
                } else if (nVersion > 7) {
                    if (checkBlock(pFile, nBlockSize, 16))
                        break;
                } else {
                    if (checkBlock(pFile, nBlockSize, 14))
                        break;
                }
                json jEvent;
                jEvent.push_back(fileRead32(pFile)); // step
                float fDuration, fOffset;
                if (nVersion > 8) {
                    jEvent.push_back(fileReadBCD(pFile)); // offset
                    jEvent.push_back(fileReadBCD(pFile)); // duration
                    nBlockSize -= 4;
                } else {
                    jEvent.push_back(0);
                    jEvent.push_back(float(fileRead16(pFile)) / 100 + fileRead16(pFile)); // fractional + integral (BCD)
                }
                jEvent.push_back(fileRead8u(pFile)); // command
                jEvent.push_back(fileRead8u(pFile)); // value 1 start
                jEvent.push_back(fileRead8u(pFile)); // value 2 start
                jEvent.push_back(fileRead8u(pFile)); // value 1 end
                jEvent.push_back(fileRead8u(pFile)); // value 2 end

                if (nVersion > 7) {
                    // Read stutter legacy values
                    uint8_t stut_cnt = fileRead8u(pFile);    // Legacy stutter count
                    uint8_t stut_dur = fileRead8u(pFile);    // Legacy stutter duration
                    if (stut_cnt > 0) {                      // Stutter speed calculated from legacy values
                        uint16_t legacy_clocks_step = 24 * patj.value("beats", 4) / patj.value("steps", 16);  // 6 by default (96/16) => 4 steps/beat
                        jEvent.push_back(legacy_clocks_step / stut_cnt);
                    } else {
                        jEvent.push_back(0);
                    }
                    jEvent.push_back(0);    // Stutter velocity FX
                    nBlockSize -= 2;
                } else {
                    jEvent.push_back(0);
                    jEvent.push_back(0);
                }
                jEvent.push_back(0);        // Stutter speed ramp

                if (nVersion > 8) {         // Play chance
                    jEvent.push_back(int(fileReadBCD(pFile) * 100));
                    nBlockSize -= 1;
                } else {
                    jEvent.push_back(100);
                }
                jEvent.push_back(1);        // Play frequency
                jEvent.push_back(100);      // Stutter chance
                jEvent.push_back(1);        // Stutter frequency
                fileRead8(pFile);           // Padding
                nBlockSize -= 14;
                // printf(" Step:%u Duration:%u Command:%02X, Value1:%u..%u, Value2:%u..%u\n", nTime, nDuration, nCommand, nValue1start, nValue2end,
                // nValue2start, nValue2end);
                patj["events"].push_back(jEvent);
            }
            j["patns"][std::to_string(nPattern)] = patj;
        } else if (memcmp(sHeader, "bank", 4) == 0) {
            // Load scenes
            if (checkBlock(pFile, nBlockSize, 6))
                continue;
            uint8_t nScene = fileRead8u(pFile) - 1; // Legacy did not save scene (bank) 0
            fileRead8(pFile); // Padding
            uint32_t nSequences = fileRead32(pFile);
            nBlockSize -= 6;
            json jScene;
            uint8_t nextPhrase[] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}; // Index of next phrase to add MIDI channel based sequence.
            bool bAddScene = false;
            for (uint32_t nSequence = 0; nSequence < nSequences; ++nSequence) {
                if (nVersion > 5 && checkBlock(pFile, nBlockSize, 24))
                    continue;
                else if (checkBlock(pFile, nBlockSize, 8))
                    continue;
                uint8_t nMidiChan; // Used to define which phrase to add sequence to
                json jSeq;
                bool bAddSeq = false;
                switch (fileRead8u(pFile)) {
                        case 0:
                            // DISABLED
                            jSeq["repeat"] = 0;
                            break;
                        case 1:
                            // ONESHOT
                            jSeq["mode"] = MODE_END_IMMEDIATE;
                            break;
                        case 2:
                            // LOOP
                            jSeq["followAction"] = FOLLOW_ACTION_RELATIVE;
                            jSeq["followParam"] = 0;
                            break;
                        case 3:
                            // ONESHOTALL
                            break;
                        case 4:
                            // LOOPALL
                            jSeq["followAction"] = FOLLOW_ACTION_RELATIVE;
                            jSeq["followParam"] = 0;
                            break;
                        case 5:
                            // ONESHOTSYNC
                            jSeq["mode"] = MODE_END_SYNC;
                            break;
                        case 6:
                            // LOOPSYNC
                            jSeq["followAction"] = FOLLOW_ACTION_RELATIVE;
                            jSeq["followParam"] = 0;
                            break;
                }
                uint8_t nGroup = fileRead8u(pFile);
                jSeq["group"] = nGroup;
                fileRead8u(pFile); // No longer use trigger note
                fileRead8(pFile); // Padding
                char sName[17];
                memset(sName, '\0', 17);
                if (nVersion > 5) {
                    if (checkBlock(pFile, nBlockSize, 24))
                        continue;
                    for (size_t nIndex = 0; nIndex < 16; ++nIndex)
                        sName[nIndex] = fileRead8u(pFile);
                    sName[16] = '\0';
                    nBlockSize -= 16;
                } else {
                    sprintf(sName, "%d", nSequence + 1);
                }
                jSeq["name"] = std::string(sName);
                uint32_t nTracks = fileRead32(pFile);
                nBlockSize -= 8;
                if (nVersion > 9)
                    bs = 8;
                else
                    bs = 6;
                for (uint32_t nTrack = 0; nTrack < nTracks; ++nTrack) {
                    if (checkBlock(pFile, nBlockSize, bs))
                        break;
                    json trackj;
                    if (nVersion > 9)
                        fileRead16(pFile); // Type & chain id not used
                    nMidiChan = fileRead8u(pFile);
                    trackj["chan"] = nMidiChan;
                    trackj["output"] = fileRead8u(pFile);
                    trackj["map"] = fileRead8u(pFile);
                    fileRead8(pFile); // Padding
                    uint16_t nPatterns = fileRead16(pFile);
                    nBlockSize -= bs;
                    // printf("    Track:%u Channel:%u Output:%u Map:%u\n", nTrack, pTrack->getChannel(), pTrack->getOutput(), pTrack->getMap());
                    for (uint16_t nPattern = 0; nPattern < nPatterns; ++nPattern) {
                        if (checkBlock(pFile, nBlockSize, 8))
                            break;
                        uint32_t nTime = fileRead32(pFile);
                        uint32_t nId = fileRead32(pFile);
                        if (j["patns"].contains(std::to_string(nId))) {
                            trackj["patns"][std::to_string(nTime)] = nId;
                            bAddSeq = true;
                        }
                        nBlockSize -= 8;
                    }
                    jSeq["tracks"].push_back(trackj);
                }
                if (checkBlock(pFile, nBlockSize, 4))
                    break;
                uint32_t nTimebaseEvents = fileRead32(pFile);
                nBlockSize -= 4;
                for (uint32_t nEvent = 0; nEvent < nTimebaseEvents; ++nEvent) {
                    if (checkBlock(pFile, nBlockSize, 8))
                        break;
                    json tbjEvent;
                    tbjEvent["bar"] = fileRead16(pFile);
                    tbjEvent["tick"] = fileRead16(pFile);
                    tbjEvent["type"] = fileRead16(pFile);
                    tbjEvent["value"] = fileRead16(pFile);
                    nBlockSize -= 8;
                    jSeq["timebase"].push_back(tbjEvent);
                    // printf("    Timebase event:%u at time %u\n", pSequence->)
                }
                if (nTracks == 1) {
                    // Single track sequence so add to phrase defined by MIDI channel
                    uint8_t nPhrase = nextPhrase[nMidiChan];
                    if (jScene["phrases"].size() <= nPhrase) {
                        // Create phrase
                        json jPhrase;
                        jPhrase["name"] = std::string(1, 'A' + nPhrase);
                        jPhrase["mode"] = 4; // Phrase play mode
                        jScene["phrases"].push_back(jPhrase);
                    }
                    if (bAddSeq) {
                        // Don't add empty sequences
                        while (jScene["phrases"][nPhrase]["sequences"].size() < nMidiChan)
                            jScene["phrases"][nPhrase]["sequences"].emplace_back();
                        jScene["phrases"][nPhrase]["sequences"][nMidiChan] = jSeq;
                        nextPhrase[nMidiChan] += 1;
                        bAddScene = true;
                    }
                }
                else {
                    //!@todo Handle multi-track sequences
                }
            }
            if (bAddScene) // Don't add empty scenes
                j["scenes"].push_back(jScene);
        }
    }
    fclose(pFile);
    std::string json_str = j.dump();
    free(g_pState);
    g_pState = (char*)malloc(json_str.size() + 1);
    std::strcpy(g_pState, json_str.c_str());
    return g_pState;
}

void setPattern(uint32_t id, const char* patn_state) {
    json jPattern = json::parse(patn_state);
    Pattern* pPattern = g_seqMan.getPattern(id);
    pPattern->clear();
    pPattern->setBeatsInPattern(jPattern.value("beats", 4));
    pPattern->setStepsPerBeat(jPattern.value("steps", 16) / pPattern->getBeatsInPattern());
    pPattern->setScale(jPattern.value("scale", 0));
    pPattern->setTonic(jPattern.value("tonic", 0));
    pPattern->setRefNote(jPattern.value("refNote", 60));
    pPattern->setZoom(jPattern.value("zoom", 0));
    if (jPattern.contains("ccnum")) {
        for (uint8_t ccnum = 0; ccnum < 128; ++ccnum)
            pPattern->setInterpolateCC(ccnum, jPattern["ccnum"][ccnum]);
    }
    pPattern->setQuantizeNotes(jPattern.value("quantize", 0));
    pPattern->setSwingDiv(jPattern.value("swingDiv", 1));
    pPattern->setSwingAmount(jPattern.value("swing", 0.0));
    pPattern->setHumanTime(jPattern.value("humanTime", 0.0));
    pPattern->setHumanVelo(jPattern.value("humanVel", 0.0));
    pPattern->setPlayChance(float(jPattern.value("chance", 100)) / 100);
    for (auto& jEvent: jPattern["events"]) {
        uint32_t nStep = jEvent[0];
        float fDuration = jEvent[1];
        float fOffset = jEvent[2];
        uint8_t nCommand = jEvent[3];
        uint8_t nValue1start = jEvent[4];
        uint8_t nValue2start = jEvent[6];
        StepEvent* pEvent = pPattern->addEvent(nStep, nCommand, nValue1start, nValue2start, fDuration, fOffset);
        pEvent->setValue1end(jEvent[5]);
        pEvent->setValue2end(jEvent[7]);
        pEvent->setStutterSpeed(jEvent[8]);
        pEvent->setStutterVelfx(jEvent[9]);
        pEvent->setStutterRamp(jEvent[10]);
        pEvent->setPlayChance(float(jEvent[11]) / 100);
        pEvent->setPlayFreq(jEvent[12]);
        pEvent->setStutterChance(float(jEvent[13]) / 100);
        pEvent->setStutterFreq(jEvent[14]);
    }
}

bool setState(const char* state) {
    try {
        json j = json::parse(state);
        g_nPhrase = 0;
        g_nSequence = 0;
        uint8_t nLowestScene = 255;

        g_seqMan.init();

        setTempo(j.value("tempo", g_dTempo)); //!@todo Do we want to reset tempo to default or use previous if not in state?
        setDefaultBpb(j.value("bpb", DEFAULT_BPB));
        //fprintf(stderr, "Default Timesig = %d\n", j.value("bpb", DEFAULT_BPB));

        if (j.contains("patns")) {
            for (auto& [key, jPattern]: j["patns"].items()) {
                uint32_t id = std::stoi(key);
                //!@todo We could reuse setPattern but that means encoding and re-decoding the json
                Pattern* pPattern = g_seqMan.getPattern(id);
                pPattern->clear();
                pPattern->setBeatsInPattern(jPattern.value("beats", 4));
                pPattern->setStepsPerBeat(jPattern.value("steps", 16) / pPattern->getBeatsInPattern());
                pPattern->setScale(jPattern.value("scale", 0));
                pPattern->setTonic(jPattern.value("tonic", 0));
                pPattern->setRefNote(jPattern.value("refNote", 60));
                pPattern->setZoom(jPattern.value("zoom", 0));
                if (jPattern.contains("ccnum")) {
                    for (uint8_t ccnum = 0; ccnum < 128; ++ccnum)
                        pPattern->setInterpolateCC(ccnum, jPattern["ccnum"][ccnum]);
                }
                pPattern->setQuantizeNotes(jPattern.value("quantize", 0));
                pPattern->setSwingDiv(jPattern.value("swingDiv", 1));
                pPattern->setSwingAmount(jPattern.value("swing", 0.0));
                pPattern->setHumanTime(jPattern.value("humanTime", 0.0));
                pPattern->setHumanVelo(jPattern.value("humanVel", 0.0));
                pPattern->setPlayChance(float(jPattern.value("chance", 100)) / 100);
                for (auto& jEvent: jPattern["events"]) {
                    uint32_t nStep = jEvent[0];
                    float fOffset = jEvent[1];
                    float fDuration = jEvent[2];
                    uint8_t nCommand = jEvent[3];
                    uint8_t nValue1start = jEvent[4];
                    uint8_t nValue2start = jEvent[6];
                    StepEvent* pEvent = pPattern->addEvent(nStep, nCommand, nValue1start, nValue2start, fDuration, fOffset);
                    pEvent->setValue1end(jEvent[5]);
                    pEvent->setValue2end(jEvent[7]);
                    pEvent->setStutterSpeed(jEvent[8]);
                    pEvent->setStutterVelfx(jEvent[9]);
                    // Legacy format
                    if (jEvent.size() == 11) {
                        pEvent->setPlayChance(float(jEvent[10]) / 100);
                    }
                    // Extended parameters: stutter speed-ramp, play freq, stutter chance, stutter freq
                    else {
                        pEvent->setStutterRamp(jEvent[10]);
                        pEvent->setPlayChance(float(jEvent[11]) / 100);
                        pEvent->setPlayFreq(jEvent[12]);
                        pEvent->setStutterChance(float(jEvent[13]) / 100);
                        pEvent->setStutterFreq(jEvent[14]);
                    }
                }
            }
        }
        if (j.contains("scenes")) {
            for (uint32_t nScene = 0; nScene <j["scenes"].size(); ++nScene) {
                json jScene = j["scenes"][nScene];
                if (nScene < nLowestScene)
                    nLowestScene = nScene;
                uint32_t nPhrase = 0;
                uint8_t phrase_bpb;
                std::vector<std::array<int16_t, 6>> vFollowActions;
                for (auto& jPhrase: jScene["phrases"]) {
                    Sequence* pPhrase = g_seqMan.insertPhrase(nScene, -1);
                    if (!pPhrase)
                        continue;

                    if (jPhrase.contains("name"))
                        pPhrase->setName(jPhrase["name"]);
                    if (jPhrase.contains("mode"))
                        pPhrase->setPlayMode(jPhrase["mode"]);

                    // Set phrase time signature, fixing if needed
                    phrase_bpb = jPhrase.value("bpb", DEFAULT_BPB);
                    if (phrase_bpb <= 0)
                        phrase_bpb = DEFAULT_BPB;
                    pPhrase->setTimeSig(phrase_bpb);
                    //fprintf(stderr, "Phrase %d Timesig = %d\n", nPhrase, phrase_bpb);

                    pPhrase->setTempo(jPhrase.value("tempo", 0));
                    pPhrase->setRepeat(jPhrase.value("repeat", 1));

                    // Store the follow configuration to apply after all sequences have been created
                    std::array<int16_t, 6> followAction;
                    followAction[0] = nPhrase;
                    followAction[1] = PHRASE_CHANNEL;
                    followAction[2] = jPhrase.value("followAction", FOLLOW_ACTION_NONE);
                    followAction[3] = jPhrase.value("followParam", 0);
                    followAction[4] = jPhrase.value("playFlags", 0);
                    followAction[5] = jPhrase.value("followRepeat", 0);
                    vFollowActions.push_back(followAction);

                    uint8_t nSeq = 0;
                    for (auto& jSeq: jPhrase["sequences"]) {
                        uint32_t nTracks = jSeq["tracks"].size();
                        if (nTracks == 1) {
                            // Single track sequences are mapped by their first midi channel
                            //nSeq = jSeq["tracks"][0].value("chan", 0);
                        } else {
                            //!@todo Handle multtrack sequences
                            //fprintf(stderr, "Ignoring multitrack sequence\n");
                            //continue;
                        }
                        Sequence* pSequence = g_seqMan.getSequence(nScene, nPhrase, nSeq);
                        if (!pSequence) {
                            fprintf(stderr, "getSequence(%u, %u, %u) failed\n", nScene, nPhrase, nSeq);
                            continue;
                        }
                        pSequence->setPlayMode(jSeq.value("mode", 1));
                        pSequence->setGroup(jSeq.value("group", 0)); //!@todo Set default group to MIDI channel
                        pSequence->setName(jSeq.value("name", ""));
                        pSequence->setRepeat(jSeq.value("repeat", 1));

                        // Store the follow configuration to apply after all sequences have been created
                        std::array<int16_t, 6> followAction;
                        followAction[0] = nPhrase;
                        followAction[1] = nSeq;
                        followAction[2] = jSeq.value("followAction", FOLLOW_ACTION_NONE);
                        followAction[3] = jSeq.value("followParam", 0);
                        followAction[4] = jSeq.value("playFlags", 0);
                        followAction[5] = jSeq.value("followRepeat", 0);
                        vFollowActions.push_back(followAction);
                        uint32_t nTrack = 0;
                        for (auto& jTrack: jSeq["tracks"]) {
                            if (pSequence->getTracks() <= nTrack)
                                pSequence->addTrack(nTrack);
                            Track* pTrack = pSequence->getTrack(nTrack);
                            pTrack->setChannel(jTrack.value("chan", 0));
                            pTrack->setOutput(jTrack.value("output", 0));
                            pTrack->setMap(jTrack.value("map", 0));
                            for (auto& [sTime, jPatn]: jTrack["patns"].items()){
                                uint32_t nTime = std::stoi(sTime);
                                uint32_t nPatn = jPatn.get<uint32_t>();
                                g_seqMan.addPattern(pSequence, nTrack, nTime, nPatn, true);
                            }
                            ++nTrack;
                        }
                        if (jSeq.contains("timebase")) {
                            for (auto& jTbEvt: jSeq["timebase"]) {
                                pSequence->getTimebase()->addTimebaseEvent(jTbEvt["bar"], jTbEvt["tick"], jTbEvt["type"], jTbEvt["value"]);
                            }
                        }
                        ++nSeq;
                    }
                    // Set Phrase BPB after adding the patterns
                    pPhrase->setTimeSig(phrase_bpb);
                    ++nPhrase;
                }
                // Set follow actions late, after creating all sequence objects
                for (auto& followAction : vFollowActions) {
                    Sequence* pSeq = g_seqMan.getSequence(nScene, followAction[0], followAction[1]);
                    g_seqMan.setFollowAction(nScene, pSeq, followAction[2], followAction[3], followAction[4], followAction[5]);
                }
            }
        }
        // Reset dirty flag
        g_bDirty = false;
        // Setup scene
        if (nLowestScene == 255)
            nLowestScene = 0;
        setScene(j.value("scene", nLowestScene));
    } catch (const nlohmann::json::exception& e) {
        fprintf(stderr, "Failed to set zynseq state due to json handling exception: %s\n", e.what());
        reset();
        return false;
    }
    return true;
}

const char* getState() {
    uint8_t nScene = getScene();
    json jState;
    jState["tempo"] = g_dTempo;
    jState["bpb"] = g_nDefaultBpb;
    jState["scene"] = nScene;
    // Iterate through patterns
    uint32_t nPattern = 0;
    while ((nPattern = g_seqMan.getNextPattern(nPattern)) != -1) {
        Pattern* pPattern = g_seqMan.getPattern(nPattern);
        // Only save patterns with content
        if (pPattern->getEventAt(0)) {
            json jPatn;
            uint32_t nBeats = pPattern->getBeatsInPattern();
            jPatn["beats"] = nBeats;
            jPatn["steps"] = nBeats * pPattern->getStepsPerBeat();
            jPatn["scale"] = pPattern->getScale();
            jPatn["tonic"] = pPattern->getTonic();
            jPatn["refNote"] = pPattern->getRefNote();
            jPatn["zoom"] = pPattern->getZoom();
            jPatn["quantize"] = pPattern->getQuantizeNotes();
            jPatn["swingDiv"] = pPattern->getSwingDiv();
            jPatn["swing"] = pPattern->getSwingAmount();
            jPatn["humanTime"] = pPattern->getHumanTime();
            jPatn["humanVel"] = pPattern->getHumanVelo();
            jPatn["chance"] = int(pPattern->getPlayChance() * 100);
            uint32_t nEvent = 0;
            while (StepEvent* pEvent = pPattern->getEventAt(nEvent++)) {
                json jEvt;
                // Event Position (step)
                jEvt.push_back(pEvent->getPosition());
                jEvt.push_back(pEvent->getOffset());
                jEvt.push_back(pEvent->getDuration());
                jEvt.push_back(pEvent->getCommand());
                jEvt.push_back(pEvent->getValue1start());
                jEvt.push_back(pEvent->getValue1end());
                jEvt.push_back(pEvent->getValue2start());
                jEvt.push_back(pEvent->getValue2end());
                jEvt.push_back(pEvent->getStutterSpeed());
                jEvt.push_back(pEvent->getStutterVelfx());
                jEvt.push_back(pEvent->getStutterRamp());
                jEvt.push_back(int(pEvent->getPlayChance() * 100));
                jEvt.push_back(pEvent->getPlayFreq());
                jEvt.push_back(int(pEvent->getStutterChance() * 100));
                jEvt.push_back(pEvent->getStutterFreq());
                jPatn["events"].push_back(jEvt);
            }
            jState["patns"][std::to_string(nPattern)] = jPatn;
        }
    }

    // Iterate through scenes
    for (uint32_t nScene = 0; nScene < g_seqMan.getNumScenes(); ++nScene) {
        json jScene;
        uint32_t nPhrase = 0;
        while (true) {
            Sequence* pPhrase = g_seqMan.getSequence(nScene, nPhrase, PHRASE_CHANNEL);
            if (!pPhrase) // Reached end of phrases
                break;
            json jPhrase;
            //!@todo Optimise - do not save default values
            jPhrase["name"] = pPhrase->getName().c_str();
            jPhrase["mode"] = pPhrase->getPlayMode();
            jPhrase["bpb"] = pPhrase->getTimeSig();
            jPhrase["tempo"] = pPhrase->getTempo();
            jPhrase["repeat"] = pPhrase->getRepeat();
            jPhrase["followAction"] = pPhrase->getFollowAction();
            jPhrase["followParam"] = pPhrase->getFollowParam();
            jPhrase["playFlags"] = pPhrase->getPlayFlags();
            jPhrase["followRepeat"] = pPhrase->getFollowRepeat();
            jPhrase["state"] = pPhrase->getPlayState();
            for (const auto& pSequence : pPhrase->m_aChildSequences) {
                json jSeq;
                if (pSequence) {
                    jSeq["mode"] = pSequence->getPlayMode();
                    jSeq["group"] = pSequence->getGroup();
                    jSeq["name"] = pSequence->getName().c_str();
                    jSeq["mode"] = pSequence->getPlayMode();
                    jSeq["repeat"] = pSequence->getRepeat();
                    jSeq["followAction"] = pSequence->getFollowAction();
                    jSeq["followParam"] = pSequence->getFollowParam();
                    jSeq["state"] = pSequence->getPlayState();
                    for (size_t nTrack = 0; nTrack < pSequence->getTracks(); ++nTrack) {
                        Track* pTrack = pSequence->getTrack(nTrack);
                        if (pTrack) {
                            json jTrack;
                            jTrack["chan"] = pTrack->getChannel();
                            jTrack["output"] = pTrack->getOutput();
                            jTrack["map"] = pTrack->getMap();
                            for (uint16_t nPattern = 0; nPattern < pTrack->getPatterns(); ++nPattern) {
                                std::string sPos = std::to_string(pTrack->getPatternPositionByIndex(nPattern));
                                Pattern* pPattern   = pTrack->getPatternByIndex(nPattern);
                                uint32_t nPatternId = g_seqMan.getPatternIndex(pPattern);
                                jTrack["patns"][sPos] = nPatternId;
                            }
                            jSeq["tracks"].push_back(jTrack);
                        }
                    }
                    Timebase* pTimebase = pSequence->getTimebase();
                    if (pTimebase) {
                        json jTimebase;
                        for (uint32_t nIndex = 0; nIndex < pTimebase->getEventQuant(); ++nIndex) {
                            TimebaseEvent* pEvent = pTimebase->getEvent(nIndex);
                            jTimebase["bar"] = pEvent->bar;
                            jTimebase["tick"] = pEvent->clock;
                            jTimebase["type"] = pEvent->type;
                            jTimebase["value"] = pEvent->value;
                            jSeq["timebase"].push_back(jTimebase);
                        }
                    }
                }
                jPhrase["sequences"].push_back(jSeq);
            }
            jScene["phrases"].push_back(jPhrase);
            ++nPhrase;
        }
        jState["scenes"].push_back(jScene);
    }

    std::string json_str = jState.dump();
    free(g_pState);
    g_pState = (char*)malloc(json_str.size() + 1);
    std::strcpy(g_pState, json_str.c_str());
    return g_pState;
}

void freeState() {
    free (g_pState);
    g_pState = nullptr;
}

const char* convertPattern(uint32_t nPattern, const char* filename) {
    // Legacy binary format
    uint32_t nVersion = 0;
    FILE* pFile;
    pFile = fopen(filename, "r");
    if (pFile == NULL)
        return nullptr;
    json jPattern;
    char sHeader[4];
    // Iterate each block within IFF file
    while (fread(sHeader, 4, 1, pFile) == 1) {
        uint32_t nBlockSize = fileRead32u(pFile);
        if (memcmp(sHeader, "vers", 4) == 0) {
            if (nBlockSize != 10) {
                fclose(pFile);
                printf("Error reading vers block from pattern file\n");
                return nullptr;
            }
            nVersion = fileRead32u(pFile);
            if (nVersion < 4 || nVersion > FILE_VERSION) {
                fclose(pFile);
                DPRINTF("Unsupported pattern file version %d. Not loading file.\n", nVersion);
                return nullptr;
            }
            // Loaded from file but not used!
            // g_nBeatsPerBar, g_nVerticalZoom, g_nHorizontalZoom
            fileRead16u(pFile);
            fileRead16u(pFile);
            fileRead16u(pFile);
            // printf("Version:%u Beats per bar:%u Zoom V:%u H:%u\n", nVersion, g_nBeatsPerBar, g_nVerticalZoom, g_nHorizontalZoom);
        } else if (memcmp(sHeader, "patn", 4) == 0) {
            if (nVersion > 8) {
                if (checkBlock(pFile, nBlockSize, 28))
                    continue;
            } else if (nVersion > 4) {
                if (checkBlock(pFile, nBlockSize, 10))
                    continue;
            } else {
                if (checkBlock(pFile, nBlockSize, 8))
                    continue;
            }
            jPattern["beats"] = fileRead32u(pFile);
            jPattern["steps"] = fileRead16u(pFile);
            jPattern["scale"] = fileRead8u(pFile);
            jPattern["tonic"] = fileRead8u(pFile);
            if (nVersion > 4) {
                jPattern["refNote"] = fileRead8u(pFile);
                nBlockSize -= 1;
            }
            if (nVersion > 8) {
                jPattern["quantize"] = fileRead8u(pFile);
                jPattern["swingDiv"] = fileRead8u(pFile);
                jPattern["swing"] = fileReadBCD(pFile);
                jPattern["humanTime"] = fileReadBCD(pFile);
                jPattern["humanVel"] = fileReadBCD(pFile);
                jPattern["chance"] = int(100 * fileReadBCD(pFile));
                nBlockSize -= 18;
            }
            if (nVersion > 4) {
                fileRead8u(pFile);
                nBlockSize -= 1;
            }
            nBlockSize -= 8;
            // printf("Pattern:%u Beats:%u StepsPerBeat:%u Scale:%u Tonic:%u\n", nPattern, pPattern->getBeatsInPattern(nPattern), pPattern->getStepsPerBeat(),
            // pPattern->getScale(), pPattern->getTonic());
            while (nBlockSize) {
                if (nVersion > 8) {
                    if (checkBlock(pFile, nBlockSize, 21))
                        break;
                } else if (nVersion > 7) {
                    if (checkBlock(pFile, nBlockSize, 16))
                        break;
                } else {
                    if (checkBlock(pFile, nBlockSize, 14))
                        break;
                }
                json jEvent;
                jEvent.push_back(fileRead32(pFile)); // step
                if (nVersion > 8) {
                    jEvent.push_back(fileReadBCD(pFile)); // offset
                    jEvent.push_back(fileReadBCD(pFile)); // duration
                    nBlockSize -= 4;
                } else {
                    jEvent.push_back(0);
                    jEvent.push_back(float(fileRead16(pFile)) / 100 + fileRead16(pFile)); // fractional + integral (BCD)
                }
                jEvent.push_back(fileRead8u(pFile)); // command
                jEvent.push_back(fileRead8u(pFile)); // value 1 start
                jEvent.push_back(fileRead8u(pFile)); // value 2 start
                jEvent.push_back(fileRead8u(pFile)); // value 1 end
                jEvent.push_back(fileRead8u(pFile)); // value 2 end
                if (nVersion > 7) {
                    // Read legacy values
                    uint8_t stut_cnt = fileRead8u(pFile);    // Legacy stutter count
                    uint8_t stut_dur = fileRead8u(pFile);    // Legacy stutter duration
                    if (stut_cnt > 0) {                      // Stutter speed calculated from legacy values
                        uint16_t legacy_clocks_step = 24 * jPattern.value("beats", 4) / jPattern.value("steps", 16);  // 6 by default (96/16) => 4 steps/beat
                        jEvent.push_back(legacy_clocks_step / stut_cnt);
                    } else {
                        jEvent.push_back(0);
                    }
                    jEvent.push_back(0);                     // Stutter velocity FX
                    nBlockSize -= 2;
                } else {
                    jEvent.push_back(0);
                    jEvent.push_back(0);
                }
                jEvent.push_back(0);                         // Stutter Ramp
                if (nVersion > 8) {                          // Play chance
                    jEvent.push_back(int(100 * fileReadBCD(pFile)));
                    nBlockSize -= 1;
                } else {
                    jEvent.push_back(100);
                }
                jEvent.push_back(1);                         // Play frequency
                jEvent.push_back(100);                       // Stutter chance
                jEvent.push_back(1);                         // Stutter frequency
                fileRead8(pFile);                            // Padding
                nBlockSize -= 14;
                // printf(" Step:%u Duration:%u Command:%02X, Value1:%u..%u, Value2:%u..%u\n", nTime, nDuration, nCommand, nValue1start, nValue2end,
                // nValue2start, nValue2end);
                jPattern["events"].push_back(jEvent);
            }
        }
    }
    fclose(pFile);
    // printf("Ver: %d Loaded %lu pattern from file %s\n", nVersion, m_mPatterns.size(), filename);
    std::string json_str = jPattern.dump();
    freeState();
    g_pState = (char*)malloc(json_str.size() + 1);
    std::strcpy(g_pState, json_str.c_str());
    return g_pState;
}

void savePatternSnapshot() {
    if (g_pPattern)
        g_pPattern->saveSnapshot();
}

void resetPatternSnapshots() {
    if (g_pPattern)
        g_pPattern->resetSnapshots();
}

bool undoPattern() {
    if (g_pPattern)
        return g_pPattern->undo();
    return false;
}

bool redoPattern() {
    if (g_pPattern)
        return g_pPattern->redo();
    return false;
}

bool undoPatternAll() {
    if (g_pPattern)
        return g_pPattern->undoAll();
    return false;
}

bool redoPatternAll() {
    if (g_pPattern)
        return g_pPattern->redoAll();
    return false;
}

void setPatternZoom(int16_t zoom) {
    if (g_pPattern)
        g_pPattern->setZoom(zoom);
}

int16_t getPatternZoom() {
    if (g_pPattern)
        return g_pPattern->getZoom();
    return 0;
}

// ** This is not user by Pattern editor anymore. Is this used by arranger? **

uint16_t getVerticalZoom() { return g_nVerticalZoom; }

void setVerticalZoom(uint16_t zoom) { g_nVerticalZoom = zoom; }

uint16_t getHorizontalZoom() { return g_nHorizontalZoom; }

void setHorizontalZoom(uint16_t zoom) { g_nHorizontalZoom = zoom; }

// ** Direct MIDI interface **

// Schedule a MIDI message to be sent in next JACK process period
void sendMidiMsg(MIDI_MESSAGE& msg) {
    // Find first available time slot
    uint32_t tick = g_nBarStartTick + g_nTick;;
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    g_bMutex = true;
    g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(tick, new SEQ_EVENT({tick, 0, msg})));
    g_bMutex = false;
}

// Schedule a note off event after 'duration' ms
void noteOffTimer(uint8_t note, uint8_t channel, uint32_t duration) {
    std::this_thread::sleep_for(std::chrono::milliseconds(duration));
    MIDI_MESSAGE msg;
    msg.command = MIDI_NOTE_OFF | (channel & 0x0F);
    msg.value1 = note;
    msg.value2 = 0;
    sendMidiMsg(msg);
}

void playNote(uint8_t note, uint8_t velocity, uint8_t channel, uint32_t duration) {
    if (note > 127 || velocity > 127 || channel > 15 || duration > 60000)
        return;
    MIDI_MESSAGE msg;
    msg.command = MIDI_NOTE_ON | channel;
    msg.value1 = note;
    msg.value2 = velocity;
    sendMidiMsg(msg);
    if (duration) {
        std::thread noteOffThread(noteOffTimer, note, channel, duration);
        noteOffThread.detach();
    }
}

void sendMidiCommand(uint8_t status, uint8_t value1, uint8_t value2) {
    MIDI_MESSAGE msg;
    msg.command = status;
    msg.value1 = value1;
    msg.value2 = value2;
    sendMidiMsg(msg);
}

// ** Pattern management functions **

uint32_t createPattern() { return g_seqMan.createPattern(); }

void toggleMute(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Track* pTrack = g_seqMan.getSequence(scene, phrase, sequence)->getTrack(track);
    if (pTrack)
        pTrack->mute(!pTrack->isMuted());
}

bool isMuted(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Track* pTrack = g_seqMan.getSequence(scene, phrase, sequence)->getTrack(track);
    if (pTrack)
        return pTrack->isMuted();
    return false;
}

void enableMidiRecord(bool enable) { g_bMidiRecord = enable; }

bool isMidiRecord() { return g_bMidiRecord; }

bool isPatternEmpty(uint32_t pattern) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    return pPattern->getEventAt(0) == NULL;
}

void selectPattern(uint32_t pattern) {
    g_pPattern = g_seqMan.getPattern(pattern);
}

uint32_t getPatternIndex() { return g_seqMan.getPatternIndex(g_pPattern); }

uint32_t getSteps() {
    if (g_pPattern)
        return g_pPattern->getSteps();
    return 0;
}

uint32_t getPatternLength(uint32_t pattern) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern)
        return pPattern->getLength();
    return 0;
}

uint8_t getNoteAtIndex(uint32_t pattern, uint32_t index) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (!pPattern || index >= pPattern->getEvents())
        return 0xff;
    StepEvent* pEvent = pPattern->getEventAt(index);
    if (pEvent->getCommand() == MIDI_NOTE_ON)
        return pEvent->getValue1start();
    return 0xff;
}

uint32_t getBeatsInPattern(uint32_t pattern) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern)
        return pPattern->getBeatsInPattern();
    return 0;
}

void setBeatsInPattern(uint32_t pattern, uint32_t beats) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern) {
        pPattern->setBeatsInPattern(beats);
        g_seqMan.updateAllSequenceLengths();
        setPatternModified(pPattern, true, true);
        g_bDirty = true;
    }
}

uint32_t getClocksPerStep(uint32_t pattern) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern)
        return pPattern->getClocksPerStep();
    return 6;
}

uint32_t getStepsPerBeat() {
    if (g_pPattern)
        return g_pPattern->getStepsPerBeat();
    return 4;
}

void setStepsPerBeat(uint32_t steps) {
    if (g_pPattern) {
        g_pPattern->setStepsPerBeat(steps);
        setPatternModified(g_pPattern, true, true);
        g_bDirty = true;
    }
}

uint32_t getSwingDiv() {
    if (g_pPattern)
        return g_pPattern->getSwingDiv();
    return 1;
}

void setSwingDiv(uint32_t div) {
    if (g_pPattern) {
        g_pPattern->setSwingDiv(div);
        // setPatternModified(g_pPattern, true, false);
        g_bDirty = true;
    }
}

float getSwingAmount() {
    if (g_pPattern)
        return g_pPattern->getSwingAmount();
    return 0.0;
}

void setSwingAmount(float amount) {
    if (g_pPattern) {
        g_pPattern->setSwingAmount(amount);
        // setPatternModified(g_pPattern, true, false);
        g_bDirty = true;
    }
}

float getHumanTime() {
    if (g_pPattern)
        return g_pPattern->getHumanTime();
    return 0.0;
}

void setHumanTime(float amount) {
    if (g_pPattern) {
        g_pPattern->setHumanTime(amount);
        // setPatternModified(g_pPattern, true, false);
        g_bDirty = true;
    }
}

float getHumanVelo() {
    if (g_pPattern)
        return g_pPattern->getHumanVelo();
    return 0.0;
}

void setHumanVelo(float amount) {
    if (g_pPattern) {
        g_pPattern->setHumanVelo(amount);
        // setPatternModified(g_pPattern, true, false);
        g_bDirty = true;
    }
}

float getPlayChance() {
    if (g_pPattern)
        return g_pPattern->getPlayChance();
    return 0.0;
}

void setPlayChance(float chance) {
    if (g_pPattern) {
        g_pPattern->setPlayChance(chance);
        // setPatternModified(g_pPattern, true, false);
        g_bDirty = true;
    }
}

bool addNote(uint32_t step, uint8_t note, uint8_t velocity, float duration, float offset) {
    if (g_pPattern) {
        if (g_pPattern->addNote(step, note, velocity, duration, offset)) {
            setPatternModified(g_pPattern, true, false);
            g_bDirty = true;
            return true;
        }
    }
    return false;
}

void removeNote(uint32_t step, uint8_t note) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->removeNote(step, note);
        g_bDirty = true;
    }
}

void clearNotes() {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->clearNotes();
        g_bDirty = true;
    }
}

int32_t getEventDataAt(uint32_t index, StepEvent* data){
    if (g_pPattern) {
        StepEvent* ev = g_pPattern->getEventAt(index);
        if (ev) {
            memcpy(data, ev, sizeof(StepEvent));
            return index;
        }
    }
    return -1;
}

int32_t getBufferEventDataAt(uint32_t index, StepEvent* data){
    if (g_pPattern) {
        StepEvent* ev = g_pPatternBuffer->getEventAt(index);
        if (ev) {
            memcpy(data, ev, sizeof(StepEvent));
            return index;
        }
    }
    return -1;
}

int32_t getNoteIndex(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getNoteIndex(step, note);
    return -1;
}

int32_t getNoteData(uint32_t step, uint8_t note, StepEvent* data, bool cp_buffer){
    if (g_pPattern) {
        if (cp_buffer)
            return g_pPatternBuffer->getNoteData(step, note, data);
        else
            return g_pPattern->getNoteData(step, note, data);
    }
    return -1;
}

int32_t setNoteData(uint32_t step, uint8_t note, StepEvent* data){
    if (g_pPattern) {
        int32_t i = g_pPattern->setNoteData(step, note, data);
        if (i > 0) g_bDirty = true;
        return i;
    }
    return -1;
}

int32_t getNoteStart(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getNoteStart(step, note);
    return -1;
}

uint8_t getNoteVelocity(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getNoteVelocity(step, note);
    return 0;
}

void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setNoteVelocity(step, note, velocity);
        g_bDirty = true;
    }
}

float getNoteOffset(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getNoteOffset(step, note);
    return 0.0;
}

void setNoteOffset(uint32_t step, uint8_t note, float offset) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setNoteOffset(step, note, offset);
        g_bDirty = true;
    }
}

bool addControl(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd, float duration, float offset) {
    if (g_pPattern) {
        if (g_pPattern->addControl(step, control, valueStart, valueEnd, duration, offset)) {
            setPatternModified(g_pPattern, true, false);
            g_bDirty = true;
            return true;
        }
    }
    return false;
}

void removeControl(uint32_t step, uint8_t control) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->removeControl(step, control);
        g_bDirty = true;
    }
}

void clearControl(uint8_t control) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->clearControl(control);
        g_bDirty = true;
    }
}

int32_t getControlStart(uint32_t step, uint8_t control) {
    if (g_pPattern)
        return g_pPattern->getControlStart(step, control);
    return -1;
}

float getControlDuration(uint32_t step, uint8_t control) {
    if (g_pPattern)
        return g_pPattern->getControlDuration(step, control);
    return 0;
}

uint8_t getControlValue(uint32_t step, uint8_t control) {
    if (g_pPattern)
        return g_pPattern->getControlValue(step, control);
    return 0;
}

uint8_t getControlValueEnd(uint32_t step, uint8_t control) {
    if (g_pPattern)
        return g_pPattern->getControlValueEnd(step, control);
    return 0;
}

void setControlValue(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setControlValue(step, control, valueStart, valueEnd);
        g_bDirty = true;
    }
}

float getControlOffset(uint32_t step, uint8_t control) {
    if (g_pPattern)
        return g_pPattern->getControlOffset(step, control);
    return 0.0;
}

void setControlOffset(uint32_t step, uint8_t control, float offset) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setControlOffset(step, control, offset);
        g_bDirty = true;
    }
}

void setNoteStutter(uint32_t step, uint8_t note, uint8_t speed, uint8_t velfx, uint8_t ramp) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutter(step, note, speed, velfx, ramp);
        g_bDirty = true;
    }
}

uint8_t getNoteStutterSpeed(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterSpeed(step, note);
    return 0;
}

void setNoteStutterSpeed(uint32_t step, uint8_t note, uint8_t speed) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterSpeed(step, note, speed);
        g_bDirty = true;
    }
}

uint8_t getNoteStutterVelfx(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterVelfx(step, note);
    return 0;
}

void setNoteStutterVelfx(uint32_t step, uint8_t note, uint8_t velfx) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterVelfx(step, note, velfx);
        g_bDirty = true;
    }
}

uint8_t getNoteStutterRamp(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterRamp(step, note);
    return 0;
}

void setNoteStutterRamp(uint32_t step, uint8_t note, uint8_t ramp) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterRamp(step, note, ramp);
        g_bDirty = true;
    }
}

float getNotePlayChance(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getPlayChance(step, note);
    return 1.0;
}

void setNotePlayChance(uint32_t step, uint8_t note, float chance) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setPlayChance(step, note, chance);
        g_bDirty = true;
    }
}

uint8_t getNotePlayFreq(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getPlayFreq(step, note);
    return 1.0;
}

void setNotePlayFreq(uint32_t step, uint8_t note, uint8_t freq) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setPlayFreq(step, note, freq);
        g_bDirty = true;
    }
}

float getNoteStutterChance(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterChance(step, note);
    return 1.0;
}

void setNoteStutterChance(uint32_t step, uint8_t note, float chance) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterChance(step, note, chance);
        g_bDirty = true;
    }
}

uint8_t getNoteStutterFreq(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterFreq(step, note);
    return 1.0;
}

void setNoteStutterFreq(uint32_t step, uint8_t note, uint8_t freq) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterFreq(step, note, freq);
        g_bDirty = true;
    }
}

float getNoteDuration(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getNoteDuration(step, note);
    return 0.0;
}

bool addProgramChange(uint32_t step, uint8_t program) {
    if (g_pPattern) {
        if (g_pPattern->addProgramChange(step, program)) {
            setPatternModified(g_pPattern, true, false);
            g_bDirty = true;
            return true;
        }
    }
    return false;
}

void removeProgramChange(uint32_t step) {
    if (g_pPattern) {
        if (g_pPattern->removeProgramChange(step))
            return;
        setPatternModified(g_pPattern, true, false);
        g_bDirty = true;
    }
}

uint8_t getProgramChange(uint32_t step) {
    if (g_pPattern)
        return g_pPattern->getProgramChange(step);
    return 0xFF;
}

void transpose(int8_t value) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->transpose(value);
        g_bDirty = true;
    }
}

void changeVelocityAll(int value) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeVelocityAll(value);
        g_bDirty = true;
    }
}

void changeVelocityList(float value, uint32_t* evi_list, uint32_t n) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeVelocityList(value, evi_list, n);
        g_bDirty = true;
    }
}

void changeDurationAll(float value) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeDurationAll(value);
        g_bDirty = true;
    }
}

void changeDurationList(float value, uint32_t* evi_list, uint32_t n) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeDurationList(value, evi_list, n);
        g_bDirty = true;
    }
}

void setScale(uint32_t scale) {
    if (g_pPattern) {
        if (scale != g_pPattern->getScale())
            g_bDirty = true;
        g_pPattern->setScale(scale);
    }
}

uint32_t getScale() {
    if (g_pPattern)
        return g_pPattern->getScale();
    return 0;
}

void setTonic(uint8_t tonic) {
    if (g_pPattern) {
        g_pPattern->setTonic(tonic);
        g_bDirty = true;
    }
}

uint8_t getTonic() {
    if (g_pPattern)
        return g_pPattern->getTonic();
    return 0;
}

void clearPattern(uint32_t pattern) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern) {
        setPatternModified(pPattern, true, false);
        pPattern->clear();
        // pPattern->resetSnapshots();
        g_bDirty = true;
    }
}

void copyPattern(uint32_t source, uint32_t destination) {
    g_seqMan.copyPattern(source, destination);
    g_bDirty = true;
}

void pastePatternBuffer(uint32_t pattern, int32_t dstep, float doffset, int8_t dnote, bool truncate) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern) {
        if (g_pPatternBuffer) {
            pPattern->pastePattern(g_pPatternBuffer, dstep, doffset, dnote, truncate);
            g_bDirty = true;
        }
    }
}

uint32_t copyPatternBuffer(uint32_t pattern, uint32_t step1, uint32_t step2, uint8_t note1, uint8_t note2, bool cut) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern) {
        // Free last selection
        if (g_pPatternBuffer)
            delete g_pPatternBuffer;
        // Copy new selection to buffer
        g_pPatternBuffer = pPattern->getPatternSelection(step1, step2, note1, note2, cut);
        // If something was cutted ...
        uint32_t n = g_pPatternBuffer->getEvents();
        if (cut &&  n > 0)
            g_bDirty = true;
        return n;
    }
    return 0;
}

uint32_t getPatternSelectionIndexes(uint32_t pattern, uint32_t* ev_indexes, uint32_t limit, uint32_t step1, uint32_t step2, uint8_t note1, uint8_t note2) {
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if (pPattern) {
        return pPattern->getPatternSelectionIndexes(ev_indexes, limit, step1, step2, note1, note2);
    }
    return 0;
}

void setInputRest(uint8_t note) {
    if (note > 127)
        g_nInputRest = 0xFF;
    g_nInputRest = note;
    g_bDirty = true;
}

uint8_t getInputRest() { return g_nInputRest; }

bool isPatternModified() {
    if (g_bPatternModified) {
        g_bPatternModified = false;
        return true;
    }
    return false;
}

uint8_t getRefNote() {
    if (g_pPattern)
        return g_pPattern->getRefNote();
    return 60;
}

void setRefNote(uint8_t note) {
    if (g_pPattern)
        g_pPattern->setRefNote(note);
}

uint8_t getQuantizeNotes() {
    if (g_pPattern)
        return g_pPattern->getQuantizeNotes();
    return false;
}

void setQuantizeNotes(uint8_t qn) {
    if (g_pPattern)
        g_pPattern->setQuantizeNotes(qn);
}

void setInterpolateCC(uint8_t ccnum, bool flag) {
    if (g_pPattern)
        g_pPattern->setInterpolateCC(ccnum, flag);
}

bool getInterpolateCC(uint8_t ccnum) {
    if (g_pPattern)
        return g_pPattern->getInterpolateCC(ccnum);
    return false;
}

void setInterpolateCCDefaults() {
    if (g_pPattern)
        g_pPattern->setInterpolateCCDefaults();
}

uint32_t getLastStep() {
    if (g_pPattern)
        return g_pPattern->getLastStep();
    return -1;
}

uint32_t getPatternPlayhead() {
    if (g_pPattern)
        return g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayPosition() / g_pPattern->getClocksPerStep();
    return 0;
}

void setPatternModified(Pattern* pPattern, bool bModified, bool bModifiedTracks) {
    if (bModified && bModifiedTracks)
        g_seqMan.setPatternModified(pPattern);
    g_bPatternModified = bModified;
}

// ** Sequence management functions **

bool addPattern(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    bool bUpdated = false;
    if (pSequence) {
        bUpdated = g_seqMan.addPattern(pSequence, track, position, pattern, force);
        g_bDirty |= bUpdated;
    }
    return bUpdated;
}

void removePattern(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        g_seqMan.removePattern(pSequence, track, position);
        g_bDirty = true;
    }
}

uint32_t getPattern(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence == nullptr)
        return 0xffffffff;
    Track* pTrack = pSequence->getTrack(track);
    if (!pTrack)
        return 0xffffffff;
    Pattern* pPattern = pTrack->getPattern(position);
    if (!pPattern)
        return 0xffffffff;
    return g_seqMan.getPatternIndex(pPattern);
}

uint32_t getPatternAt(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence == nullptr)
        return -1;
    Track* pTrack = pSequence->getTrack(track);
    if (!pTrack)
        return -1;
    Pattern* pPattern = pTrack->getPatternAt(position);
    if (!pPattern)
        return -1;
    return g_seqMan.getPatternIndex(pPattern);
}

uint8_t getSequenceMode(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getPlayMode();
    return 0;
}

void setSequenceMode(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t mode) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->setPlayMode(mode);
        g_bDirty = true;
    }
}

uint8_t getPlayState(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getPlayState();
    else
        return STOPPED;
}

void setSequenceRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t repeat) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->setRepeat(repeat);
        g_bDirty = true;
    }
}

uint8_t getSequenceRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        return pSequence->getRepeat();
    }
    return 0;
}

void setSequenceTempo(uint8_t scene, uint8_t phrase, uint8_t sequence, float tempo) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        pSequence->setTempo(tempo);
}

float getSequenceTempo(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getTempo();
    return 0.0f;
}

void setSequenceBpb(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t bpb) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        pSequence->setTimeSig(bpb);
}

uint8_t getSequenceBpb(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getTimeSig();
    return 0;
}

bool selectSequence(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    if (g_seqMan.getSequence(scene, phrase, sequence) == nullptr)
        return false;
    g_nPhrase = phrase;
    g_nSequence = sequence;
    return true;
}

bool isEmpty(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->isEmpty();
    return true;
}

void setPlayState(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t state) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence == nullptr)
        return;
    if (state == STARTING || state == PLAYING) {
        // If no playing sequences, set BPB to the sequence's phrase's timesig
        // This is disabled. We could want to enable it in the future, or not ;-)
        //if (g_seqMan.getPlayingSequencesCount() == 0) {
		//	setBpb(getPhraseBPB(scene, phrase));
    	//}
        transportStart(TRANSPORT_CLIENT_ZYNSEQ);
    }
    else if (!g_nPlayingSequences && state == STOPPING)
        state = STOPPED;
    g_seqMan.setPlayState(pSequence, state);
}

void togglePlayState(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (!pSequence)
        return;
    if (pSequence->getRepeat() == 0) {
        g_seqMan.stopGroup(pSequence->getGroup());
        return;
    }
    uint8_t nState = pSequence->getPlayState();
    switch (nState) {
    case STOPPED:
        nState = STARTING;
        break;
    case STARTING:
        nState = STOPPED;
        break;
    case PLAYING:
        nState = STOPPING_SYNC;
        break;
    case STOPPING:
    case STOPPING_SYNC:
        nState = PLAYING;
        break;
    case CHILD_PLAYING:
        nState = CHILD_STOPPING;
        break;
    case CHILD_STOPPING:
        nState = STARTING;
        break;
    }
    setPlayState(scene, phrase, sequence, nState);
}

uint32_t getSequenceState(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getState();
    return 0;
}

uint32_t getStateChange(uint32_t* states, uint32_t size) {
    if (size == 0)
        return 0;
    uint32_t count = 0;
    uint8_t phrase = 0;
    uint8_t channel = 0;
    while (Sequence* pPhraseSequence = g_seqMan.getSequence(g_nScene, phrase, PHRASE_CHANNEL)) {
        for (uint8_t channel = 0; channel < 32; ++channel) {
            Sequence* pSequence = pPhraseSequence->m_aChildSequences[channel];
            if (pSequence && pSequence->isModified()) {
                states[count] = (phrase << 24) | (channel << 16) | (pSequence->getState() & 0xffff);
                if (++count >= size)
                    return count;
            }
        }
        if (pPhraseSequence->isModified())
            states[count++] = (phrase << 24) | (PHRASE_CHANNEL << 16) | (pPhraseSequence->getState() & 0xffff);
        if (count >= size)
            return count;
        ++phrase;
    }
    return count;
}

uint8_t* getProgress() {
    return g_seqMan.getProgress();
}

uint32_t getBeat() {
    return g_nBeat;
}

void stop() {
    g_seqMan.stop();
    g_mSchedule.clear();
}

uint32_t getSequencePlayPosition(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        return pSequence->getPlayPosition();
    }
    return 0;
}

void setSequencePlayPosition(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t clock) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->setPlayPosition(clock);
    }
}

uint32_t getSequenceLength(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        return pSequence->getLength();
    }
    return 0;
}

void setSequenceLength(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t length) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        pSequence->updateLength(length);
}

void clearSequence(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->clear();
        g_bDirty = true;
    }
}

size_t getPlayingSequences() {
    return g_seqMan.getPlayingSequencesCount();
}

// ** Sequence management functions **

uint8_t getSequenceGroup(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        return pSequence->getGroup();
    }
    return 0;
}

void setSequenceGroup(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t group) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->setGroup(group);
        g_bDirty = true;
    }
}

bool hasSequenceChanged(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        return pSequence->isModified();
    }
    return false;
}

uint32_t addTrackToSequence(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    g_bDirty = true;
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->addTrack(track);
    return 0;
}

void removeTrackFromSequence(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        if (!pSequence->removeTrack(track))
           return;
    }
    pSequence->updateLength();
    g_bDirty = true;
}

void addTempoEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, float tempo, uint16_t bar, uint16_t tick) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->addTempo(tempo, bar, tick);
    }
    g_bDirty = true;
}

void removeTempoEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar, uint16_t tick) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->removeTempo(bar, tick);
    }
    g_bDirty = true;
}

float getTempoAt(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar, uint16_t tick) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        return pSequence->getTempoAt(bar, tick);
    }
    return 0.0f;
}

void addTimeSigEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar, uint8_t timeSig) {
    if (bar < 1)
        bar = 1;
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        pSequence->addTimeSig(timeSig, bar);
    }
    g_bDirty = true;
}

void removeTimeSigEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        pSequence->removeTimeSig(bar);
    g_bDirty = true;
}

uint8_t getTimeSigAt(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getTimeSigAt(bar);
    return 0;
}

uint32_t getTracksInSequence(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getTracks();
    return 0;
}

void setSequenceName(uint8_t scene, uint8_t phrase, uint8_t sequence, const char* name) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        pSequence->setName(std::string(name));
}

const char* getSequenceName(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        strncpy(g_sName, pSequence->getName().c_str(), sizeof(g_sName) - 1);
        g_sName[sizeof(g_sName) - 1] = 0;  // Ensure null termination
    } else {
        g_sName[0] = 0;
    }
    return g_sName;
}

void setSequenceFollowAction(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t action) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        g_bDirty |= g_seqMan.setFollowAction(scene, pSequence, action, pSequence->getFollowParam(), pSequence->getPlayFlags(), pSequence->getFollowRepeat());
}

uint8_t getSequenceFollowAction(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getFollowAction();
    return FOLLOW_ACTION_NONE;
}

void setSequenceFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence, int16_t param) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        g_bDirty |= g_seqMan.setFollowAction(scene, pSequence, pSequence->getFollowAction(), param, pSequence->getPlayFlags(), pSequence->getFollowRepeat());
}

int16_t getSequenceFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getFollowParam();
    return 0;
}

void setSequencePlayFlags(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t flags) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        g_bDirty |= g_seqMan.setFollowAction(scene, pSequence, pSequence->getFollowAction(), pSequence->getFollowParam(), flags);
}

uint32_t getSequencePlayFlags(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getPlayFlags();
    return 0;
}

void setSequenceFollowRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t repeat) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        g_bDirty |= g_seqMan.setFollowAction(scene, pSequence, pSequence->getFollowAction(), pSequence->getFollowParam(), pSequence->getPlayFlags(), repeat);
}

uint8_t getSequenceFollowRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getFollowRepeat();
    return 0;
}

void updateSequenceInfo() {
    g_seqMan.updateAllSequenceLengths();
}

// ** Scene management **

bool setScene(uint8_t scene) {
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    g_bMutex = true;
    bool bCreated = g_seqMan.setScene(scene);
    g_bMutex = false;
    g_nScene = scene;
    return bCreated;
}

uint8_t getScene() {
    return g_nScene;
}

uint8_t getNumScenes() {
    return g_seqMan.getNumScenes();
}

void removeScene(uint8_t scene) {
    g_seqMan.removeScene(scene);
}

// ** Track management **

uint32_t getPatternsInTrack(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (!pTrack)
            return 0;
        return pTrack->getPatterns();
    }
    return 0;
}

void setTrackOutput(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint8_t output) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (pTrack) {
            pTrack->setOutput(output);
            g_bDirty = true;
        }
    }
}

uint8_t getTrackOutput(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (pTrack) {
            return pTrack->getOutput();
        }
    }
    return 0xFF;
}

void setChannel(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint8_t channel) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (pTrack) {
            pTrack->setChannel(channel);
            g_bDirty = true;
        }
    }
}

uint8_t getChannel(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (pTrack) {
            return pTrack->getChannel();
        }
    }
    return 0xFF;
}

void solo(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, bool solo) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (pTrack) {
            pTrack->solo();
        }
    }
}

bool isSolo(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence) {
        Track* pTrack = pSequence->getTrack(track);
        if (pTrack) {
            return pTrack->isSolo();
        }
    }
    return false;
}

// ** Transport management **/
uint8_t getTransportState() {
    return g_nTransportState;
}

void transportStart(uint8_t id) {
    if (g_nTransportState != PLAYING)
        g_nTransportState = STARTING;
    g_nTransportClients |= (1 << id);
}

void transportStop(uint8_t id) {
    if (id == 255)
        g_nTransportClients = 0;
    else {
        g_nTransportClients &= ~(1 << id);
    }
    if ((g_nTransportClients == 0) && (g_nTransportState != STOPPED))
        g_nTransportState = STOPPING;
}

void transportToggle(uint8_t id) {
    if (g_nTransportState != STOPPED)
        transportStop(id);
    else
        transportStart(id);
}

void setTempo(double tempo) {
    if (tempo >= 10.0 && tempo < 500.0) {
        g_dTempo = tempo;
        updateClockTiming();
        g_seqMan.setTempo(tempo);
        //DPRINTF("Tempo set to: %f FramesPerClock: %u\n", g_dTempo, g_dFramesPerTick);
    }
}

double getTempo() {
    return g_dTempo;
}

void setBpb(uint8_t beats) {
    //!@todo This should happen at bar boundary
    if (beats > 0) {
        g_nBeatsPerBar = beats;
    }
}

uint8_t getBpb() {
    return g_nBeatsPerBar;
}

void setDefaultBpb(uint8_t beats) {
    if (beats > 0) {
        g_nDefaultBpb = beats;
        g_seqMan.setDefaultTimeSig(beats);
    }
}

uint8_t getDefaultBpb() { return g_nDefaultBpb; }

void setMetronomeMode(uint8_t mode) {
    if (mode >= METRO_MODE_LAST)
        return;
    g_nMetronomeMode = mode;
    if (mode >= METRO_MODE_ON)
        transportStart(TRANSPORT_CLIENT_METRO);
    else
        transportStop(TRANSPORT_CLIENT_METRO);
}

uint8_t getMetronomeMode() {
    return g_nMetronomeMode;
}

void setMetronomeVolume(float level) {
    if (level > 1.0)
        level = 1.0;
    if (level < 0.0)
        level = 0.0;
    g_fMetronomeLevel = level;
}

float getMetronomeVolume() { return g_fMetronomeLevel; }

uint8_t getExtClockPPQN() {
    return g_nExtClockPPQN;
}

void setExtClockPPQN(uint8_t ppqn) {
    //!@todo Allow pulse per bar - ppqn may be fractional
    if (ppqn > 0)
        g_nExtClockPPQN = ppqn;
    else
        g_nExtClockPPQN = 1;
}

#include <chrono>
#include <deque>

void tapTempo() {
    using Clock = std::chrono::steady_clock;
    static Clock::time_point lastCallTime;
    static bool hasLast = false;
    static std::deque<double> intervals; // seconds between calls
    auto now = Clock::now();

    // Timeout: reset if last call was more than 1 second ago
    if (hasLast) {
        std::chrono::duration<double> sinceLast = now - lastCallTime;
        if (sinceLast.count() > 1.0) {
            intervals.clear();
            hasLast = false;
        }
    }
    if (hasLast) {
        std::chrono::duration<double> diff = now - lastCallTime;
        double seconds = diff.count();
        if (seconds > 0.0) {
            intervals.push_back(seconds);
            if (intervals.size() > 4)
                intervals.pop_front();
        }
    }
    lastCallTime = now;
    hasLast = true;
    if (intervals.empty())
        return; // Not enough recent taps

    // Average interval
    double sum = 0.0;
    for (double s : intervals)
        sum += s;
    double averageInterval = sum / intervals.size();
    setTempo(60.0 / averageInterval);
}

void enableChannel(uint8_t channel, bool enable) {
    g_seqMan.enableChannel(channel, enable);
}

bool isChannelEnabled(uint8_t channel) {
    return g_seqMan.isChannelEnabled(channel);
}

/* Phrase management */

uint8_t getNumPhrases(uint8_t scene) {
    return g_seqMan.getNumPhrases(scene);
}

void insertPhrase(uint8_t scene, uint8_t phrase)
{
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    g_seqMan.insertPhrase(scene, phrase);
    g_bMutex = false;
    g_bDirty = true;
}

void duplicatePhrase(uint8_t scene, uint8_t phrase)
{
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    g_seqMan.duplicatePhrase(scene, phrase);
    g_bMutex = false;
    g_bDirty = true;
}

void removePhrase(uint8_t scene, uint8_t phrase) {
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    stop(); //!@todo Blunt stop everything to avoid pointers to events in deleted sequences segfault!
    g_seqMan.removePhrase(scene, phrase);
    g_bMutex = false;
    g_bDirty = true;
}

void swapPhrase(uint8_t scene, uint8_t phrase1, uint8_t phrase2) {
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    g_seqMan.swapPhrase(scene, phrase1, phrase2);
    g_bMutex = false;
    g_bDirty = true;
}

void setPhraseBPB(uint8_t scene, uint8_t phrase, uint8_t bpb) {
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
	g_seqMan.setPhraseTimeSig(scene, phrase, bpb);
    g_bMutex = false;
    g_bDirty = true;
}

uint8_t getPhraseBPB(uint8_t scene, uint8_t phrase) {
	return g_seqMan.getPhraseTimeSig(scene, phrase);
}
