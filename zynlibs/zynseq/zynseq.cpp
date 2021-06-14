/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020 Brian Walton <brian@riban.co.uk>
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

#include <stdio.h> //provides printf
#include <stdlib.h> //provides exit
#include <thread> //provides thread for timer
#include "sequencemanager.h" //provides management of sequences, patterns, events, etc
#include "timebase.h" //provides timebase event map
#include <jack/jack.h> //provides JACK interface
#include <jack/midiport.h> //provides JACK MIDI interface
#include "zynseq.h" //exposes library methods as c functions
#include <set>
#include <string>
#include <cstring> //provides strcmp

#define FILE_VERSION 6

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)

SequenceManager g_seqMan; // Instance of sequence manager
Pattern* g_pPattern = 0; // Currently selected pattern
uint32_t g_nPattern = 0; // Index of currently selected pattern
Track* g_pTrack = 0; // Pattern editor track
jack_port_t * g_pInputPort; // Pointer to the JACK input port
jack_port_t * g_pOutputPort; // Pointer to the JACK output port
jack_client_t *g_pJackClient = NULL; // Pointer to the JACK client

jack_nframes_t g_nSampleRate = 44100; // Quantity of samples per second
std::map<uint32_t,MIDI_MESSAGE*> g_mSchedule; // Schedule of MIDI events (queue for sending), indexed by scheduled play time (samples since JACK epoch)
bool g_bDebug = false; // True to output debug info
bool g_bPatternModified = false; // True if pattern has changed since last check
size_t g_nPlayingSequences = 0; // Quantity of playing sequences
uint32_t g_nXruns = 0;
bool g_bDirty = false; // True if anything has been modified
std::set<std::string> g_setTransportClient; // Set of timebase clients having requested transport play 
bool g_bClientPlaying = false; // True if any external client has requested transport play
bool g_bInputEnabled = false; // True to add notes to current pattern from MIDI input

uint8_t g_nInputChannel = 0xFF; // MIDI channel for input (0xFF to disable)
bool g_bSustain = false; // True if sustain pressed during note input
uint8_t g_nInputRest = 0xFF; // MIDI note number that creates rest in pattern
uint8_t g_nTriggerStatusByte = MIDI_NOTE_ON | 15; // MIDI status byte which triggers a sequence (optimisation)
uint16_t g_nVerticalZoom = 8;
uint16_t g_nHorizontalZoom = 16;
uint16_t g_nTriggerLearning = 0; // 2 word bank|sequence that is waiting for MIDI to learn trigger (0 if not learning)
char g_sName[16]; // Buffer to hold sequence name so that it can be sent back for Python to parse

bool g_bMutex = false; // Mutex lock for access to g_mSchedule

// Tranpsort variables apply to next period
uint32_t g_nPulsePerQuarterNote = 24; //!@todo Increase resolution - maybe use ticks per beat
uint32_t g_nBeatsPerBar = 4;
float g_fBeatType = 4.0;
double g_dTicksPerBeat = 1920.0;
double g_dTempo = 120.0;
double g_dTicksPerClock = g_dTicksPerBeat / g_nPulsePerQuarterNote;
bool g_bTimebaseChanged = false; // True to trigger recalculation of timebase parameters
Timebase* g_pTimebase = NULL; // Pointer to the timebase object for selected song
TimebaseEvent* g_pNextTimebaseEvent = NULL; // Pointer to the next timebase event or NULL if no more events in this song
uint32_t g_nBar = 1; // Current bar
uint32_t g_nBeat = 1; // Current beat within bar
uint32_t g_nTick = 0; // Current tick within bar
double g_dBarStartTick = 0; // Quantity of ticks from start of song to start of current bar
jack_nframes_t g_nTransportStartFrame = 0; // Quantity of frames from JACK epoch to transport start
double g_dFramesToNextClock = 0.0; // Frames until next clock pulse
double g_dFramesPerClock = 60 * g_nSampleRate / (g_dTempo *  g_dTicksPerBeat) * g_dTicksPerClock; //!@todo Change to integer will have 0.1% jitter at 1920 ppqn and much better jitter (0.01%) at current 24ppqn
uint8_t g_nClock = 0; // Quantity of MIDI clocks since start of beat

// ** Internal (non-public) functions  (not delcared in header so need to be in correct order in source file) **

