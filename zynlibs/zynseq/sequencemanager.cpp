#include "sequencemanager.h"
#include <cstring>

/** SequenceManager class methods implementation **/

SequenceManager::SequenceManager()
{
    init();
}

void SequenceManager::init()
{
    stop();
    m_mPatterns.clear();
    m_mTriggers.clear();
    for(auto itBank = m_mBanks.begin(); itBank != m_mBanks.end(); ++itBank)
        for(auto itSeq = itBank->second.begin(); itSeq != itBank->second.end(); ++itSeq)
            delete (*itSeq);
    m_mBanks.clear();
}

int SequenceManager::fileWrite32(uint32_t value, FILE *pFile)
{
    for(int i = 3; i >=0; --i)
        fileWrite8((value >> i * 8), pFile);
    return 4;
}

int SequenceManager::fileWrite16(uint16_t value, FILE *pFile)
{
    for(int i = 1; i >=0; --i)
        fileWrite8((value >> i * 8), pFile);
    return 2;
}

int SequenceManager::fileWrite8(uint8_t value, FILE *pFile)
{
    int nResult = fwrite(&value, 1, 1, pFile);
    return 1;
}

uint8_t SequenceManager::fileRead8(FILE* pFile)
{
    uint8_t nResult = 0;
    fread(&nResult, 1, 1, pFile);
    return nResult;
}

uint16_t SequenceManager::fileRead16(FILE* pFile)
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

uint32_t SequenceManager::fileRead32(FILE* pFile)
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

bool SequenceManager::checkBlock(FILE* pFile, uint32_t nActualSize,  uint32_t nExpectedSize)
{
    if(nActualSize < nExpectedSize)
    {
        for(size_t i = 0; i < nActualSize; ++i)
            fileRead8(pFile);
        return true;
    }
    return false;
}

Pattern* SequenceManager::getPattern(uint32_t index)
{
    return &(m_mPatterns[index]);
}

uint32_t SequenceManager::getPatternIndex(Pattern* pattern)
{
    for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        if(&(it->second) == pattern)
            return it->first;
    return -1; //NOT_FOUND
}

uint32_t SequenceManager::getNextPattern(uint32_t pattern)
{
    auto it = m_mPatterns.find(pattern);
    if(it == m_mPatterns.end() || ++it == m_mPatterns.end())
        return -1;
    return it->first;
}

uint32_t SequenceManager::createPattern()
{
    uint32_t nSize = m_mPatterns.size();
    for(uint32_t nIndex = 1; nIndex <= nSize; ++nIndex)
    {
        if(m_mPatterns.find(nIndex) != m_mPatterns.end())
            continue;
        m_mPatterns[nIndex]; // Insert a default pattern
        return nIndex;
    }
    m_mPatterns[++nSize]; // Append a default pattern
    return nSize;
}

void SequenceManager::deletePattern(uint32_t index)
{
    m_mPatterns.erase(index);
}

void SequenceManager::copyPattern(uint32_t source, uint32_t destination)
{
    if(source == destination)
        return;
    m_mPatterns[destination].clear();
    m_mPatterns[destination].setBeatsInPattern(m_mPatterns[source].getBeatsInPattern());
    m_mPatterns[destination].setStepsPerBeat(m_mPatterns[source].getStepsPerBeat());
    uint32_t nIndex = 0;
    while(StepEvent* pEvent = m_mPatterns[source].getEventAt(nIndex++))
        m_mPatterns[destination].addEvent(pEvent);
}

Sequence* SequenceManager::getSequence(uint8_t bank, uint8_t sequence)
{
    // Add missing sequences
    while(m_mBanks[bank].size() <= sequence)
        m_mBanks[bank].push_back(new Sequence());
    return m_mBanks[bank][sequence];
}

bool SequenceManager::addPattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force)
{
    Sequence* pSequence = getSequence(bank, sequence);
    Track* pTrack = pSequence->getTrack(track);
    if(!pTrack)
        return false;
    bool bUpdated = pTrack->addPattern(position, &(m_mPatterns[pattern]), force);
    updateSequenceLength(bank, sequence);
    return bUpdated;
}

void SequenceManager::removePattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position)
{
    Sequence* pSequence = getSequence(bank, sequence);
    Track* pTrack = pSequence->getTrack(track);
    if(!pTrack)
        return;
    pTrack->removePattern(position);
    updateSequenceLength(bank, sequence);
}

void SequenceManager::updateSequenceLength(uint8_t bank, uint8_t sequence)
{
    getSequence(bank, sequence)->updateLength();
}

