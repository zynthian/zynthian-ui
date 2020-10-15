/**	Sequence class methods implementation **/

#include "sequence.h"

Sequence::Sequence()
{
}

Sequence::~Sequence()
{
}

bool Sequence::addPattern(uint32_t position, Pattern* pattern, bool force)
{
	// Find (and remove) overlapping patterns
	uint32_t nStart = position;
	uint32_t nEnd = nStart + pattern->getLength();
	for(uint32_t nClock = 0; nClock <= position + pattern->getLength(); ++nClock)
	{
		if(m_mPatterns.find(nClock) != m_mPatterns.end())
		{
			Pattern* pPattern = m_mPatterns[nClock];
			uint32_t nExistingStart = nClock;
			uint32_t nExistingEnd = nExistingStart + pPattern->getLength();

			if((nStart >= nExistingStart && nStart < nExistingEnd) || (nEnd > nExistingStart && nEnd <= nExistingEnd))
			{
				if(!force)
					return false;
				// Found overlapping pattern so remove from sequence but don't delete (that is responsibility of PatternManager)
				m_mPatterns.erase(nClock);
				if(m_nCurrentPatternPos == nClock)
					m_nCurrentPatternPos = -1;
			}
		}
	}
	m_mPatterns[position] = pattern;
	if(m_nSequenceLength < position + pattern->getLength())
		m_nSequenceLength = position + pattern->getLength(); //!@todo Does this shrink and stretch song?
	return true;
}

void Sequence::removePattern(uint32_t position)
{
	m_mPatterns.erase(position);
	if(m_nCurrentPatternPos == position)
		m_nCurrentPatternPos = -1;
	updateLength();
}

Pattern* Sequence::getPattern(uint32_t position)
{
	auto it = m_mPatterns.find(position);
	if(it == m_mPatterns.end())
		return NULL;
	return it->second;
}

uint8_t Sequence::getChannel()
{
	return m_nChannel;
}

void Sequence::setChannel(uint8_t channel)
{
	if(channel > 15)
		return;
	m_nChannel = channel;
}

uint8_t Sequence::getOutput()
{
	return m_nOutput;
}

void Sequence::setOutput(uint8_t output)
{
	m_nOutput = output;
}

uint8_t Sequence::getPlayMode()
{
	return m_nMode;
}

void Sequence::setPlayMode(uint8_t mode)
{
	if(mode > LASTPLAYMODE)
		return;
	m_nMode = mode;
}

uint8_t Sequence::getPlayState()
{
	return m_nState;
}

void Sequence::setPlayState(uint8_t state)
{
	if(state > LASTPLAYSTATUS)
		return;
	if(state == STOPPING)
		switch(m_nMode)
		{
			case DISABLED:
			case ONESHOT:
			case LOOP:
				m_nState = STOPPED;
				return;
		}
	else if(state == STARTING)
		m_nDivCount = 0; //!@todo What should div count be?
	if(m_nSequenceLength)
		m_nState = state;
	else
		m_nState = STOPPED;
}

void Sequence::togglePlayState()
{
	if(m_nState == STOPPED || m_nState == STOPPING)
		setPlayState(STARTING);
	else
		setPlayState(STOPPING);
}

bool Sequence::clock(uint32_t nTime, bool bSync)
{
	// Clock cycle - update position and associated counters, status, etc.
	// After this call all counters point to next position
	bool bReturn = false;
	uint8_t nState = m_nState;
	if(bSync && m_nState == STARTING)
		m_nState = PLAYING;
	if(bSync && m_nState == STOPPING && (m_nMode == ONESHOTSYNC || m_nMode == LOOPSYNC))
		m_nState = STOPPED;
	if(m_nState == STOPPED || m_nState == STARTING)
		return bReturn;
	if(m_nDivCount-- == 0)
	{
		// Reached next step
		m_nLastClockTime = nTime;
		m_nDivCount = m_nClkPerStep - 1;
		if(m_nPosition >= m_nSequenceLength)
		{
			// Reached end of sequence
			if(m_nState == STOPPING)
			{
				m_nState = STOPPED;
				return bReturn;
			}
			switch(m_nMode)
			{
				case ONESHOT:
				case DISABLED:
				case ONESHOTALL:
				case ONESHOTSYNC:
					m_nState = STOPPED;
					return bReturn;
				case LOOP:
				case LOOPALL:
				case LOOPSYNC:
					m_nPosition = 0;
					break;
			}
		}

		if(m_mPatterns.find(m_nPosition) != m_mPatterns.end())
		{
			// Playhead at start of pattern
			m_nCurrentPatternPos = m_nPosition;
			m_nCurrentStep = 0;
			m_nNextEvent = 0;
			m_nClkPerStep = m_mPatterns[m_nCurrentPatternPos]->getClocksPerStep();
			if(m_nClkPerStep == 0)
				m_nClkPerStep = 1;
			m_nEventValue = -1;
			bReturn = true;
		}
		else if(m_nCurrentPatternPos >= 0 && m_nPosition >= m_nCurrentPatternPos + m_mPatterns[m_nCurrentPatternPos]->getLength())
		{
			// At end of pattern
			m_nCurrentPatternPos = -1;
			m_nNextEvent = -1;
			m_nCurrentStep = 0;
			m_nClkPerStep = 1;
			m_nEventValue = -1;
		}
		else
		{
			// Within or between pattern
			bReturn = true;
		}
	}
	++m_nPosition;
	if(nState != m_nState && m_nTallyChannel < 16 && m_nTrigger < 128)
	{
		m_bStateChanged = true;
		bReturn = true;
	}
	return bReturn;
}