// Enable / disable debug output
void enableDebug(bool bEnable)
{
    printf("libseq setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
}

// Convert tempo to frames per tick
double getFramesPerTick(double dTempo)
{
    //!@todo Be cosistent in use of ticks or clocks
    return 60 * g_nSampleRate / (dTempo *  g_dTicksPerBeat);
}

// Convert tempo to frames per clock
double getFramesPerClock(double dTempo)
{
    return getFramesPerTick(dTempo) * g_dTicksPerClock;
}

// Update bars, beats, ticks for given position in frames
void updateBBT(jack_position_t* position)
{
    //!@todo Populate bbt_sequence (experimental so not urgent but could be useful)
    double dFrames = 0;
    double dFramesPerTick = getFramesPerTick(g_dTempo); //!@todo Need to use default tempo from start of song but current tempo now!!!
    static double dDebugFramesPerTick = 0;
    uint32_t nBar = 0;
    uint32_t nBeat = 0;
    uint32_t nTick = 0;
    uint8_t nBeatsPerBar = 4;
    uint32_t nTicksPerBar = g_dTicksPerBeat * nBeatsPerBar;
    bool bDone = false;
    double dFramesInSection;
    uint32_t nTicksInSection;
    uint32_t nTicksFromStart = 0;

    position->tick = position->frame % uint32_t(dFramesPerTick);
    position->beat = (uint32_t(position->frame / dFramesPerTick) % uint32_t(g_dTicksPerBeat)) + 1;
    position->bar = (uint32_t(position->frame / dFramesPerTick / g_dTicksPerBeat) % nBeatsPerBar) + 1;
    position->beats_per_bar = float(g_nBeatsPerBar);
    position->beats_per_minute = g_dTempo;
    position->beat_type = g_fBeatType;
    position->ticks_per_beat = g_dTicksPerBeat;
    position->bar_start_tick = 0; //!@todo Need to calculate this
    //g_pNextTimebaseEvent = g_pTimebase->getPreviousTimebaseEvent(position->bar, (position->beat - 1) * position->ticks_per_beat + position->tick  , TIMEBASE_TYPE_ANY);


    // Iterate through events, calculating quantity of frames between each event
    /*
    if(g_pTimebase)
    {
        for(size_t nIndex = 0; nIndex < g_pTimebase->getEventQuant(); ++nIndex)
        {
            // Get next event
            TimebaseEvent* pEvent = g_pTimebase->getEvent(nIndex);
            // Calculate quantity of ticks between events and frames between events
            nTicksInSection = (pEvent->bar * nTicksPerBar + pEvent->clock * g_dFramesPerClock - nTicksFromStart);
            dFramesInSection = nTicksInSection * dFramesPerTick;
            // Break if next event is beyond requested position
            if(dFrames + dFramesInSection > position->frame)
                break;
            // Update frame counter, bar and tick from which to count last section
            dFrames += dFramesInSection;
            nBar = pEvent->bar;
            nTick = pEvent->clock * g_dTicksPerClock;
            nTicksFromStart += nTicksInSection;
            // Update tempo and time signature from event
            if(pEvent->type == TIMEBASE_TYPE_TEMPO)
                dFramesPerTick = getFramesPerTick(pEvent->value);
            else if(pEvent->type == TIMEBASE_TYPE_TIMESIG)
            {
                nBeatsPerBar = pEvent->value >> 8;
                nBeatsType = pEvent->value & 0x00FF;
                nTicksPerBar = g_dTicksPerBeat * nBeatsPerBar;
            }
        }
    }
    */
    // Calculate BBT from last section
    dFramesInSection = position->frame - dFrames;
    nTicksInSection = dFramesInSection / dFramesPerTick;
    uint32_t nBarsInSection = nTicksInSection / nTicksPerBar;
    position->bar = nBar + nBarsInSection + 1;
    uint32_t nTicksInLastBar = nTicksInSection % nTicksPerBar;
    position->beat = nTicksInLastBar / g_dTicksPerBeat + 1;
    position->tick = nTicksInLastBar % position->beat;
    nTicksFromStart += nTicksInSection;
    position->bar_start_tick = nTicksFromStart - nTicksInLastBar;
    g_nClock = position->tick % (uint32_t)g_dTicksPerClock;
    //g_dTempo = g_pTimebase->getTempo(g_nBar, (g_nBeat * g_dTicksPerBeat + g_nTick) / g_dTicksPerClock);
    //g_nBeatsPerBar = uint32_t(g_pTimebase->getTimeSig(g_nBar, (g_nBeat * g_dTicksPerBeat + g_nTick) / g_dTicksPerClock)) >> 8;
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
    Iterate through timebase events spliting song into sections delimited by timebase events: time signature / tempo changes, calculating BBT for each section up to current position.
    Add events from sequences to schedule
*/
void onJackTimebase(jack_transport_state_t nState, jack_nframes_t nFramesInPeriod,
          jack_position_t *pPosition, int bUpdate, void* pArgs)
{
    // Process timebase events
    /* Disabled timebase events until linear song implemented
    while(g_pTimebase && g_pNextTimebaseEvent && (g_pNextTimebaseEvent->bar <= g_nBar)) // || g_pNextTimebaseEvent->bar == g_nBar && g_pNextTimebaseEvent->clock <= g_nClock))
    {
        if(g_pNextTimebaseEvent->type == TIMEBASE_TYPE_TEMPO)
        {
            g_dTempo = g_pNextTimebaseEvent->value;
            g_dFramesPerClock = getFramesPerClock(g_dTempo);
            pPosition->beats_per_minute = g_dTempo;
            g_bTimebaseChanged = true;
            DPRINTF("Tempo change to %0.0fbpm frames/clk: %f\n", g_dTempo, g_dFramesPerClock);
        }
        else if(g_pNextTimebaseEvent->type == TIMEBASE_TYPE_TIMESIG)
        {
            g_nBeatsPerBar = g_pNextTimebaseEvent->value >> 8;
            g_fBeatType = g_pNextTimebaseEvent->value & 0x0F;
            pPosition->beats_per_bar = float(g_nBeatsPerBar);
            g_bTimebaseChanged = true;
            DPRINTF("Time signature change to %u/%0.0f\n", g_nBeatsPerBar, g_fBeatType);
        }
        g_pNextTimebaseEvent = g_pTimebase->getNextTimebaseEvent(g_pNextTimebaseEvent);
    }
    */

    // Calculate BBT at start of next period if transport starting, locating or change in tempo or timebase (although latter is commented out)
    if(bUpdate || g_bTimebaseChanged)
    {
        /*
        if(g_pTimebase)
        {
            g_dTempo = g_pTimebase->getTempo(g_nBar, (g_nBeat * g_dTicksPerBeat + g_nTick));
            g_nBeatsPerBar = g_pTimebase->getTimeSig(g_nBar, (g_nBeat * g_dTicksPerBeat + g_nTick)) >> 8;
        }
        */
        // Update position based on parameters passed
        if(pPosition->valid & JackPositionBBT)
        {
            // Set position from BBT
            DPRINTF("bUpdate: %s, g_bTimebaseChanged: %s, Position valid flags: %u\n", bUpdate?"True":"False", g_bTimebaseChanged?"True":"False", pPosition->valid);
            DPRINTF("PreSet position from BBT Bar: %u Beat: %u Tick: %u Clock: %u\n", pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
            DPRINTF("Beats per bar: %f Tempo: %f\n", pPosition->beats_per_bar, g_dTempo);
            // Fix overruns
            pPosition->beat += pPosition->tick / (uint32_t)pPosition->ticks_per_beat;
            pPosition->tick %= (uint32_t)(pPosition->ticks_per_beat);
            pPosition->bar += (pPosition->beat - 1) / pPosition->beats_per_bar;
            pPosition->beat = ((pPosition->beat - 1) % (uint32_t)(pPosition->beats_per_bar)) + 1;
            pPosition->frame = transportGetLocation(pPosition->bar, pPosition->beat, pPosition->tick);
            pPosition->ticks_per_beat = g_dTicksPerBeat;
            pPosition->beats_per_minute = g_dTempo; //!@todo Need to set tempo from position pointer to allow external clients to set tempo
            g_nClock = pPosition->tick / g_dTicksPerClock;
            g_nBar = pPosition->bar;
            g_nBeat = pPosition->beat;
            g_nTick = pPosition->tick;
            DPRINTF("Set position from BBT Bar: %u Beat: %u Tick: %u Clock: %u\n", pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
        }
        else// if(!bUpdate) //!@todo I have masked bUpdate because I don't see why we would be reaching here but we do and need to figure out why
        {
            updateBBT(pPosition);
            DPRINTF("Set position from frame %u\n", pPosition->frame);
        }
        g_nTransportStartFrame = jack_frame_time(g_pJackClient) - pPosition->frame; //!@todo This isn't setting to transport start position
        pPosition->valid = JackPositionBBT;
        g_dFramesPerClock = getFramesPerClock(g_dTempo);
        g_bTimebaseChanged = false;
        DPRINTF("New position: Jack frame: %u Frame: %u Bar: %u Beat: %u Tick: %u Clock: %u\n", g_nTransportStartFrame, pPosition->frame, pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
        //!@todo Check impact of timebase discontinuity
    }
    else
    {
        //DPRINTF("Update position with values from previous period Jack frame: %u Frame: %u Bar: %u Beat: %u Tick: %u Clock: %u\n", g_nTransportStartFrame, pPosition->frame, pPosition->bar, pPosition->beat, pPosition->tick, g_nClock);
        // Set BBT values calculated during previous period
        pPosition->bar = g_nBar;
        pPosition->beat = g_nBeat;
        pPosition->tick = g_nTick % (uint32_t)g_dTicksPerBeat;
        pPosition->bar_start_tick = g_dBarStartTick;
        pPosition->beats_per_bar = float(g_nBeatsPerBar);
        pPosition->beat_type = g_fBeatType;
        pPosition->ticks_per_beat = g_dTicksPerBeat;
        pPosition->beats_per_minute = g_dTempo;
        // Loop frame if not playing song
//        if(!g_nBeat && isSongPlaying())
//            pPosition->frame = transportGetLocation(pPosition->bar, pPosition->beat, pPosition->tick); //!@todo Does this work? (yes). Are there any discontinuity or impact on other clients? Can it be optimsed?
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
int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
    static jack_position_t transportPosition; // JACK transport position structure populated each cycle and checked for transport progress
    static uint8_t nClock = g_nPulsePerQuarterNote; // Clock pulse count 0..g_nPulsePerQuarterNote - 1
    static uint32_t nTicksPerPulse;
    static double dTicksPerFrame;
    static double dBeatsPerMinute; // Store so that we can check for change and do less maths
    static double dBeatsPerBar; // Store so that we can check for change and do less maths
    static jack_nframes_t nFramerate; // Store so that we can check for change and do less maths
    static uint32_t nFramesPerPulse;
    
    // Get output buffer that will be processed in this process cycle
    void* pOutputBuffer = jack_port_get_buffer(g_pOutputPort, nFrames);
    unsigned char* pBuffer;
    jack_midi_clear_buffer(pOutputBuffer);
    jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);
    jack_transport_state_t nState = jack_transport_query(g_pJackClient, &transportPosition);

    // Process MIDI input
    void* pInputBuffer = jack_port_get_buffer(g_pInputPort, nFrames);
    jack_midi_event_t midiEvent;
    jack_nframes_t nCount = jack_midi_get_event_count(pInputBuffer);
    for(jack_nframes_t i = 0; i < nCount; i++)
    {
        jack_midi_event_get(&midiEvent, pInputBuffer, i);
        /*  Not using MIDI transport control or clock
        switch(midiEvent.buffer[0])
        {
            case MIDI_STOP:
                DPRINTF("StepJackClient MIDI STOP\n");
                break;
            case MIDI_START:
                DPRINTF("StepJackClient MIDI START\n");
                break;
            case MIDI_CONTINUE:
                DPRINTF("StepJackClient MIDI CONTINUE\n");
                break;
            case MIDI_CLOCK:
                DPRINTF("StepJackClient MIDI CLOCK\n");
                // Ignore MIDI clock - let Jack timebase master handle it
                break;
            case MIDI_POSITION:
            {
                //!@todo Should we let Jack timebase master manage MIDI position changes?
                uint32_t nPos = (midiEvent.buffer[1] + (midiEvent.buffer[2] << 7)) * 6;
                DPRINTF("StepJackClient POSITION %d (clocks)\n", nPos);
                break;
            }
            case MIDI_SONG:
                DPRINTF("StepJackClient Select song %d\n", midiEvent.buffer[1]);
                break;
            default:
                break;
        }
        */

        // Handle MIDI Note On events to trigger seqeuences
        if((midiEvent.buffer[0] == g_nTriggerStatusByte) && midiEvent.buffer[2])
        {
            uint8_t nNote = midiEvent.buffer[1];
            if(g_nTriggerLearning)
            {
                setTriggerNote((g_nTriggerLearning >> 8) & 0xFF, g_nTriggerLearning & 0xFF, nNote);
            }
            else
            {
                uint16_t nSeq = g_seqMan.getTriggerSequence(nNote);
                if(nSeq)
                    togglePlayState(nSeq >> 8, nSeq & 0xFF);
            }
        }

        // Handle MIDI events for programming patterns from MIDI input
        if(g_bInputEnabled && g_pTrack && g_pPattern && g_nInputChannel == (midiEvent.buffer[0] & 0x0F))
        {
            uint32_t nStep = g_pTrack->getPatternPlayhead();
            bool bAdvance = false;
            if(((midiEvent.buffer[0] & 0xF0) == 0xB0) && midiEvent.buffer[1] == 64)
            {
                // Sustain pedal event
                if(midiEvent.buffer[2])
                    g_bSustain = true;
                else
                {
                    g_bSustain = false;
                    bAdvance = true;
                }
            }
            else if(((midiEvent.buffer[0] & 0xF0) == 0x90) && midiEvent.buffer[2])
            {
                // Note on event
                g_bPatternModified = true;
                uint32_t nDuration = getNoteDuration(nStep, midiEvent.buffer[1]);
                if(g_bSustain)
                    g_pPattern->addNote(nStep, midiEvent.buffer[1], midiEvent.buffer[2], nDuration + 1);
                else
                {
                    bAdvance = true;
                    if(nDuration)
                        g_pPattern->removeNote(nStep, midiEvent.buffer[1]);
                    else if(midiEvent.buffer[1] != g_nInputRest)
                        g_pPattern->addNote(nStep, midiEvent.buffer[1], midiEvent.buffer[2], 1);
                }
            }
            if(bAdvance && transportGetPlayStatus() != JackTransportRolling)
            {
                g_pTrack->setPosition(0);
                if(++nStep >= g_pPattern->getSteps())
                    nStep = 0;
                g_pTrack->setPatternPlayhead(nStep);
            }
        }
    }

    // Send MIDI output aligned with first sample of frame resulting in similar latency to audio
    //!@todo Interpolate events across frame, e.g. CC variations
    while(g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;

    // Iterate through clocks in this period, adding any events and handling any timebase changes
    if(nState == JackTransportRolling)
    {
        bool bSync = false; // True if at start of bar
        while(g_dFramesToNextClock < nFrames)
        {
            bSync = false;
            if(g_nClock == 0)
            {
                // Clock zero so on beat
                bSync = (g_nBeat == 1);
                g_nTick = 0; //!@todo ticks are not updated under normal rolling condition
            }
            // Schedule events in next period
            // Pass clock time and schedule to pattern manager so it can populate with events. Pass sync pulse so that it can synchronise its sequences, e.g. start zynpad sequences
            g_nPlayingSequences = g_seqMan.clock(nNow + g_dFramesToNextClock, &g_mSchedule, bSync, g_dFramesPerClock); //!@todo Optimise to reduce rate calling clock especialy if we increase the clock rate from 24 to 96 or above. Maybe return the time until next check
            // Advance clock
            if(++g_nClock >= g_nPulsePerQuarterNote)
            {
                g_nClock = 0;
                if(++g_nBeat > g_nBeatsPerBar)
                {
                    g_nBeat = 1;
                    if(g_bClientPlaying) //!@todo This will advance bar and stop manual beats per bar changes working when other clients are playing
                        ++g_nBar;
                }
                DPRINTF("Beat %u of %u\n", g_nBeat, g_nBeatsPerBar);
            }
            g_dFramesToNextClock += g_dFramesPerClock;
        }
        g_dFramesToNextClock -= nFrames;
        //g_nTick = g_dTicksPerBeat - nRemainingFrames / getFramesPerTick(g_dTempo);
        
        if(bSync && g_nPlayingSequences == 0)
        {
            //!@todo bSync might have been reset by second clock within period - this should go within g_dFramesToNextClock loop
            //!@todo We stop at end of bar to encourage previous block of code to run but we may prefer to stop more promptly
            DPRINTF("Stopping transport because no sequences playing clock: %u beat: %u tick: %u\n", g_nClock, g_nBeat, g_nTick);
            transportStop("zynseq");
        }
    }

    // Process events scheduled to be sent to MIDI output
    if(g_mSchedule.size())
    {
        auto it = g_mSchedule.begin();
        jack_nframes_t nTime, nNextTime = 0;
        while(it != g_mSchedule.end())
        {
            if(it->first >= nNow + nFrames)
                break; // Event scheduled beyond this buffer
            if(it->first < nNow)
            {
                nTime = nNextTime; // This event is in the past so send as soon as possible
                // If lots of events are added in past then they may be sent out of order because frame boundary may be hit and existing events will be left in their previous position, e.g. at time 57 then up to 56 events could be inserted before this. Low risk and only for immediate events so unlikely to have significant impact.
                DPRINTF("Sending event from past (Scheduled:%u Now:%u Diff:%d samples)\n", it->first, nNow, nNow - it->first);
            }
            else
                nTime = it->first - nNow; // Schedule event at scheduled time sequence
            if(nTime < nNextTime)
                nTime = nNextTime; // Ensure we send events in order - this may bump events slightly later than scheduled (by individual frames (samples) so not much)
            if(nTime >= nFrames)
            {
                g_bMutex = false;
                return 0; // Must have bumped beyond end of this frame time so must wait until next frame - earlier events were processed and pointer nulled so will not trigger in next period
            }
            nNextTime = nTime + 1;
            // Get a pointer to the next 3 available bytes in the output buffer
            //!@todo Should we use correct buffer size based on MIDI message size, e.g. 1 byte for realtime messages?
            pBuffer = jack_midi_event_reserve(pOutputBuffer, nTime, 3);
            if(pBuffer == NULL)
                break; // Exceeded buffer size (or other issue)
            if(it->second)
            {
                pBuffer[0] = it->second->command;
                pBuffer[1] = it->second->value1;
                pBuffer[2] = it->second->value2;
                delete it->second;
                it->second = NULL;
            }
            ++it;
            DPRINTF("Sending MIDI event %d,%d,%d at %u\n", pBuffer[0],pBuffer[1],pBuffer[2], nNow + nTime);
        }
        g_mSchedule.erase(g_mSchedule.begin(), it);
    }
    g_bMutex = false;
    return 0;
}

int onJackSampleRateChange(jack_nframes_t nFrames, void *pArgs)
{
    DPRINTF("zynseq: Jack sample rate: %u\n", nFrames);
    g_nSampleRate = nFrames;
    g_dFramesPerClock = getFramesPerClock(g_dTempo);
    return 0;
}

int onJackXrun(void *pArgs)
{
    DPRINTF("zynseq detected XRUN %u\n", ++g_nXruns);
    //g_bTimebaseChanged = true; // Discontinuity so need to recalculate timebase parameters
    return 0;
}

void end()
{
    DPRINTF("zynseq exit\n");
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    for(auto it : g_mSchedule)
    {
        delete it.second;
    }
}

// ** Library management functions **

bool init(bool bTimebaseMaster)
{
    // Register with Jack server
    char *sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;
    
    if(g_pJackClient)
        return false; // Already initialised

    if((g_pJackClient = jack_client_open("zynthstep", nOptions, &nStatus, sServerName)) == 0)
    {
        fprintf(stderr, "libzynseq failed to start jack client: %d\n", nStatus);
        return false;
    }

    // Create input port
    if(!(g_pInputPort = jack_port_register(g_pJackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0)))
    {
        fprintf(stderr, "libzynseq cannot register input port\n");
        return false;
    }

    // Create output port
    if(!(g_pOutputPort = jack_port_register(g_pJackClient, "output", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0)))
    {
        fprintf(stderr, "libzynseq cannot register output port\n");
        return false;
    }
    
    g_nSampleRate = jack_get_sample_rate(g_pJackClient);
    g_dFramesPerClock = getFramesPerClock(g_dTempo);

    // Register JACK callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    jack_set_sample_rate_callback(g_pJackClient, onJackSampleRateChange, 0);
    jack_set_xrun_callback(g_pJackClient, onJackXrun, 0); //!@todo Remove xrun handler (just for debug)

    if(jack_activate(g_pJackClient)) {
        fprintf(stderr, "libzynseq cannot activate client\n");
        return false;
    }

    if(bTimebaseMaster)
        if(transportRequestTimebase())
            DPRINTF("Registered as timebase master\n");
        else
            DPRINTF("Failed to register as timebase master\n");

    // Register the cleanup function to be called when program exits
    atexit(end);
        
    transportStop("zynseq");
    transportLocate(0);
    return true; //!@todo If library loaded and initialised by Python then methods called too early (soon) it segfaults
}

bool isModified()
{
    return g_bDirty;
}

int fileWrite8(uint8_t value, FILE *pFile)
{
    int nResult = fwrite(&value, 1, 1, pFile);
    return 1;
}

int fileWrite32(uint32_t value, FILE *pFile)
{
    for(int i = 3; i >=0; --i)
        fileWrite8((value >> i * 8), pFile);
    return 4;
}

int fileWrite16(uint16_t value, FILE *pFile)
{
    for(int i = 1; i >=0; --i)
        fileWrite8((value >> i * 8), pFile);
    return 2;
}

uint8_t fileRead8(FILE* pFile)
{
    uint8_t nResult = 0;
    fread(&nResult, 1, 1, pFile);
    return nResult;
}

uint16_t fileRead16(FILE* pFile)
{
    uint16_t nResult = 0;
    for(int i = 1; i >=0; --i)
    {
        uint8_t nValue;
        fread(&nValue, 1, 1, pFile);
        nResult |= nValue << (i * 8);
    }
    return nResult;
}

uint32_t fileRead32(FILE* pFile)
{
    uint32_t nResult = 0;
    for(int i = 3; i >=0; --i)
    {
        uint8_t nValue;
        fread(&nValue, 1, 1, pFile);
        nResult |= nValue << (i * 8);
    }
    return nResult;
}

bool checkBlock(FILE* pFile, uint32_t nActualSize,  uint32_t nExpectedSize)
{
    if(nActualSize < nExpectedSize)
    {
        for(size_t i = 0; i < nActualSize; ++i)
            fileRead8(pFile);
        return true;
    }
    return false;
}

bool load(const char* filename)
{
    g_pTrack = NULL;
    g_seqMan.init();
    uint32_t nVersion = 0;
    FILE *pFile;
    pFile = fopen(filename, "r");
    if(pFile == NULL)
        return false;
    char sHeader[4];
    // Iterate each block within IFF file
    while(fread(sHeader, 4, 1, pFile) == 1)
    {
        uint32_t nBlockSize = fileRead32(pFile);
        if(memcmp(sHeader, "vers", 4) == 0)
        {
            if(nBlockSize != 16)
            {
                fclose(pFile);
                //printf("Error reading vers block from sequence file\n");
                return false;
            }
            nVersion = fileRead32(pFile);
            if(nVersion < 4 || nVersion > FILE_VERSION)
            {
                fclose(pFile);
                DPRINTF("Unsupported sequence file version %d. Not loading file.\n", nVersion);
                return false;
            }
            g_dTempo = fileRead16(pFile); //!@todo save and load tempo as fraction of BPM
            g_nBeatsPerBar = fileRead16(pFile);
            g_seqMan.setTriggerChannel(fileRead8(pFile));
            g_nTriggerStatusByte = MIDI_NOTE_ON | g_seqMan.getTriggerChannel();
            fileRead8(pFile); //!@todo Set JACK input
            fileRead8(pFile); //!@todo Set JACK output
            fileRead8(pFile); // padding
            g_nVerticalZoom = fileRead16(pFile);
            g_nHorizontalZoom = fileRead16(pFile);
            //printf("Version:%u Tempo:%0.2lf Beats per bar:%u Zoom V:%u H:%u\n", nVersion, g_dTempo, g_nBeatsPerBar, g_nVerticalZoom, g_nHorizontalZoom);
        }
        if(memcmp(sHeader, "patn", 4) == 0)
        {
            if(nVersion == 4)
            {
            if(checkBlock(pFile, nBlockSize, 12))
                continue;
            }
            else
            {
                if(checkBlock(pFile, nBlockSize, 14))
                    continue;
            }
            uint32_t nPattern = fileRead32(pFile);
            Pattern* pPattern = g_seqMan.getPattern(nPattern);
            pPattern->setBeatsInPattern(fileRead32(pFile));
            pPattern->setStepsPerBeat(fileRead16(pFile));
            pPattern->setScale(fileRead8(pFile));
            pPattern->setTonic(fileRead8(pFile));
            if(nVersion >=5)
            {
                pPattern->setRefNote(fileRead8(pFile));
                fileRead8(pFile);
                nBlockSize -= 2;
            }
            nBlockSize -= 12;
            //printf("Pattern:%u Beats:%u StepsPerBeat:%u Scale:%u Tonic:%u\n", nPattern, pPattern->getBeatsInPattern(), pPattern->getStepsPerBeat(), pPattern->getScale(), pPattern->getTonic());
            while(nBlockSize)
            {
                if(checkBlock(pFile, nBlockSize, 14))
                    break;
                uint32_t nStep = fileRead32(pFile);
                uint32_t nDuration = fileRead32(pFile);
                uint8_t nCommand = fileRead8(pFile);
                uint8_t nValue1start = fileRead8(pFile);
                uint8_t nValue2start = fileRead8(pFile);
                uint8_t nValue1end = fileRead8(pFile);
                uint8_t nValue2end = fileRead8(pFile);
                fileRead8(pFile); // Padding
                StepEvent* pEvent = pPattern->addEvent(nStep, nCommand, nValue1start, nValue2start, nDuration);
                pEvent->setValue1end(nValue1end);
                pEvent->setValue2end(nValue2end);
                nBlockSize -= 14;
                //printf(" Step:%u Duration:%u Command:%02X, Value1:%u..%u, Value2:%u..%u\n", nTime, nDuration, nCommand, nValue1start, nValue2end, nValue2start, nValue2end);
            }
        }
        else if(memcmp(sHeader, "bank", 4) == 0)
        {
            // Load banks
            if(checkBlock(pFile, nBlockSize, 6))
                continue;
            uint8_t nBank = fileRead8(pFile);
            fileRead8(pFile); // Padding
            uint32_t nSequences = fileRead32(pFile);
            nBlockSize -= 6;
            //printf("Bank %u with %u sequences\n", nBank, nSequences);
            for(uint32_t nSequence = 0; nSequence < nSequences; ++nSequence)
            {
                if(checkBlock(pFile, nBlockSize, 8))
                    continue;
                if(nVersion >= 6 && checkBlock(pFile, nBlockSize, 24))
                    continue;
                Sequence* pSequence = g_seqMan.getSequence(nBank, nSequence);
                pSequence->setPlayMode(fileRead8(pFile));
                uint8_t nGroup = fileRead8(pFile);
                pSequence->setGroup(nGroup);
                g_seqMan.setTriggerNote(nBank, nSequence, fileRead8(pFile));
                fileRead8(pFile); //Padding
                char sName[17];
                memset(sName, '\0', 17);
                if(nVersion >= 6)
                {
                    if(checkBlock(pFile, nBlockSize, 24))
                        continue;
                    for(size_t nIndex = 0; nIndex < 16; ++nIndex)
                        sName[nIndex] = fileRead8(pFile);
                    sName[16] = '\0';
                    nBlockSize -= 16;
                }
                else
                {
                    sprintf(sName, "%d", nSequence + 1);
                }
                pSequence->setName(std::string(sName));
                uint32_t nTracks = fileRead32(pFile);
                nBlockSize -= 8;
                //printf("  Mode:%u Group:%u Tracks:%u\n", pSequence->getPlayMode(), pSequence->getGroup(), nTracks);
                for(uint32_t nTrack = 0; nTrack < nTracks; ++nTrack)
                {
                    if(checkBlock(pFile, nBlockSize, 6))
                        break;
                    if(pSequence->getTracks() <= nTrack)
                        pSequence->addTrack(nTrack);
                    Track* pTrack = pSequence->getTrack(nTrack);
                    pTrack->setChannel(fileRead8(pFile));
                    pTrack->setOutput(fileRead8(pFile));
                    pTrack->setMap(fileRead8(pFile));
                    fileRead8(pFile); // Padding
                    uint16_t nPatterns = fileRead16(pFile);
                    nBlockSize -= 6;
                    //printf("    Track:%u Channel:%u Output:%u Map:%u\n", nTrack, pTrack->getChannel(), pTrack->getOutput(), pTrack->getMap());
                    for(uint16_t nPattern = 0; nPattern < nPatterns; ++nPattern)
                    {
                        if(checkBlock(pFile, nBlockSize, 8))
                            break;
                        uint32_t nTime = fileRead32(pFile);
                        uint32_t nPatternId = fileRead32(pFile);
                        g_seqMan.addPattern(nBank, nSequence, nTrack, nTime, nPatternId, true);
                        nBlockSize -= 8;
                        //printf("      Pattern:%u at time:%u\n", nPatternId, nTime);
                    }
                }
                if(checkBlock(pFile, nBlockSize, 4))
                    break;
                uint32_t nTimebaseEvents = fileRead32(pFile);
                nBlockSize -= 4;
                for(uint32_t nEvent = 0; nEvent < nTimebaseEvents; ++nEvent)
                {
                    if(checkBlock(pFile, nBlockSize, 8))
                        break;
                    pSequence->getTimebase()->addTimebaseEvent(fileRead16(pFile), fileRead16(pFile), fileRead16(pFile), fileRead16(pFile));
                    nBlockSize -= 8;
                    //printf("    Timebase event:%u at time %u\n", pSequence->)
                }
                pSequence->updateLength();
            }
        }
    }
    fclose(pFile);
    //printf("Ver: %d Loaded %lu patterns, %lu sequences, %lu banks from file %s\n", nVersion, m_mPatterns.size(), m_mSequences.size(), m_mBanks.size(), filename);
    g_bDirty = false;
    Sequence* pSequence = g_seqMan.getSequence(0, 0);
    g_pTrack = pSequence->getTrack(0);
    return true;
}

void save(const char* filename)
{
    //!@todo Need to save / load ticks per beat (unless we always use 1920)
    FILE *pFile;
    int nPos = 0;
    pFile = fopen(filename, "w");
    if(pFile == NULL)
    {
        fprintf(stderr, "ERROR: SequenceManager failed to open file %s\n", filename);
        return;
    }
    uint32_t nBlockSize;
    fwrite("vers", 4, 1, pFile); // IFF block name
    nPos += 4;
    nPos += fileWrite32(16, pFile); // IFF block size
    nPos += fileWrite32(FILE_VERSION, pFile); // IFF block content
    nPos += fileWrite16(uint16_t(g_dTempo), pFile); //!@todo Write current tempo
    nPos += fileWrite16(g_nBeatsPerBar, pFile); //!@todo Write current beats per bar
    nPos += fileWrite8(g_seqMan.getTriggerChannel(), pFile);
    nPos += fileWrite8('\0', pFile); // JACK input not yet implemented
    nPos += fileWrite8('\0', pFile); // JACK output not yet implemented
    nPos += fileWrite8('\0', pFile);
    nPos += fileWrite16(g_nVerticalZoom, pFile);
    nPos += fileWrite16(g_nHorizontalZoom, pFile);

    // Iterate through patterns
    uint32_t nPattern = 0;
    do
    {
        Pattern* pPattern = g_seqMan.getPattern(nPattern);
        // Only save patterns with content
        if(pPattern->getEventAt(0))
        {
            fwrite("patnxxxx", 8, 1, pFile);
            nPos += 8;
            uint32_t nStartOfBlock = nPos;
            nPos += fileWrite32(nPattern, pFile);
            nPos += fileWrite32(pPattern->getBeatsInPattern(), pFile);
            nPos += fileWrite16(pPattern->getStepsPerBeat(), pFile);
            nPos += fileWrite8(pPattern->getScale(), pFile);
            nPos += fileWrite8(pPattern->getTonic(), pFile);
            nPos += fileWrite8(pPattern->getRefNote(), pFile);
            nPos += fileWrite8('\0', pFile);
            uint32_t nEvent = 0;
            while(StepEvent* pEvent = pPattern->getEventAt(nEvent++))
            {
                nPos += fileWrite32(pEvent->getPosition(), pFile);
                nPos += fileWrite32(pEvent->getDuration(), pFile);
                nPos += fileWrite8(pEvent->getCommand(), pFile);
                nPos += fileWrite8(pEvent->getValue1start(), pFile);
                nPos += fileWrite8(pEvent->getValue2start(), pFile);
                nPos += fileWrite8(pEvent->getValue1end(), pFile);
                nPos += fileWrite8(pEvent->getValue2end(), pFile);
                nPos += fileWrite8('\0', pFile); // Pad to even block (could do at end but simplest here)
            }
            nBlockSize = nPos - nStartOfBlock;
            fseek(pFile, nStartOfBlock - 4, SEEK_SET);
            fileWrite32(nBlockSize, pFile);
            fseek(pFile, 0, SEEK_END);
        }
        nPattern = g_seqMan.getNextPattern(nPattern);
    } while(nPattern != -1);
    
    // Iterate through banks
    for(uint32_t nBank = 1; nBank < g_seqMan.getBanks(); ++nBank)
    {
        uint32_t nSequences = g_seqMan.getSequencesInBank(nBank);
        if(nSequences == 0)
            continue;
        fwrite("bankxxxx", 8, 1, pFile);
        nPos += 8;
        uint32_t nStartOfBlock = nPos;
        nPos += fileWrite8(nBank, pFile);
        nPos += fileWrite8(0, pFile);
        nPos += fileWrite32(nSequences, pFile);
        for(uint32_t nSequence = 0; nSequence < nSequences; ++nSequence)
        {
            Sequence* pSequence = g_seqMan.getSequence(nBank, nSequence);
            nPos += fileWrite8(pSequence->getPlayMode(), pFile);
            nPos += fileWrite8(pSequence->getGroup(), pFile);
            nPos += fileWrite8(g_seqMan.getTriggerNote(nBank, nSequence), pFile);
            nPos += fileWrite8('\0', pFile);
            std::string sName = pSequence->getName();
            for(size_t nIndex = 0; nIndex < sName.size(); ++nIndex)
                nPos += fileWrite8(sName[nIndex], pFile);
            for(size_t nIndex = sName.size(); nIndex < 16; ++nIndex)
                nPos += fileWrite8('\0', pFile);
            nPos += fileWrite32(pSequence->getTracks(), pFile);
            for(size_t nTrack = 0; nTrack < pSequence->getTracks(); ++nTrack)
            {
                Track* pTrack = pSequence->getTrack(nTrack);
                if(pTrack)
                {
                    nPos += fileWrite8(pTrack->getChannel(), pFile);
                    nPos += fileWrite8(pTrack->getOutput(), pFile);
                    nPos += fileWrite8(pTrack->getMap(), pFile);
                    nPos += fileWrite8('\0', pFile);
                    nPos += fileWrite16(pTrack->getPatterns(), pFile);
                    for(uint16_t nPattern = 0; nPattern < pTrack->getPatterns(); ++nPattern)
                    {
                        nPos += fileWrite32(pTrack->getPatternPositionByIndex(nPattern), pFile);
                        Pattern* pPattern = pTrack->getPatternByIndex(nPattern);
                        uint32_t nPatternId = g_seqMan.getPatternIndex(pPattern);
                        nPos += fileWrite32(nPatternId, pFile);
                    }
                }
                else
                {
                    // Shouldn't need this but add empty tracks
                    nPos += fileWrite32(0, pFile);
                    nPos += fileWrite16(0, pFile);
                }
                
            }
            Timebase* pTimebase = pSequence->getTimebase();
            if(pTimebase)
            {
                nPos += fileWrite32(pTimebase->getEventQuant(), pFile);
                for(uint32_t nIndex = 0; nIndex < pTimebase->getEventQuant(); ++nIndex)
                {
                    TimebaseEvent* pEvent = pTimebase->getEvent(nIndex);
                    nPos += fileWrite16(pEvent->bar, pFile);
                    nPos += fileWrite16(pEvent->clock, pFile);
                    nPos += fileWrite16(pEvent->type, pFile);
                    nPos += fileWrite16(pEvent->value, pFile);
                }
            }
            else
            {
                nPos += fileWrite32(0, pFile);
            }            
        }
        nBlockSize = nPos - nStartOfBlock;
        fseek(pFile, nStartOfBlock - 4, SEEK_SET);
        fileWrite32(nBlockSize, pFile);
        fseek(pFile, 0, SEEK_END);
    }

    fclose(pFile);
    g_bDirty = false;
}

uint16_t getVerticalZoom()
{
    return g_nVerticalZoom;
}

void setVerticalZoom(uint16_t zoom)
{
    g_nVerticalZoom = zoom;
}

uint16_t getHorizontalZoom()
{
    return g_nHorizontalZoom;
}

void setHorizontalZoom(uint16_t zoom)
{
    g_nHorizontalZoom = zoom;
}

// ** Direct MIDI interface **

// Schedule a MIDI message to be sent in next JACK process cycle
void sendMidiMsg(MIDI_MESSAGE* pMsg)
{
    // Find first available time slot
    uint32_t time = jack_frames_since_cycle_start(g_pJackClient);
    while(g_bMutex)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    g_bMutex = true;
    while(g_mSchedule.find(time) != g_mSchedule.end())
        ++time;
    g_mSchedule[time] = pMsg;
    g_bMutex = false;
}

// Schedule a note off event after 'duration' ms
void noteOffTimer(uint8_t note, uint8_t channel, uint32_t duration)
{
    std::this_thread::sleep_for(std::chrono::milliseconds(duration));
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_NOTE_ON | (channel & 0x0F);
    pMsg->value1 = note;
    pMsg->value2 = 0;
    sendMidiMsg(pMsg);
}

void playNote(uint8_t note, uint8_t velocity, uint8_t channel, uint32_t duration)
{
    if(note>127 || velocity > 127 || channel > 15 || duration >60000)
        return;
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_NOTE_ON | channel;
    pMsg->value1 = note;
    pMsg->value2 = velocity;
    sendMidiMsg(pMsg);
    if(duration)
    {
        std::thread noteOffThread(noteOffTimer, note, channel, duration);
        noteOffThread.detach();
    }
}

//!@todo Do we still need functions to send MIDI transport control (start, stop, continuew, songpos, song select, clock)?

void sendMidiStart()
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_START;
    sendMidiMsg(pMsg);
    DPRINTF("Sending MIDI Start... does it get recieved back???\n");
}

void sendMidiStop()
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_STOP;
    sendMidiMsg(pMsg);
}

void sendMidiContinue()
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_CONTINUE;
    sendMidiMsg(pMsg);
}

void sendMidiSongPos(uint16_t pos)
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_POSITION;
    pMsg->value1 = pos & 0x7F;
    pMsg->value2 = (pos >> 7) & 0x7F;
    sendMidiMsg(pMsg);
}

void sendMidiSong(uint32_t pos)
{
    if(pos > 127)
        return;
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_SONG;
    pMsg->value1 = pos & 0x7F;
    sendMidiMsg(pMsg);
}

void sendMidiClock()
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_CLOCK;
    sendMidiMsg(pMsg);
}

void sendMidiCommand(uint8_t status, uint8_t value1, uint8_t value2)
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = status;
    pMsg->value1 = value1;
    pMsg->value2 = value2;
    sendMidiMsg(pMsg);
}

