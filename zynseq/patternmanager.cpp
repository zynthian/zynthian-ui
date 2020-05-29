#include "patternmanager.h"
#include <cstring>

/** PatternManager class methods implementation **/

PatternManager* PatternManager::m_pPatternManager = NULL; //Initialise instance to null

PatternManager::PatternManager()
{
}

PatternManager* PatternManager::getPatternManager()
{
	if(m_pPatternManager == 0)
		m_pPatternManager = new PatternManager();
	return m_pPatternManager;
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

void PatternManager::load(const char* filename)
{
	m_mSequences.clear();
	m_mPatterns.clear();
	uint32_t nSequence = 0;
	FILE *pFile;
	pFile = fopen(filename, "r");
	if(pFile == NULL)
	{
		fprintf(stderr, "ERROR: PatternManager failed to open file for load %s\n", filename);
		return;
	}
	char sHeader[4];
	// Iterate each block within RIFF file
	while(fread(sHeader, 4, 1, pFile) == 1)
	{
//		printf("Looking for RIFF block...\n");
		// Load patterns
		uint32_t nBlockSize = fileRead32(pFile);
		if(memcmp(sHeader, "patn", 4) == 0)
		{
			if(nBlockSize < 12)
				continue;
			Pattern* pPattern = getPattern(fileRead32(pFile));
			pPattern->setSteps(fileRead32(pFile));
			pPattern->setClocksPerStep(fileRead16(pFile));
			pPattern->setStepsPerBeat(fileRead16(pFile));
			nBlockSize -= 12;
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
			uint32_t nMasterEvents = fileRead32(pFile);
			nBlockSize -= 10;
			if(nBlockSize < nMasterEvents * 8) //!@todo Handle variable length data
				continue;
			for(uint32_t nEvent = 0; nEvent < nMasterEvents; ++nEvent)
			{
				m_mSongs[nSong].addMasterEvent(fileRead32(pFile), fileRead16(pFile), fileRead16(pFile));
				nBlockSize -= 8;
				printf("Loading master track event\n");
			}
			while(nBlockSize)
			{
				if(nBlockSize < 6)
					break;
				m_mSongSequences[++nSequence] = nSong;
				m_mSongs[nSong].addTrack(nSequence);
				m_mSequences[nSequence].setChannel(fileRead8(pFile));
				m_mSequences[nSequence].setOutput(fileRead8(pFile));
				m_mSequences[nSequence].setPlayMode(fileRead8(pFile));
				m_mSequences[nSequence].setGroup(fileRead8(pFile));
				uint16_t nPatterns = fileRead16(pFile);
				nBlockSize -= 6;
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
	}
	fclose(pFile);
	printf("Loaded %lu patterns, %lu sequences, %lu songs from file %s\n", m_mPatterns.size(), m_mSequences.size(), m_mSongs.size(), filename);
}

void PatternManager::save(const char* filename)
{
	FILE *pFile;
	int nPos = 0;
	pFile = fopen(filename, "w");
	if(pFile == NULL)
	{
		fprintf(stderr, "ERROR: PatternManager failed to open file %s\n", filename);
		return;
	}
	uint32_t nBlockSize;
	uint32_t nQoP = 0;
	// Iterate through patterns
	for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
	{
		// Only save patterns with content
		if((*it).second.getEventAt(0))
		{
			++nQoP; // Quantity of patterns - purely for reporting
			fwrite("patnxxxx", 8, 1, pFile);
			nPos += 8;
			uint32_t nStartOfBlock = nPos;
			nPos += fileWrite32(it->first, pFile);
			nPos += fileWrite32(it->second.getSteps(), pFile);
			nPos += fileWrite16(it->second.getClocksPerStep(), pFile);
			nPos += fileWrite16(it->second.getStepsPerBeat(), pFile);
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
	uint32_t nQoS = 0; // Quantity of songs - purely for reporting
	uint32_t nQoSeq = 0; // Quantity of sequences - purely for reporting
	for(auto it = m_mSongs.begin(); it != m_mSongs.end(); ++it)
	{
		++nQoS;
		uint32_t nSong = it->first;
		fwrite("songxxxx", 8, 1, pFile);
		nPos += 8;
		uint32_t nStartOfBlock = nPos;
		nPos += fileWrite32(nSong, pFile);
		nPos += fileWrite16(m_mSongs[nSong].getBar(), pFile);
		nPos += fileWrite32(m_mSongs[nSong].getMasterEvents(), pFile);
		for(uint32_t nEvent = 0; nEvent < m_mSongs[nSong].getMasterEvents(); ++nEvent)
		{
			nPos += fileWrite32(m_mSongs[nSong].getMasterEventTime(nEvent), pFile);
			nPos += fileWrite16(m_mSongs[nSong].getMasterEventCommand(nEvent), pFile);
			nPos += fileWrite16(m_mSongs[nSong].getMasterEventData(nEvent), pFile);
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
			printf("SAVE writing quantity of patterns = %d for song %d at file pos %d\n", nPatterns, nSong, nPos);
			fseek(pFile, 0, SEEK_END);
		}
		nBlockSize = nPos - nStartOfBlock;
		fseek(pFile, nStartOfBlock - 4, SEEK_SET);
		fileWrite32(nBlockSize, pFile);
		fseek(pFile, 0, SEEK_END);
	}
	fclose(pFile);
	printf("Saved %d patterns, %d sequences, %d songs to file %s\n", nQoP, nQoSeq, nQoS, filename);
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
	m_mPatterns[destination].setSteps(m_mPatterns[source].getSteps());
	m_mPatterns[destination].setClocksPerStep(m_mPatterns[source].getClocksPerStep());
	m_mPatterns[destination].setStepsPerBeat(m_mPatterns[source].getStepsPerBeat());
	size_t nIndex = 0;
	while(StepEvent* pEvent = m_mPatterns[source].getEventAt(nIndex++))
		m_mPatterns[destination].addEvent(pEvent);
}

Sequence* PatternManager::getSequence(uint32_t sequence)
{
	return &(m_mSequences[sequence]);
}

void PatternManager::updateSequenceLengths()
{
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		it->second.updateLength();
}

void PatternManager::clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync)
{
	/** Get events scheduled for next step from each playing sequence.
		Populate schedule with start, end and interpolated events at sample offset
	*/
	//!@todo Optimise to only send clock to active sequences
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
	{
		if(it->second.clock(nTime, bSync))
		{
			while(SEQ_EVENT* pEvent = it->second.getEvent())
			{
				while(pSchedule->find(pEvent->time) != pSchedule->end())
					++(pEvent->time);
				(*pSchedule)[pEvent->time] = new MIDI_MESSAGE(pEvent->msg);
				//printf("Scheduling event 0x%x 0x%x 0x%x at %d\n", pEvent->msg.command, pEvent->msg.value1, pEvent->msg.value2, pEvent->time);
			}
		}
	}
}

void PatternManager::setSequenceClockRates(uint32_t samples)
{
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		it->second.setClockRate(samples);
}

void PatternManager::setPlayPosition(uint32_t position)
{
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		it->second.setPlayPosition(position);
}

Song* PatternManager::getSong(size_t index)
{
	return &(m_mSongs[index]);
}

void PatternManager::addTrack(uint32_t song)
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
	m_mSongs[song].addTrack(nSequence);
	m_mSongSequences[nSequence] = song;
}

void PatternManager::removeTrack(uint32_t song, uint32_t track)
{
	uint32_t sequence = m_mSongs[song].getSequence(track);
	if(sequence)
	{
		m_mSongSequences.erase(sequence);
		m_mSongs[song].removeTrack(track);
	}
}

void PatternManager::copySong(uint32_t source, uint32_t destination)
{
	if(source == destination)
		return;
	m_mSongs[destination].clear();
	for(uint32_t nEvent = 0; nEvent < m_mSongs[source].getMasterEvents(); ++ nEvent)
		m_mSongs[destination].addMasterEvent(m_mSongs[source].getMasterEventTime(nEvent), m_mSongs[source].getMasterEventCommand(nEvent), m_mSongs[source].getMasterEventData(nEvent));
	m_mSongs[destination].setBar(m_mSongs[source].getBar());
	for(size_t nTrack = 0; nTrack < m_mSongs[source].getTracks(); ++nTrack)
		m_mSongs[destination].addTrack(m_mSongs[source].getSequence(nTrack));
}

void PatternManager::clearSong(uint32_t song)
{
	while(m_mSongs[song].getTracks())
		removeTrack(song, 0);
}

void PatternManager::startSong(uint32_t song)
{
	if(song)
	{
		for(size_t nTrack = 0; nTrack < m_mSongs[song].getTracks(); ++ nTrack)
		{
			uint32_t sequence = m_mSongs[song].getSequence(nTrack);
			m_mSequences[sequence].setPlayState(PLAYING);
		}
	}
}

void PatternManager::stopSong(uint32_t song)
{
	if(song)
	{
		for(size_t nTrack = 0; nTrack < m_mSongs[song].getTracks(); ++ nTrack)
		{
			uint32_t sequence = m_mSongs[song].getSequence(nTrack);
			m_mSequences[sequence].setPlayState(STOPPED);
		}
	}
}

void PatternManager::setSongPosition(uint32_t song, uint32_t pos)
{
	if(song)
	{
		for(size_t nTrack = 0; nTrack < m_mSongs[song].getTracks(); ++ nTrack)
		{
			uint32_t sequence = m_mSongs[song].getSequence(nTrack);
			m_mSequences[sequence].setPlayPosition(pos);
		}
	}
}
