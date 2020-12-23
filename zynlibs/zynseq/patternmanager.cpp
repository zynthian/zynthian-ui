#include "patternmanager.h"
#include <cstring>

/** PatternManager class methods implementation **/

PatternManager* PatternManager::m_pPatternManager = NULL; //Initialise instance to null

PatternManager::PatternManager()
{
	init();
}

PatternManager* PatternManager::getPatternManager()
{
	if(m_pPatternManager == 0)
		m_pPatternManager = new PatternManager();
	return m_pPatternManager;
}

void PatternManager::init()
{
	m_mSequences.clear();
	m_mPatterns.clear();
	m_mSongs.clear();
	m_mTriggers.clear();
	m_nCurrentSong = 1;
	m_nCurrentlyPlayingSong = 1;
	m_mSequences[0]; // Create sequence 1 to use for pattern editor
	m_mSongs[0].addTrack(1); // Sequence 1, song 0 used for pattern editor (cannot use seq 0)
	m_mSongSequences[1] = 0; // Update reverse lookup table
}

int PatternManager::fileWrite32(uint32_t value, FILE *pFile)
{
	for(int i = 3; i >=0; --i)
		fileWrite8((value >> i * 8), pFile);
	return 4;
}

int PatternManager::fileWrite16(uint16_t value, FILE *pFile)
{
	for(int i = 1; i >=0; --i)
		fileWrite8((value >> i * 8), pFile);
	return 2;
}

int PatternManager::fileWrite8(uint8_t value, FILE *pFile)
{
	int nResult = fwrite(&value, 1, 1, pFile);
	return 1;
}

uint8_t PatternManager::fileRead8(FILE* pFile)
{
	uint8_t nResult = 0;
	fread(&nResult, 1, 1, pFile);
	return nResult;
}

uint16_t PatternManager::fileRead16(FILE* pFile)
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

uint32_t PatternManager::fileRead32(FILE* pFile)
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