uint8_t getTriggerChannel()
{
    return g_seqMan.getTriggerChannel();
}

void setTriggerChannel(uint8_t channel)
{
    if(channel > 15)
        channel = 0xFF;
    g_seqMan.setTriggerChannel(channel);
    g_nTriggerStatusByte = MIDI_NOTE_ON | g_seqMan.getTriggerChannel();
    g_bDirty = true;
}

uint8_t getTriggerNote(uint8_t bank, uint8_t sequence)
{
    return g_seqMan.getTriggerNote(bank, sequence);
}

void setTriggerNote(uint8_t bank, uint8_t sequence, uint8_t note)
{
    g_seqMan.setTriggerNote(bank, sequence, note);
    g_bDirty = true;
}

// ** Pattern management functions **

uint32_t createPattern()
{
    return g_seqMan.createPattern();
}

void cleanPatterns()
{
    g_seqMan.cleanPatterns();
}

void toggleMute(uint8_t bank, uint8_t sequence, uint32_t track)
{
	Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
	if(pTrack)
		pTrack->mute(!pTrack->isMuted());
}

bool isMuted(uint8_t bank, uint8_t sequence, uint32_t track)
{
	Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
	if(pTrack)
		return pTrack->isMuted();
	return false;
}	

void enableMidiInput(bool enable)
{
    g_bInputEnabled = enable;
}

