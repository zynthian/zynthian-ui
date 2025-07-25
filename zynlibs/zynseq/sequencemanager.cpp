/*  Defines SequenceManager class managing collection of sequences
 *
 *   Copyright (c) 2020-2025 Brian Walton
 *
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the Free Software
 *   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "sequencemanager.h"
#include <cstring>
#include <stdio.h>

/** SequenceManager class methods implementation **/

SequenceManager::SequenceManager() { init(); }

void SequenceManager::init() {
    stop();
    m_mTriggers.clear();
    for (auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        delete (it->second);
    m_mPatterns.clear();
    m_mSequences.clear();
}

int SequenceManager::fileWrite32(uint32_t value, FILE* pFile) {
    for (int i = 3; i >= 0; --i)
        fileWrite8((value >> i * 8), pFile);
    return 4;
}

int SequenceManager::fileWrite16(uint16_t value, FILE* pFile) {
    for (int i = 1; i >= 0; --i)
        fileWrite8((value >> i * 8), pFile);
    return 2;
}

int SequenceManager::fileWrite8(uint8_t value, FILE* pFile) {
    int nResult = fwrite(&value, 1, 1, pFile);
    return 1;
}

uint8_t SequenceManager::fileRead8(FILE* pFile) {
    uint8_t nResult = 0;
    fread(&nResult, 1, 1, pFile);
    return nResult;
}

uint16_t SequenceManager::fileRead16(FILE* pFile) {
    uint16_t nResult = 0;
    for (int i = 1; i >= 0; --i) {
        uint8_t nValue;
        fread(&nValue, 1, 1, pFile);
        nResult |= nValue << (i * 8);
    }
    return nResult;
}

uint32_t SequenceManager::fileRead32(FILE* pFile) {
    uint32_t nResult = 0;
    for (int i = 3; i >= 0; --i) {
        uint8_t nValue;
        fread(&nValue, 1, 1, pFile);
        nResult |= nValue << (i * 8);
    }
    return nResult;
}

bool SequenceManager::checkBlock(FILE* pFile, uint32_t nActualSize, uint32_t nExpectedSize) {
    if (nActualSize < nExpectedSize) {
        for (size_t i = 0; i < nActualSize; ++i)
            fileRead8(pFile);
        return true;
    }
    return false;
}

Pattern* SequenceManager::getPattern(uint32_t index) {
    if (m_mPatterns.find(index) == m_mPatterns.end())
        m_mPatterns[index] = new Pattern();
    return m_mPatterns[index];
}

uint32_t SequenceManager::getPatternIndex(Pattern* pattern) {
    for (auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        if (it->second == pattern)
            return it->first;
    return -1; // NOT_FOUND
}

uint32_t SequenceManager::getNextPattern(uint32_t pattern) {
    auto it = m_mPatterns.find(pattern);
    if (it == m_mPatterns.end() || ++it == m_mPatterns.end())
        return -1;
    return it->first;
}

uint32_t SequenceManager::createPattern() {
    uint32_t pattern = 0;
    while (m_mPatterns.find(++pattern) != m_mPatterns.end())
        ;
    m_mPatterns[pattern] = new Pattern(); // Insert a default pattern
    return pattern;
}

void SequenceManager::deletePattern(uint32_t index) {
    if (m_mPatterns.find(index) != m_mPatterns.end()) {
        delete (m_mPatterns[index]);
        m_mPatterns.erase(index);
    }
}

void SequenceManager::copyPattern(uint32_t source, uint32_t destination) {
    if (source == destination)
        return;
    Pattern* pPattern = getPattern(destination);
    *pPattern = *(m_mPatterns[source]);
}

void SequenceManager::setPatternModified(Pattern* pPattern) {
    for (auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it) {
        Sequence sequence = it->second;
        bool bFound = false;
        for (uint32_t nTrack = 0; nTrack < sequence.getTracks() && !bFound; ++nTrack) {
            Track* pTrack = sequence.getTrack(nTrack);
            for (uint32_t nPattern = 0; nPattern < pTrack->getPatterns() && !bFound; ++nPattern) {
                if (pTrack->getPatternByIndex(nPattern) == pPattern)
                    bFound = true;
            }
            if (bFound) {
                pTrack->setModified();
                sequence.setModified();
            }
        }
    }
}

Sequence* SequenceManager::getSequence(uint32_t sequence, bool create_pattern) {
    if (m_mSequences.find(sequence) == m_mSequences.end()) {
        // Sequence does not exist so create and configure
        if (create_pattern) {
            uint32_t pattern = createPattern();
            addPattern(sequence, 0, 0, pattern, true);
        }
        m_mSequences[sequence].setSequenceId(sequence);
    }
    return &(m_mSequences[sequence]);
}

bool SequenceManager::addPattern(uint32_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force) {
    Track* pTrack = m_mSequences[sequence].getTrack(track);
    if (!pTrack)
        return false;
    bool bUpdated = pTrack->addPattern(position, getPattern(pattern), force);
    updateSequenceLength(sequence);
    return bUpdated;
}

void SequenceManager::removePattern(uint32_t sequence, uint32_t track, uint32_t position) {
    Sequence* pSequence = getSequence(sequence);
    Track* pTrack = pSequence->getTrack(track);
    if (!pTrack)
        return;
    pTrack->removePattern(position);
    updateSequenceLength(sequence);
}

void SequenceManager::updateSequenceLength(uint32_t sequence) {
    getSequence(sequence)->updateLength();
}

void SequenceManager::updateAllSequenceLengths() {
    for (auto itSeq = m_mSequences.begin(); itSeq != m_mSequences.end(); ++itSeq)
        itSeq->second.updateLength();
}

size_t SequenceManager::clock(std::pair<double, double> timeinfo, std::multimap<uint32_t, MIDI_MESSAGE*>* pSchedule, bool bSync) {
    /** Get events scheduled for next step from all tracks in each playing sequence.
        Populate schedule with start, end and interpolated events
    */
    uint32_t nTime = timeinfo.first;
    double dSamplesPerClock = timeinfo.second;
    std::vector<uint32_t> vNext;
    std::vector<uint32_t> vScene;
    for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end();) {
        uint32_t sequence = *it;
        Sequence* pSequence = getSequence(sequence);
        uint8_t nGroup = pSequence->getGroup();
        if (pSequence->getPlayState() == STOPPED) {
            it = m_vPlayingSequences.erase(it);
            if (nGroup < 17)
                m_aGroupProgress[nGroup] = 0;
            continue;
        }
        uint8_t nEventType = pSequence->clock(nTime, bSync, dSamplesPerClock);
        if (nEventType & 1) {
            // A step event
            while (SEQ_EVENT* pEvent = pSequence->getEvent()) {
                uint32_t nEventTime = pEvent->time;
                MIDI_MESSAGE* pNewEvent = new MIDI_MESSAGE(pEvent->msg);
                pSchedule->insert(std::pair<uint32_t, MIDI_MESSAGE*>(nEventTime, pNewEvent));
            }
        }
        if (nEventType & 4) {
            // Tempo change
            m_fTempo = pSequence->getTempo();
            m_bTempoChanged = true;
        }
        if (nEventType & 8) {
            // Reached end of sequence repeats
            if (nEventType & 2 && pSequence->getFollowAction() != FOLLOW_ACTION_NONE)
                // Scene launcher reached end
                vScene.push_back(sequence);

            switch (pSequence->getFollowAction()) {
                case FOLLOW_ACTION_LOOP:
                    vNext.push_back(sequence);
                    break;
                case FOLLOW_ACTION_PREV:
                    if (sequence > 16)
                        vNext.push_back(sequence - 17);
                    break;
                case FOLLOW_ACTION_NEXT:
                    vNext.push_back(sequence + 17);
                    break;
                case FOLLOW_ACTION_JUMP:
                    vNext.push_back(pSequence->getFollowActionParam());
                    break;
            }
        } else if (nEventType & 2) {
            // Scene launcher start
            vScene.push_back(sequence);
        }

        if (nGroup == 16)
            m_aGroupProgress[nGroup] = (100 * pSequence->getPlayPosition() / (m_nBeatsPerBar * 24));
        else if (nGroup < 16 && pSequence->getLength())
            m_aGroupProgress[nGroup] = (100 * pSequence->getPlayPosition() / pSequence->getLength());
        ++it;
    }
    // Start pending follow-on sequences
    for (auto it = vNext.begin(); it != vNext.end(); ++it) {
        setSequencePlayState(*it, PLAYING);
    }
    // Process pending scene launchers
    for (auto it = vScene.begin(); it != vScene.end(); ++it) {
        uint32_t sequence = *it;
        Sequence* pSequence = getSequence(sequence);
        uint8_t state = pSequence->getPlayState(); 
        if (state == PLAYING) {
            // Scene started - Check for change of time signature
            Track* pTrack = pSequence->getTrack(0);
            if (pTrack) {
                Pattern* pPattern = pTrack->getPattern(0);
                if (pPattern) {
                    uint8_t timeSig = pPattern->getBeatsInPattern();
                    if (timeSig > 1 && timeSig != m_nTimeSig) {
                        m_nTimeSig = timeSig;
                        m_bTimeSigChanged = true;
                    }
                }
            }
        }
        onSceneLauncherState(sequence, state);
    }
    return m_vPlayingSequences.size();
}

void SequenceManager::setSequencePlayState(uint32_t sequence, uint8_t state) {
    Sequence* pSequence = getSequence(sequence);
    if (state == STARTING || state == PLAYING) {
        bool bAddToList = true;
        // Stop other sequences in same group
        for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it) {
            Sequence* pPlayingSequence = getSequence(*it);
            if (pSequence == pPlayingSequence)
                bAddToList = false;
            else if (pPlayingSequence->getGroup() == pSequence->getGroup()) {
                if (pPlayingSequence->getPlayState() == STARTING)
                    pPlayingSequence->setPlayState(STOPPED);
                else if (pPlayingSequence->getPlayState() != STOPPED) {
                    pPlayingSequence->setPlayState(STOPPING_SYNC);
                }
            }
        }
        if (bAddToList)
            m_vPlayingSequences.push_back(sequence);
    }
    pSequence->setPlayState(state);

    if (state == STOPPING && pSequence->getGroup() == 16)
        // Stop running sequences if scene requested to stop
        onSceneLauncherState(sequence, state);
}