bool PatternManager::load(const char* filename)
{
	init();
	uint32_t nSequence = 1;
	uint32_t nVersion = 0;
	FILE *pFile;
	pFile = fopen(filename, "r");
	if(pFile == NULL)
	{
		fprintf(stderr, "ERROR: PatternManager failed to open file for load %s\n", filename);
		return false;
	}
	char sHeader[4];
	// Iterate each block within RIFF file
	while(fread(sHeader, 4, 1, pFile) == 1)
	{
//		printf("Looking for RIFF block...\n");
		// Load patterns
		uint32_t nBlockSize = fileRead32(pFile);
		if(memcmp(sHeader, "vers",4) == 0)
		{
			nVersion = fileRead32(pFile);
			if(nVersion < FILE_VERSION)
				printf("Zynseq loading version %u of song file which is older than current version %u\n", nVersion, FILE_VERSION);
		}
		if(memcmp(sHeader, "patn", 4) == 0)
		{
			if(nBlockSize < 14)
				continue;
			Pattern* pPattern = getPattern(fileRead32(pFile));
			if(nVersion < 2)
			{
				uint32_t nSteps = fileRead32(pFile);
				uint16_t nClkPerStep = fileRead16(pFile);
				pPattern->setBeatsInPattern(nSteps * nClkPerStep / 24);
			}
			else
			{
				pPattern->setBeatsInPattern(fileRead32(pFile));
				fileRead16(pFile); //!@todo remove or use this for clocks per beat
			}
			pPattern->setStepsPerBeat(fileRead16(pFile));
			pPattern->setScale(fileRead8(pFile));
			pPattern->setTonic(fileRead8(pFile));
			nBlockSize -= 14;
			while(nBlockSize)
			{
				uint32_t nTime = fileRead32(pFile);
				uint32_t nDuration = fileRead32(pFile);
				uint8_t nCommand = fileRead8(pFile);
				uint8_t nValue1start = fileRead8(pFile);
				uint8_t nValue2start = fileRead8(pFile);
				uint8_t nValue1end = fileRead8(pFile);
				uint8_t nValue2end = fileRead8(pFile);
				fileRead8(pFile); // Padding
				StepEvent* pEvent = pPattern->addEvent(nTime, nCommand, nValue1start, nValue2start, nDuration);
				pEvent->setValue1end(nValue1end);
				pEvent->setValue2end(nValue2end);
				nBlockSize -= 14;
			}
		}
		else if(memcmp(sHeader, "song", 4) == 0)
		{
			// Load songs
			if(nBlockSize < 10)
				continue;
			uint32_t nSong = fileRead32(pFile);
			m_mSongs[nSong].setBar(fileRead16(pFile));
			if(nVersion >= 3)
				m_mSongs[nSong].setTempo(fileRead16(pFile));
			uint32_t nTimebaseEvents = fileRead32(pFile);
			nBlockSize -= 10;
			if(nBlockSize < nTimebaseEvents * 8) //!@todo Handle variable length data
				continue;
			for(uint32_t nEvent = 0; nEvent < nTimebaseEvents; ++nEvent)
			{
				m_mSongs[nSong].getTimebase()->addTimebaseEvent(fileRead16(pFile), fileRead16(pFile), fileRead16(pFile), fileRead16(pFile));
				nBlockSize -= 8;
			}
			while(nBlockSize)
			{
				if(nBlockSize < 8)
					break;
				m_mSongSequences[++nSequence] = nSong;
				m_mSongs[nSong].addTrack(nSequence);
				m_mSequences[nSequence].setChannel(fileRead8(pFile));
				m_mSequences[nSequence].setOutput(fileRead8(pFile));
				m_mSequences[nSequence].setPlayMode(fileRead8(pFile));
				m_mSequences[nSequence].setGroup(fileRead8(pFile));
				m_mSequences[nSequence].setTrigger(fileRead8(pFile));
				m_mSequences[nSequence].setMap(fileRead8(pFile));
				uint16_t nPatterns = fileRead16(pFile);
				nBlockSize -= 8;
				while(nPatterns--)
				{
					if(nBlockSize < 8)
						break;
					uint32_t nTime = fileRead32(pFile);
					uint32_t nPattern = fileRead32(pFile);
					m_mSequences[nSequence].addPattern(nTime, getPattern(nPattern));
					nBlockSize -= 8;
				}
			}
		}
		else if(memcmp(sHeader, "trig", 4) == 0)
		{
			// Load trigger inputs
			if(nBlockSize < 2)
				continue;
			setTriggerChannel(fileRead8(pFile));
			fileRead8(pFile); // Not implemented different JACK inputs
		}
	}
	fclose(pFile);
	//printf("Ver: %d Loaded %lu patterns, %lu sequences, %lu songs from file %s\n", nVersion, m_mPatterns.size(), m_mSequences.size(), m_mSongs.size(), filename);
	return true;
}

