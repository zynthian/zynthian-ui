/**    Track class methods implementation **/

#include "track.h"

bool Track::addPattern(uint32_t position, Pattern* pattern, bool force)
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
                // Found overlapping pattern so remove from track but don't delete (that is responsibility of PatternManager)
                m_mPatterns.erase(nClock);
                if(m_nCurrentPatternPos == nClock)
                    m_nCurrentPatternPos = -1;
            }
        }
    }
    m_mPatterns[position] = pattern;
    if(m_nTrackLength < position + pattern->getLength())
        m_nTrackLength = position + pattern->getLength(); //!@todo Does this shrink and stretch song?
    return true;
}

void Track::removePattern(uint32_t position)
{
    m_mPatterns.erase(position);
    if(m_nCurrentPatternPos == position)
        m_nCurrentPatternPos = -1;
    updateLength();
}

Pattern* Track::getPattern(uint32_t position)
{
    auto it = m_mPatterns.find(position);
    if(it == m_mPatterns.end())
        return NULL;
    return it->second;
}

Pattern* Track::getPatternAt(uint32_t position)
{
    for(auto it = m_mPatterns.begin(); it!= m_mPatterns.end(); ++it)
    {
        if(it->first <= position && position + 1 < it->first + it->second->getLength() )
            return it->second;
    }
    return NULL;
}

uint8_t Track::getChannel()
{
    return m_nChannel;
}

void Track::setChannel(uint8_t channel)
{
    if(channel > 15)
        return;
    m_nChannel = channel;
}

uint8_t Track::getOutput()
{
    return m_nOutput;
}

void Track::setOutput(uint8_t output)
{
    m_nOutput = output;
}

uint8_t Track::clock(uint32_t nTime, uint32_t nPosition, double dSamplesPerClock, bool bSync)
{
    if(m_nTrackLength == 0)
        return 0;
	if(m_bMute)
		return 0;
    uint8_t nReturn = 0;
    m_dSamplesPerClock = dSamplesPerClock;

    if(m_mPatterns.find(nPosition) != m_mPatterns.end())
    {
        //printf("Start of pattern\n");
        // Playhead at start of pattern
        m_nCurrentPatternPos = nPosition;
        m_nCurrentStep = 0;
        m_nNextEvent = 0;
        m_nClkPerStep = m_mPatterns[m_nCurrentPatternPos]->getClocksPerStep();
        if(m_nClkPerStep == 0)
            m_nClkPerStep = 1;
        m_nEventValue = -1;
        m_nDivCount = m_nClkPerStep; // Trigger first step immediately
        //printf("m_nCurrentPatternPos: %u m_nClkPerStep: %u\n", m_nCurrentPatternPos, m_nClkPerStep);
    }
    else if(m_nCurrentPatternPos >= 0 && nPosition >= m_nCurrentPatternPos + m_mPatterns[m_nCurrentPatternPos]->getLength())
    {
        //printf("End of pattern\n");
        // At end of pattern
        m_nCurrentPatternPos = -1;
        m_nNextEvent = -1;
        m_nCurrentStep = 0;
        m_nClkPerStep = 1;
        m_nEventValue = -1;
        m_nDivCount = 0;
    }
    
    if(m_nCurrentPatternPos >= 0 && m_nDivCount == m_nClkPerStep)
    {
        //printf("Reached next step \n");
        // Reached next step
        m_nLastClockTime = nTime;
        m_nDivCount = 0;
        nReturn = 1;
    }

    ++m_nDivCount;
    return nReturn;
}

SEQ_EVENT* Track::getEvent()
{
    // This function is called repeatedly for each clock period until no more events are available to populate JACK MIDI output schedule
    static SEQ_EVENT seqEvent; // A MIDI event timestamped for some imminent or future time
    if(m_nCurrentPatternPos < 0 || m_nNextEvent < 0)
        return NULL; //!@todo Can we stop between note on and note off being processed resulting in stuck note?
    // Track is being played and playhead is within a pattern
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
            seqEvent.time = m_nLastClockTime + pEvent->getDuration() * pPattern->getClocksPerStep() * m_dSamplesPerClock - 1; // -1 to send note-off one sample before next step
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
    //printf("Track::getEvent Scheduled event %u,%u,%u at %u currentTime: %u duration: %u clkperstep: %u sampleperclock: %f event position: %u\n", seqEvent.msg.command, seqEvent.msg.value1, seqEvent.msg.value2, seqEvent.time, m_nLastClockTime, pEvent->getDuration(), pPattern->getClocksPerStep(), m_dSamplesPerClock, pEvent->getPosition());
    return &seqEvent;
}

uint32_t Track::updateLength()
{
    m_nTrackLength = 0;
    for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        if(it->first + it->second->getLength() > m_nTrackLength)
            m_nTrackLength = it->first + it->second->getLength();
    return m_nTrackLength;
}

uint32_t Track::getLength()
{
    return m_nTrackLength;
}

void Track::clear()
{
    m_mPatterns.clear();
    m_nTrackLength = 0;
    m_nEventValue = -1;
    m_nCurrentPatternPos = -1;
    m_nNextEvent = -1;
    m_nCurrentStep = 0;
    m_nClkPerStep = 1;
    m_nDivCount = 0;
}

uint32_t Track::getPatternPlayhead()
{
    return m_nCurrentStep;
}


void Track::setPatternPlayhead(uint32_t step)
{
    if(m_nCurrentPatternPos >= 0 && step < m_mPatterns[m_nCurrentPatternPos]->getSteps())
        m_nCurrentStep = step;
//    printf("Track::setPatternPlayhead(step=%u) m_nCurrentPatternPos:%u steps in pattern: %u m_nCurrentStep:%u\n", step, m_nCurrentPatternPos, m_mPatterns[m_nCurrentPatternPos]->getSteps(),  m_nCurrentStep);
}


void Track::setPosition(uint32_t position)
{
    m_nDivCount = m_nClkPerStep;
    m_nCurrentStep = position / m_nClkPerStep;
    m_nNextEvent = -1; // Avoid playing wrong pattern
    for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
    {
        if(it->first <= position && it->first + it->second->getLength() > position)
        {
            // Found pattern that spans position
            m_nCurrentPatternPos = it->first;
            break;
        }
    }
}

uint32_t Track::getNextPattern(uint32_t previous)
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

size_t Track::getPatterns()
{
    return m_mPatterns.size();
}

void Track::setMap(uint8_t map)
{
    m_nMap = map;
}

uint8_t Track::getMap()
{
    return m_nMap;
}

void Track::solo(bool solo)
{
    m_bSolo = solo;
}

bool Track::isSolo()
{
    return m_bSolo;
}

void Track::mute(bool mute)
{
    m_bMute = mute;
    m_nEventValue = -1;
    m_nCurrentPatternPos = -1;
    m_nNextEvent = -1;
}

bool Track::isMuted()
{
    return m_bMute;
}

bool Track::hasChanged()
{
    bool bState = m_bChanged;
    m_bChanged = false;
    return bState;
}

Pattern* Track::getPatternByIndex(size_t index)
{
    size_t nIndex = 0;
    for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
    {
        if(index == nIndex)
            return it->second;
        ++nIndex;
    }
    return NULL;
}

uint32_t Track::getPatternPositionByIndex(size_t index)
{
    if(index >= m_mPatterns.size())
        return -1;
    auto it = m_mPatterns.begin();
    while(index--)
        ++it;
    return it->first;
}

uint32_t Track::getPatternPosition(Pattern* pattern)
{
    for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
    {
        if(it->second == pattern)
            return it->first;
    }
    return -1;
}