void selectPattern(uint32_t pattern)
{
    g_pPattern = g_seqMan.getPattern(pattern);
    if(g_pPattern)
        g_nPattern = pattern;
    g_bPatternModified = true;
}

uint32_t getPatternIndex()
{
    return g_nPattern;
}

uint32_t getSteps()
{
    if(g_pPattern)
        return g_pPattern->getSteps();
    return 0;
}

uint32_t getPatternLength(uint32_t pattern)
{
    Pattern* pPattern = g_seqMan.getPattern(pattern);
    if(pPattern)
        return pPattern->getLength();
    return 0;
}

uint32_t getBeatsInPattern()
{
    if(g_pPattern)
        return g_pPattern->getBeatsInPattern();
    return 0;
}

void setBeatsInPattern(uint32_t beats)
{
    if(!g_pPattern)
        return;
    g_pPattern->setBeatsInPattern(beats);
    g_seqMan.updateAllSequenceLengths();
    g_bPatternModified = true;
    g_bDirty = true;
}

uint32_t getClocksPerStep()
{
    if(g_pPattern)
        return g_pPattern->getClocksPerStep();
    return 6;
}

uint32_t getStepsPerBeat()
{
    if(g_pPattern)
        return g_pPattern->getStepsPerBeat();
    return 4;
}

