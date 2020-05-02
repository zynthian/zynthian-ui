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
int32_t g_nTempo = 120; // BPM
int32_t g_nClockCounter; // MIDI clock generator frame  counter
bool g_bDebug = false; // True to output debug info

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
		PatternManager::getPatternManager()->clock(jack_last_frame_time(g_pJackClient) + g_nBufferSize, &g_mSchedule);
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
	for(i = 0; i < nCount; i++)
	{
		jack_midi_event_get(&midiEvent, pInputBuffer, i);
		switch(midiEvent.buffer[0])
		{
			case MIDI_STOP:
				printf("StepJackClient MIDI STOP\n");
				//!@todo Send note off messages
				break;
			case MIDI_START:
				printf("StepJackClient MIDI START\n");
				break;
			case MIDI_CONTINUE:
				printf("StepJackClient MIDI CONTINUE\n");
				break;
			case MIDI_CLOCK:
//				g_bClockIdle = false;
				break;
			case MIDI_POSITION:
				printf("Song position %d\n", midiEvent.buffer[1] + midiEvent.buffer[1] << 7);
				break;
			case MIDI_SONG:
				printf("Select song %d\n", midiEvent.buffer[1]);
			default:
				printf("Unhandled MIDI message %d\n", midiEvent.buffer[0]);
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

	if((g_nClockCounter -= nFrames) <= 0)
	{
		//!@todo Improve MIDI clock jitter
		g_bClockIdle = false;
		g_nClockCounter = 60 * g_nSamplerate / (24 * g_nTempo) + g_nClockCounter;
		if(g_bDebug)
		{
			static jack_time_t gThen;
			jack_time_t nNow = jack_get_time();
			printf("%" PRId64 " %" PRId64 "\n", nNow, (nNow - gThen)/1000);
			gThen = nNow;
		}
	}

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
	PatternManager::getPatternManager()->setSequenceClockRates(g_nTempo, g_nSamplerate);
	return 0;
}

int onJackXrun(void *pArgs)
{
	printf("XRUN\n");
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
	setTempo(120); // Default tempo - expect host to set this but need something to start with
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

	// Register the cleanup function to be called when program exits
	// It raises a segmentation fault on exit, so it's disabled
	//atexit(end);

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

void noteOffTimer(uint8_t note, uint8_t channel, uint32_t duration)
{
	std::this_thread::sleep_for(std::chrono::milliseconds(duration));
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_NOTE_ON | (channel & 0x0F);
	pMsg->value1 = note;
	pMsg->value2 = 0;
	uint32_t time = jack_last_frame_time(g_pJackClient) + g_nBufferSize;
	while(g_mSchedule.find(time) != g_mSchedule.end())
		++time;
	g_mSchedule[time] = pMsg;
}

void playNote(uint8_t note, uint8_t velocity, uint8_t channel, uint32_t duration)
{
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_NOTE_ON | (channel & 0x0F);
	pMsg->value1 = note;
	pMsg->value2 = velocity;
	uint32_t time = jack_last_frame_time(g_pJackClient) + g_nBufferSize;
	while(g_mSchedule.find(time) != g_mSchedule.end())
		++time;
	g_mSchedule[time] = pMsg;
	std::thread noteOffThread(noteOffTimer, note, channel, 200);
	noteOffThread.detach();
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

void setSteps(uint32_t steps)
{
	if(g_pPattern)
		g_pPattern->setSteps(steps);
	PatternManager::getPatternManager()->updateSequenceLengths();
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

void setTempo(int32_t tempo)
{
	if(tempo < 0)
		return; // Using signed int to allow comparison of countdown timer without casting
	g_nTempo = tempo;
	PatternManager::getPatternManager()->setSequenceClockRates(g_nTempo, g_nSamplerate);
	g_nClockCounter = 60 * g_nSamplerate / (24 * g_nTempo);
}

int32_t getTempo()
{
	return g_nTempo;
}