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
	if(m_nMode == DISABLED)
	{
		m_nState = STOPPED;
		m_bStateChanged = true;
	}
	m_bChanged = true;
}

uint8_t Sequence::getPlayState()
{
	return m_nState;
}

void Sequence::setPlayState(uint8_t state)
{
	if(state > LASTPLAYSTATUS || m_nMode == DISABLED || state == m_nState)
		return;
	m_bStateChanged = true;
	m_bChanged = true;
	if(state == STOPPING)
		switch(m_nMode)
		{
			case ONESHOT:
			case LOOP:
				m_nState = STOPPED;
				return;
		}
	else if(state == STARTING)
		setPlayPosition(0); // Set to start of sequence when starting
	else if(state == PLAYING)
		setPlayPosition(0); // Resume when playing
//		m_nDivCount = 0; //!@todo What should div count be?
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

uint8_t Sequence::clock(uint32_t nTime, bool bSync, double dSamplesPerClock)
{
	// Clock cycle - update position and associated counters, status, etc.
	// After this call all counters point to next position
	// Events are triggered when m_nDivCount. Step is incremented after this so the countdown occurs whilst m_nCurrentStep is already set.
	// nTime has absolute time and provides info to populate events with times that signal JACK main audio callback when to trigger events
	m_dSamplesPerClock = dSamplesPerClock;
	uint8_t nReturn = 0;
	uint8_t nState = m_nState;
	if(bSync && m_nState == STARTING)
	{
		m_nState = PLAYING;
		m_bChanged = true;
	}
	if(bSync && m_nState == STOPPING && m_nMode != ONESHOTALL && m_nMode != LOOPALL)
	{
		m_nState = STOPPED;
		m_bChanged = true;
	}
	if(m_nState != STOPPED && m_nState != STARTING)
	{
		//printf("Sequence clocked at %u. Step: %u m_nDivCount: %u m_nClkPerStep: %u\n", m_nPosition, m_nCurrentStep, m_nDivCount, m_nClkPerStep);
		if(m_nDivCount == 0)
		{
			// Reached next step
			m_nLastClockTime = nTime;
			if(m_nPosition >= m_nSequenceLength || (bSync && m_nMode == LOOPSYNC))
			{
				//printf("Reached end of sequence\n");
				// Reached end of sequence
				if(m_nState == STOPPING)
				{
					m_nState = STOPPED;
					m_nPosition = 0;
					m_bStateChanged = true;
					m_bChanged = true;
					return true;
				}
				switch(m_nMode)
				{
					case ONESHOT:
					case DISABLED:
					case ONESHOTALL:
					case ONESHOTSYNC:
						m_nState = STOPPED;
						m_nPosition = 0;
						m_bStateChanged = true;
						m_bChanged = true;
						return true;
					case LOOP:
					case LOOPALL:
					case LOOPSYNC:
						m_nPosition = 0;
						break;
				}
			}

			if(m_mPatterns.find(m_nPosition) != m_mPatterns.end())
			{
				//printf("Start of pattern\n");
				// Playhead at start of pattern
				m_nCurrentPatternPos = m_nPosition;
				m_nCurrentStep = 0;
				m_nNextEvent = 0;
				m_nClkPerStep = m_mPatterns[m_nCurrentPatternPos]->getClocksPerStep();
				if(m_nClkPerStep == 0)
					m_nClkPerStep = 1;
				m_nEventValue = -1;
				nReturn = 1;
				//printf("m_nCurrentPatternPos: %u m_nClkPerStep: %u\n", m_nCurrentPatternPos, m_nClkPerStep);
			}
			else if(m_nCurrentPatternPos >= 0 && m_nPosition >= m_nCurrentPatternPos + m_mPatterns[m_nCurrentPatternPos]->getLength())
			{
				//printf("End of pattern\n");
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
				nReturn = 1;
			}
			m_nDivCount = m_nClkPerStep;
		}
		--m_nDivCount;
		++m_nPosition;
	}
	if(nState != m_nState || m_bStateChanged)
	{
		m_bStateChanged = false;
		return nReturn | 2;
	}
	return nReturn;
}

SEQ_EVENT* Sequence::getEvent()
{
	// This function is called repeatedly for each clock period until no more events are available to populate JACK MIDI output schedule
	static SEQ_EVENT seqEvent; // A MIDI event timestamped for some imminent or future time
	if(m_nState == STOPPED || m_nState == STARTING || m_nCurrentPatternPos < 0 || m_nNextEvent < 0)
		return NULL; //!@todo Can we stop between note on and note off being processed resulting in stuck note?
	
	//!@todo If STOPPING then the next event is found even if not on this clock cycle
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
			seqEvent.time = m_nLastClockTime + pEvent->getDuration() * (pPattern->getClocksPerStep() - 1) * m_dSamplesPerClock; // -1 to send note-off one clock before next step
			//printf("Scheduling note off. Event duration: %u, clocks per step: %u, samples per clock: %u\n", pEvent->getDuration(), pPattern->getClocksPerStep(), m_nSamplePerClock);
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
	//printf("sequence::getEvent Scheduled event %u,%u,%u at %u currentTime: %u duration: %u clkperstep: %u sampleperclock: %f event position: %u\n", seqEvent.msg.command, seqEvent.msg.value1, seqEvent.msg.value2, seqEvent.time, m_nLastClockTime, pEvent->getDuration(), pPattern->getClocksPerStep(), m_dSamplesPerClock, pEvent->getPosition());
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
	//!@todo Is this used?
	return m_nCurrentStep * m_nClkPerStep;
}

uint32_t Sequence::getPlayPosition()
{
	return m_nPosition;
}

void Sequence::setPlayPosition(uint32_t clock)
{
	m_nPosition = clock;
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

	if(clock >= it->first + pPattern->getLength() || clock < it->first)
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
	m_nGroup = group;
	m_bChanged = true;
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

bool Sequence::hasChanged()
{
	bool bState = m_bChanged;
	m_bChanged = false;
	return bState;
}