void setStepsPerBeat(uint32_t steps)
{
    if(!g_pPattern)
        return;
    g_pPattern->setStepsPerBeat(steps);
    g_bPatternModified = true;
    g_bDirty = true;
}

bool addNote(uint32_t step, uint8_t note, uint8_t velocity, uint32_t duration)
{
    if(!g_pPattern)
        return false;
    g_bPatternModified = true;
    g_bDirty = true;
    return g_pPattern->addNote(step, note, velocity, duration);
}

void removeNote(uint32_t step, uint8_t note)
{
    if(!g_pPattern)
        return;
    g_bPatternModified = true;
    g_pPattern->removeNote(step, note);
    g_bDirty = true;
}

uint8_t getNoteVelocity(uint32_t step, uint8_t note)
{
    if(g_pPattern)
        return g_pPattern->getNoteVelocity(step, note);
    return 0;
}

void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity)
{
    if(!g_pPattern)
        return;
    g_bPatternModified = true;
    g_pPattern->setNoteVelocity(step, note, velocity);
    g_bDirty = true;
}

uint32_t getNoteDuration(uint32_t step, uint8_t note)
{
    if(g_pPattern)
        return g_pPattern->getNoteDuration(step, note);
    return 0;
}

void transpose(int8_t value)
{
    if(!g_pPattern)
        return;
    g_bPatternModified = true;
    g_pPattern->transpose(value);
    g_bDirty = true;
}

