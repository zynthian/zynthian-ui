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
#include <jack/jack.h> //provides JACK interface
#include <jack/midiport.h> //provides JACK MIDI interface

Pattern* g_pPattern = 0; // Currently selected pattern
jack_port_t * g_pInputPort; // Pointer to the JACK input port
jack_port_t * g_pOutputPort; // Pointer to the JACK output port
jack_client_t *g_pJackClient = NULL; // Pointer to the JACK client
bool g_bClockIdle = true; // True to indicate clock pulse
bool g_bRunning = true; // False to stop clock thread, e.g. on exit
jack_nframes_t g_nSamplerate; // Quantity of samples per second
jack_nframes_t g_nBufferSize; // Quantity of samples in JACK buffer passed each process cycle
std::map<uint32_t,MIDI_MESSAGE*> g_mSchedule; // Schedule of MIDI events (queue for sending), indexed by scheduled play time (samples since JACK epoch)
bool g_bDebug = false; // True to output debug info
jack_nframes_t g_nSamplesPerClock = 918; // Quantity of samples per MIDI clock [Default: 918 gives 120BPM at 44100 samples per second]
jack_nframes_t g_nSamplesPerClockLast = 918; // Quantity of samples per MIDI clock [Default: 918 gives 120BPM at 44100 samples per second]
jack_nframes_t g_nLastTime = 0; // Time of previous MIDI clock in frames (samples) since JACK epoch
jack_nframes_t g_nClockEventTime; // Time of current MIDI clock in frames (samples) since JACK epoch
jack_nframes_t g_nClockEventTimeOffset;


bool g_bLocked = false; // True when locked to MIDI clock
bool g_bPlaying = false; // Local interpretation of whether MIDI clock is running

// ** Internal (non-public) functions  (not delcared in header so need to be in correct order in source file) **

void debug(bool bEnable)
{
	g_bDebug = bEnable;
}

void onClock()
{
	while(g_bRunning)
	{
		while(g_bClockIdle)
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		g_bClockIdle = true;
//		printf("Clock at %u (+%u)\n", g_nClockEventTime, g_nClockEventTimeOffset);
		jack_time_t nTime = jack_last_frame_time(g_pJackClient);
		//	Check if clock pulse duration is significantly different to last. If so, set sequence clock rates.
		int nClockPeriod = g_nClockEventTime - g_nLastTime;
		if(g_nLastTime && !g_bLocked)
		{
			// First cycle after start of clock
			PatternManager::getPatternManager()->setSequenceClockRates(nClockPeriod);
//			printf("Setting clock rates to %u\n", nClockPeriod);
			g_nSamplesPerClock = nClockPeriod;
			g_bLocked = true;
		}
		g_nLastTime = g_nClockEventTime;
		if(g_bLocked)
		{
			int nOffset = nClockPeriod - g_nSamplesPerClock;
			if(nOffset > 10 || nOffset < -10)
			{
				g_nSamplesPerClock = nClockPeriod;
//				printf("Setting clock rates to %u\n", nClockPeriod);
				PatternManager::getPatternManager()->setSequenceClockRates(nClockPeriod);
			}
		}
		PatternManager::getPatternManager()->clock(nTime + g_nBufferSize, &g_mSchedule);
	}
}

int onJackProcess(jack_nframes_t nFrames, void *pArgs)
{
	/*	nFrames is the quantity of frames to process in this cycle
		jack_last_frame_time is the quantity of samples since JACK started
		jack_midi_event_write sends MIDI message at sample time offset
		
		Iterate through list of slots within this process period
		For each slot, add MIDI events to the output buffer at appropriate sample offset
		Remove slots
		
		Process incoming MIDI events
	*/
	int i;
	// Get output buffer that will be processed in this process cycle
	void* pOutputBuffer = jack_port_get_buffer(g_pOutputPort, nFrames);
	unsigned char* pBuffer;
	jack_midi_clear_buffer(pOutputBuffer);

	// Process MIDI input
	void* pInputBuffer = jack_port_get_buffer(g_pInputPort, nFrames);
	jack_midi_event_t midiEvent;
	jack_nframes_t nCount = jack_midi_get_event_count(pInputBuffer);
	jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);
	for(i = 0; i < nCount; i++)
	{
		jack_midi_event_get(&midiEvent, pInputBuffer, i);
		switch(midiEvent.buffer[0])
		{
			case MIDI_STOP:
				printf("StepJackClient MIDI STOP\n");
				//!@todo Send note off messages
				g_nLastTime = 0;
				g_bLocked = false;
				g_bPlaying = false;
				break;
			case MIDI_START:
				printf("StepJackClient MIDI START\n");
				g_nLastTime = 0;
				g_bLocked = false;
				g_bPlaying = true;
				break;
			case MIDI_CONTINUE:
				printf("StepJackClient MIDI CONTINUE\n");
				g_nLastTime = 0;
				g_bLocked = false;
				g_bPlaying = true;
				break;
			case MIDI_CLOCK:
				g_nClockEventTimeOffset = midiEvent.time;
				g_nClockEventTime = nNow + midiEvent.time;
				g_bClockIdle = false;
				g_bPlaying = true;
				break;
			case MIDI_POSITION:
				printf("Song position %d\n", midiEvent.buffer[1] + midiEvent.buffer[1] << 7);
				break;
			case MIDI_SONG:
				printf("Select song %d\n", midiEvent.buffer[1]);
			default:
				//printf("Unhandled MIDI message %d\n", midiEvent.buffer[0]);
				break;
		}
	}

	// Send MIDI output aligned with first sample of frame resulting in similar latency to audio
	//!@todo Interpolate events across frame, e.g. CC variations
	auto it = g_mSchedule.begin();
	while(it != g_mSchedule.end())
	{
		if(it->first > jack_last_frame_time(g_pJackClient))
			break;
		// Get a pointer to the next 3 available bytes in the output buffer
		pBuffer = jack_midi_event_reserve(pOutputBuffer, 0, 3);
		pBuffer[0] = it->second->command;
		pBuffer[1] = it->second->value1;
		pBuffer[2] = it->second->value2;
		delete it->second;
		++it;
		if(g_bDebug)
			printf("Sending MIDI event %d,%d,%d\n", pBuffer[0],pBuffer[1],pBuffer[2]);
	}
	g_mSchedule.erase(g_mSchedule.begin(), it); //!@todo Check that erasing schedule items works, e.g. that schedule is ordered

	return 0;
}

