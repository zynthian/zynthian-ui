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
#include <chrono> //provides timespan for timer
#include "zynseq.h" //exposes library methods as c functions
#include "patternmanager.h" //provides management of patterns and sequences
#include "timebase.h" //provides timebase event map
#include <jack/jack.h> //provides JACK interface
#include <jack/midiport.h> //provides JACK MIDI interface

Pattern* g_pPattern = 0; // Currently selected pattern
jack_port_t * g_pInputPort; // Pointer to the JACK input port
jack_port_t * g_pOutputPort; // Pointer to the JACK output port
jack_client_t *g_pJackClient = NULL; // Pointer to the JACK client

bool g_bClockIdle = true; // False to indicate clock pulse
bool g_bClockRateChange = true; // True when a recalculation of clock rate required
bool g_bRunning = true; // False to stop clock thread, e.g. on exit
jack_nframes_t g_nSamplerate; // Quantity of samples per second
jack_nframes_t g_nBufferSize; // Quantity of samples in JACK buffer passed each process cycle
std::map<uint32_t,MIDI_MESSAGE*> g_mSchedule; // Schedule of MIDI events (queue for sending), indexed by scheduled play time (samples since JACK epoch)
bool g_bDebug = false; // True to output debug info
jack_nframes_t g_nClockEventTime; // Time of current clock pulse in frames (samples) since JACK epoch
uint32_t g_nSongPosition = 0; // Clocks since start of song
uint32_t g_nSongLength = 0; // Clocks cycles to end of song
bool g_bModified = false; // True if pattern has changed since last check

uint8_t g_nInputChannel = 1; // MIDI input channel (>15 to disable MIDI input)

bool g_bPlaying = false; // True if any sequences playing
uint8_t g_nSongStatus = STOPPED;
bool g_bSync = false; // True to indicate transport is at a sync pulse (start of bar)
bool g_bMutex = false; // Mutex lock for access to g_mSchedule

// Tranpsort variables
float g_fBeatsPerBar = 4.0;
float g_fBeatType = 4.0;
double g_dTicksPerBeat = 1920.0;
double g_dTempo = 120.0;
bool g_bTimebaseChanged = false;
Timebase* g_pTimebase = NULL;
jack_nframes_t g_nSampleRate = 44100;
uint32_t g_nMeasure = 1; // Current measure
uint32_t g_nBeat = 1; // Current beat within measure
uint32_t g_nTick = 0; // Current tick within beat


// ** Internal (non-public) functions  (not delcared in header so need to be in correct order in source file) **