void SequenceManager::onSceneLauncherState(uint32_t sequence, uint8_t state) {
    uint32_t base_seq = sequence - 16;
    if (state == PLAYING) {
        for (uint8_t chan = 0; chan < 16; ++chan) {
            uint32_t nSlaveSeq = base_seq + chan;
            Sequence* pSlaveSeq = getSequence(nSlaveSeq);
            if (pSlaveSeq->getRepeat() == 0)// || pSlaveSeq->getPlayState() == PLAYING)
                continue;
            setSequencePlayState(nSlaveSeq, PLAYING);
        }
    } else if (state == STOPPING) {
        for (uint8_t chan = 0; chan < 16; ++chan) {
            uint32_t nSlaveSeq = base_seq + chan;
            if (getSequence(nSlaveSeq)->getPlayState() == STOPPED)
                continue;
            setSequencePlayState(nSlaveSeq, STOPPING);
        }
    } else if (state == STOPPED) {
        for (uint8_t chan = 0; chan < 16; ++chan) {
            uint32_t nSlaveSeq = base_seq + chan;
            if (getSequence(nSlaveSeq)->getPlayState() != STOPPED)
                setSequencePlayState(nSlaveSeq, STOPPED);
        }
    }
}

void SequenceManager::updateFollowAction(uint32_t sequence, uint32_t newSeq) {
    // Search all sequences for jump to this sequence and change it to the new sequence number
    for (auto itSeq = m_mSequences.begin(); itSeq != m_mSequences.end(); ++itSeq) {
        uint8_t action = itSeq->second.getFollowAction();
        uint32_t param = itSeq->second.getFollowActionParam();
        if (action == FOLLOW_ACTION_JUMP && param == sequence)
            itSeq->second.setFollowAction(FOLLOW_ACTION_JUMP, newSeq);
    }
}