int onJackBufferSizeChange(jack_nframes_t nFrames, void *pArgs)
{
	printf("zynseq: Jack buffer size: %d\n", nFrames);
	g_nBufferSize = nFrames;
	return 0;
}

int onJackSampleRateChange(jack_nframes_t nFrames, void *pArgs)
{
	printf("zynseq: Jack samplerate: %d\n", nFrames);
	g_nSamplerate = nFrames;
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

	std::thread clockHandler(onClock);
	clockHandler.detach();

	// Register the cleanup function to be called when program exits
	atexit(end);
	return true;
}

void load(char* filename)
{
	PatternManager::getPatternManager()->load(filename);
}

void save(char* filename)
{
	PatternManager::getPatternManager()->save(filename);
}


// ** Direct MIDI interface **

// Schedule a MIDI message to be sent in next JACK process cycle
void sendMidiMsg(MIDI_MESSAGE* pMsg)
{
	uint32_t time = jack_last_frame_time(g_pJackClient) + g_nBufferSize;
	while(g_mSchedule.find(time) != g_mSchedule.end())
		++time;
	g_mSchedule[time] = pMsg;
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
	std::thread noteOffThread(noteOffTimer, note, channel, 200);
	noteOffThread.detach();
}

void transportStart()
{
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_START;
	sendMidiMsg(pMsg);
}

void transportStop()
{
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_STOP;
	sendMidiMsg(pMsg);
}

void transportContinue()
{
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_CONTINUE;
	sendMidiMsg(pMsg);
}

// Send a single MIDI clock
void transportClock()
{
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_CLOCK;
	sendMidiMsg(pMsg);
}

bool isTransportRunning()
{
	return g_bPlaying;
}

void transportToggle()
{
	if(g_bPlaying)
		transportStop();
	else
		transportStart();
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
	else
		return 0;
}

void setSteps(uint32_t steps)
{
	if(g_pPattern)
		g_pPattern->setSteps(steps);
	PatternManager::getPatternManager()->updateSequenceLengths();
}

uint32_t getClockDivisor()
{
	if(g_pPattern)
		return g_pPattern->getClockDivisor();
	return 6;
}

void setClockDivisor(uint32_t divisor)
{
	if(g_pPattern)
		g_pPattern->setClockDivisor(divisor);
	PatternManager::getPatternManager()->updateSequenceLengths();
}

uint32_t getStepsPerBeat()
{
	if(g_pPattern)
		return g_pPattern->getStepsPerBeat();
	return 4;
}

void setStepsPerBeat(uint32_t steps)
{
	if(g_pPattern)
		g_pPattern->setStepsPerBeat(steps);
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
	if(source == destination)
		return;
	Pattern* pSource = PatternManager::getPatternManager()->getPattern(source);
	Pattern* pDestination = PatternManager::getPatternManager()->getPattern(destination);
	PatternManager::getPatternManager()->copyPattern(pSource, pDestination);
}


// ** Sequence management functions **

uint32_t getStep(uint32_t sequence)
{
	return PatternManager::getPatternManager()->getSequence(sequence)->getStep();
}

void addPattern(uint32_t sequence, uint32_t position, uint32_t pattern)
{
	PatternManager* pPm = PatternManager::getPatternManager();
	pPm->getSequence(sequence)->addPattern(position, pPm->getPattern(pattern));
}

void removePattern(uint32_t sequence, uint32_t position)
{
	PatternManager* pPm = PatternManager::getPatternManager();
	pPm->getSequence(sequence)->removePattern(position);
}

uint32_t getPattern(uint32_t sequence, uint32_t position)
{
	PatternManager* pPm = PatternManager::getPatternManager();
	Sequence* pSeq = pPm->getSequence(sequence);
	Pattern* pPattern = pSeq->getPattern(position);
	return pPm->getPatternIndex(pPattern); //!@todo getPattern should return NOT_FOUND
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


void togglePlayMode(uint32_t sequence)
{
	PatternManager::getPatternManager()->getSequence(sequence)->togglePlayMode();
}

uint32_t getPlayPosition(uint32_t sequence)
{
	return PatternManager::getPatternManager()->getSequence(sequence)->getPlayPosition();
}

uint32_t getSequenceLength(uint32_t sequence)
{
	return PatternManager::getPatternManager()->getSequence(sequence)->getLength();
}

void clearSequence(uint32_t sequence)
{
	PatternManager::getPatternManager()->getSequence(sequence)->clear();
}