// Enable / disable debug output
void debug(bool bEnable)
{
    printf("libseq setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
}

// Convert tempo to frames per tick
double getFramesPerTick(double dTempo)
{
    double dFramesPerTick = 60 * g_nSampleRate / (dTempo *  g_dTicksPerBeat);
    return dFramesPerTick;
}

// Update bars, beats, ticks for given position in frames
void updateBBT(jack_position_t* position)
{
    //!@todo There is a rounding error where each beat is calculated to the nearest 256 frames (possibly period size) then corrected every 7 or 8 beats (at 44100fps, 256 period, 120BPM)
    // This may be because this is only called once every period so need to consider partial progress through clock
    
    //!@todo Populate bbt_offset (experimental so not urgent but could be useful)
    double dFrames = 0;
    double dFramesPerTick = getFramesPerTick(g_dTempo); //!@todo Need to use default tempo from start of song but current tempo now!!!
    static double dDebugFramesPerTick = 0;
    uint32_t nMeasure = 0;
    uint32_t nBeat = 0;
    uint32_t nTick = 0;
    uint8_t nBeatsPerMeasure = DEFAULT_TIMESIG >> 8;
    uint8_t nBeatsType = DEFAULT_TIMESIG & 0x00FF;
    uint32_t nTicksPerMeasure = g_dTicksPerBeat * nBeatsPerMeasure;
    bool bDone = false;
    double dFramesInSection;
    uint32_t nTicksInSection;
    uint32_t nTicksFromStart = 0;

    // Iterate through events, calculating quantity of frames between each event
    if(g_pTimebase)
    {
        for(size_t nIndex = 0; nIndex < g_pTimebase->getEventQuant(); ++nIndex)
        {
            break; //!@todo REMOVE THIS DEBUG
            // Get next event
            TimebaseEvent* pEvent = g_pTimebase->getEvent(nIndex);
            // Calculate quantity of ticks between events and frames between events
            nTicksInSection = (pEvent->measure * nTicksPerMeasure + pEvent->tick - nTicksFromStart);
            dFramesInSection = nTicksInSection * dFramesPerTick;
            // Break if next event is beyond requested position
            if(dFrames + dFramesInSection > position->frame)
                break;
            // Update frame counter, measure and tick from which to count last section
            dFrames += dFramesInSection;
            nMeasure = pEvent->measure;
            nTick = pEvent->tick;
            nTicksFromStart += nTicksInSection;
            // Update tempo and time signature from event
            if(pEvent->type == TIMEBASE_TYPE_TEMPO)
                dFramesPerTick = getFramesPerTick(pEvent->value);
            else if(pEvent->type == TIMEBASE_TYPE_TIMESIG)
            {
                nBeatsPerMeasure = pEvent->value >> 8;
                nBeatsType = pEvent->value & 0x00FF;
                nTicksPerMeasure = g_dTicksPerBeat * nBeatsPerMeasure;
            }
        }
    }
    // Calculate BBT from last section
    dFramesInSection = position->frame - dFrames;
    nTicksInSection = dFramesInSection / dFramesPerTick;
    uint32_t nMeasuresInSection = nTicksInSection / nTicksPerMeasure;
    position->bar = nMeasure + nMeasuresInSection + 1;
    uint32_t nTicksInLastMeasure = nTicksInSection % nTicksPerMeasure;
    position->beat = nTicksInLastMeasure / g_dTicksPerBeat + 1;
    position->tick = nTicksInLastMeasure % position->beat;
    nTicksFromStart += nTicksInSection;
    position->bar_start_tick = nTicksFromStart - nTicksInLastMeasure;
    static uint32_t nDebugFrames = 0;
    static uint32_t nDebugBeat = 0;
    if(nDebugBeat != position->beat)
    {
        printf("Beat %u, %u frames since last beat\n", position->beat, position->frame - nDebugFrames);
        nDebugBeat = position->beat;
        nDebugFrames = position->frame;
    }
}

/* Handle timebase callback - Update timebase elements (BBT) from transport position
*  nState: Current jack transport state
*  nFrames: Quantity of frames in current period
*  pos: pointer to position structure for the next cycle; pos->frame will be its frame number. If new_pos is FALSE, this structure contains extended position information from the current cycle. If TRUE, it contains whatever was set by the requester. The timebase_callback's task is to update the extended information here.
*   newPos: TRUE (non-zero) for a newly requested pos, or for the first cycle after the timebase_callback is defined.
*   args: the argument supplied by jack_set_timebase_callback().
*/
void onJackTimebase(jack_transport_state_t nState, jack_nframes_t nframes,
          jack_position_t *pos, int newPos, void* args)
{
    static uint32_t nNextBar = 1;
    static uint32_t nNextClockTick = 0;
        
    if(newPos || g_bTimebaseChanged)
    {
        pos->frame = transportGetLocation(pos->bar, pos->beat, pos->tick);
        pos->valid = JackPositionBBT;
        nNextBar = pos->bar;
        g_bTimebaseChanged = false;
    }
    else
    {
        updateBBT(pos);
    }
    pos->beats_per_bar = g_fBeatsPerBar;
    pos->beat_type = g_fBeatType;
    pos->ticks_per_beat = g_dTicksPerBeat;
    pos->beats_per_minute = g_dTempo; //!@todo This should be set somewhere
    if(nState == JackTransportRolling)
    {
        if(pos->bar == nNextBar && pos->beat == 1)
            g_bSync = true; //!@todo Check that we always catch first beat

        //!@todo Remove nTestFrames debug
        static jack_nframes_t nTestFrames = 0;
        if(nNextClockTick < 24 * pos->tick / pos->ticks_per_beat)
        {
            //!@todo This is only called every period so pulse may occure part way into period 
            g_bClockIdle = false;
            printf("Clock pulse triggered by JackTimebase %u frames after previous pulse\n", pos->frame - nTestFrames);
            nTestFrames = pos->frame;
            nNextClockTick += pos->ticks_per_beat / 24;
            if(nNextClockTick > pos->ticks_per_beat)
                nNextClockTick = 0;
        }
    }
    nNextBar = pos->bar + 1;
    
    static uint32_t nDebugBeat = 0;
    static uint32_t nDebugLastFrame = 0;
    if(nDebugBeat != pos->beat)
    {
        printf("Beat %d, Frame %u (+%u)\n", pos->beat, pos->frame, pos->frame - nDebugLastFrame);
        nDebugLastFrame = pos->frame;
        nDebugBeat = pos->beat;
    }
}

// Thread that waits for a clock pulse
void onClock()
{
    //!@todo Start new clock thread when needed (something playing) and exit when nothing playing???
    while(g_bRunning)
    {
        while(g_bClockIdle)
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        g_bClockIdle = true;
        //if(g_bPlaying)
        {
            while(g_bMutex)
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            g_bMutex = true;
            PatternManager::getPatternManager()->clock(g_nClockEventTime, &g_mSchedule, g_bSync); // Pass current clock time and schedule to pattern manager so it can populate with events. Pass sync pulse so that it can syncronise its sequences, e.g. start zynpad sequences
            if(g_bSync)
            {
                g_bPlaying = PatternManager::getPatternManager()->isPlaying(); // Update playing state each sync cycle
                if(g_nSongStatus == STARTING)
                    g_nSongStatus = PLAYING;
                g_bSync = false;
            }
            g_bMutex = false;

            if(g_nSongStatus == PLAYING)
                ++g_nSongPosition;
            // Check for end of song
            //!@todo song length should really be a property of the song class
        }
    }
}

int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
    /*  nFrames is the quantity of frames to process in this cycle
        jack_last_frame_time is the quantity of samples since JACK started
        jack_midi_event_write sends MIDI message at sample time offset
        
        Iterate through list of slots within this process period
        For each slot, add MIDI events to the output buffer at appropriate sample offset
        Remove slots
        
        Process incoming MIDI events
    */
    static jack_position_t transportPosition; // JACK transport position structure populated each cycle and checked for transport progress
    static bool bSync = false; // Track if we have sent a sync pulse for this bar
    static uint8_t nClock = 24; // Clock pulse count 0..23
    static uint32_t nTicksPerPulse;
    static double dTicksPerFrame;
    static double dTicksPerBeat; // Store so that we can check for change and do less maths
    static double dBeatsPerMinute; // Store so that we can check for change and do less maths
    static double dBeatsPerBar; // Store so that we can check for change and do less maths
    static jack_nframes_t nFramerate; // Store so that we can check for change and do less maths
    static uint32_t nFramesPerPulse;
    
    // Get output buffer that will be processed in this process cycle
    void* pOutputBuffer = jack_port_get_buffer(g_pOutputPort, nFrames);
    unsigned char* pBuffer;
    jack_midi_clear_buffer(pOutputBuffer);
    jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);

    // Only play sequences if JACK transport is rolling
    if(jack_transport_query(g_pJackClient, &transportPosition) == JackTransportRolling && transportPosition.valid & JackPositionBBT)
    {
        if(g_bClockRateChange || dTicksPerBeat != transportPosition.ticks_per_beat || dBeatsPerMinute != transportPosition.beats_per_minute || nFramerate != transportPosition.frame_rate | dBeatsPerBar != transportPosition.beats_per_bar)
        {
            // Something has changed so recalculate values
            dTicksPerBeat = transportPosition.ticks_per_beat;
            dBeatsPerBar = transportPosition.beats_per_bar;
            dBeatsPerMinute = transportPosition.beats_per_minute;
            nFramerate = transportPosition.frame_rate;
            nTicksPerPulse = transportPosition.ticks_per_beat / 24;;
            dTicksPerFrame = transportPosition.ticks_per_beat * transportPosition.beats_per_minute / 60 / transportPosition.frame_rate;
            PatternManager::getPatternManager()->setSequenceClockRates(nTicksPerPulse / dTicksPerFrame);
            g_bClockRateChange = false;
            nFramesPerPulse = nTicksPerPulse / dTicksPerFrame;
        }
        /*
        Get tick.
        Find how many ticks since last pulse.
        Find how many frames since last pulse.
        Check if in this period.
        Schedule for one period in future + one pulse.
        */
        /*
        uint32_t nTickSinceStartOfBar = transportPosition.tick + transportPosition.ticks_per_beat * (transportPosition.beat - 1);
        uint32_t nPulsesSinceStartOfBar = nTickSinceStartOfBar / nTicksPerPulse;
        uint32_t nThisClock = nPulsesSinceStartOfBar % 24;
        if(nThisClock != nClock)
        {
            nClock = nThisClock;
            if(nPulsesSinceStartOfBar == 0)
            {
                g_bSync = true;
                if(g_bPlaying)
                    printf("Bar: %u Beat: %u Clock: %u Tick: %u %s \n", transportPosition.bar, transportPosition.beat, nClock, transportPosition.tick, g_bSync?"SYNC":"");
            }
            uint32_t nTicksSincePulse = transportPosition.tick % nTicksPerPulse;
            uint32_t nFramesSincePulse = nTicksSincePulse / dTicksPerFrame;
//          printf("NextPulse: %u frames (transportPosition.tick: %u nTicksPerPulse: %u)\n", nFramesSincePulse, transportPosition.tick, nTicksPerPulse);
//      if(nFramesSincePulse < nFrames) //!@todo Handle several pulses in same frame
//      {
            // There is a clock pulse due in this cycle
            //!@todo g_bSync is currently being set late because we are looking forward for next pulse but using current beat. Maybe that is okay.
            g_nClockEventTime = nNow + nFrames;// +nFramesSincePulse // By working with one cycle (period) lag we can set offset in next frame for low jitter but one cycle latency
            //g_bClockIdle = false; // Clock pulse
            //!@todo We need to position playback correctly, i.e. manage discontinuity in clock / position
            //!@todo Update song position if song playing (or maybe we just derive it dynamically)
            //!@todo First beat after start can be wrong duration, e.g. too few clock cycles probably due to sync being late
        }
        */
    }

    // Process MIDI input
    void* pInputBuffer = jack_port_get_buffer(g_pInputPort, nFrames);
    jack_midi_event_t midiEvent;
    jack_nframes_t nCount = jack_midi_get_event_count(pInputBuffer);
    for(jack_nframes_t i = 0; i < nCount; i++)
    {
        jack_midi_event_get(&midiEvent, pInputBuffer, i);
        switch(midiEvent.buffer[0])
        {
            case MIDI_STOP:
                if(g_bDebug)
                    printf("StepJackClient MIDI STOP\n");
                //!@todo Send note off messages
                pauseSong();
                break;
            case MIDI_START:
                if(g_bDebug)
                    printf("StepJackClient MIDI START\n");
                stopSong();
                startSong();
                break;
            case MIDI_CONTINUE:
                if(g_bDebug)
                    printf("StepJackClient MIDI CONTINUE\n");
                startSong();
                break;
            case MIDI_CLOCK:
                if(g_bDebug)
                    printf("StepJackClient MIDI CLOCK\n");
                // Ignore MIDI clock - let Jack timebase master handle it
                break;
            case MIDI_POSITION:
            {
                //!@todo Should we let Jack timebae master manage MIDI position changes?
                uint32_t nPos = (midiEvent.buffer[1] + (midiEvent.buffer[2] << 7)) * 6;
                if(g_bDebug)
                    printf("StepJackClient POSITION %d (clocks)\n", nPos);
                setSongPosition(nPos);
                break;
            }
            case MIDI_SONG:
                if(g_bDebug)
                    printf("StepJackClient Select song %d\n", midiEvent.buffer[1]);
                PatternManager::getPatternManager()->setCurrentSong(midiEvent.buffer[1] + 1);
                break;
            default:
//              if(g_bDebug)
//                  printf("StepJackClient Unhandled MIDI message %d\n", midiEvent.buffer[0]);
                break;
        }
        // Handle MIDI Note On events to trigger sequences
        if((midiEvent.buffer[0] == (MIDI_NOTE_ON | PatternManager::getPatternManager()->getTriggerChannel())) && midiEvent.buffer[2])
        {
            if(PatternManager::getPatternManager()->trigger(midiEvent.buffer[1]) && !g_bPlaying)
                sendMidiStart();
        }
        // Handle MIDI Note On events for programming patterns from MIDI input
        if(PatternManager::getPatternManager()->getCurrentSong() == 0 && g_nInputChannel < 16 && (midiEvent.buffer[0] == (MIDI_NOTE_ON | g_nInputChannel)) && midiEvent.buffer[2])
        {
            if(g_pPattern)
            {
                Sequence* pSeq = PatternManager::getPatternManager()->getSequence(1);
                uint32_t nStep = pSeq->getStep();
                if(getNoteVelocity(nStep, midiEvent.buffer[1]))
                    g_pPattern->removeNote(nStep, midiEvent.buffer[1]);
                else
                    g_pPattern->addNote(nStep, midiEvent.buffer[1], midiEvent.buffer[2], 1);
                if(!g_bPlaying)
                {
                    if(++nStep >= g_pPattern->getSteps())
                        nStep = 0;
                    pSeq->setStep(nStep);
                }
                g_bModified = true;
            }
        }
    }

    // Send MIDI output aligned with first sample of frame resulting in similar latency to audio
    //!@todo Send at sample accurate timing rather than salvo at start of frame - reduce jitter
    //!@todo Interpolate events across frame, e.g. CC variations
    while(g_bMutex)
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    g_bMutex = true;
    auto it = g_mSchedule.begin();
    jack_nframes_t nTime, nNextTime = 0;
    if(g_mSchedule.size())
    {
        while(it != g_mSchedule.end())
        {
            if(it->first >= nNow + g_nBufferSize)
                break; // Event scheduled beyond this buffer
            if(it->first < nNow)
            {
                nTime = nNextTime; // This event is in the past so send as soon as possible
                // If lots of events are added in past then they may be sent out of order because frame boundary may be hit and existing events will be left in thier previous position, e.g. at time 57 then up to 56 events could be inserted before this. Low risk and only for immediate events so unlikely to have significnat impact.
                printf("Sending event from past (%u/%u)\n", it->first, nNow); //!@todo remove this debug
            }
            else
                nTime = it->first - nNow; // Schedule event at scheduled time offset
            if(nTime < nNextTime)
                nTime = nNextTime; // Ensure we send events in order - this may bump events slightly latter than scheduled (by individual samples so not much)
            if(nTime >= g_nBufferSize)
            {
                g_bMutex = false;
                return 0; // Must have bumped beyond end of this frame time so must wait until next frame
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
            if(g_bDebug)
                printf("Sending MIDI event %d,%d,%d\n", pBuffer[0],pBuffer[1],pBuffer[2]);
        }
        g_mSchedule.erase(g_mSchedule.begin(), it); //!@todo Check that erasing schedule items works, e.g. that schedule is ordered
    }
    g_bMutex = false;
    return 0;
}

