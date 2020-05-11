#include "patternmanager.h"
#include <cstring>

/**	PatternManager class methods implementation **/

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
	FILE *pFile;
	pFile = fopen(filename, "r");
	if(pFile == NULL)
	{
		fprintf(stderr, "ERROR: PatternManager failed to open file for load %s\n", filename);
		return;
	}
	size_t nPos = 0;
	char sHeader[4];
	// Iterate each block within RIFF file
	while(fread(sHeader, 4, 1, pFile) == 1)
	{
		// Assume found RIFF header
		uint32_t nBlockSize = fileRead32(pFile);
		if(memcmp(sHeader, "patn", 4) == 0)
		{
			if(nBlockSize < 12)
				continue;
			Pattern* pPattern = getPattern(fileRead32(pFile));
			pPattern->setSteps(fileRead32(pFile));
			uint32_t nValue = fileRead32(pFile);
			pPattern->setClockDivisor(nValue & 0xFF);
			pPattern->setStepsPerBeat(nValue >> 16);
			nPos += 12;
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
				nPos += 14;
			}
		}
		else if(memcmp(sHeader, "seq ", 4) == 0)
		{
			if(nBlockSize < 12)
				continue;
			uint32_t nSequence = fileRead32(pFile);
			uint8_t nChannel = fileRead8(pFile);
			uint8_t nOutput = fileRead8(pFile);
			m_mSequences[nSequence].setChannel(nChannel);
			m_mSequences[nSequence].setOutput(nOutput);
			nPos += 6;
			nBlockSize -= 6;
			while(nBlockSize)
			{
				uint32_t nTime = fileRead32(pFile);
				uint32_t nPattern = fileRead32(pFile);
				m_mSequences[nSequence].addPattern(nTime, getPattern(nPattern));
				nPos += 8;
				nBlockSize -= 8;
			}
		}
	}
	fclose(pFile);
	printf("Loaded %lu patterns and %lu sequences from file %s\n", m_mPatterns.size(), m_mSequences.size(), filename);
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
			nPos += fileWrite32((*it).first, pFile);
			nPos += fileWrite32((*it).second.getSteps(), pFile);
			nPos += fileWrite32((*it).second.getClockDivisor() | (((*it).second.getStepsPerBeat()) << 16), pFile);
			size_t nEvent = 0;
			while(StepEvent* pEvent = (*it).second.getEventAt(nEvent++))
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
	// Iterate through sequences
	uint32_t nQoS = 0; // Quantity of sequences - purely for reporting
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
	{
		++nQoS;
		fwrite("seq xxxx", 8, 1, pFile);
		nPos += 8;
		uint32_t nStartOfBlock = nPos;
		nPos += fileWrite32((*it).first, pFile);
		nPos += fileWrite8((*it).second.getChannel(), pFile);
		nPos += fileWrite8((*it).second.getOutput(), pFile);
		nBlockSize = nPos - nStartOfBlock;
		fseek(pFile, nStartOfBlock - 4, SEEK_SET);
		fileWrite32(nBlockSize, pFile);
		fseek(pFile, 0, SEEK_END);
	}
	fclose(pFile);
	printf("Saved %d patterns and %d sequences to file %s\n", nQoP, nQoS, filename);
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
	return 0; //!@todo PatternManager::getPatternIndex should return NOT_FOUND
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

void PatternManager::copyPattern(Pattern* source, Pattern* destination)
{
	if(!source || ! destination)
		return;
	destination->clear();
	destination->setSteps(source->getSteps());
	destination->setClockDivisor(source->getClockDivisor());
	size_t nIndex = 0;
	while(StepEvent* pEvent = source->getEventAt(nIndex++))
		destination->addEvent(pEvent);
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

void PatternManager::clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule)
{
	/**	Get events scheduled for next step from each playing sequence.
		Populate schedule with start, end and interpolated events at sample offset
	*/
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
	{
		if(it->second.clock(nTime))
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

void PatternManager::setSequenceClockRates(uint32_t tempo, uint32_t samplerate)
{
	for(auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
		it->second.setClockRate(tempo, samplerate);
}