void PatternManager::save(const char* filename)
{
	//!@todo Need to save / load ticks per beat (unless we always use 1920)
	FILE *pFile;
	int nPos = 0;
	pFile = fopen(filename, "w");
	if(pFile == NULL)
	{
		fprintf(stderr, "ERROR: PatternManager failed to open file %s\n", filename);
		return;
	}
	uint32_t nBlockSize;
	fwrite("vers", 4, 1, pFile); // RIFF block name
	nPos += 4;
	nPos += fileWrite32(4, pFile); // RIFF block size
	nPos += fileWrite32(FILE_VERSION, pFile); // RIFF block content

	uint32_t nQoP = 0; // Quantity of patterns - purely for reporting
	uint32_t nQoS = 0; // Quantity of songs - purely for reporting
	uint32_t nQoSeq = 0; // Quantity of sequences - purely for reporting
	// Iterate through patterns
	for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
	{
		// Only save patterns with content
		if((*it).second.getEventAt(0))
		{
			++nQoP;
			fwrite("patnxxxx", 8, 1, pFile);
			nPos += 8;
			uint32_t nStartOfBlock = nPos;
			nPos += fileWrite32(it->first, pFile);
			nPos += fileWrite32(it->second.getBeatsInPattern(), pFile);
			nPos += fileWrite16(it->second.getClocksPerStep(), pFile);
			nPos += fileWrite16(it->second.getStepsPerBeat(), pFile);
			nPos += fileWrite8(it->second.getScale(), pFile);
			nPos += fileWrite8(it->second.getTonic(), pFile);
			size_t nEvent = 0;
			while(StepEvent* pEvent = it->second.getEventAt(nEvent++))
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
	}
	// Iterate through songs
	for(auto it = m_mSongs.begin(); it != m_mSongs.end(); ++it)
	{
		++nQoS;
		uint32_t nSong = it->first;
		if(nSong == 0)
			continue; // Don't save song 0
		fwrite("songxxxx", 8, 1, pFile);
		nPos += 8;
		uint32_t nStartOfBlock = nPos;
		nPos += fileWrite32(nSong, pFile);
		nPos += fileWrite16(m_mSongs[nSong].getBar(), pFile);
		nPos += fileWrite16(m_mSongs[nSong].getTempo(), pFile);
		nPos += fileWrite32(m_mSongs[nSong].getTimebase()->getEventQuant(), pFile);
		for(size_t nIndex = 0; nIndex < m_mSongs[nSong].getTimebase()->getEventQuant(); ++nIndex)
		{
			TimebaseEvent* pEvent = m_mSongs[nSong].getTimebase()->getEvent(nIndex);
			nPos += fileWrite16(pEvent->bar, pFile);
			nPos += fileWrite16(pEvent->clock, pFile);
			nPos += fileWrite16(pEvent->type, pFile);
			nPos += fileWrite16(pEvent->value, pFile);
		}
		for(uint32_t nSequence = 0; nSequence < m_mSongSequences.size(); ++nSequence)
		{
			if(m_mSongSequences[nSequence] != nSong)
				continue;
			nQoSeq++;
			nPos += fileWrite8(m_mSequences[nSequence].getChannel(), pFile);
			nPos += fileWrite8(m_mSequences[nSequence].getOutput(), pFile);
			nPos += fileWrite8(m_mSequences[nSequence].getPlayMode(), pFile);
			nPos += fileWrite8(m_mSequences[nSequence].getGroup(), pFile);
			nPos += fileWrite8(m_mSequences[nSequence].getTrigger(), pFile);
			nPos += fileWrite8(m_mSequences[nSequence].getMap(), pFile);
			nPos += fileWrite16('\0', pFile); // Placeholder
			uint32_t nPatternPos = 0xFFFFFFFF;
			uint16_t nPatterns = 0;
			while((nPatternPos = m_mSequences[nSequence].getNextPattern(nPatternPos)) != 0xFFFFFFFF)
			{
				nPos += fileWrite32(nPatternPos, pFile);
				nPos += fileWrite32(getPatternIndex(m_mSequences[nSequence].getPattern(nPatternPos)), pFile);
				++nPatterns;
			}
			fseek(pFile, nPos - nPatterns * 8 - 2, SEEK_SET);
			fileWrite16(nPatterns, pFile);
			fseek(pFile, 0, SEEK_END);
		}
		nBlockSize = nPos - nStartOfBlock;
		fseek(pFile, nStartOfBlock - 4, SEEK_SET);
		fileWrite32(nBlockSize, pFile);
		fseek(pFile, 0, SEEK_END);
	}

	// Triggers
	fwrite("trigxxxx", 8, 1, pFile);
	nPos += 8;
	uint32_t nStartOfBlock = nPos;
	nPos += fileWrite8(m_nTriggerChannel, pFile);
	nPos += fileWrite8('\0', pFile); // JACK input not yet implemented
	nBlockSize = nPos - nStartOfBlock;
	fseek(pFile, nStartOfBlock - 4, SEEK_SET);
	fileWrite32(nBlockSize, pFile);
	fseek(pFile, 0, SEEK_END);

	fclose(pFile);
	//printf("Saved %d patterns, %d sequences, %d songs to file %s\n", nQoP, nQoSeq, nQoS, filename);
}

Pattern* PatternManager::getPattern(size_t index)
{
	return &(m_mPatterns[index]);
}

uint32_t PatternManager::getPatternIndex(Pattern* pattern)
{
	//!@todo Is there benefit refactoring to just use index rather than pointer?
	for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
		if(&(it->second) == pattern)
			return it->first;
	return -1; //NOT_FOUND
}

size_t PatternManager::createPattern()
{
	size_t nSize = m_mPatterns.size();
	for(size_t nIndex = 0; nIndex < nSize; ++ nIndex)
	{
		if(m_mPatterns.find(nIndex) != m_mPatterns.end())
			continue;
		m_mPatterns[nIndex]; // Create a default pattern
		return nIndex;
	}
	m_mPatterns[nSize];
	return nSize;
}

void PatternManager::deletePattern(size_t index)
{
	m_mPatterns.erase(index);
}

void PatternManager::copyPattern(uint32_t source, uint32_t destination)
{
	if(source == destination)
		return;
	m_mPatterns[destination].clear();
	m_mPatterns[destination].setBeatsInPattern(m_mPatterns[source].getBeatsInPattern());
	m_mPatterns[destination].setStepsPerBeat(m_mPatterns[source].getStepsPerBeat());
	size_t nIndex = 0;
	while(StepEvent* pEvent = m_mPatterns[source].getEventAt(nIndex++))
		m_mPatterns[destination].addEvent(pEvent);
}

Sequence* PatternManager::getSequence(uint32_t sequence)
{
	return &(m_mSequences[sequence]);
}

uint32_t PatternManager::updateSequenceLengths(uint32_t song)
{
	uint32_t nSongLength = 0;
	size_t nTrack = 0;
	while(uint32_t nSeq = m_mSongs[song].getSequence(nTrack++))
	{
		uint32_t nSeqLen = m_mSequences[nSeq].updateLength();
		if(nSeqLen > nSongLength)
			nSongLength = nSeqLen;
	}
	return nSongLength;
}

void PatternManager::updateAllSequenceLengths()
{
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		it->second.updateLength();
}

bool PatternManager::clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync, double dSamplesPerClock)
{
	//!@todo It may be better for each sequence to have a flag indicating if it is part of the song or a pad rather than simple >1000
	bool bPlaying = doClock(m_nCurrentlyPlayingSong, nTime, pSchedule, bSync, dSamplesPerClock); // Clock song
	bPlaying |= doClock(m_nCurrentlyPlayingSong + 1000, nTime, pSchedule, bSync, dSamplesPerClock); // Clock zynpads
	if(m_nCurrentSong != m_nCurrentlyPlayingSong)
	{
		bPlaying |= doClock(m_nCurrentSong, nTime, pSchedule, bSync, dSamplesPerClock);
		bPlaying |= doClock(m_nCurrentSong + 1000, nTime, pSchedule, bSync, dSamplesPerClock);
	}
	bPlaying |= doClock(0, nTime, pSchedule, bSync, dSamplesPerClock); // Clock pattern editor
	return bPlaying;
}