int onJackBufferSizeChange(jack_nframes_t nFrames, void *pArgs)
{
    if(g_bDebug)
        printf("zynseq: Jack buffer size: %d\n", nFrames);
    g_nBufferSize = nFrames;
    return 0;
}

int onJackSampleRateChange(jack_nframes_t nFrames, void *pArgs)
{
    if(g_bDebug)
        printf("zynseq: Jack samplerate: %d\n", nFrames);
    g_nSamplerate = nFrames;
    //!@todo Recalculate transport timing parameters?
    return 0;
}

int onJackXrun(void *pArgs)
{
    if(g_bDebug)
        printf("zynseq detected XRUN\n");
    return 0;
}

void end()
{
    printf("zynseq exit\n");
    g_bRunning = false;
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    for(auto it : g_mSchedule)
    {
        delete it.second;
    }
}

// ** Library management functions **

bool init()
{
    // Register with Jack server
    char *sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;
    
    if(g_pJackClient)
        return false;

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

    // Register JACK callbacks
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);
    jack_set_buffer_size_callback(g_pJackClient, onJackBufferSizeChange, 0);
    jack_set_sample_rate_callback(g_pJackClient, onJackSampleRateChange, 0);
    jack_set_xrun_callback(g_pJackClient, onJackXrun, 0); //!@todo Remove xrun handler (just for debug)

    if(jack_activate(g_pJackClient)) {
        fprintf(stderr, "libzynseq cannot activate client\n");
        return false;
    }

    if(transportRequestTimebase())
        printf("Registered as timebase master\n");
    else
        printf("Failed to register as timebase master\n");

    std::thread clockHandler(onClock);
    clockHandler.detach();

    // Register the cleanup function to be called when program exits
    atexit(end);
    return true;
}

