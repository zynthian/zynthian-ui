/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020-2025 Brian Walton <brian@riban.co.uk>
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
#include <queue>
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

struct ev_start {
    uint32_t start;
    uint8_t velocity;
    float offset;
};
static struct ev_start startEvents[128];

jack_port_t* g_pInputPort;            // Pointer to the JACK input port
jack_port_t* g_pOutputPort;           // Pointer to the JACK output port
jack_port_t* g_pClippyPort;           // Pointer to the JACK output port feeding clippy
jack_port_t* g_pMetronomePort;        // Pointer to the JACK metronome audio output port
jack_client_t* g_pJackClient = NULL;  // Pointer to the JACK client
jack_nframes_t g_nSampleRate = 48000; // Quantity of samples per second
uint32_t g_nXruns = 0;

uint8_t g_nScene = 0;                               // Index of currently selected scene
SequenceManager g_seqMan;                           // Instance of sequence manager
Pattern* g_pPattern = NULL;                         // Pointer to currently edited pattern
uint16_t g_nPhrase = 0;                              // Index of currently edited phrase
uint16_t g_nSequence = 0;                           // Index of currently edited sequence
std::multimap<uint32_t, SEQ_EVENT*> g_mSchedule;    // Schedule of sequence events (queue for sending), indexed by scheduled play time (samples since JACK epoch)
bool g_bMutex = false;                              // Mutex lock for access to g_mSchedule
bool g_bDebug = false;                              // True to output debug info
bool g_bPatternModified = false;                    // True if pattern has changed since last check
bool g_bDirty = false;                              // True if anything has been modified
std::set<std::string> g_setTransportClient;         // Set of timebase clients having requested transport play
bool g_bClientPlaying = false;                      // True if any external client has requested transport play
bool g_bMidiRecord = false;                         // True to add notes to current pattern from MIDI input
uint8_t g_nSustainValue = 0;                        // Last sustain pedal value during note input (recording)
uint32_t g_nSustainStart = 0;                       // Step when sustain pedal was last pressed
uint32_t g_nLastStepCC = 0;                         // Step when last => WARNING!! Doesn't work if capturing several CC at once!
bool g_naHeldNote[16][128];                         // Array of flags indicating a note has been played on a MIDI channel
bool g_bPlayingSequences = false;                   // True if any sequences are playing

char g_sName[256];           // Buffer to hold sequence name so that it can be sent back for Python to parse
uint8_t g_nInputRest = 0xFF;     // MIDI note number that creates rest in pattern
uint16_t g_nVerticalZoom = 16;   // Quantity of rows to show in pattern and arranger view
uint16_t g_nHorizontalZoom = 16; // Quantity of beats to show in arranger view

// Transport variables apply to next period
uint8_t g_nTimeSig                    = 4;
uint8_t g_nBeatType                   = 4;
uint32_t g_nTicksPerBeat              = 1920;
uint32_t g_nTicksPerClock             = g_nTicksPerBeat / PPQN;
double g_dTempo                       = 120.0;
bool g_bTimebaseChanged               = false;     // True to trigger recalculation of timebase parameters
Timebase* g_pTimebase                 = NULL;      // Pointer to the timebase object for selected song
TimebaseEvent* g_pNextTimebaseEvent   = NULL;      // Pointer to the next timebase event or NULL if no more events in this song
uint32_t g_nBar                       = 1;         // Current bar
uint32_t g_nBeat                      = 1;         // Current beat within bar
uint32_t g_nTick                      = 0;         // Current tick within bar
uint32_t g_nBarStartTick              = 0;         // Quantity of ticks from start of song to start of current bar
jack_nframes_t g_nTransportStartFrame = 0;         // Quantity of frames from JACK epoch to transport start
std::queue<std::pair<jack_nframes_t, jack_nframes_t>> g_qClockPos; // Queue of pending clock positions relative to JACK epoch and clock duration in frames at this time
jack_nframes_t g_nFramesPerClock      = getFramesPerClock(g_dTempo);  // it should have 0.1% jitter at 1920 PPQN and much better jitter (0.01%) at current 24PPQN
uint16_t g_nClock                     = 0;         // Quantity of clocks since start of beat
uint16_t g_nMidiClock                 = 0;         // Quantity of *RECEIVED* MIDI clocks since start of beat
uint16_t g_nAnalogClock               = 0;         // Quantity of *RECEIVED* ANALOG clocks since start of beat
int8_t g_nAnalogClocksBeat            = 2;         // Number of analog clocks per beat (Analog Clock Divisor)
uint8_t g_nClockSource                = TRANSPORT_CLOCK_INTERNAL; // Source of clock that progresses playback
bool g_bSendMidiClock                 = false;     // True to send MIDI clock
jack_nframes_t g_nFramesSinceLastBeat = 0;         // Quantity of frames since last beat

float g_fSwingAmount = 0.0; // Swing amount, range from 0 to 1, but values over 0.5 are not "MPC swing"
float g_fHumanTime = 0.0;   // Timing Humanization, range from 0 to FLOAT_MAX
float g_fHumanVelo = 0.0;   // Velocity Humanization, range from 0 to FLOAT_MAX
float g_fPlayChance = 1.0;  // Probability for playing notes (0 = Notes are not played, 0.5 = Notes plays with prob.50%, 1 = All notes play always)

size_t g_nMetronomePtr = -1;   // Position within metronome click wav data (-1 if not playing, e.g. between beats)
float g_fMetronomeLevel = 1.0; // Factor to scale metronome level (volume)
bool g_bMetronome = false;     // True to enable metronome
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

// Convert tempo to frames per tick
double getFramesPerTick(double dTempo) {
    //!@todo Be cosistent in use of ticks or clocks
    return 60 * g_nSampleRate / (dTempo * g_nTicksPerBeat);
}

// Convert tempo to frames per clock
jack_nframes_t getFramesPerClock(double dTempo) { return getFramesPerTick(dTempo) * g_nTicksPerClock; }