void clear()
{
    if(!g_pPattern)
        return;
    g_bPatternModified = true;
    g_pPattern->clear();
    g_bDirty = true;
}

void copyPattern(uint32_t source, uint32_t destination)
{
    g_seqMan.copyPattern(source, destination);
    g_bDirty = true;
}

void setInputChannel(uint8_t channel)
{
    if(channel > 15)
        g_nInputChannel = 0xFF;
    g_nInputChannel = channel;
    g_bDirty = true;
}

uint8_t getInputChannel()
{
    return g_nInputChannel;
}

void setInputRest(uint8_t note)
{
    if(note > 127)
        g_nInputRest = 0xFF;
    g_nInputRest = note;
    g_bDirty = true;
}

uint8_t getInputRest()
{
    return g_nInputRest;
}

void setScale(uint32_t scale)
{
    if(!g_pPattern)
        return;
    if(scale != g_pPattern->getScale())
        g_bDirty = true;
    g_pPattern->setScale(scale);
}

uint32_t getScale()
{
    if(g_pPattern)
        return g_pPattern->getScale();
    return 0;
}

void setTonic(uint8_t tonic)
{
    if(!g_pPattern)
        return;
    g_pPattern->setTonic(tonic);
    g_bDirty = true;
}

uint8_t getTonic()
{
    if(g_pPattern)
        return g_pPattern->getTonic();
    return 0;
}