void SequenceManager::updateAllSequenceLengths()
{
    for(auto itBank = m_mBanks.begin(); itBank != m_mBanks.end(); ++itBank)
        for(auto itSeq = itBank->second.begin(); itSeq != itBank->second.end(); ++itSeq)
            (*itSeq)->updateLength();
}

size_t SequenceManager::clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync, double dSamplesPerClock)
{
    /** Get events scheduled for next step from all tracks in each playing sequence.
        Populate schedule with start, end and interpolated events
    */
    for(auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); )
    {
        Sequence* pSequence = getSequence(it->first, it->second);
        if(pSequence->getPlayState() == STOPPED)
        {
            it = m_vPlayingSequences.erase(it);
            continue;
        }
        uint8_t nEventType = pSequence->clock(nTime, bSync, dSamplesPerClock);
        if(nEventType & 1)
        {
            // A step event
            while(SEQ_EVENT* pEvent = pSequence->getEvent())
            {
                uint32_t nEventTime = pEvent->time;
                while(pSchedule->find(nEventTime) != pSchedule->end())
                    ++nEventTime; // Move event forward until we find a spare time slot
                MIDI_MESSAGE* pNewEvent = new MIDI_MESSAGE(pEvent->msg);
                (*pSchedule)[nEventTime] = pNewEvent;
                //printf("Clock time: %u Scheduling event 0x%x 0x%x 0x%x with time %u at %u\n", nTime, pEvent->msg.command, pEvent->msg.value1, pEvent->msg.value2, pEvent->time, nEventTime);
            }
        }
        if(nEventType & 2)
        {
            // Change of state
            uint8_t nTallyChannel = getTriggerChannel();
            uint8_t nTrigger = getTriggerNote(it->first, it->second);
            if(nTallyChannel < 16 && nTrigger < 128)
            {
                MIDI_MESSAGE* pEvent = new MIDI_MESSAGE();
                pEvent->command = MIDI_NOTE_ON | nTallyChannel;
                pEvent->value1 = nTrigger;
                switch(pSequence->getPlayState())
                {
                    //!@todo Tallies are hard coded to Akai APC but should be configurable
                    case STOPPED:
                        pEvent->value2 = 3;
                        break;
                    case PLAYING:
                        pEvent->value2 = 1;
                        break;
                    case STOPPING:
                        pEvent->value2 = 4;
                        break;
                    case STARTING:
                        pEvent->value2 = 5;
                        break;
                    default:
                        continue;
                }
                //!@todo Can we optimise time search?
                while(pSchedule->find(nTime) != pSchedule->end())
                    ++nTime; // Move event forward until we find a spare time slot
                (*pSchedule)[nTime] = pEvent;
            }
        }
        ++it;
    }
    return m_vPlayingSequences.size();
}

void SequenceManager::setSequencePlayState(uint8_t bank, uint8_t sequence, uint8_t state)
{
    Sequence* pSequence = getSequence(bank, sequence);
    if(state == STARTING || state == PLAYING)
    {
        bool bAddToList = true;
        // Stop other sequences in same group
        for(auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it)
        {
            Sequence* pPlayingSequence = getSequence(it->first, it->second);
            if(pPlayingSequence == pSequence)
                bAddToList = false;
            else
                if(pPlayingSequence->getGroup() == pSequence->getGroup())
                {
                    if(pPlayingSequence->getPlayState() == STARTING)
                        pPlayingSequence->setPlayState(STOPPED);
                    else if(pPlayingSequence->getPlayState() != STOPPED)
                        pPlayingSequence->setPlayState(STOPPING);
                }
        }
        if(bAddToList)
            m_vPlayingSequences.push_back(std::pair<uint32_t,uint32_t>(bank,sequence));
    }
    pSequence->setPlayState(state);
}

uint8_t SequenceManager::getTriggerNote(uint8_t bank, uint8_t sequence)
{
    uint16_t nValue = (bank << 8) | sequence;
    for(auto it = m_mTriggers.begin(); it != m_mTriggers.end(); ++it)
        if(it->second == nValue)
            return it->first;
    return 0xFF;
}

void SequenceManager::setTriggerNote(uint8_t bank, uint8_t sequence, uint8_t note)
{
    m_mTriggers.erase(getTriggerNote(bank, sequence));
    if(note < 128)
        m_mTriggers[note] = (bank << 8) | sequence;
}

uint8_t SequenceManager::getTriggerChannel()
{
    return m_nTriggerChannel;
}