// Update bars, beats, ticks for given position in frames
void updateBBT(jack_position_t* position) {
    //!@todo Populate bbt_sequence (experimental so not urgent but could be useful)
    jack_nframes_t nFrames = 0;
    jack_nframes_t nFramesPerTick = getFramesPerTick(g_dTempo); //!@todo Need to use default tempo from start of song but current tempo now!!!
    uint32_t nBar = 0;
    uint32_t nBeat = 0;
    uint32_t nTick = 0;
    uint8_t nTimeSig = 4;
    uint32_t nTicksPerBar = g_nTicksPerBeat * nTimeSig;
    bool bDone = false;
    jack_nframes_t nFramesInSection;
    uint32_t nTicksInSection;
    uint32_t nTicksFromStart = 0;

    position->tick = position->frame % uint32_t(nFramesPerTick);
    position->beat = (uint32_t(position->frame / nFramesPerTick) % uint32_t(g_nTicksPerBeat)) + 1;
    position->bar = (uint32_t(position->frame / nFramesPerTick / g_nTicksPerBeat) % nTimeSig) + 1;
    position->beats_per_bar = g_nTimeSig;
    position->beats_per_minute = g_dTempo;
    position->beat_type = g_nBeatType;
    position->ticks_per_beat = g_nTicksPerBeat;
    position->bar_start_tick = 0; //!@todo Need to calculate this

    // g_pNextTimebaseEvent = g_pTimebase->getPreviousTimebaseEvent(position->bar, (position->beat - 1) * position->ticks_per_beat + position->tick  ,
    // TIMEBASE_TYPE_ANY);

    // Iterate through events, calculating quantity of frames between each event
    /*
    if(g_pTimebase)
    {
        for(size_t nIndex = 0; nIndex < g_pTimebase->getEventQuant(); ++nIndex)
        {
            // Get next event
            TimebaseEvent* pEvent = g_pTimebase->getEvent(nIndex);
            // Calculate quantity of ticks between events and frames between events
            nTicksInSection = (pEvent->bar * nTicksPerBar + pEvent->clock * g_nFramesPerClock - nTicksFromStart);
            nFramesInSection = nTicksInSection * nFramesPerTick;
            // Break if next event is beyond requested position
            if(nFrames + nFramesInSection > position->frame)
                break;
            // Update frame counter, bar and tick from which to count last section
            nFrames += nFramesInSection;
            nBar = pEvent->bar;
            nTick = pEvent->clock * g_nTicksPerClock;
            nTicksFromStart += nTicksInSection;
            // Update tempo and time signature from event
            if(pEvent->type == TIMEBASE_TYPE_TEMPO)
                nFramesPerTick = getFramesPerTick(pEvent->value);
            else if(pEvent->type == TIMEBASE_TYPE_TIMESIG)
            {
                nTimeSig = pEvent->value >> 8;
                nBeatsType = pEvent->value & 0x00FF;
                nTicksPerBar = g_nTicksPerBeat * nTimeSig;
            }
        }
    }
    */
    // Calculate BBT from last section
    nFramesInSection = position->frame - nFrames;
    nTicksInSection = nFramesInSection / nFramesPerTick;
    uint32_t nBarsInSection = nTicksInSection / nTicksPerBar;
    position->bar = nBar + nBarsInSection + 1;
    uint32_t nTicksInLastBar = nTicksInSection % nTicksPerBar;
    position->beat = nTicksInLastBar / g_nTicksPerBeat + 1;
    position->tick = nTicksInLastBar % position->beat;
    nTicksFromStart += nTicksInSection;
    position->bar_start_tick = nTicksFromStart - nTicksInLastBar;
    g_nClock = position->tick % (uint32_t)g_nTicksPerClock;
    // g_dTempo = g_pTimebase->getTempo(g_nBar, (g_nBeat * g_nTicksPerBeat + g_nTick) / g_nTicksPerClock);
    // g_nTimeSig = uint32_t(g_pTimebase->getTimeSig(g_nBar, (g_nBeat * g_nTicksPerBeat + g_nTick) / g_nTicksPerClock)) >> 8;
}