bool isPatternModified()
{
    if(g_bPatternModified)
    {
        g_bPatternModified = false;
        return true;
    }
    return false;
}

uint8_t getRefNote()
{
    if(g_pPattern)
        return g_pPattern->getRefNote();
    return 60;
}

void setRefNote(uint8_t note)
{
    if(g_pPattern)
        g_pPattern->setRefNote(note);
}

uint32_t getLastStep()
{
    if(!g_pPattern)
        return -1;
    return g_pPattern->getLastStep();
}

// ** Sequence management functions **

uint32_t getPatternPlayhead(uint8_t bank, uint8_t sequence, uint32_t track)
{
    Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
    if(!pTrack)
        return 0;
    return pTrack->getPatternPlayhead();
}

bool addPattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force)
{
    bool bUpdated = g_seqMan.addPattern(bank, sequence, track, position, pattern, force);
    if(bank + sequence)
        g_bDirty |= bUpdated;
    return bUpdated;
}

void removePattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position)
{
    g_seqMan.removePattern(bank, sequence, track, position);
    g_bDirty = true;
}

uint32_t getPattern(uint8_t bank, uint8_t sequence, uint32_t track,  uint32_t position)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    Track* pTrack = pSequence->getTrack(track);
    if(!pTrack)
        return -1;
    Pattern* pPattern = pTrack->getPattern(position);
    return g_seqMan.getPatternIndex(pPattern);
}

uint32_t getPatternAt(uint8_t bank, uint8_t sequence, uint32_t track,  uint32_t position)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    Track* pTrack = pSequence->getTrack(track);
    if(!pTrack)
        return -1;
    Pattern* pPattern = pTrack->getPatternAt(position);
    if(!pPattern)
        return -1;
    return g_seqMan.getPatternIndex(pPattern);
}

uint8_t getPlayMode(uint8_t bank, uint8_t sequence)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    return pSequence->getPlayMode();
}

void setPlayMode(uint8_t bank, uint8_t sequence, uint8_t mode)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    pSequence->setPlayMode(mode);
    if(bank + sequence)
        g_bDirty = true;
}

uint8_t getPlayState(uint8_t bank, uint8_t sequence)
{
    return g_seqMan.getSequence(bank, sequence)->getPlayState();
}

void setPlayState(uint8_t bank, uint8_t sequence, uint8_t state)
{
    if(transportGetPlayStatus() != JackTransportRolling)
    {
        if(state == STARTING)
        {
            setTransportToStartOfBar();
            transportStart("zynseq");
        }
        else if(state == STOPPING)
            state = STOPPED;
    }
    g_seqMan.setSequencePlayState(bank, sequence, state);
}

void togglePlayState(uint8_t bank, uint8_t sequence)
{
    uint8_t nState = g_seqMan.getSequence(bank, sequence)->getPlayState();
    switch(nState)
    {
        case STOPPED:
            nState = STARTING;
            break;
        case STARTING:
        case RESTARTING:
            nState = STOPPED;
            break;
        case PLAYING:
            nState = STOPPING;
            break;
        case STOPPING:
            nState = PLAYING;
            break;
    }
    setPlayState(bank, sequence, nState);
}

void stop()
{
    g_seqMan.stop();
}

uint32_t getPlayPosition(uint8_t bank, uint8_t sequence)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    return pSequence->getPlayPosition();
}

void setPlayPosition(uint8_t bank, uint8_t sequence, uint32_t clock)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    pSequence->setPlayPosition(clock);
}

uint32_t getSequenceLength(uint8_t bank, uint8_t sequence)
{
    return g_seqMan.getSequence(bank, sequence)->getLength();
}

void clearSequence(uint8_t bank, uint8_t sequence)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    pSequence->clear();
    g_bDirty = true;
}

void setSequencesInBank(uint8_t bank, uint8_t sequences)
{
    while(g_bMutex)
            std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    g_seqMan.setSequencesInBank(bank, sequences);
    g_bMutex = false;
}

size_t getSequencesInBank(uint32_t bank)
{
    return g_seqMan.getSequencesInBank(bank);
}

void clearBank(uint32_t bank)
{
    g_seqMan.clearBank(bank);
}


// ** Sequence management functions **

uint8_t getGroup(uint8_t bank, uint8_t sequence)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    return pSequence->getGroup();
}

void setGroup(uint8_t bank, uint8_t sequence, uint8_t group)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    return pSequence->setGroup(group);
    g_bDirty = true;
}

bool hasSequenceChanged(uint8_t bank, uint8_t sequence)
{
    return g_seqMan.getSequence(bank, sequence)->hasChanged();
}

uint32_t addTrackToSequence(uint8_t bank, uint8_t sequence, uint32_t track)
{
    g_bDirty = true;
    return g_seqMan.getSequence(bank, sequence)->addTrack(track);
}

void removeTrackFromSequence(uint8_t bank, uint8_t sequence, uint32_t track)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    if(!pSequence->removeTrack(track))
        return;
    pSequence->updateLength();
    g_bDirty = true;
}

void addTempoEvent(uint8_t bank, uint8_t sequence, uint32_t tempo, uint16_t bar, uint16_t tick)
{
	//!@todo Concert tempo events to use double for tempo value
    g_seqMan.getSequence(bank, sequence)->addTempo(tempo, bar, tick);
    g_bDirty = true;
}