bool load(char* filename)
{
    return PatternManager::getPatternManager()->load(filename);
}

void save(char* filename)
{
    PatternManager::getPatternManager()->save(filename);
}


// ** Direct MIDI interface **

// Schedule a MIDI message to be sent in next JACK process cycle
void sendMidiMsg(MIDI_MESSAGE* pMsg)
{
    //!@todo Should we schedule MIDI messages to be sent at offset within period?
    // Find first available time slot
    uint32_t time = 0;
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
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_NOTE_ON | (channel & 0x0F);
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
    printf("Sending MIDI Start... does it get recieved back???\n");
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

// Send a single MIDI clock
void sendMidiClock()
{
    MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
    pMsg->command = MIDI_CLOCK;
    sendMidiMsg(pMsg);
}

bool isPlaying()
{
    return g_bPlaying;
}

uint8_t getTriggerChannel()
{
    return PatternManager::getPatternManager()->getTriggerChannel();
}

void setTriggerChannel(uint8_t channel)
{
    if(channel > 15)
        return;
    PatternManager::getPatternManager()->setTriggerChannel(channel);
}

uint8_t getTriggerNote(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getTriggerNote(sequence);
}

void setTriggerNote(uint32_t sequence, uint8_t note)
{
    PatternManager::getPatternManager()->setTriggerNote(sequence, note);
}

// ** Pattern management functions **

void selectPattern(uint32_t pattern)
{
    g_pPattern = PatternManager::getPatternManager()->getPattern(pattern);
}

uint32_t getSteps()
{
    if(g_pPattern)
        return g_pPattern->getSteps();
    return 0;
}

uint32_t getPatternLength(uint32_t pattern)
{
    Pattern* pPattern = PatternManager::getPatternManager()->getPattern(pattern);
    if(pPattern)
        return pPattern->getLength();
    return 0;
}

void setSteps(uint32_t steps)
{
    if(g_pPattern)
        g_pPattern->setSteps(steps);
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(0);
}

uint32_t getBeatsInPattern()
{
    if(getStepsPerBeat())
        return getSteps() / getStepsPerBeat() ;
    return 0;
}

void setBeatsInPattern(uint32_t beats)
{
    setSteps(getStepsPerBeat() * beats);
}

uint32_t getClocksPerStep()
{
    if(g_pPattern)
        return g_pPattern->getClocksPerStep();
    return 6;
}

void setClocksPerStep(uint32_t divisor)
{
    if(g_pPattern)
        g_pPattern->setClocksPerStep(divisor);
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(0);
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
    g_pPattern->setSteps(getBeatsInPattern() * steps);
    g_pPattern->setStepsPerBeat(steps); // Do this second 'cos it changes beats in pattern calculation
}

uint8_t getBeatType()
{
    if(!g_pPattern)
        return 4;
    return g_pPattern->getBeatType();
}

void setBeatType(uint8_t beatType)
{
    if(!g_pPattern)
        return;
    g_pPattern->setBeatType(beatType);
}

void addNote(uint32_t step, uint8_t note, uint8_t velocity, uint32_t duration)
{
    if(g_pPattern)
        g_pPattern->addNote(step, note, velocity, duration);
}

void removeNote(uint32_t step, uint8_t note)
{
    if(g_pPattern)
        g_pPattern->removeNote(step, note);
}

uint8_t getNoteVelocity(uint32_t step, uint8_t note)
{
    if(g_pPattern)
        return g_pPattern->getNoteVelocity(step, note);
    return 0;
}

void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity)
{
    if(g_pPattern)
        g_pPattern->setNoteVelocity(step, note, velocity);
}