/*  Handle timebase callback - update timebase elements (BBT) from transport position
    nState: Current jack transport state
    nFramesInPeriod: Quantity of frames in current period
    pPosition: Pointer to position structure for the next cycle
    bUpdate: True (non-zero) to request position be updated to position defined in pPosition (also true on first callback)
    pArgs: Pointer to argument supplied by jack_set_timebase_callback (not used here)

    [Info]
    If bUpdate is false then calculate BBT from pPosition->frame: quantity of frames from start of song.
    If bUpdate is true then calculate pPostion-frame from BBT info

    [Process]
    Calculate bars, beats, ticks at pPosition->frame from start of song or calculate frame from BBT:
    Iterate through timebase events spliting song into sections delimited by timebase events: time signature / tempo changes, calculating BBT for each section
   up to current position. Add events from sequences to schedule
*/
void onJackTimebase(jack_transport_state_t nState, jack_nframes_t nFramesInPeriod, jack_position_t* pPosition, int bUpdate, void* pArgs) {
    // Process timebase events
    /* Disabled timebase events until linear song implemented
    while(g_pTimebase && g_pNextTimebaseEvent && (g_pNextTimebaseEvent->bar <= g_nBar)) // || g_pNextTimebaseEvent->bar == g_nBar && g_pNextTimebaseEvent->clock
    <= g_nClock))
    {
        if(g_pNextTimebaseEvent->type == TIMEBASE_TYPE_TEMPO)
        {
            g_dTempo = g_pNextTimebaseEvent->value;
            g_nFramesPerClock = getFramesPerClock(g_dTempo);
            pPosition->beats_per_minute = g_dTempo;
            g_bTimebaseChanged = true;
            DPRINTF("Tempo change to %0.0fbpm frames/clk: %f\n", g_dTempo, g_nFramesPerClock);
        }
        else if(g_pNextTimebaseEvent->type == TIMEBASE_TYPE_TIMESIG)
        {
            g_nTimeSig = g_pNextTimebaseEvent->value >> 8;
            g_nBeatType = g_pNextTimebaseEvent->value & 0x0F;
            pPosition->beats_per_bar = g_nTimeSig;
            g_bTimebaseChanged = true;
            DPRINTF("Time signature change to %u/%u\n", g_nTimeSig, g_nBeatType);
        }
        g_pNextTimebaseEvent = g_pTimebase->getNextTimebaseEvent(g_pNextTimebaseEvent);
    }
    */

    // Calculate BBT at start of next period if transport starting, locating or change in tempo or timebase (although latter is commented out)
    if (bUpdate || g_bTimebaseChanged) {
        /*
        if(g_pTimebase)
        {
            g_dTempo = g_pTimebase->getTempo(g_nBar, (g_nBeat * g_nTicksPerBeat + g_nTick));
            g_nTimeSig = g_pTimebase->getTimeSig(g_nBar, (g_nBeat * g_nTicksPerBeat + g_nTick)) >> 8;
        }
        */
        // Update position based on parameters passed
        if (pPosition->valid & JackPositionBBT) {
            // Set position from BBT
            DPRINTF("bUpdate: %s, g_bTimebaseChanged: %s, Position valid flags: %u\n", bUpdate ? "True" : "False", g_bTimebaseChanged ? "True" : "False",
                    pPosition->valid);
            DPRINTF("PreSet position from BBT Bar: %u Beat: %u Tick: %u Clock: %u\n", pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
            DPRINTF("Beats per bar: %f Tempo: %f\n", pPosition->beats_per_bar, g_dTempo);
            // Fix overruns
            pPosition->beat += pPosition->tick / (uint32_t)pPosition->ticks_per_beat;
            pPosition->tick %= (uint32_t)(pPosition->ticks_per_beat);
            pPosition->bar += (pPosition->beat - 1) / pPosition->beats_per_bar;
            pPosition->beat = ((pPosition->beat - 1) % (uint32_t)(pPosition->beats_per_bar)) + 1;
            pPosition->frame = transportGetLocation(pPosition->bar, pPosition->beat, pPosition->tick);
            pPosition->ticks_per_beat = g_nTicksPerBeat;
            pPosition->beats_per_minute = g_dTempo; //!@todo Need to set tempo from position pointer to allow external clients to set tempo
            g_nClock = pPosition->tick / g_nTicksPerClock;
            g_nBar = pPosition->bar;
            g_nBeat = pPosition->beat;
            g_nTick = pPosition->tick;
            DPRINTF("Set position from BBT Bar: %u Beat: %u Tick: %u Clock: %u\n", pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
        } else // if(!bUpdate) //!@todo I have masked bUpdate because I don't see why we would be reaching here but we do and need to figure out why
        {
            updateBBT(pPosition);
            DPRINTF("Set position from frame %u\n", pPosition->frame);
        }
        g_nTransportStartFrame = jack_frame_time(g_pJackClient) - pPosition->frame; //!@todo This isn't setting to transport start position
        pPosition->valid = JackPositionBBT;
        g_nFramesPerClock = getFramesPerClock(g_dTempo);
        g_bTimebaseChanged = false;
        DPRINTF("New position: Jack frame: %u Frame: %u Bar: %u Beat: %u Tick: %u Clock: %u\n", g_nTransportStartFrame, pPosition->frame, pPosition->bar,
                pPosition->beat, pPosition->tick, g_nClock);
        //!@todo Check impact of timebase discontinuity
    } else {
        // DPRINTF("Update position with values from previous period Jack frame: %u Frame: %u Bar: %u Beat: %u Tick: %u Clock: %u\n", g_nTransportStartFrame,
        // pPosition->frame, pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
        //  Set BBT values calculated during previous period
        pPosition->bar = g_nBar;
        pPosition->beat = g_nBeat;
        pPosition->tick = g_nTick % (uint32_t)g_nTicksPerBeat;
        pPosition->bar_start_tick = g_nBarStartTick;
        pPosition->beats_per_bar = g_nTimeSig;
        pPosition->beat_type = g_nBeatType;
        pPosition->ticks_per_beat = g_nTicksPerBeat;
        pPosition->beats_per_minute = g_dTempo;
        // Loop frame if not playing song
        //        if(!g_nBeat && isSongPlaying())
        //            pPosition->frame = transportGetLocation(pPosition->bar, pPosition->beat, pPosition->tick); //!@todo Does this work? (yes). Are there any
        //            discontinuity or impact on other clients? Can it be optimsed?
    }
}

/*  Process jack cycle - must complete within single jack period
    nFrames: Quantity of frames in this period
    pArgs: Parameters passed to function by main thread (not used here)

    [For info]
    jack_last_frame_time() returns the quantity of samples since JACK started until start of this period
    jack_midi_event_write sends MIDI message at sample time sequence within this period

    [Process]
    Process incoming MIDI events
    Iterate through events scheduled to trigger within this process period
    For each event, add MIDI events to the output buffer at appropriate sample sequence
    Remove events from schedule
*/
int onJackProcess(jack_nframes_t nFrames, void* pArgs) {
    static jack_position_t transportPosition; // JACK transport position structure populated each cycle and checked for transport progress
    static jack_nframes_t nLastBeatFrame = 0; // Frames since jack epoch of last quarter note used to calc tempo of external clock
    //static std::pair<jack_nframes_t, jack_nframes_t> lastClock;

    // Get output buffer that will be processed in this process cycle
    void* pOutputBuffer = jack_port_get_buffer(g_pOutputPort, nFrames);
    void* pClippyBuffer = jack_port_get_buffer(g_pClippyPort, nFrames);
    unsigned char* pBuffer;
    jack_midi_clear_buffer(pOutputBuffer);
    jack_midi_clear_buffer(pClippyBuffer);
    jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);
    static double dLast = nNow;
    jack_transport_state_t nTransportState = jack_transport_query(g_pJackClient, &transportPosition);

    jack_default_audio_sample_t* pOutMetronome = (jack_default_audio_sample_t*)jack_port_get_buffer(g_pMetronomePort, nFrames);
    memset(pOutMetronome, 0, sizeof(jack_default_audio_sample_t) * nFrames);

    // Process MIDI input
    void* pInputBuffer = jack_port_get_buffer(g_pInputPort, nFrames);
    jack_midi_event_t midiEvent;
    jack_nframes_t nCount = jack_midi_get_event_count(pInputBuffer);
    uint8_t bPatternRecording = (g_bMidiRecord && g_pPattern);
    // Track* pTrack = g_pSequence->getTrack(g_pSequence->m_nCurrentTrack);
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    for (jack_nframes_t i = 0; i < nCount; i++) {
        if (jack_midi_event_get(&midiEvent, pInputBuffer, i))
            continue;
        if (g_nClockSource & (TRANSPORT_CLOCK_MIDI | TRANSPORT_CLOCK_ANALOG)) {
            switch (midiEvent.buffer[0]) {
            /*
            case MIDI_STOP:
                break;
            */
            case MIDI_START:
                g_nBar = 1;
                g_bMutex = false;
                transportStart("zynseq");
                while (g_bMutex)
                    std::this_thread::sleep_for(std::chrono::microseconds(10));
                g_bMutex = true;
                nTransportState = JackTransportRolling;
                g_nClock = 0;
                g_nMidiClock = 0;
                g_nAnalogClock = 0;
                nLastBeatFrame = 0;
                g_nBeat = 1;
                break;
            case MIDI_CONTINUE:
                // For analog clock source => update tempo on each bar
                if (g_nClockSource & TRANSPORT_CLOCK_ANALOG) {
                    if (nLastBeatFrame)
                        setTempo(60.0 * (double)g_nSampleRate / (nNow + midiEvent.time - nLastBeatFrame));
                    //DPRINTF("BPM = 60 * %u / (%u + %u - %u) = %f\n", g_nSampleRate, nNow, midiEvent.time, nLastBeatFrame, 60.0 * (double)g_nSampleRate / (nNow + midiEvent.time - nLastBeatFrame));
                    nLastBeatFrame = nNow + midiEvent.time;
                }
                g_bMutex = false;
                transportStart("zynseq");
                while (g_bMutex)
                    std::this_thread::sleep_for(std::chrono::microseconds(10));
                g_bMutex = true;
                nTransportState = JackTransportRolling;
                break;
            case MIDI_CLOCK:
                if (g_nClockSource & TRANSPORT_CLOCK_MIDI) {
                    // DPRINTF("MIDI CLOCK %u, %u => %u\n", g_nMidiClock, g_nClock, midiEvent.time);
                    if (g_nMidiClock == 0) {
                        // Update tempo on each beat
                        if (nLastBeatFrame)
                            setTempo(60.0 * (double)g_nSampleRate / (nNow + midiEvent.time - nLastBeatFrame));
                        // DPRINTF("BPM = 60 * %u / (%u + %u - %u) = %f\n", g_nSampleRate, nNow, midiEvent.time, nLastBeatFrame, 60.0 * (double)g_nSampleRate /
                        // (nNow + midiEvent.time - nLastBeatFrame));
                        nLastBeatFrame = nNow + midiEvent.time;
                    }
                    if (nTransportState == JackTransportRolling)
                        g_qClockPos.push(std::pair<jack_nframes_t, jack_nframes_t>(nNow + midiEvent.time, g_nFramesPerClock));
                    // PPQN is fixed to 24 in MIDI 1.0
                    if (g_nMidiClock < 23)
                        g_nMidiClock++;
                    else
                        g_nMidiClock = 0;
                }
                // For analog clock source => update tempo on each analog clock
                else if (g_nClockSource & TRANSPORT_CLOCK_ANALOG) {
                    if (nLastBeatFrame)
                        setTempo(60.0 * (double)g_nSampleRate / (g_nAnalogClocksBeat * (nNow + midiEvent.time - nLastBeatFrame)));
                    //printf("BPM = 60 * %u / (%u * (%u + %u - %u)) = %f\n", g_nSampleRate, g_nAnalogClocksBeat, nNow, midiEvent.time, nLastBeatFrame, 60.0 * (double)g_nSampleRate / (g_nAnalogClocksBeat * (nNow + midiEvent.time - nLastBeatFrame)));
                    nLastBeatFrame = nNow + midiEvent.time;

                    // Adjust time of next clock in queue, so it keep aligned with analog pulse
                    if (!g_qClockPos.empty()) {
                        uint16_t target_clock = (g_nAnalogClock * PPQN / g_nAnalogClocksBeat) % PPQN;
                        //printf("Clock => %u, Target Clock => %u\n",  g_nClock, target_clock);
						// Analog clock is advanced => Move next clock in queue to Now
						if (g_nClock > target_clock) {
							g_nClock = target_clock;
							g_qClockPos.back().first = nLastBeatFrame;
							//printf("Next Clock advanced to %lu\n",  g_qClockPos.back().first);
						}
						// Analog clock is delayed => Delay next clock in queue
						else if (g_nClock < target_clock) {
							g_nClock = target_clock;
							g_qClockPos.back().first = nLastBeatFrame + g_nFramesPerClock;
							//printf("Next Clock delayed to %lu\n",  g_qClockPos.back().first);
						}
					}
					g_nAnalogClock ++;
					if (g_nAnalogClock >= g_nAnalogClocksBeat) g_nAnalogClock = 0;
                }
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
                uint8_t nSong = midiEvent.buffer[1];
                DPRINTF("StepJackClient Select song %u\n", nSong);
                if (nSong < g_seqMan.getNumScenes())
                    setScene(nSong); //!@todo Restricted to existing scenes but may want to allow creating new scene
                break;
            }
            default:
                break;
            }
        }

        // Handle MIDI events for programming patterns from MIDI input
        if (bPatternRecording) {
            uint32_t nStep = getPatternPlayhead();
            uint8_t nPlayState = g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayState();
            uint8_t nCommand = midiEvent.buffer[0] & 0xF0;

            // Real Time Capture (while playing)
            if (nPlayState) {
                // Note on event
                if (nCommand == MIDI_NOTE_ON && midiEvent.buffer[2] > 0) {
                    startEvents[midiEvent.buffer[1]].start = nStep;
                    startEvents[midiEvent.buffer[1]].velocity = midiEvent.buffer[2];
                    // Calculate clock position offset, in steps (from 0.0 to 1.0)
                    float offset = double(g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayPosition()) / double(g_pPattern->getClocksPerStep()) - double(nStep);
                    // Subtract latency delay
                    offset -= double(nFrames) / double(g_pPattern->getClocksPerStep() * g_nFramesPerClock);
                    // Add event offset relative to last clock
                    // if (lastClock.first) {
                    // offset += double(midiEvent.time + nNow - lastClock.first - nFrames) / double(g_pPattern->getClocksPerStep() * g_nFramesPerClock);
                    //}
                    if (offset < 0.0) offset = 0;
                    // Capture not quantized => quantization is done in real time (see track.cpp)
                    startEvents[midiEvent.buffer[1]].offset = offset;
                }
                // Note off event
                else if ((nCommand == MIDI_NOTE_ON && midiEvent.buffer[2] == 0) || nCommand == MIDI_NOTE_OFF) {
                    if (startEvents[midiEvent.buffer[1]].start != -1) {
                        double dDur = double(g_seqMan.getSequence(g_nScene, g_nPhrase, g_nSequence)->getPlayPosition()) -
                                      (startEvents[midiEvent.buffer[1]].start + startEvents[midiEvent.buffer[1]].offset) * g_pPattern->getClocksPerStep();
                        if (dDur < 1.0)
                            dDur = g_pPattern->getLength() + dDur;
                        g_pPattern->addNote(startEvents[midiEvent.buffer[1]].start, midiEvent.buffer[1], startEvents[midiEvent.buffer[1]].velocity,
                                            dDur / g_pPattern->getClocksPerStep(), startEvents[midiEvent.buffer[1]].offset);
                        startEvents[midiEvent.buffer[1]].start = -1;
                        setPatternModified(g_pPattern, true, false);
                    }
                }
                // CC event
                else if (nCommand == MIDI_CONTROL) {
                    // Manage sustain pedal (CC64)
                    if (midiEvent.buffer[1] == 64) {
                        if (midiEvent.buffer[2] > 0 && g_nSustainValue == 0) {
                            g_nSustainValue = midiEvent.buffer[2];
                            g_nSustainStart = nStep;
                            // Add new pedal press
                            g_pPattern->addControl(g_nSustainStart, 64, g_nSustainValue, g_nSustainValue);
                            setPatternModified(g_pPattern, true, false);
                        } else if (midiEvent.buffer[2] == 0) {
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
                        	g_pPattern->removeControlInterval(g_nLastStepCC + 1, nStep, (uint8_t)midiEvent.buffer[1]);
                        // Add new CC event
                        g_pPattern->addControl(nStep, (uint8_t)midiEvent.buffer[1], (uint8_t)midiEvent.buffer[2], (uint8_t)midiEvent.buffer[2]);
                        g_nLastStepCC = nStep;
                        setPatternModified(g_pPattern, true, false);
                    }
                }
            }
            // Step capture
            else {
                bool bAdvance = false;
                // Use sustain pedal for advance step
                if (nCommand == MIDI_CONTROL && midiEvent.buffer[1] == 64) {
                    if (midiEvent.buffer[2] > 0)
                        g_nSustainValue = midiEvent.buffer[2];
                    else {
                        g_nSustainValue = 0;
                        bAdvance = true;
                    }
                }
                // Note on event
                else if (nCommand == MIDI_NOTE_ON && midiEvent.buffer[2]) {
                    setPatternModified(g_pPattern, true, false);
                    uint32_t nDuration = getNoteDuration(nStep, midiEvent.buffer[1]);
                    if (g_nSustainValue > 0)
                        g_pPattern->addNote(nStep, midiEvent.buffer[1], midiEvent.buffer[2], nDuration + 1);
                    else {
                        bAdvance = true;
                        if (nDuration)
                            g_pPattern->removeNote(nStep, midiEvent.buffer[1]);
                        else if (midiEvent.buffer[1] != g_nInputRest)
                            g_pPattern->addNote(nStep, midiEvent.buffer[1], midiEvent.buffer[2], 1);
                    }
                }
                // Advance step
                if (bAdvance && nTransportState != JackTransportRolling) {
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

    // Iterate through clocks in this period, adding any events and handling any timebase changes
    if (nTransportState == JackTransportRolling) {
        bool bSync = false;              // True if at start of bar
        jack_nframes_t nClockOffset = 0; // Position within this period that clock 0 occurs
        // There should always be a clock scheduled for internal clock source when transport is rolling
        if (g_nClockSource & TRANSPORT_CLOCK_INTERNAL && g_qClockPos.empty()) {
            // No clock scheduled so must be starting up
            g_qClockPos.push(std::pair<jack_nframes_t, jack_nframes_t>(nNow, g_nFramesPerClock));
            //g_nClock = 0;
        }
        // Process clock
        while (!g_qClockPos.empty() && (g_qClockPos.front().first < nNow + nFrames)) {
            bSync = false;
            if (g_nClock == 0) {
                // Clock zero so on beat
                bSync = (g_nBeat == 1);
                g_nTick = 0; //!@todo ticks are not updated under normal rolling condition
                g_pMetro = bSync ? &g_metro_peep : &g_metro_pip;
                g_nMetronomePtr = 0;
                nClockOffset = g_qClockPos.front().first - nNow;
                DPRINTF("Beat %u of %u clock %u timestamp: %f (%f)\n", g_nBeat, g_nTimeSig, g_nClock, g_qClockPos.front().first, g_qClockPos.front().first - dLast);
                dLast = g_qClockPos.front().first;
            }
            // Schedule events in next period
            // Pass clock time and schedule to pattern manager so it can populate with events. Pass sync pulse so that it can synchronise its sequences, e.g.
            // start zynpad sequences
            g_bPlayingSequences = g_seqMan.clock(g_qClockPos.front(), &g_mSchedule, bSync);
            //!@todo Optimise to reduce rate calling clock especially if we increase the clock rate from 24 to 96 or above. Maybe return the time until next check

            // Advance clock
            if (++g_nClock >= PPQN) {
                g_nClock = 0;
                if (++g_nBeat > g_nTimeSig) {
                    g_nBeat = 1;
                    ++g_nBar;
                }
            }
            if (g_bSendMidiClock && g_bClientPlaying) {
                // Add a MIDI clock to the queue
                jack_nframes_t nClockTime = g_qClockPos.front().first - nNow;
                //if (bSync)
                //    g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(nClockTime, new SEQ_EVENT({nClockTime, 0, MIDI_MESSAGE{MIDI_CONTINUE, 0, 0}})));
                g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(nClockTime, new SEQ_EVENT({nClockTime, 0, MIDI_MESSAGE{MIDI_CLOCK, 0, 0}})));
            }
            if (g_nClockSource & TRANSPORT_CLOCK_INTERNAL)
                g_qClockPos.push(std::pair<jack_nframes_t, jack_nframes_t>(g_qClockPos.back().first + g_nFramesPerClock, g_nFramesPerClock));
            g_qClockPos.pop();
        }
        // g_nTick = g_nTicksPerBeat - nRemainingFrames / getFramesPerTick(g_dTempo);

        if (!g_bPlayingSequences && (g_nClockSource & TRANSPORT_CLOCK_INTERNAL)) {
            DPRINTF("Stopping transport because no sequences playing now: %u clock: %u beat: %u tick: %u\n", nNow, g_nClock, g_nBeat, g_nTick);
            g_bMutex = false;
            transportStop("zynseq");
            while (g_bMutex)
                std::this_thread::sleep_for(std::chrono::microseconds(10));
            g_bMutex = true;
            g_nMetronomePtr = -1;
            // if(g_nClockSource & TRANSPORT_CLOCK_INTERNAL)
            {
                // Remove pending clocks
                std::queue<std::pair<jack_nframes_t, jack_nframes_t>> qEmpty;
                std::swap(g_qClockPos, qEmpty);
            }
        }

        if (g_bMetronome && g_nMetronomePtr >= 0) {
            for (int n = nClockOffset; n < nFrames; ++n) {
                if (g_nMetronomePtr < g_pMetro->size) {
                    pOutMetronome[n] = g_pMetro->data[g_nMetronomePtr++] * g_fMetronomeLevel;
                } else {
                    g_nMetronomePtr = -1;
                    break;
                }
            }
        }

        // Check for timebase changes from patterns
        if (g_seqMan.isTempoChanged()) {
            float tempo = g_seqMan.getTempo();
            setTempo(tempo);
        }
        if (g_seqMan.isTimeSigChanged()) {
            uint8_t newTimeSig = g_seqMan.getTimeSig();
            if (newTimeSig > 1)
                g_nTimeSig = newTimeSig;
        }
    }

    // Process events scheduled to be sent to MIDI output
    if (g_mSchedule.size()) {
        auto it = g_mSchedule.begin();
        jack_nframes_t nTime = 0;
        while (it != g_mSchedule.end()) {
            bool bSkip = false;
            if (it->first >= nNow + nFrames)
                break; // Event scheduled beyond this buffer
            if (it->first < nNow) {
                nTime = 0; // This event is in the past so send as soon as possible
                DPRINTF("Sending event [%x,%x,%x] from past (Scheduled:%u Now:%u Diff:%d samples)\n", it->second->msg.command, it->second->msg.value1, it->second->msg.value2, it->first, nNow, nNow - it->first);
            } else
                nTime = it->first - nNow; // Schedule event at scheduled time sequence
            if (nTime >= nFrames) {
                g_bMutex = false;
                return 0; // Must have bumped beyond end of this frame time so must wait until next frame - earlier events were processed and pointer nulled so
                          // will not trigger in next period
            }
            if (it->second) {
                size_t nSize = 1;
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
                if (!bSkip) {
                    pBuffer = jack_midi_event_reserve(it->second->output == 0xfe ? pClippyBuffer : pOutputBuffer, nTime, nSize);
                    if (pBuffer == NULL)
                        break; // Exceeded buffer size (or other issue)
                    pBuffer[0] = it->second->msg.command;
                    if (nSize > 1)
                        pBuffer[1] = it->second->msg.value1;
                    if (nSize > 2)
                        pBuffer[2] = it->second->msg.value2;
                    DPRINTF("Sending MIDI event %x,%x,%x at %u\n", pBuffer[0], pBuffer[1], pBuffer[2], nNow + nTime);
                }
                delete it->second;
                it->second = NULL;
            }
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
    g_nFramesPerClock = getFramesPerClock(g_dTempo);
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

    // Create input port
    if (!(g_pInputPort = jack_port_register(g_pJackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0))) {
        fprintf(stderr, "libzynseq cannot register input port\n");
        return;
    }

    // Create output ports
    if (!(g_pOutputPort = jack_port_register(g_pJackClient, "output", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libzynseq cannot register output port\n");
        return;
    }
    if (!(g_pClippyPort = jack_port_register(g_pJackClient, "clippy", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libzynseq cannot register clippy output port\n");
        return;
    }

    // Create metronome output port
    if (!(g_pMetronomePort = jack_port_register(g_pJackClient, "metronome", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "linzynseq cannot register metronome port\n");
        return;
    }

    g_nSampleRate = jack_get_sample_rate(g_pJackClient);
    g_nFramesPerClock = getFramesPerClock(g_dTempo);

    // Register JACK callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    jack_set_sample_rate_callback(g_pJackClient, onJackSampleRateChange, 0);
    //    jack_set_xrun_callback(g_pJackClient, onJackXrun, 0); //!@todo Remove xrun handler (just for debug)

    if (jack_activate(g_pJackClient)) {
        fprintf(stderr, "libzynseq cannot activate client\n");
        return;
    }

    // Register the cleanup function to be called when program exits
    atexit(end);

    transportRequestTimebase();
    transportLocate(0);
    selectPattern(1);
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
    g_nBeat = 1;
    g_nTimeSig = 4;
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
            j["sig"] = fileRead16(pFile);
            fileRead8u(pFile); // No longer use trigger channel
            fileRead8u(pFile); // No longer use trigger input
            fileRead8u(pFile); // No longer use trigger output
            fileRead8(pFile); // padding
            fileRead8u(pFile); // No longer use vertical zoom
            fileRead8u(pFile); // No longer use horizontal zoom
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
                json eventj;
                eventj.push_back(fileRead32(pFile)); // step
                float fDuration, fOffset;
                if (nVersion > 8) {
                    eventj.push_back(fileReadBCD(pFile)); // offset
                    eventj.push_back(fileReadBCD(pFile)); // duration
                    nBlockSize -= 4;
                } else {
                    eventj.push_back(0);
                    eventj.push_back(float(fileRead16(pFile)) / 100 + fileRead16(pFile)); // fractional + integral (BCD)
                }
                eventj.push_back(fileRead8u(pFile)); // command
                eventj.push_back(fileRead8u(pFile)); // value 1 start
                eventj.push_back(fileRead8u(pFile)); // value 2 start
                eventj.push_back(fileRead8u(pFile)); // value 1 end
                eventj.push_back(fileRead8u(pFile)); // value 2 end
                if (nVersion > 7) {
                    eventj.push_back(fileRead8u(pFile)); // stutter count
                    eventj.push_back(fileRead8u(pFile)); // stutter duration
                    nBlockSize -= 2;
                }
                if (nVersion > 8) {
                    eventj.push_back(float(fileRead8u(pFile))); // play chance
                    nBlockSize -= 1;
                }
                fileRead8(pFile); // Padding
                nBlockSize -= 14;
                // printf(" Step:%u Duration:%u Command:%02X, Value1:%u..%u, Value2:%u..%u\n", nTime, nDuration, nCommand, nValue1start, nValue2end,
                // nValue2start, nValue2end);
                patj["events"].push_back(eventj);
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
                    json tbeventj;
                    tbeventj["bar"] = fileRead16(pFile);
                    tbeventj["tick"] = fileRead16(pFile);
                    tbeventj["type"] = fileRead16(pFile);
                    tbeventj["value"] = fileRead16(pFile);
                    nBlockSize -= 8;
                    jSeq["timebase"].push_back(tbeventj);
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
    // printf("Ver: %d Loaded %lu patterns, %lu sequences, %lu banks from file %s\n", nVersion, m_mPatterns.size(), m_mSequences.size(), m_mBanks.size(),
    // filename);

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
        uint32_t nStep = jEvent.value("step", 0);
        float fDuration = jEvent.value("duration", 1.0);
        float fOffset = jEvent.value("offset", 0.0);
        uint8_t nCommand = jEvent.value("command", 144);
        uint8_t nValue1start = jEvent["val1Start"];
        uint8_t nValue2start = jEvent["val2Start"];
        StepEvent* pEvent = pPattern->addEvent(nStep, nCommand, nValue1start, nValue2start, fDuration, fOffset);
        pEvent->setValue1end(jEvent.value("val1End", nValue1start));
        pEvent->setValue2end(jEvent.value("val2End", nValue2start));
        pEvent->setStutterCount(jEvent.value("stutCnt", 0));
        pEvent->setStutterDur(jEvent.value("stutDur", 1));
        pEvent->setPlayChance(float(jEvent.value("chance", 100)) / 100);
    }
}

bool setState(const char* state) {
    try {
        json j = json::parse(state);
        g_nPhrase = 0;
        g_nSequence = 0;
        uint8_t nLowestScene = 255;

        g_seqMan.init();

        g_dTempo = j.value("tempo", g_dTempo); //!@todo Do we want to reset tempo to default or use previous if not in state?
        g_nTimeSig = j.value("sig", 4);

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
                    pEvent->setStutterCount(jEvent[8]);
                    pEvent->setStutterDur(jEvent[9]);
                    pEvent->setPlayChance(float(jEvent[10]) / 100);
                }
            }
        }
        if (j.contains("scenes")) {
            for (uint32_t nScene = 0; nScene <j["scenes"].size(); ++nScene) {
                json jScene = j["scenes"][nScene];
                if (nScene < nLowestScene)
                    nLowestScene = nScene;
                uint32_t nPhrase = 0;
                std::vector<std::array<int16_t, 4>> vFollowActions;
                for (auto& jPhrase: jScene["phrases"]) {
                    Sequence* pPhrase = g_seqMan.insertPhrase(nScene, -1);
                    if (!pPhrase)
                        continue;
                    if (jPhrase.contains("name"))
                        pPhrase->setName(jPhrase["name"]);
                    if (jPhrase.contains("mode"))
                        pPhrase->setPlayMode(jPhrase["mode"]);
                    pPhrase->setTimeSig(jPhrase.value("sig", 0));
                    pPhrase->setTempo(jPhrase.value("tempo", 0));
                    if (jPhrase.contains("repeat"))
                        pPhrase->setRepeat(jPhrase["repeat"]);
                    // Store the follow configuration to apply after all sequences have been created
                    std::array<int16_t, 4> followAction;
                    followAction[0] = nPhrase;
                    followAction[1] = PHRASE_CHANNEL;
                    followAction[2] = jPhrase.value("followAction", FOLLOW_ACTION_NONE);
                    followAction[3] = jPhrase.value("followParam", 0);
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
                        std::array<int16_t, 4> followAction;
                        followAction[0] = nPhrase;
                        followAction[1] = nSeq;
                        followAction[2] = jSeq.value("followAction", FOLLOW_ACTION_NONE);
                        followAction[3] = jSeq.value("followParam", 0);
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
                    ++nPhrase;
                }
                // Set follow actions late, after creating all sequence objects
                for (auto& followAction : vFollowActions) {
                    Sequence* pSeq = g_seqMan.getSequence(nScene, followAction[0], followAction[1]);
                    g_seqMan.setFollowAction(nScene, pSeq, followAction[2], followAction[3]);
                }
            }
        }
        g_bDirty = false;
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
    jState["sig"] = g_nTimeSig;
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
                jEvt.push_back(pEvent->getStutterCount());
                jEvt.push_back(pEvent->getStutterDur());
                jEvt.push_back(int(pEvent->getPlayChance()) * 100);
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
            jPhrase["sig"] = pPhrase->getTimeSig();
            jPhrase["tempo"] = pPhrase->getTempo();
            jPhrase["repeat"] = pPhrase->getRepeat();
            jPhrase["followAction"] = pPhrase->getFollowAction();
            jPhrase["followParam"] = pPhrase->getFollowParam();
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
            // g_nTimeSig, g_nVerticalZoom, g_nHorizontalZoom
            fileRead16u(pFile);
            fileRead16u(pFile);
            fileRead16u(pFile);
            // printf("Version:%u Beats per bar:%u Zoom V:%u H:%u\n", nVersion, g_nTimeSig, g_nVerticalZoom, g_nHorizontalZoom);
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
                jPattern["chance"] = fileReadBCD(pFile);
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
                jEvent["step"] = fileRead32u(pFile);
                if (nVersion > 8) {
                    jEvent["offset"] = fileReadBCD(pFile);
                    jEvent["duration"] = fileReadBCD(pFile);
                    nBlockSize -= 4;
                } else {
                    jEvent["duration"] = float(fileRead16u(pFile)) / 100 + fileRead16u(pFile); // fractional + integral (BCD)
                }
                jEvent["command"] = fileRead8u(pFile);
                jEvent["val1Start"] = fileRead8u(pFile);
                jEvent["val2Start"] = fileRead8u(pFile);
                jEvent["val1End"] = fileRead8u(pFile);
                jEvent["val2End"] = fileRead8u(pFile);
                if (nVersion > 7) {
                    jEvent["stutCnt"] = fileRead8u(pFile);
                    jEvent["stutDur"] = fileRead8u(pFile);
                    nBlockSize -= 2;
                }
                if (nVersion > 8) {
                    jEvent["chance"] = (float(fileRead8u(pFile)) / 100);
                    nBlockSize -= 1;
                }
                fileRead8(pFile); // Padding
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

// Schedule a MIDI message to be sent in next JACK process cycle
void sendMidiMsg(MIDI_MESSAGE& msg) {
    // Find first available time slot
    uint32_t time = jack_frames_since_cycle_start(g_pJackClient);
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    g_bMutex = true;
    g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(time, new SEQ_EVENT({time, 0, msg})));
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

//!@todo Do we still need functions to send MIDI transport control (start, stop, continuew, songpos, song select, clock)?

void sendMidiStart() {
    MIDI_MESSAGE msg;
    msg.command = MIDI_START;
    sendMidiMsg(msg);
    DPRINTF("Sending MIDI Start... does it get recieved back???\n");
}

void sendMidiStop() {
    MIDI_MESSAGE msg;
    msg.command = MIDI_STOP;
    sendMidiMsg(msg);
}

void sendMidiContinue() {
    MIDI_MESSAGE msg;
    msg.command = MIDI_CONTINUE;
    sendMidiMsg(msg);
}

void sendMidiSongPos(uint16_t pos) {
    MIDI_MESSAGE msg;
    msg.command = MIDI_POSITION;
    msg.value1 = pos & 0x7F;
    msg.value2 = (pos >> 7) & 0x7F;
    sendMidiMsg(msg);
}

void sendMidiSong(uint32_t pos) {
    if (pos > 127)
        return;
    MIDI_MESSAGE msg;
    msg.command = MIDI_SONG;
    msg.value1 = pos & 0x7F;
    sendMidiMsg(msg);
}

void sendMidiClock() {
    MIDI_MESSAGE msg;
    msg.command = MIDI_CLOCK;
    sendMidiMsg(msg);
}

void sendMidiCommand(uint8_t status, uint8_t value1, uint8_t value2) {
    MIDI_MESSAGE msg;
    msg.command = status;
    msg.value1 = value1;
    msg.value2 = value2;
    sendMidiMsg(msg);
}

uint8_t getMidiClockOutput() { return g_bSendMidiClock; }

void setMidiClockOutput(bool enable) { g_bSendMidiClock = enable; }

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

uint8_t getStutterCount(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterCount(step, note);
    return 0;
}

void setStutterCount(uint32_t step, uint8_t note, uint8_t count) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterCount(step, note, count);
        g_bDirty = true;
    }
}

uint8_t getStutterDur(uint32_t step, uint8_t note) {
    if (g_pPattern)
        return g_pPattern->getStutterDur(step, note);
    return 0;
}

void setStutterDur(uint32_t step, uint8_t note, uint8_t dur) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->setStutterDur(step, note, dur);
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

void changeDurationAll(float value) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeDurationAll(value);
        g_bDirty = true;
    }
}

void changeStutterCountAll(int value) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeStutterCountAll(value);
        g_bDirty = true;
    }
}

void changeStutterDurAll(int value) {
    if (g_pPattern) {
        setPatternModified(g_pPattern, true, false);
        g_pPattern->changeStutterDurAll(value);
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
    return g_seqMan.getSequence(scene, phrase, sequence)->getPlayState();
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

void setSequenceSig(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t sig) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        pSequence->setTimeSig(sig);
}

uint8_t getSequenceSig(uint8_t scene, uint8_t phrase, uint8_t sequence) {
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
    if (!g_bPlayingSequences) {
        if (state == STARTING) {
            if (g_nClockSource & TRANSPORT_CLOCK_INTERNAL)
                setTransportToStartOfBar();
            transportStart("zynseq");
        } else if (state == STOPPING)
            state = STOPPED;
    }
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
        g_bDirty |= g_seqMan.setFollowAction(scene, pSequence, action, pSequence->getFollowParam());
}

void setSequenceFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence, int16_t param) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        g_bDirty |= g_seqMan.setFollowAction(scene, pSequence, pSequence->getFollowAction(), param);
}

uint8_t getSequenceFollowAction(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getFollowAction();
    return FOLLOW_ACTION_NONE;
}

int16_t getSequenceFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    Sequence* pSequence = g_seqMan.getSequence(scene, phrase, sequence);
    if (pSequence)
        return pSequence->getFollowParam();
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

void setTransportToStartOfBar() {
    jack_position_t position;
    jack_transport_query(g_pJackClient, &position);
    position.beat = 1;
    position.tick = 0;
    //    position.valid = JackPositionBBT;
    jack_transport_reposition(g_pJackClient, &position);
    //    g_pNextTimebaseEvent = g_pTimebase->getPreviousTimebaseEvent(position.bar, 1, TIMEBASE_TYPE_ANY); //!@todo Might miss event if 2 at start of bar
}

void transportLocate(uint32_t frame) { jack_transport_locate(g_pJackClient, frame); }

/*  Calculate the song position in frames from BBT
 */
jack_nframes_t transportGetLocation(uint32_t bar, uint32_t beat, uint32_t tick) {
    // Convert one-based bars and beats to zero-based
    if (bar > 0)
        --bar;
    if (beat > 0)
        --beat;
    uint32_t nTicksToPrev = 0;
    uint32_t nTicksToEvent = 0;
    uint32_t nTicksPerBar = g_nTicksPerBeat * g_nTimeSig;
    //!@todo Handle changes in tempo and time signature
    //uint32_t nFramesPerTick = getFramesPerTick(DEFAULT_TEMPO);
    uint32_t nFramesPerTick = getFramesPerTick(g_dTempo);
    uint32_t nFrames = 0; // Frames to position
    /*
    if(g_pTimebase)
    {
        for(size_t nIndex = 0; nIndex < g_pTimebase->getEventQuant(); ++nIndex)
        {
            TimebaseEvent* pEvent = g_pTimebase->getEvent(nIndex);
            if(pEvent->bar > bar || pEvent->bar == bar && pEvent->clock > (g_nTicksPerBeat * beat + tick) / g_nTicksPerBeat / PPQN)
                break; // Ignore events later than new position
            nTicksToEvent = pEvent->bar * nTicksPerBar + pEvent->clock * g_nTicksPerBeat / PPQN;
            uint32_t nTicksInBlock = nTicksToEvent - nTicksToPrev;
            nFrames += nFramesPerTick * nTicksInBlock;
            nTicksToPrev = nTicksToEvent;
            if(pEvent->type == TIMEBASE_TYPE_TEMPO)
                nFramesPerTick = getFramesPerTick(pEvent->value);
            else if(pEvent->type == TIMEBASE_TYPE_TIMESIG)
                nTicksPerBar = g_nTicksPerBeat * (pEvent->value >> 8);
        }
    }
    */
    nFrames += nFramesPerTick * (bar * nTicksPerBar + beat * g_nTicksPerBeat + tick - nTicksToPrev);
    return nFrames;
}

bool transportRequestTimebase() {
    if (jack_set_timebase_callback(g_pJackClient, 0, onJackTimebase, NULL))
        return false;
    return true;
}

void transportReleaseTimebase() { jack_release_timebase(g_pJackClient); }

void transportStart(const char* client) {
    bool bPlaying = (g_setTransportClient.size() != 0);
    g_bClientPlaying = true;
    g_setTransportClient.emplace(client);
    if (bPlaying)
        return;

    jack_position_t pos;
    if (jack_transport_query(g_pJackClient, &pos) != JackTransportRolling)
        jack_transport_start(g_pJackClient);
    if (g_nClockSource & TRANSPORT_CLOCK_INTERNAL) {
        // Send MIDI start message
        jack_nframes_t nClockTime = jack_last_frame_time(g_pJackClient);
        while (g_bMutex)
            std::this_thread::sleep_for(std::chrono::microseconds(10));
        g_bMutex = true;
        g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(nClockTime, new SEQ_EVENT({nClockTime, 0, MIDI_MESSAGE{MIDI_START, 0, 0}})));
        g_bMutex = false;
    }
}

void transportStop(const char* client) {
    if (strcmp(client, "ALL") == 0)
        g_setTransportClient.clear();
    else if (!g_bClientPlaying)
        return;
    else {
        auto itClient = g_setTransportClient.find(std::string(client));
        if (itClient != g_setTransportClient.end())
            g_setTransportClient.erase(itClient);
    }
    g_bClientPlaying = (g_setTransportClient.size() != 0);
    if (g_bClientPlaying)
        return;
    jack_transport_stop(g_pJackClient);
    if (g_nClockSource & TRANSPORT_CLOCK_INTERNAL) {
        // Send MIDI stop message
        jack_nframes_t nClockTime = jack_last_frame_time(g_pJackClient);
        while (g_bMutex)
            std::this_thread::sleep_for(std::chrono::microseconds(10));
        g_bMutex = true;
        g_mSchedule.insert(std::pair<uint32_t, SEQ_EVENT*>(nClockTime, new SEQ_EVENT({0, 0, MIDI_MESSAGE({MIDI_STOP, 0, 0})})));
        g_bMutex = false;
    }
}

void transportToggle(const char* client) {
    if (transportGetPlayStatus() == JackTransportRolling)
        transportStop(client);
    else
        transportStart(client);
}

uint8_t transportGetPlayStatus() {
    jack_position_t position; // Not used but required to query transport
    jack_transport_state_t nState;
    return jack_transport_query(g_pJackClient, &position);
}

void setTempo(double tempo) {
    if (tempo >= 10.0 && tempo < 500.0) {
        g_dTempo = tempo;
        if (transportGetPlayStatus() != JackTransportRolling)
            transportLocate(0); // Cludge to update transport tempo when transport not running
        g_nFramesPerClock = getFramesPerClock(g_dTempo);
        g_seqMan.setTempo(tempo);
        DPRINTF("Tempo set to: %f FramesPerClock: %f\n", g_dTempo, g_nFramesPerClock);
    }
}

double getTempo() { return g_dTempo; }

void setTimeSig(uint8_t beats) {
    if (beats > 0) {
        g_nTimeSig = beats;
        g_seqMan.setTimeSig(beats);
    }
}

uint8_t getTimeSig() { return g_nTimeSig; }

void transportSetSyncTimeout(uint32_t timeout) { jack_set_sync_timeout(g_pJackClient, timeout); }

void enableMetronome(bool enable) {
    g_bMetronome = enable;
    g_nMetronomePtr = -1;
}

bool isMetronomeEnabled() { return g_bMetronome; }

void setMetronomeVolume(float level) {
    if (level > 1.0)
        level = 1.0;
    if (level < 0.0)
        level = 0.0;
    g_fMetronomeLevel = level;
}

float getMetronomeVolume() { return g_fMetronomeLevel; }

uint8_t getClockSource() { return g_nClockSource; }

void setClockSource(uint8_t source) {
    if (source == 0)
        return;
    g_nClockSource = source;
    std::queue<std::pair<jack_nframes_t, jack_nframes_t>> qEmpty;
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    std::swap(g_qClockPos, qEmpty);
    g_bMutex = false;
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
}

void removePhrase(uint8_t scene, uint8_t phrase) {
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    stop(); //!@todo Blunt stop everything to avoid pointers to events in deleted sequences segfault!
    g_seqMan.removePhrase(scene, phrase);
    g_bMutex = false;
}

void swapPhrase(uint8_t scene, uint8_t phrase1, uint8_t phrase2) {
    while (g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    g_seqMan.swapPhrase(scene, phrase1, phrase2);
    g_bMutex = false;
}