void SequenceManager::moveSequence(uint32_t sequence, uint32_t newSeq) {
    auto node = m_mSequences.extract(sequence);
    if (!node.empty()) {
        node.key() = newSeq;
        node.mapped().setSequenceId(newSeq);
        m_mSequences.erase(newSeq);
        m_mSequences.insert(std::move(node));
    }
    updateFollowAction(sequence, newSeq);
}

void SequenceManager::swapSequence(uint32_t sequence1, uint32_t sequence2) {
    std::swap(m_mSequences[sequence1], m_mSequences[sequence2]);
    updateFollowAction(sequence1, sequence2);
    updateFollowAction(sequence2, sequence1);
}

uint8_t SequenceManager::getTriggerNote(uint32_t sequence) {
    for (auto it = m_mTriggers.begin(); it != m_mTriggers.end(); ++it)
        if (it->second == sequence)
            return it->first;
    return 0xFF;
}

void SequenceManager::setTriggerNote(uint32_t sequence, uint8_t note) {
    m_mTriggers.erase(getTriggerNote(sequence));
    if (note < 128)
        m_mTriggers[note] = sequence;
}

uint8_t SequenceManager::getTriggerChannel() { 
    return m_nTriggerChannel;
}

void SequenceManager::setTriggerChannel(uint8_t channel) {
    m_nTriggerChannel = channel;
}