uint32_t getNoteDuration(uint32_t step, uint8_t note)
{
    if(g_pPattern)
        return g_pPattern->getNoteDuration(step, note);
    return 0;
}

void transpose(int8_t value)
{
    if(g_pPattern)
        g_pPattern->transpose(value);
}

void clear()
{
    if(g_pPattern)
        g_pPattern->clear();
}

void copyPattern(uint32_t source, uint32_t destination)
{
    PatternManager::getPatternManager()->copyPattern(source, destination);
}

void setInputChannel(uint8_t channel)
{
    if(channel > 15)
        g_nInputChannel = 0xFF;
    g_nInputChannel = channel;
}

uint8_t getInputChannel()
{
    return g_nInputChannel;
}

void setScale(uint32_t scale)
{
    if(g_pPattern)
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
    if(g_pPattern)
        g_pPattern->setTonic(tonic);
}

uint8_t getTonic()
{
    if(g_pPattern)
        return g_pPattern->getTonic();
    return 0;
}

bool isModified()
{
    if(g_bModified)
    {
        g_bModified = false;
        return true;
    }
    return false;
}

// ** Sequence management functions **

uint32_t getStep(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getStep();
}

bool addPattern(uint32_t sequence, uint32_t position, uint32_t pattern, bool force)
{
    PatternManager* pPm = PatternManager::getPatternManager();
    bool bUpdated = pPm->getSequence(sequence)->addPattern(position, pPm->getPattern(pattern), force);
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(pPm->getCurrentSong());
    return bUpdated;
}