inline bool PatternManager::doClock(uint32_t nSong, uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync, double dSamplesPerClock)
{
	/** Get events scheduled for next step from each playing sequence.
		Populate schedule with start, end and interpolated events at sample offset
	*/
	if(nSong == 1000)
		return false; // Base song is 0 which is used for pattern editor so has not corresponding zynpad
	size_t nTrack = 0;
	bool bPlaying = false;
	while(uint32_t nSeq = m_mSongs[nSong].getSequence(nTrack++))
	{
		uint8_t nEventType = m_mSequences[nSeq].clock(nTime, bSync, dSamplesPerClock);
		if(nEventType & 1)
		{
			while(SEQ_EVENT* pEvent = m_mSequences[nSeq].getEvent())
			{
				uint32_t nTime = pEvent->time;
				while(pSchedule->find(nTime) != pSchedule->end())
					++nTime; // Move event forward until we find a spare time slot
				MIDI_MESSAGE* pNewEvent = new MIDI_MESSAGE(pEvent->msg);
				(*pSchedule)[nTime] = pNewEvent;
				//printf("Clock time: %u Scheduling event 0x%x 0x%x 0x%x at %u\n", nTime, pEvent->msg.command, pEvent->msg.value1, pEvent->msg.value2, pEvent->time);
			}
		}
		if(nEventType & 2)
		{
			uint8_t nTallyChannel = m_mSequences[nSeq].getTallyChannel();
			uint8_t nTrigger = m_mSequences[nSeq].getTrigger();
			if(nTallyChannel < 16 && nTrigger < 128)
			{
				MIDI_MESSAGE* pEvent = new MIDI_MESSAGE();
				pEvent->command = MIDI_NOTE_ON | nTallyChannel;
				pEvent->value1 = nTrigger;
				switch(m_mSequences[nSeq].getPlayState())
				{
					//!@todo Tallies are hard coded to Akai APC but should be configurable
					case STOPPED:
						pEvent->value2 = 3;
						break;
					case PLAYING:
						if(m_nCurrentlyPlayingSong != m_nCurrentSong)
						{
							stopSong();
							m_nCurrentlyPlayingSong = m_nCurrentSong;
						}
						pEvent->value2 = 1;
						break;
					case STOPPING:
						pEvent->value2 = 4;
						break;
					case STARTING:
						pEvent->value2 = 5;
						break;
				}
				//!@todo Can we optimise time search?
				while(pSchedule->find(nTime) != pSchedule->end())
					++nTime; // Move event forward until we find a spare time slot
				(*pSchedule)[nTime] = pEvent;
			}
		}
		bPlaying |= (m_mSequences[nSeq].getPlayState() != STOPPED);
	}
	return bPlaying;
}