uint8_t SequenceManager::getTriggerDevice() {
    return m_nTriggerDevice;
}

void SequenceManager::setTriggerDevice(uint8_t idev) {
    m_nTriggerDevice = idev;
}

uint32_t SequenceManager::getTriggerSequence(uint8_t note) {
    auto it = m_mTriggers.find(note);
    if (it != m_mTriggers.end())
        return it->second;
    return 0;
}

size_t SequenceManager::getPlayingSequencesCount() { return m_vPlayingSequences.size(); }

void SequenceManager::stop() {
    for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it) {
        getSequence(*it)->setPlayState(STOPPED);
    }
    m_vPlayingSequences.clear();
}

void SequenceManager::cleanPatterns() {
    // Create copy of patterns map
    std::map<uint32_t, Pattern*> mPatterns;
    for (auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        mPatterns[it->first] = it->second;

    // Remove all patterns that are used by tracks
    for (auto itSeq = m_mSequences.begin(); itSeq != m_mSequences.end(); ++itSeq) {
        uint32_t nTrack = 0;
        while (Track* pTrack = itSeq->second.getTrack(nTrack++)) {
            uint32_t nIndex = 0;
            while (Pattern* pPattern = pTrack->getPatternByIndex(nIndex++))
                mPatterns.erase(getPatternIndex(pPattern));
        }
    }

    // Remove patterns in main map that are in search map and empty
    for (auto it = mPatterns.begin(); it != mPatterns.end(); ++it) {
        if (it->second->getEvents() == 0) {
            delete (it->second);
            m_mPatterns.erase(it->first);
        }
    }
}

uint32_t SequenceManager::getSequencesInBank(uint8_t bank) {
    //!@todo Try to factor out.
    std::map <uint32_t, bool> m;
    uint32_t bk = bank << 24;
    for (auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it) {
        if ((it->first & bk) == bk)
            m[it->first] = true;
    }
    return m.size();
}

void SequenceManager::removeSequence(uint32_t sequence) {
    m_mSequences.erase(sequence);
}

void SequenceManager::clearBank(uint32_t bank) {
    //!@todo Optimse
    uint32_t bk = bank << 24;
    for (auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it) {
        if ((it->first & bk) == bk)
            it = m_mSequences.erase(it);
    }
}

uint32_t SequenceManager::getBanks() {
    //!@todo Try to factor out.
    std::map <uint8_t, bool> m;
    for (auto it = m_mSequences.begin(); it != m_mSequences.end(); ++it)
        m[it->first >> 24] = true;
    return m.size();
}

bool SequenceManager::isTempoChanged() { return m_bTempoChanged; }

float SequenceManager::getTempo(bool clear) {
    if (clear)
        m_bTempoChanged = false;
    return m_fTempo;
}

bool SequenceManager::isTimeSigChanged() { return m_bTimeSigChanged; }

uint16_t SequenceManager::getTimeSig(bool clear) {
    if (clear)
        m_bTimeSigChanged = false;
    return m_nTimeSig;
}

void SequenceManager::setTimeSig(uint8_t sig) {
    m_nTimeSig = sig;
}

uint8_t SequenceManager::getProgress(uint8_t group) {
    if (group < 17)
        return m_aGroupProgress[group];
    return 0;
}

void SequenceManager::setBeatsPerBar(uint8_t beats) {
    m_nBeatsPerBar = beats;
}