void removePattern(uint32_t sequence, uint32_t position)
{
    PatternManager* pPm = PatternManager::getPatternManager();
    pPm->getSequence(sequence)->removePattern(position);
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(pPm->getCurrentSong());
}

uint32_t getPattern(uint32_t sequence, uint32_t position)
{
    PatternManager* pPm = PatternManager::getPatternManager();
    Sequence* pSeq = pPm->getSequence(sequence);
    Pattern* pPattern = pSeq->getPattern(position);
    return pPm->getPatternIndex(pPattern);
}

void setChannel(uint32_t sequence, uint8_t channel)
{
    PatternManager::getPatternManager()->getSequence(sequence)->setChannel(channel);
}

uint8_t getChannel(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getChannel(); 
}

void setOutput(uint32_t sequence, uint8_t output)
{
    PatternManager::getPatternManager()->getSequence(sequence)->setOutput(output);
}

uint8_t getPlayMode(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getPlayMode();
}

void setPlayMode(uint32_t sequence, uint8_t mode)
{
    PatternManager::getPatternManager()->getSequence(sequence)->setPlayMode(mode);
}

uint8_t getPlayState(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getPlayState();
}

void setPlayState(uint32_t sequence, uint8_t state)
{
    if(state == STARTING)
        g_bClockRateChange = true;
    PatternManager::getPatternManager()->setSequencePlayState(sequence, state);
    g_bPlaying = PatternManager::getPatternManager()->isPlaying();
}