Song* PatternManager::getSong(size_t index)
{
	return &(m_mSongs[index]);
}

uint32_t PatternManager::addTrack(uint32_t song)
{
	// Need to find first missing sequence id from each song's list of track sequences...
	uint32_t nSequence = 1;
	for(; nSequence < m_mSongSequences.size() + 1; ++nSequence)
	{
		if(m_mSongSequences.find(nSequence) != m_mSongSequences.end())
			continue;
		break;
	}
	m_mSequences[nSequence].clear();
	m_mSongSequences[nSequence] = song;
	return m_mSongs[song].addTrack(nSequence);
}

void PatternManager::removeTrack(uint32_t song, uint32_t track)
{
	// Remove sequence from m_mSequences, m_mSongSequences, m_mTriggers, track from song
	uint32_t sequence = m_mSongs[song].getSequence(track);
	if(sequence)
	{
		m_mSongSequences.erase(sequence);
		setTriggerNote(sequence, -1);
		m_mSongs[song].removeTrack(track);
		m_mSequences.erase(sequence);
	}
}

void PatternManager::copySong(uint32_t source, uint32_t destination)
{
	if(source == destination)
		return;
	m_mSongs[destination].clear();
	for(uint32_t nEvent = 0; nEvent < m_mSongs[source].getTimebase()->getEventQuant(); ++ nEvent)
	{
		TimebaseEvent* pSourceEvent = m_mSongs[source].getTimebase()->getEvent(nEvent);
		m_mSongs[destination].getTimebase()->addTimebaseEvent(pSourceEvent->bar, pSourceEvent->clock, pSourceEvent->type, pSourceEvent->value);
	}
	for(size_t nTrack = 0; nTrack < m_mSongs[source].getTracks(); ++nTrack)
		m_mSongs[destination].addTrack(m_mSongs[source].getSequence(nTrack));
}

void PatternManager::clearSong(uint32_t song)
{
	while(m_mSongs[song].getTracks())
		removeTrack(song, 0);
}

void PatternManager::startSong(bool bFast)
{
	for(size_t nTrack = 0; nTrack < m_mSongs[m_nCurrentSong].getTracks(); ++nTrack)
	{
		uint32_t nSequence = m_mSongs[m_nCurrentSong].getSequence(nTrack);
		m_mSequences[nSequence].setPlayState(bFast?PLAYING:STARTING);
	}
	/*
	for(size_t nTrack = 0; nTrack < m_mSongs[m_nCurrentSong + 1000].getTracks(); ++nTrack)
	{
		uint32_t nSequence = m_mSongs[m_nCurrentSong + 1000].getSequence(nTrack);
		if(m_mSequences[nSequence].isSolo())
			m_mSequences[nSequence].setPlayState(bFast?PLAYING:STARTING);
	}
	*/
}

void PatternManager::stopSong()
{
	for(size_t nTrack = 0; nTrack < m_mSongs[m_nCurrentlyPlayingSong].getTracks(); ++nTrack)
	{
		uint32_t nSequence = m_mSongs[m_nCurrentlyPlayingSong].getSequence(nTrack);
		m_mSequences[nSequence].setPlayState(STOPPED);
	}
}

