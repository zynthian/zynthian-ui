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
uint32_t g_nSyncPeriod = 96; // Time between sync pulses (clock cycles)
uint32_t g_nSyncCount = 0; // Time since last sync pulse (clock cycles)

bool g_bLocked = false; // True when locked to MIDI clock
bool g_bPlaying = false; // Local interpretation of play status

// ** Internal (non-public) functions  (not delcared in header so need to be in correct order in source file) **

void debug(bool bEnable)
{
	printf("libseq setting debug mode %s\n", bEnable?"on":"off");
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
				if(g_bDebug)
					printf("Setting clock rates to %u\n", nClockPeriod);
				PatternManager::getPatternManager()->setSequenceClockRates(nClockPeriod);
			}
		}
		bool bSync = (++g_nSyncCount >= g_nSyncPeriod);
		if(bSync)
		{
			g_nSyncCount = 0;
			if(g_bDebug)
				printf("+\n");
		}
		PatternManager::getPatternManager()->clock(g_nClockEventTime + g_nBufferSize, &g_mSchedule, bSync);
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
//				if(g_bDebug)
					printf("StepJackClient MIDI STOP\n");
				//!@todo Send note off messages
				pauseSong();
				break;
			case MIDI_START:
//				if(g_bDebug)
					printf("StepJackClient MIDI START\n");
				stopSong();
				startSong();
				break;
			case MIDI_CONTINUE:
//				if(g_bDebug)
					printf("StepJackClient MIDI CONTINUE\n");
				startSong();
				break;
			case MIDI_CLOCK:
				if(g_bDebug)
					printf("StepJackClient MIDI CLOCK\n");
				g_nClockEventTimeOffset = midiEvent.time;
				g_nClockEventTime = nNow + midiEvent.time;
				g_bClockIdle = false;
				break;
			case MIDI_POSITION:
			{
				uint32_t nPos = (midiEvent.buffer[1] + (midiEvent.buffer[2] << 7)) * 6;
//				if(g_bDebug)
					printf("StepJackClient POSITION %d (clocks)\n", nPos);
				setSongPosition(nPos);
				if(nPos == 0)
					setPlayPosition(0, 0);
				break;
			}
			case MIDI_SONG:
//				if(g_bDebug)
					printf("StepJackClient Select song %d\n", midiEvent.buffer[1]);
				PatternManager::getPatternManager()->setCurrentSong(midiEvent.buffer[1] + 1);
				break;
			default:
//				if(g_bDebug)
//					printf("StepJackClient Unhandled MIDI message %d\n", midiEvent.buffer[0]);
				break;
		}
		if((midiEvent.buffer[0] == (MIDI_NOTE_ON | PatternManager::getPatternManager()->getTriggerChannel())) && midiEvent.buffer[2])
			PatternManager::getPatternManager()->trigger(midiEvent.buffer[1]);
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

void sendMidiStart()
{
	MIDI_MESSAGE* pMsg = new MIDI_MESSAGE;
	pMsg->command = MIDI_START;
	sendMidiMsg(pMsg);
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
	PatternManager::getPatternManager()->updateSequenceLengths();
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
	PatternManager::getPatternManager()->copyPattern(source, destination);
}


// ** Sequence management functions **

uint32_t getStep(uint32_t sequence)
{
	return PatternManager::getPatternManager()->getSequence(sequence)->getStep();
}

void setStep(uint32_t sequence, uint32_t step)
{
	PatternManager::getPatternManager()->getSequence(sequence)->setStep(step);
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
	PatternManager::getPatternManager()->getSequence(sequence)->setPlayState(state);
	PatternManager::getPatternManager()->getSequence(sequence)->setPlayState(state);
}

void togglePlayState(uint32_t sequence)
{
	PatternManager::getPatternManager()->getSequence(sequence)->togglePlayState();
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
	PatternManager::getPatternManager()->getSequence(sequence)->clear();
}

void setSyncPeriod(uint32_t period)
{
	g_nSyncPeriod = period;
}

uint32_t getSyncPeriod()
{
	return g_nSyncPeriod;
}

void resetSync()
{
	g_nSyncCount = g_nSyncPeriod;
}

uint8_t getGroup(uint32_t sequence)
{
	return PatternManager::getPatternManager()->getSequence(sequence)->getGroup();
}

void setGroup(uint32_t sequence, uint8_t group)
{
	PatternManager::getPatternManager()->getSequence(sequence)->setGroup(group);
}


// ** Song management functions **

uint32_t addTrack(uint32_t song)
{
	return PatternManager::getPatternManager()->addTrack(song);
}

void removeTrack(uint32_t song, uint32_t track)
{
	PatternManager::getPatternManager()->removeTrack(song, track);
}

void setTempo(uint32_t song, uint32_t tempo, uint32_t time)
{
	PatternManager::getPatternManager()->getSong(song)->setTempo(tempo, time);
}

uint32_t getTempo(uint32_t song, uint32_t time)
{
	return PatternManager::getPatternManager()->getSong(song)->getTempo(time);
}

uint32_t getMasterEvents(uint32_t song)
{
    return PatternManager::getPatternManager()->getSong(song)->getMasterEvents();
}

uint32_t getMasterEventTime(uint32_t song, uint32_t event)
{
    return PatternManager::getPatternManager()->getSong(song)->getMasterEventTime(event);
}

uint16_t getMasterEventCommand(uint32_t song, uint32_t event)
{
    return PatternManager::getPatternManager()->getSong(song)->getMasterEventCommand(event);
}

uint16_t getMasterEventData(uint32_t song, uint32_t event)
{
    return PatternManager::getPatternManager()->getSong(song)->getMasterEventData(event);
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
}

void copySong(uint32_t source, uint32_t destination)
{
	PatternManager::getPatternManager()->copySong(source, destination);
}

void setBarLength(uint32_t song, uint32_t period)
{
	PatternManager::getPatternManager()->getSong(song)->setBar(period);
}

uint32_t getBarLength(uint32_t song)
{
	return PatternManager::getPatternManager()->getSong(song)->getBar();
}

void startSong()
{
	PatternManager::getPatternManager()->startSong();
//	else
//		PatternManager::getPatternManager()->getSequence(0)->setPlayState(PLAYING);
	g_nLastTime = 0;
	g_nSyncCount = 0;
	g_bLocked = false;
	g_bPlaying = true;
}

void pauseSong()
{
	PatternManager::getPatternManager()->stopSong();
//	PatternManager::getPatternManager()->getSequence(0)->setPlayState(STOPPED);
	g_nLastTime = 0;
	g_bLocked = false;
	g_bPlaying = false;
}

void stopSong()
{
	PatternManager::getPatternManager()->stopSong();
//	PatternManager::getPatternManager()->getSequence(0)->setPlayState(STOPPED);
	g_bPlaying = false;
	setSongPosition(0);
}

void setSongPosition(uint32_t pos)
{
	PatternManager::getPatternManager()->setSongPosition(pos);
}

uint32_t getSongPosition()
{
	return PatternManager::getPatternManager()->getSongPosition();
}

uint32_t getSong()
{
	return PatternManager::getPatternManager()->getCurrentSong();
}

void selectSong(uint32_t song)
{
	PatternManager::getPatternManager()->setCurrentSong(song);
}