void togglePlayState(uint32_t sequence)
{
    uint8_t nState = PatternManager::getPatternManager()->getSequence(sequence)->getPlayState();
    nState = (nState == STOPPED || nState == STOPPING)?STARTING:STOPPING;
    setPlayState(sequence, nState);
}

void stop()
{
    stopSong();
    PatternManager::getPatternManager()->stop();
}

uint32_t getPlayPosition(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getPlayPosition();
}

void setPlayPosition(uint32_t sequence, uint32_t clock)
{
    PatternManager::getPatternManager()->getSequence(sequence)->setPlayPosition(clock);
}

uint32_t getSequenceLength(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getLength();
}

void clearSequence(uint32_t sequence)
{
    // This is only used by pattern editor
    PatternManager::getPatternManager()->getSequence(sequence)->clear();
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(0);
}


uint8_t getGroup(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getGroup();
}

void setGroup(uint32_t sequence, uint8_t group)
{
    PatternManager::getPatternManager()->getSequence(sequence)->setGroup(group);
}

uint8_t getTallyChannel(uint32_t sequence)
{
    return PatternManager::getPatternManager()->getSequence(sequence)->getTallyChannel();
}

void setTallyChannel(uint32_t sequence, uint8_t channel)
{
    PatternManager::getPatternManager()->getSequence(sequence)->setTallyChannel(channel);
}


// ** Song management functions **

uint32_t addTrack(uint32_t song)
{
    return PatternManager::getPatternManager()->addTrack(song);
}

void removeTrack(uint32_t song, uint32_t track)
{
    PatternManager::getPatternManager()->removeTrack(song, track);
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(song);
}

void setTempo(uint32_t song, uint32_t tempo, uint16_t measure, uint16_t tick)
{
    PatternManager::getPatternManager()->getSong(song)->setTempo(tempo, measure, tick);
}

uint32_t getTempo(uint32_t song, uint16_t measure, uint16_t tick)
{
    return PatternManager::getPatternManager()->getSong(song)->getTempo(measure, tick);
}

void setTimeSig(uint32_t song, uint8_t beats, uint8_t type, uint16_t measure)
{
    PatternManager::getPatternManager()->getSong(song)->setTimeSig((beats << 8) & type, measure);
}

uint16_t getTimeSig(uint32_t song, uint16_t measure)
{
    return PatternManager::getPatternManager()->getSong(song)->getTimeSig(measure);
}

uint8_t getBeatsPerBar(uint32_t song, uint16_t measure)
{
    return getTimeSig(song, measure) >> 8;
}

uint8_t getBeatType(uint32_t song, uint16_t measure)
{
    return getTimeSig(song, measure) & 0xFF;
}

uint32_t getTracks(uint32_t song)
{
    return PatternManager::getPatternManager()->getSong(song)->getTracks();
}

uint32_t getSequence(uint32_t song, uint32_t track)
{
    return PatternManager::getPatternManager()->getSong(song)->getSequence(track);
}

void clearSong(uint32_t song)
{
    PatternManager::getPatternManager()->clearSong(song);
    g_nSongLength = 0;
}

void copySong(uint32_t source, uint32_t destination)
{
    PatternManager::getPatternManager()->copySong(source, destination);
}

void startSong(bool bFast)
{
    PatternManager::getPatternManager()->startSong(bFast);
    g_nSongStatus = bFast?PLAYING:STARTING;
    g_bPlaying = PatternManager::getPatternManager()->isPlaying();
}

void pauseSong()
{
    g_nSongStatus = STOPPED;
    PatternManager::getPatternManager()->stopSong();
    g_bPlaying = PatternManager::getPatternManager()->isPlaying();
}

void stopSong()
{
    g_nSongStatus = STOPPED;
    PatternManager::getPatternManager()->stopSong();
//  PatternManager::getPatternManager()->getSequence(0)->setPlayState(STOPPED);
    setSongPosition(0);
    g_bPlaying = PatternManager::getPatternManager()->isPlaying();
}

void toggleSong()
{
    if(g_nSongStatus == STOPPED)
        startSong();
    else
        pauseSong();
}

bool isSongPlaying()
{ 
    return g_nSongStatus == PLAYING;
}

