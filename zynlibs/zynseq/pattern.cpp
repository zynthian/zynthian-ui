#include "pattern.h"

/**	Pattern class methods implementation **/

Pattern::Pattern(uint32_t steps, uint8_t clkPerStep, uint8_t stepsPerBeat, uint8_t beatType) :
	m_nClkPerStep(clkPerStep),
	m_nLength(steps),
	m_nStepsPerBeat(stepsPerBeat),
	m_nBeatType(beatType)
{
}

Pattern::~Pattern()
{
}

StepEvent* Pattern::addEvent(uint32_t position, uint8_t command, uint8_t value1, uint8_t value2, uint32_t duration)
{
	//Delete overlapping events
	for(auto it = m_vEvents.begin(); it!=m_vEvents.end(); ++it)
	{
		uint32_t nEventStart = position;
		uint32_t nEventEnd = nEventStart + duration;
		uint32_t nCheckStart = (*it).getPosition();
		uint32_t nCheckEnd = nCheckStart + (*it).getDuration();
		bool bOverlap = (nCheckStart >= nEventStart && nCheckStart < nEventEnd) || (nCheckEnd > nEventStart && nCheckEnd <= nEventEnd);
		if(bOverlap && (*it).getCommand() == command && (*it).getValue1start() == value1)
		{
			it = m_vEvents.erase(it) - 1;
			if(it == m_vEvents.end())
				break;
		}
	}
	uint32_t nTime = position % m_nLength;
	auto it = m_vEvents.begin();
	for(; it != m_vEvents.end(); ++it)
	{
		if((*it).getPosition() > position)
			break;
	}
	auto itInserted = m_vEvents.insert(it, StepEvent(position, command, value1, value2, duration));
	return &(*itInserted);
};

StepEvent* Pattern::addEvent(StepEvent* pEvent)
{
	StepEvent* pNewEvent = addEvent(pEvent->getPosition(), pEvent->getCommand(), pEvent->getValue1start(), pEvent->getValue2start(), pEvent->getDuration());
	pNewEvent->setValue1end(pEvent->getValue1end());
	pNewEvent->setValue2end(pEvent->getValue2end());
	return pNewEvent;
}

void Pattern::deleteEvent(uint32_t position, uint8_t command, uint8_t value1)
{
	for(auto it = m_vEvents.begin(); it!=m_vEvents.end(); ++it)
	{
		if((*it).getPosition() == position && (*it).getCommand() == command && (*it).getValue1start() == value1)
		{
			m_vEvents.erase(it);
			return;
		}
	}
}

void Pattern::addNote(uint32_t step, uint8_t note, uint8_t velocity, uint32_t duration)
{
	//!@todo Should we limit note length to size of pattern?
	if(step >= m_nLength || note > 127 || velocity > 127 || duration > m_nLength)
		return;
	addEvent(step, MIDI_NOTE_ON, note, velocity, duration);
}

void Pattern::removeNote(uint32_t step, uint8_t note)
{
	deleteEvent(step, MIDI_NOTE_ON, note);
}

uint8_t Pattern::getNoteVelocity(uint32_t step, uint8_t note)
{
	for(auto it = m_vEvents.begin(); it!=m_vEvents.end(); ++it)
	{
		if((*it).getPosition() == step && (*it).getCommand() == MIDI_NOTE_ON && (*it).getValue1start() == note)
		return (*it).getValue2start();
	}
	return 0;
}

void Pattern::setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity)
{
	if(velocity > 127)
		return;
	for(auto it = m_vEvents.begin(); it!=m_vEvents.end(); ++it)
	{
		if((*it).getPosition() == step && (*it).getCommand() == MIDI_NOTE_ON && (*it).getValue1start() == note)
			(*it).setValue2start(velocity);
	}
}

uint8_t Pattern::getNoteDuration(uint32_t step, uint8_t note)
{
	if(step >= m_nLength)
		return 0;
	for(auto it = m_vEvents.begin(); it!=m_vEvents.end(); ++it)
	{
		if((*it).getPosition() != step || (*it).getCommand() != MIDI_NOTE_ON || (*it).getValue1start() != note)
			continue;
		return (*it).getDuration();
	}
	return 0;
}