uint32_t getTempoAt(uint8_t bank, uint8_t sequence, uint16_t bar, uint16_t tick)
{
    return g_seqMan.getSequence(bank, sequence)->getTempo(bar, tick);
}

void addTimeSigEvent(uint8_t bank, uint8_t sequence, uint8_t beats, uint8_t type, uint16_t bar)
{
    if(bar < 1)
        bar = 1;
    g_seqMan.getSequence(bank, sequence)->addTimeSig((beats << 8) | type, bar);
    g_bDirty = true;
}

uint16_t getTimeSigAt(uint8_t bank, uint8_t sequence, uint16_t bar)
{
    return g_seqMan.getSequence(bank, sequence)->getTimeSig(bar);
}

uint8_t getBeatsPerBar(uint8_t bank, uint8_t sequence, uint16_t bar)
{
    return getTimeSigAt(bank, sequence, bar) >> 8;
}

uint32_t getTracksInSequence(uint8_t bank, uint8_t sequence)
{
    return g_seqMan.getSequence(bank, sequence)->getTracks();
}

void enableMidiLearn(uint8_t bank, uint8_t sequence)
{
    g_nTriggerLearning = (bank << 8) | sequence;
}

uint8_t getMidiLearnBank()
{
    return g_nTriggerLearning >> 8;
}

uint8_t getMidiLearnSequence()
{
    return g_nTriggerLearning & 0xFF;
}

void setSequenceName(uint8_t bank, uint8_t sequence, const char* name)
{
    g_seqMan.getSequence(bank, sequence)->setName(std::string(name));
}

const char* getSequenceName(uint8_t bank, uint8_t sequence)
{
    strcpy(g_sName, g_seqMan.getSequence(bank, sequence)->getName().c_str());
    return g_sName;
}

bool moveSequence(uint8_t bank, uint8_t sequence, uint8_t position)
{
    return g_seqMan.moveSequence(bank, sequence, position);
}

void insertSequence(uint8_t bank, uint8_t sequence)
{
    g_seqMan.insertSequence(bank, sequence);
}

void removeSequence(uint8_t bank, uint8_t sequence)
{
    g_seqMan.removeSequence(bank, sequence);
}

// ** Track management **

size_t getPatternsInTrack(uint8_t bank, uint8_t sequence, uint32_t track)
{
    Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
    if(!pTrack)
        return 0;
    return pTrack->getPatterns();
}

void setChannel(uint8_t bank, uint8_t sequence, uint32_t track, uint8_t channel)
{
    Sequence* pSequence = g_seqMan.getSequence(bank, sequence);
    Track* pTrack = pSequence->getTrack(track);
    if(!pTrack)
        return;
    pTrack->setChannel(channel);
    if(bank + sequence)
        g_bDirty = true;
}

uint8_t getChannel(uint8_t bank, uint8_t sequence, uint32_t track)
{
    Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
    if(!pTrack)
        return 0xFF;
    return pTrack->getChannel(); 
}

void solo(uint8_t bank, uint8_t sequence, uint32_t track, bool solo)
{
    Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
    if(!pTrack)
        return;
    pTrack->solo();
}

bool isSolo(uint8_t bank, uint8_t sequence, uint32_t track)
{
    Track* pTrack = g_seqMan.getSequence(bank, sequence)->getTrack(track);
    if(!pTrack)
        return false;
    return pTrack->isSolo();
}

// ** Transport management **/ 

void setTransportToStartOfBar()
{
    jack_position_t position;
    jack_transport_query(g_pJackClient, &position);
    position.beat = 1;
    position.tick = 0;
//    position.valid = JackPositionBBT;
    jack_transport_reposition(g_pJackClient, &position);
//    g_pNextTimebaseEvent = g_pTimebase->getPreviousTimebaseEvent(position.bar, 1, TIMEBASE_TYPE_ANY); //!@todo Might miss event if 2 at start of bar
}

void transportLocate(uint32_t frame)
{
    jack_transport_locate(g_pJackClient, frame);
}

/*  Calculate the song position in frames from BBT
*/
jack_nframes_t transportGetLocation(uint32_t bar, uint32_t beat, uint32_t tick)
{
    // Convert one-based bars and beats to zero-based 
    if(bar > 0)
        --bar;
    if(beat > 0)
        --beat;    
    uint32_t nTicksToPrev = 0;
    uint32_t nTicksToEvent = 0;
    uint32_t nTicksPerBar = g_dTicksPerBeat * g_nBeatsPerBar;
//!@todo Handle changes in tempo and time signature
//    double dFramesPerTick = getFramesPerTick(DEFAULT_TEMPO);
    double dFramesPerTick = getFramesPerTick(g_dTempo);
    double dFrames = 0; // Frames to position
    /*
    if(g_pTimebase)
    {
        for(size_t nIndex = 0; nIndex < g_pTimebase->getEventQuant(); ++nIndex)
        {
            TimebaseEvent* pEvent = g_pTimebase->getEvent(nIndex);
            if(pEvent->bar > bar || pEvent->bar == bar && pEvent->clock > (g_dTicksPerBeat * beat + tick) / g_dTicksPerBeat / g_nPulsePerQuarterNote)
                break; // Ignore events later than new position
            nTicksToEvent = pEvent->bar * nTicksPerBar + pEvent->clock * g_dTicksPerBeat / g_nPulsePerQuarterNote;
            uint32_t nTicksInBlock = nTicksToEvent - nTicksToPrev;
            dFrames += dFramesPerTick * nTicksInBlock;
            nTicksToPrev = nTicksToEvent;
            if(pEvent->type == TIMEBASE_TYPE_TEMPO)
                dFramesPerTick = getFramesPerTick(pEvent->value);
            else if(pEvent->type == TIMEBASE_TYPE_TIMESIG)
                nTicksPerBar = g_dTicksPerBeat * (pEvent->value >> 8);
        }
    }
    */
    dFrames += dFramesPerTick * (bar * nTicksPerBar + beat * g_dTicksPerBeat + tick - nTicksToPrev);
    return dFrames;
}

bool transportRequestTimebase()
{
    if(jack_set_timebase_callback(g_pJackClient, 0, onJackTimebase, NULL))
        return false;
    return true;
}

void transportReleaseTimebase()
{
    jack_release_timebase(g_pJackClient);
}

void transportStart(const char* client)
{
    if(strcmp("zynseq", client))
    {
        // Not zynseq so flag other client(s) playing
        g_bClientPlaying = true;
        g_setTransportClient.emplace(client);
    }
    jack_position_t pos;
    if(jack_transport_query(g_pJackClient, &pos) == JackTransportStopped)
    {
        g_dFramesToNextClock = 0.0;
        jack_transport_start(g_pJackClient);
    }
}

void transportStop(const char* client)
{
    auto itClient = g_setTransportClient.find(std::string(client));
    if(itClient != g_setTransportClient.end())
        g_setTransportClient.erase(itClient);
    g_bClientPlaying = (g_setTransportClient.size() != 0);
    if(!g_bClientPlaying && g_nPlayingSequences == 0)
        jack_transport_stop(g_pJackClient);
}

void transportToggle(const char* client)
{
    if(transportGetPlayStatus() == JackTransportRolling)
        transportStop(client);
    else
        transportStart(client);
}

uint8_t transportGetPlayStatus()
{
    jack_position_t position; // Not used but required to query transport
    jack_transport_state_t nState;
    return jack_transport_query(g_pJackClient, &position);
}

void setTempo(double tempo)
{
    if(tempo > 0.0 && tempo < 500.0)
    {
        g_dTempo = tempo;
        g_dFramesPerClock = getFramesPerClock(tempo);
    }
}

double getTempo()
{
    return g_dTempo;
}

void setBeatsPerBar(uint32_t beats)
{
    if(beats > 0)
        g_nBeatsPerBar = beats;
}

uint32_t getBeatsPerBar()
{
    return g_nBeatsPerBar;
}

void transportSetSyncTimeout(uint32_t timeout)
{
    jack_set_sync_timeout(g_pJackClient, timeout);
}