void SequenceManager::setTriggerChannel(uint8_t channel)
{
    if(channel > 15)
        m_nTriggerChannel = 0xFF;
    else
        m_nTriggerChannel = channel;
}

uint16_t SequenceManager::getTriggerSequence(uint8_t note)
{
    auto it = m_mTriggers.find(note);
    if(it != m_mTriggers.end())
        return it->second;
    return 0;
}

size_t SequenceManager::getPlayingSequencesCount()
{
    return m_vPlayingSequences.size();
}

void SequenceManager::stop()
{
    for(auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it)
        getSequence(it->first, it->second)->setPlayState(STOPPED);
    m_vPlayingSequences.clear();
}

void SequenceManager::cleanPatterns()
{
    // Create copy of patterns map
    std::map<uint32_t,Pattern*> mPatterns;
    for(auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        mPatterns[it->first] = &(it->second);

    // Remove all patterns that are used by tracks
    for(auto itBank = m_mBanks.begin(); itBank != m_mBanks.end(); ++itBank)
    {
        for(auto itSeq = itBank->second.begin(); itSeq != itBank->second.end(); ++itSeq)
        {
            uint32_t nTrack = 0;
            while(Track* pTrack = (*itSeq)->getTrack(nTrack++))
            {
                uint32_t nIndex = 0;
                while(Pattern* pPattern = pTrack->getPatternByIndex(nIndex++))
                    mPatterns.erase(getPatternIndex(pPattern));
            }
        }
    }

    // Remove patterns in main map that are in search map and empty
    for(auto it = mPatterns.begin(); it != mPatterns.end(); ++it)
    {
        if(it->second->getEvents() == 0)
            m_mPatterns.erase(it->first);
    }
}

void SequenceManager::setSequencesInBank(uint8_t bank, uint8_t sequences)
{
    // Remove excessive sequences
    size_t nSize = m_mBanks[bank].size();
    while(nSize > sequences)
    {
        setSequencePlayState(bank, --nSize, STOPPED);
        delete getSequence(bank, nSize);
        m_mBanks[bank].pop_back();
    }
    cleanPatterns();
    // Add required sequences
    for(size_t nSequence = nSize; nSequence < sequences; ++nSequence)
    {
        Sequence* pSequence = new Sequence();
        m_mBanks[bank].push_back(pSequence);
        // Add a new pattern at start of eacn new track
        uint32_t nPattern = createPattern();
        addPattern(bank, nSequence, 0, 0, nPattern, false);
    }
}

uint32_t SequenceManager::getSequencesInBank(uint32_t bank)
{
    return m_mBanks[bank].size();
}

bool SequenceManager::moveSequence(uint8_t bank, uint8_t sequence, uint8_t position)
{
    if(sequence >= getSequencesInBank(bank))
        setSequencesInBank(bank, sequence + 1);
    if(position >= getSequencesInBank(bank))
        setSequencesInBank(bank, position + 1);
    Sequence* pSequence = getSequence(bank, sequence); // Store sequence we want to move
    if(position < sequence)
    {
        for(size_t nIndex = sequence; nIndex > position; --nIndex)
            m_mBanks[bank][nIndex] = m_mBanks[bank][nIndex - 1];
        m_mBanks[bank][position] = pSequence;
    }
    else if(position > sequence)
    {
        for(size_t nIndex = sequence; nIndex < position; ++nIndex)
            m_mBanks[bank][nIndex] = m_mBanks[bank][nIndex + 1];
        m_mBanks[bank][position] = pSequence;
    }
    return true;
}

void SequenceManager::insertSequence(uint8_t bank, uint8_t sequence)
{
    if(sequence >= m_mBanks[bank].size())
    {
        setSequencesInBank(bank, sequence + 1);
        return;
    }
    Sequence* pSequence = new Sequence();
    m_mBanks[bank].insert(m_mBanks[bank].begin() + sequence, pSequence);
    // Add a new pattern at start of eacn new track
    cleanPatterns();
    uint32_t nPattern = createPattern();
    addPattern(bank, sequence, 0, 0, nPattern, false);
}

void SequenceManager::removeSequence(uint8_t bank, uint8_t sequence)
{
    if(sequence < m_mBanks[bank].size())
    {
        delete(m_mBanks[bank][sequence]);
        m_mBanks[bank].erase(m_mBanks[bank].begin() + sequence);
    }
}

void SequenceManager::clearBank(uint32_t bank)
{
    setSequencesInBank(bank, 0);
}

uint32_t SequenceManager::getBanks()
{
    return m_mBanks.size();
}