void Pattern::addControl(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd, uint32_t duration)
{
	uint32_t nDuration = duration;
	if(step > m_nLength || control > 127 || valueStart > 127|| valueEnd > 127 || nDuration > m_nLength)
		return;
	StepEvent* pControl = new StepEvent(step, control, valueStart, nDuration);
	pControl->setValue2end(valueEnd);
	StepEvent* pEvent = addEvent(step, MIDI_CONTROL, control, valueStart, nDuration);
	pEvent->setValue2end(valueEnd);
}

void Pattern::removeControl(uint32_t step, uint8_t control)
{
	deleteEvent(step, MIDI_CONTROL, control);
}

uint8_t Pattern::getControlDuration(uint32_t step, uint8_t control)
{
	//!@todo Implement getControlDuration
	return 0;
}

void Pattern::setSteps(uint32_t steps)
{
	uint32_t length = steps;
	size_t nIndex = 0;
	for(; nIndex < m_vEvents.size(); ++nIndex)
		if(m_vEvents[nIndex].getPosition() >= length)
			break;
	m_vEvents.resize(nIndex);
	m_nLength = length;
}

uint32_t Pattern::getSteps()
{
	return m_nLength;
}

void Pattern::setBeatType(uint8_t beatType)
{
	printf("Pattern::setBeatType(%u)\n", beatType);
	for(uint8_t nValue = 1; nValue <= 64; nValue = nValue << 1)
    {
        if(beatType > nValue)
            continue;
		m_nBeatType = nValue;
        setClocksPerStep(96 / (m_nStepsPerBeat * m_nBeatType)); //!@todo This might need more attention
        return;
    }
}

uint8_t Pattern::getBeatType()
{
	return m_nBeatType;
}

uint32_t Pattern::getLength()
{
	return m_nLength * m_nClkPerStep;
}

void Pattern::setClocksPerStep(uint32_t value)
{
	if(value < 0xFF)
		m_nClkPerStep = value;
	//!@todo quantize events
}

uint32_t Pattern::getClocksPerStep()
{
	return m_nClkPerStep;
}

void Pattern::setStepsPerBeat(uint32_t value)
{
	switch(value)
	{
		case 1:
		case 2:
		case 3:
		case 4:
		case 6:
		case 8:
		case 12:
		case 24:
			m_nStepsPerBeat = value;
			setClocksPerStep(96 / (m_nStepsPerBeat * m_nBeatType));
		break;
	}
}

uint32_t Pattern::getStepsPerBeat()
{
	return m_nStepsPerBeat;
}

void Pattern::setScale(uint8_t scale)
{
	m_nScale = scale;
}

uint8_t Pattern::getScale()
{
	return m_nScale;
}

void Pattern::setTonic(uint8_t tonic)
{
	m_nTonic = tonic;
}

uint8_t Pattern::getTonic()
{
	return m_nTonic;
}

void Pattern::transpose(int value)
{
	// Check if any notes will be transposed out of MIDI note range (0..127)
	for(auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it)
	{
		if((*it).getCommand() != MIDI_NOTE_ON)
			continue;
		int note = (*it).getValue1start() + value;
		if(note > 127 || note < 0)
			return;
	}

	for(auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it)
	{
		if((*it).getCommand() != MIDI_NOTE_ON)
			continue;
		int note = (*it).getValue1start() + value;
		if(note > 127 || note < 0)
		{
			// Delete notes that have been pushed out of range
			//!@todo Should we squash notes that are out of range back in at ends? I don't think so.
			m_vEvents.erase(it);
		}
		else
		{
			(*it).setValue1start(note);
			(*it).setValue1end(note);
		}
	}
}

void Pattern::clear()
{
	m_vEvents.clear();
}

StepEvent* Pattern::getEventAt(uint32_t index)
{
	if(index >= m_vEvents.size())
		return NULL;
	return &(m_vEvents[index]);
}