SEQ_EVENT* Sequence::getEvent()
{
	// This function is called repeatedly for each clock period until no more events are available to populate JACK MIDI output schedule
	static SEQ_EVENT seqEvent; // A MIDI event timestamped for some imminent or future time
	if(m_bStateChanged)
	{
		// Sequence play state changed so send tally
		m_bStateChanged = false;
		seqEvent.time = m_nLastClockTime;
		seqEvent.msg.command = MIDI_NOTE_ON;
		seqEvent.msg.value1 = m_nTrigger;
		switch(m_nState)
		{
			//!@todo Tallies are hard coded to Akai APC but should be configurable, but not within each sequence as that is wasteful. Could expose m_bStateChanged the put logic in PatternManager (or above)
			case STOPPED:
				seqEvent.msg.value2 = 3;
				break;
			case PLAYING:
				seqEvent.msg.value2 = 1;
				break;
			case STOPPING:
				seqEvent.msg.value2 = 4;
				break;
			case STARTING:
				seqEvent.msg.value2 = 5;
				break;
		}
		printf("Sequence::getEvent returning note ON for state change note: %d, velocity: %d\n", seqEvent.msg.value1, seqEvent.msg.value2);
		return &seqEvent;
	}
	if(m_nState == STOPPED || m_nCurrentPatternPos < 0 || m_nNextEvent < 0)
		return NULL;
	// Sequence is being played and playhead is within a pattern
	Pattern* pPattern = m_mPatterns[m_nCurrentPatternPos];
	StepEvent* pEvent = pPattern->getEventAt(m_nNextEvent); // Don't advance event here because need to interpolate
	if(pEvent && pEvent->getPosition() <= m_nCurrentStep)
	{
		// Found event at (or before) this step
		if(m_nEventValue == pEvent->getValue2end())
		{
			// We have reached the end of interpolation so move on to next event
			m_nEventValue = -1;
			pEvent = pPattern->getEventAt(++m_nNextEvent);
			if(!pEvent || pEvent->getPosition() != m_nCurrentStep)
			{
				// No more events or next event is not this step so move to next step
				if(++m_nCurrentStep >= pPattern->getSteps())
					m_nCurrentStep = 0;
				return NULL;
			}
		}
		if(m_nEventValue == -1)
		{
			// Have not yet started to interpolate value
			m_nEventValue = pEvent->getValue2start();
			seqEvent.time = m_nLastClockTime;
		}
		else if(pEvent->getValue2start() == m_nEventValue)
		{
			// Already processed start value
			m_nEventValue = pEvent->getValue2end(); //!@todo Currently just move straight to end value but should interpolate for CC
			seqEvent.time = m_nLastClockTime + pEvent->getDuration() * (pPattern->getClocksPerStep() - 1) * m_nSamplePerClock; // -1 to send note-off one clock before next step
		}
	}
	else
	{
		m_nEventValue = -1;
		if(++m_nCurrentStep >= pPattern->getSteps())
			m_nCurrentStep = 0;
		return NULL;
	}
	seqEvent.msg.command = pEvent->getCommand() | m_nChannel;
	seqEvent.msg.value1 = pEvent->getValue1start();
	seqEvent.msg.value2 = m_nEventValue;
	//printf("sequence::getEvent Event %u,%u,%u at %u currentTime: %u duration: %u clkperstep: %u sampleperclock: %u\n", seqEvent.msg.command, seqEvent.msg.value1, seqEvent.msg.value2, seqEvent.time, m_nLastClockTime, pEvent->getDuration(), pPattern->getClocksPerStep(), m_nSamplePerClock);
	return &seqEvent;
}