void PatternManager::setSongPosition(uint32_t pos)
{
	if(m_nCurrentlyPlayingSong == 0)
		pos = pos % m_mPatterns[1].getLength();
	size_t nTrack = 0;
	while(uint32_t nSequence = m_mSongs[m_nCurrentlyPlayingSong].getSequence(nTrack++))
		m_mSequences[nSequence].setPlayPosition(pos);
}

void PatternManager::setSequencePlayState(uint32_t sequence, uint8_t state)
{
	if(m_nCurrentlyPlayingSong && state == STARTING || state == PLAYING)
	{
		uint8_t nGroup = m_mSequences[sequence].getGroup();
		for(size_t nTrack = 0; nTrack < m_mSongs[m_nCurrentlyPlayingSong + 1000].getTracks(); ++nTrack)
		{
			uint32_t nSequence = m_mSongs[m_nCurrentlyPlayingSong + 1000].getSequence(nTrack);
			if(m_mSequences[nSequence].getGroup() == nGroup && m_mSequences[nSequence].getPlayState() == STARTING)
				m_mSequences[nSequence].setPlayState(STOPPED);
			else if(m_mSequences[nSequence].getGroup() == nGroup && m_mSequences[nSequence].getPlayState() != STOPPED && nSequence != sequence)
				m_mSequences[nSequence].setPlayState(STOPPING);
		}
	}
	m_mSequences[sequence].setPlayState(state);
}

uint8_t PatternManager::getTriggerNote(uint32_t sequence)
{
	return getSequence(sequence)->getTrigger();
}

void PatternManager::setTriggerNote(uint32_t sequence, uint8_t note)
{
	if(note < 128)
		m_mTriggers[note] = sequence;
	else
		m_mTriggers.erase(note);
	getSequence(sequence)->setTrigger(note);
}

uint8_t PatternManager::getTriggerChannel()
{
	return m_nTriggerChannel;
}

void PatternManager::setTriggerChannel(uint8_t channel)
{
	if(channel < 16)
		m_nTriggerChannel = channel;
}

uint32_t PatternManager::trigger(uint8_t note)
{
	if(m_mTriggers.find(note) == m_mTriggers.end())
		return 0;
	m_mSequences[m_mTriggers[note]].togglePlayState();
	return m_mTriggers[note];
}

void PatternManager::setCurrentSong(uint32_t song)
{
	m_nCurrentSong = song;
	if(m_mSongs[song].getTracks() == 0)
		for(size_t nIndex = 0; nIndex < DEFAULT_TRACK_COUNT; ++nIndex)
		{
			uint32_t nTrack = addTrack(song);
			uint32_t nSequence = m_mSongs[song].getSequence(nTrack);
			m_mSequences[nSequence].setChannel(nIndex);
			m_mSequences[nSequence].setGroup(nIndex);
			m_mSequences[nSequence].setPlayMode(ONESHOT);
		}
	if(m_mSongs[song + 1000].getTracks() == 0)
		for(size_t nIndex = 0; nIndex < DEFAULT_TRACK_COUNT; ++nIndex)
		{
			uint32_t nTrack = addTrack(song + 1000);
			uint32_t nSequence = m_mSongs[song + 1000].getSequence(nTrack);
			m_mSequences[nSequence].setChannel(0);
			m_mSequences[nSequence].setTrigger(nIndex + 60);
			m_mSequences[nSequence].setGroup(0);
			m_mSequences[nSequence].setPlayMode(LOOPSYNC);
		}
}

uint32_t PatternManager::getCurrentSong()
{
	return m_nCurrentSong;
}

bool PatternManager::isPlaying()
{
	//!@todo Should this return false if tranpsort is stopped?
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		if(it->second.getPlayState() != STOPPED)
			return true;
	return false;
}


void PatternManager::stop()
{
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		it->second.setPlayState(STOPPED);
}

void PatternManager::setSongTempo(uint16_t tempo)
{
	m_mSongs[m_nCurrentSong].setTempo(tempo); //!@todo Should this be currently playing song?
}

uint16_t PatternManager::getSongTempo()
{
	return m_mSongs[m_nCurrentSong].getTempo();  //!@todo Should this be currently playing song?
}