void setSongPosition(uint32_t pos)
{
    PatternManager::getPatternManager()->setSongPosition(pos);
    g_nSongPosition = pos;
}
void setSongToStartOfMeasure()
{
    //!@todo Implement setSontToStartOfMeasure
    /*
    Song* pSong = PatternManager::getPatternManager()->getSong(getSong());
    uint32_t nSigTime = getTimeSig(getSong(), g_nSongPosition);
    uint16_t nSig = pSong->getTimeSig(nSigTime);
    uint8_t nBeatsPerBar = nSig >> 8;
    uint8_t nBeatType = nSig & 0xff;
    uint32_t nClocksPerBar = 96 * nBeatsPerBar / nBeatType;
    //!@todo Can we use Song::getBar instead of calculating bar?
    setSongPosition(nSigTime + nClocksPerBar * ((getSongPosition() - nSigTime) / nClocksPerBar));
    printf("**Time sig %d/%d at %u. Song pos: %u\n", nBeatsPerBar, nBeatType, nSigTime, getSongPosition());
    */
}

uint32_t getSongPosition()
{
    return g_nSongPosition;
}

uint32_t getSong()
{
    return PatternManager::getPatternManager()->getCurrentSong();
}

void selectSong(uint32_t song)
{
    if(g_bDebug)
        printf("Selecting song %d\n", song);
//  stopSong();
    PatternManager::getPatternManager()->setCurrentSong(song);
    g_nSongLength = PatternManager::getPatternManager()->updateSequenceLengths(song);
}

void solo(uint32_t song, uint32_t track, int solo)
{
    Song* pSong = PatternManager::getPatternManager()->getSong(song);
    uint32_t nSequence;
    for(uint32_t i = 0; i < getTracks(song); ++i)
    {
        nSequence = pSong->getSequence(i);
        PatternManager::getPatternManager()->getSequence(nSequence)->solo(false);
        setPlayState(nSequence, STOPPED);
    }
    nSequence = pSong->getSequence(track);
    PatternManager::getPatternManager()->getSequence(nSequence)->solo(solo);
    if(solo && g_nSongStatus == PLAYING)
        setPlayState(nSequence, PLAYING);
}

void transportLocate(uint32_t frame)
{
    jack_transport_locate(g_pJackClient, frame);
}

jack_nframes_t transportGetLocation(uint32_t measure, uint32_t beat, uint32_t tick)
{
    // Convert one-based Measures and beats to zero-based 
    if(measure > 0)
        --measure;
    if(beat > 0)
        --beat;
    uint32_t nTicksToPrev = 0;
    uint32_t nTicksToEvent = 0;
    uint32_t nTicksPerMeasure = g_dTicksPerBeat * (DEFAULT_TIMESIG >> 8);
    double dFramesPerTick = getFramesPerTick(DEFAULT_TEMPO);
    double dFrames = 0; // Frames to position
    if(g_pTimebase)
    {
        for(size_t nIndex = 0; nIndex < g_pTimebase->getEventQuant(); ++nIndex)
        {
            TimebaseEvent* pEvent = g_pTimebase->getEvent(nIndex);
            if(pEvent->measure > measure || pEvent->measure == measure && pEvent->tick > g_dTicksPerBeat * beat + tick)
                break; // Ignore events later than new position
            nTicksToEvent = pEvent->measure * nTicksPerMeasure + pEvent->tick;
            uint32_t nTicksInBlock = nTicksToEvent - nTicksToPrev;
            dFrames += dFramesPerTick * nTicksInBlock;
            nTicksToPrev = nTicksToEvent;
            if(pEvent->type == TIMEBASE_TYPE_TEMPO)
                dFramesPerTick = getFramesPerTick(pEvent->value);
            else if(pEvent->type == TIMEBASE_TYPE_TIMESIG)
                nTicksPerMeasure = g_dTicksPerBeat * (pEvent->value >> 8);
        }
    }
    dFrames += dFramesPerTick * (measure * nTicksPerMeasure + beat * g_dTicksPerBeat + tick - nTicksToPrev);
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

void transportStart()
{
    jack_transport_start(g_pJackClient);
}

void transportStop()
{
    jack_transport_stop(g_pJackClient);
}

void transportToggle()
{
    if(transportGetPlayStatus() == JackTransportRolling)
        transportStop();
    else
        transportStart();
}

uint8_t transportGetPlayStatus()
{
    jack_position_t position; // Not used but required to query transport
    jack_transport_state_t nState;
    return jack_transport_query(g_pJackClient, &position);
}

void transportSetTempo(uint32_t tempo)
{
    g_dTempo = tempo;
    g_bTimebaseChanged = true;
}

uint32_t transportGetTempo()
{
    return g_dTempo;
}

void transportSetSyncTimeout(uint32_t timeout)
{
    jack_set_sync_timeout(g_pJackClient, timeout);
}

void transportSetTimebaseMap(Timebase* timebase)
{
    g_pTimebase = timebase;
}