uint32_t Sequence::updateLength()
{
	m_nSequenceLength = 0;
	for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
		if(it->first + it->second->getLength() > m_nSequenceLength)
			m_nSequenceLength = it->first + it->second->getLength();
	return m_nSequenceLength;
}

uint32_t Sequence::getLength()
{
	return m_nSequenceLength;
}

void Sequence::clear()
{
	m_mPatterns.clear();
	m_nSequenceLength = 0;
	m_nEventValue = -1;
	m_nCurrentPatternPos = -1;
	m_nNextEvent = -1;
	m_nCurrentStep = 0;
	m_nClkPerStep = 1;
	m_nDivCount = 0;
	m_nPosition = 0;
}

uint32_t Sequence::getStep()
{
	return m_nCurrentStep;
}

void Sequence::setStep(uint32_t step)
{
	if(m_nCurrentPatternPos >= 0 && step < m_mPatterns[m_nCurrentPatternPos]->getSteps())
		m_nCurrentStep = step;
}

uint32_t Sequence::getPatternPlayhead()
{
	return m_nCurrentStep * m_nClkPerStep;
}

uint32_t Sequence::getPlayPosition()
{
	return m_nPosition;
}

void Sequence::setPlayPosition(uint32_t clock)
{
	if(m_mPatterns.size() < 1)
		return;

	// Find if new position is within a pattern
	auto it = m_mPatterns.begin();
	for(; it != m_mPatterns.end(); ++it)
	{
		if(it->first > clock)
			break;
	}
	if(it != m_mPatterns.begin())
		--it;
	Pattern* pPattern = it->second;

	uint32_t nTime = clock - it->first; // Clock cycles since start of last (maybe current) pattern

	if(clock >= it->first + pPattern->getLength())
	{
		// Between patterns
		m_nCurrentPatternPos = -1;
		m_nCurrentStep = 0;
		m_nNextEvent = -1;
		m_nClkPerStep = 1;
		m_nEventValue = -1;
		m_nDivCount = 0;
	}
	else
	{
		// Within pattern
		m_nCurrentPatternPos = it->first;

		m_nClkPerStep = m_mPatterns[m_nCurrentPatternPos]->getClocksPerStep();
		if(m_nClkPerStep == 0)
			m_nClkPerStep = 1;

		m_nDivCount = (clock - m_nCurrentPatternPos) % m_nClkPerStep; // Clocks cycles until next step
		if(m_nDivCount)
			m_nDivCount = m_nClkPerStep - m_nDivCount;

		m_nPosition = clock + m_nDivCount; // Position at next step

		m_nCurrentStep = (clock - m_nCurrentPatternPos) / m_nClkPerStep;

		// Find position of first event in pattern at this step
		m_nNextEvent = -1;
		uint32_t nEvent = 0;
		while(StepEvent* pEvent = pPattern->getEventAt(nEvent++))
		{
			++m_nNextEvent;
			if(pEvent->getPosition() >= m_nCurrentStep)
				break;
		}
	}
}

uint32_t Sequence::getNextPattern(uint32_t previous)
{
	if(m_mPatterns.size() == 0)
		return 0xFFFFFFFF;
	if(previous == 0xFFFFFFFF)
		return m_mPatterns.begin()->first;
	auto it = m_mPatterns.find(previous);
	if(++it == m_mPatterns.end())
		return 0xFFFFFFFF;
	return it->first;
}

void Sequence::setGroup(uint8_t group)
{
    if(group <= 26)
        m_nGroup = group;
}

uint8_t Sequence::getGroup()
{
	return m_nGroup;
}

void Sequence::setTrigger(uint8_t trigger)
{
	if(trigger < 128)
		m_nTrigger = trigger;
	else
		m_nTrigger = 0xFF;
}

uint8_t Sequence::getTrigger()
{
	return m_nTrigger;
}

void Sequence::setMap(uint8_t map)
{
	m_nMap = map;
}

uint8_t Sequence::getMap()
{
	return m_nMap;
}

void Sequence::setTallyChannel(uint8_t channel)
{
	if(channel > 15)
		m_nTallyChannel = 255;
	else
		m_nTallyChannel = channel;
}

uint8_t Sequence::getTallyChannel()
{
	return m_nTallyChannel;
}

void Sequence::solo(bool solo)
{
	m_bSolo = solo;
}

bool Sequence::isSolo()
{
	return m_bSolo;
}
