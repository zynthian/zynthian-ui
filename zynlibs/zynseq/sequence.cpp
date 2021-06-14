#include "sequence.h"

Sequence::Sequence()
{
    addTrack(); // Ensure new sequences have at least one track
}

uint8_t Sequence::getGroup()
{
    return m_nGroup;
}

void Sequence::setGroup(uint8_t group)
{
    if(m_nGroup == group)
        return;
    m_nGroup = group;
    m_bChanged = true;
}

uint32_t Sequence::addTrack(uint32_t track)
{
    auto it = m_vTracks.begin();
    uint32_t nReturn = ++track;
    if(track == -1 || track >= m_vTracks.size())
    {
        m_vTracks.emplace_back();
        nReturn = m_vTracks.size() - 1;
    }
    else
        m_vTracks.emplace(it + track);
    m_bChanged = true;
    return nReturn;
}

bool Sequence::removeTrack(size_t track)
{
    if(track >= m_vTracks.size())
        return false;
    if(m_vTracks.size() < 2)
        return false;
    m_vTracks.erase(m_vTracks.begin() + track);
    m_bChanged = true;
    return true;
}

size_t Sequence::getTracks()
{
    return m_vTracks.size();
}

void Sequence::clear()
{
    if(m_vTracks.size())
        m_bChanged = true;
    m_vTracks.clear();
    addTrack();
    m_nLength = 0;
}

Track* Sequence::getTrack(size_t index)
{
    if(index < m_vTracks.size())
        return &(m_vTracks[index]);
    return NULL;
}

void Sequence::addTempo(uint16_t tempo, uint16_t bar, uint16_t tick)
{
    m_timebase.addTimebaseEvent(bar, tick, TIMEBASE_TYPE_TEMPO, tempo);
    m_bChanged = true;
}

uint16_t Sequence::getTempo(uint16_t bar, uint16_t tick)
{
    return m_timebase.getTempo(bar, tick);
}

void Sequence::addTimeSig(uint16_t beatsPerBar, uint16_t bar)
{
    if(bar < 1)
        bar = 1;
    m_timebase.addTimebaseEvent(bar, 0, TIMEBASE_TYPE_TIMESIG, beatsPerBar);
    m_bChanged = true;
}

uint16_t Sequence::getTimeSig(uint16_t bar)
{
    if(bar < 1)
        bar = 1;
    TimebaseEvent* pEvent = m_timebase.getPreviousTimebaseEvent(bar, 1, TIMEBASE_TYPE_TIMESIG);
    if(pEvent)
        return pEvent->value;
    return 4;
}

Timebase* Sequence::getTimebase()
{
    //!@todo Optimise timebase - only add a timebase track as required
    return &m_timebase;
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
        m_nState = STOPPED;
    m_bChanged = true;
}

uint8_t Sequence::getPlayState()
{
    return m_nState;
}

void Sequence::setPlayState(uint8_t state)
{
    uint8_t nState = m_nState;
    if(m_nMode == DISABLED)
        state = STOPPED;
    if(state == m_nState)
        return;
    if(m_nMode == ONESHOT && state == STOPPING)
        state = STOPPED;
    m_nState = state;
    if(m_nState == STOPPED)
        if(m_nMode == ONESHOT)
        {
            m_nPosition = m_nLastSyncPos;
            for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
                (*it).setPosition(m_nPosition);
        }
        else
            m_nPosition = 0;
    m_bStateChanged |= (nState != m_nState);
    m_bChanged = true;
}

uint8_t Sequence::clock(uint32_t nTime, bool bSync, double dSamplesPerClock)
{
    m_nCurrentTrack = 0;
    uint8_t nReturn = 0;
    uint8_t nState = m_nState;
    if(bSync)
    {
        if(m_nMode == ONESHOTSYNC && m_nState != STARTING)
            m_nState = STOPPED;
        if(m_nState == STARTING)
            m_nState = PLAYING;
        if(m_nState == RESTARTING)
        {
            m_nState = PLAYING;
            nState = PLAYING;
        }
        if(m_nState == STOPPING && m_nMode == LOOPSYNC)
            m_nState = STOPPED;
        if(m_nMode == ONESHOTSYNC || m_nMode == LOOPSYNC)
            m_nPosition = 0;
        m_nLastSyncPos = m_nPosition;
    }
    else if(m_nState == RESTARTING)
        m_nState = STARTING;

    if(m_nState == PLAYING || m_nState == STOPPING)
    {
        // Still playing so iterate through tracks
        for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
            nReturn |= (*it).clock(nTime, m_nPosition, dSamplesPerClock, bSync);
        ++m_nPosition;
    }
    if(m_nPosition >= m_nLength)
    {
        // End of sequence
        switch(m_nMode)
        {
            case ONESHOT:
            case ONESHOTALL:
            case ONESHOTSYNC:
                setPlayState(STOPPED);
                break;
            case LOOPSYNC:
            case LOOPALL:
                if(m_nState == PLAYING)
                {
                    m_nState = RESTARTING;
                    nState = RESTARTING;
                }
            case LOOP:
                if(m_nState == STOPPING)
                    setPlayState(STOPPED);
        }
        m_nPosition = 0;
        m_nLastSyncPos = 0;
    }

    m_bStateChanged |= (nState != m_nState);
    if(m_bStateChanged)
    {
        m_bChanged |= true;
        m_bStateChanged = false;
        return nReturn | 2;
    }
    return nReturn;
}

SEQ_EVENT* Sequence::getEvent()
{
    // This function is called repeatedly for each clock period until no more events are available to populate JACK MIDI output schedule
    if(m_nState == STOPPED || m_nState == STARTING)
        return NULL; //!@todo Can we stop between note on and note off being processed resulting in stuck note?

    SEQ_EVENT* pEvent;
    while(m_nCurrentTrack < m_vTracks.size())
    {
        pEvent = m_vTracks[m_nCurrentTrack].getEvent();
        if(pEvent)
            return pEvent;
        ++m_nCurrentTrack;
    }
    return NULL;
}

void Sequence::updateLength()
{
    m_nLength = 0;
    for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
    {
        uint32_t nTrackLength = (*it).updateLength();
        if(nTrackLength > m_nLength)
            m_nLength = nTrackLength;
    }
}

uint32_t Sequence::getLength()
{
    return m_nLength;
}

void Sequence::setPlayPosition(uint32_t position)
{
    m_nPosition = position;
}

uint32_t Sequence::getPlayPosition()
{
    return m_nPosition;
}

bool Sequence::hasChanged()
{
    bool bChanged = m_bChanged;
    for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
        bChanged |= (*it).hasChanged();
    m_bChanged = false;
    return bChanged;
}

void Sequence::setName(std::string sName)
{
    m_sName = sName;
    m_sName.resize(16);
}

std::string Sequence::getName()
{
    return m_sName;
}

