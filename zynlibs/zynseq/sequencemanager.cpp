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
    m_mBanks.clear();
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

Sequence* SequenceManager::getSequence(uint8_t bank, uint8_t sequence, bool create_pattern) {
    if (m_mBanks[bank].find(sequence) == m_mBanks[bank].end()) {
        // Sequence does not exist so create and configure
        if (create_pattern) {
            uint32_t pattern = createPattern();
            addPattern(bank, sequence, 0, 0, pattern, true);
        }
        m_mBanks[bank][sequence].setSequenceId(bank, sequence, true);
    }
    return &(m_mBanks[bank][sequence]);
}

bool SequenceManager::addPattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force) {
    Track* pTrack = m_mBanks[bank][sequence].getTrack(track);
    if (!pTrack)
        return false;
    bool bUpdated = pTrack->addPattern(position, getPattern(pattern), force);
    updateSequenceLength(bank, sequence);
    return bUpdated;
}

void SequenceManager::removePattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position) {
    Sequence* pSequence = getSequence(bank, sequence);
    Track* pTrack = pSequence->getTrack(track);
    if (!pTrack)
        return;
    pTrack->removePattern(position);
    updateSequenceLength(bank, sequence);
}

void SequenceManager::updateSequenceLength(uint8_t bank, uint8_t sequence) { getSequence(bank, sequence)->updateLength(); }

void SequenceManager::updateAllSequenceLengths() {
    for (auto itBank = m_mBanks.begin(); itBank != m_mBanks.end(); ++itBank)
        for (auto itSeq = itBank->second.begin(); itSeq != itBank->second.end(); ++itSeq)
            itSeq->second.updateLength();
}

size_t SequenceManager::clock(std::pair<double, double> timeinfo, std::multimap<uint32_t, MIDI_MESSAGE*>* pSchedule, bool bSync) {
    /** Get events scheduled for next step from all tracks in each playing sequence.
        Populate schedule with start, end and interpolated events
    */
    uint32_t nTime = timeinfo.first;
    double dSamplesPerClock = timeinfo.second;
    std::vector<uint16_t> vNext;
    for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end();) {
        uint8_t bank = *it >> 8;
        uint8_t sequence = *it & 0xff;
        Sequence* pSequence = getSequence(bank, sequence);
        if (pSequence->getPlayState() == STOPPED) {
            it = m_vPlayingSequences.erase(it);
            continue;
        }
        uint8_t nEventType = pSequence->clock(nTime, bSync, dSamplesPerClock);
        if (nEventType & 1) {
            // A step event
            while (SEQ_EVENT* pEvent = pSequence->getEvent()) {
                uint32_t nEventTime = pEvent->time;
                MIDI_MESSAGE* pNewEvent = new MIDI_MESSAGE(pEvent->msg);
                pSchedule->insert(std::pair<uint32_t, MIDI_MESSAGE*>(nEventTime, pNewEvent));
                // fprintf(stderr, "Clock time: %u Scheduling event 0x%x 0x%x 0x%x with time %u at %u framesPerClock: %f\n", nTime, pEvent->msg.command,
                // pEvent->msg.value1, pEvent->msg.value2, pEvent->time, nEventTime, dSamplesPerClock);
            }
        }
        if (nEventType & 2) {
            // Change of state
            // uint8_t nTrigger = getTriggerNote(it->first, it->second);
            // It's currently polled from python
            if (bSync && pSequence->getPlayState() == PLAYING && pSequence->getGroup() == 16) {
                // Scene started so start slave sequences
                Track* pTrack = pSequence->getTrack(0);
                if (pTrack) {
                    Pattern* pPattern = pTrack->getPattern(0);
                    if (pPattern) {
                        uint16_t timeSig = pPattern->getBeatsInPattern();
                        if (timeSig != m_nTimeSig) {
                            m_nTimeSig = timeSig;
                            m_bTimeSigChanged = true;
                        }
                    }
                }
            }
        }
        if (nEventType & 4) {
            // Tempo change
            m_fTempo = pSequence->getTempo();
            m_bTempoChanged = true;
        }
        if (nEventType & 8) {
            // Reached end of sequence repeats
            uint16_t follow = pSequence->getFollowAction();
            uint8_t action = follow & 0xff;
            uint8_t param = follow >> 8;
            uint16_t next = 0xffff;
            switch (action) {
                case FOLLOW_ACTION_AGAIN:
                    next = sequence;
                    break;
                case FOLLOW_ACTION_PREV:
                    if (sequence > 16)
                        next = (sequence - 17);
                    break;
                case FOLLOW_ACTION_NEXT:
                    next = sequence + 17;
                    break;
                case FOLLOW_ACTION_FIRST:
                    next = sequence % 17;
                    break;
                case FOLLOW_ACTION_LAST:
                    next = (m_mBanks[bank].size() / 17 - 1)  * 17 + sequence % 17;
                    break;
                case FOLLOW_ACTION_JUMP:
                    next = param;
                    break;
            }
            if (next != 0xffff)
                vNext.push_back(next | (bank << 8));
        }
        if (nEventType & 16) {
            // Reached end of scene launcher
            onSceneLauncherState(bank, sequence / 17, pSequence->getPlayState());
        }
        ++it;
    }
    // Start pending follow-on sequences
    for (auto it = vNext.begin(); it != vNext.end(); ++it)
        setSequencePlayState((*it) >> 8, (*it) & 255, PLAYING);

    return m_vPlayingSequences.size();
}

void SequenceManager::setSequencePlayState(uint8_t bank, uint8_t sequence, uint8_t state) {
    Sequence* pSequence = getSequence(bank, sequence);
    if (state == STARTING || state == PLAYING) {
        bool bAddToList = true;
        // Stop other sequences in same group
        for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it) {
            Sequence* pPlayingSequence = getSequence(*it >> 8, *it & 0xff);
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
            m_vPlayingSequences.push_back((bank << 8) | sequence);
    }

    // Handle scene launchers (group 16)
    if (pSequence->getGroup() == 16) {
        onSceneLauncherState(bank, sequence / 17, state);
    }

    pSequence->setPlayState(state);
}

void SequenceManager::onSceneLauncherState(uint8_t bank, uint8_t slot, uint8_t state) {
    uint8_t base_seq = slot * 17;
    if (state == STARTING || state == PLAYING) {
        for (uint8_t chan = 0; chan < 16; ++chan) {
            uint32_t nSlaveSeq = base_seq + chan;
            Sequence* pSlaveSeq = getSequence(bank, nSlaveSeq);
            if (pSlaveSeq->getRepeat() == 0)// || pSlaveSeq->getPlayState() == PLAYING)
                continue;
            if (pSlaveSeq->getPlayState() == STOPPING)
                setSequencePlayState(bank, nSlaveSeq, PLAYING);
            else
                setSequencePlayState(bank, nSlaveSeq, STARTING);
        }
    } else if (state == STOPPING) {
        for (uint8_t chan = 0; chan < 16; ++chan) {
            uint32_t nSlaveSeq = base_seq + chan;
            if (getSequence(bank, nSlaveSeq)->getPlayState() == STOPPED)
                continue;
            setSequencePlayState(bank, nSlaveSeq, STOPPING);
        }
    } else if (state == STOPPED) {
        for (uint8_t chan = 0; chan < 16; ++chan) {
            uint32_t nSlaveSeq = base_seq + chan;
            if (getSequence(bank, nSlaveSeq)->getPlayState() != STOPPED)
                setSequencePlayState(bank, nSlaveSeq, STOPPED);
        }
    }
}

void SequenceManager::updateFollowAction(uint8_t bank, uint8_t sequence, uint8_t newBank, uint8_t newSeq) {
    // Search all sequences in this bank for jump to this sequence and change it to the new sequence number
    for (auto itBank = m_mBanks.begin(); itBank != m_mBanks.end(); ++itBank) {
        for (auto itSeq = itBank->second.begin(); itSeq != itBank->second.end(); ++itSeq) {
            uint16_t follow = itSeq->second.getFollowAction();
            if (((follow & 0xff) == FOLLOW_ACTION_JUMP) && ((follow >> 8) == sequence))
                itSeq->second.setFollowAction(FOLLOW_ACTION_JUMP, newSeq);
        }
    }
}

void SequenceManager::moveSequence(uint8_t bank, uint8_t sequence, uint8_t newSeq) {
    auto node = m_mBanks[bank].extract(sequence);
    if (!node.empty()) {
        node.key() = newSeq;
        node.mapped().setSequenceId(bank, newSeq, false);
        m_mBanks[bank].erase(newSeq);
        m_mBanks[bank].insert(std::move(node));
    }
    updateFollowAction(bank, sequence, bank, newSeq);
}

void SequenceManager::swapSequence(uint8_t bank, uint8_t sequence1, uint8_t sequence2) {
    std::swap(m_mBanks[bank][sequence1], m_mBanks[bank][sequence2]);
    updateFollowAction(bank, sequence1, bank, sequence2);
    updateFollowAction(bank, sequence2, bank, sequence1);
}

uint8_t SequenceManager::getTriggerNote(uint8_t bank, uint8_t sequence) {
    uint16_t nValue = (bank << 8) | sequence;
    for (auto it = m_mTriggers.begin(); it != m_mTriggers.end(); ++it)
        if (it->second == nValue)
            return it->first;
    return 0xFF;
}

void SequenceManager::setTriggerNote(uint8_t bank, uint8_t sequence, uint8_t note) {
    m_mTriggers.erase(getTriggerNote(bank, sequence));
    if (note < 128)
        m_mTriggers[note] = (bank << 8) | sequence;
}

uint8_t SequenceManager::getTriggerChannel() { return m_nTriggerChannel; }

void SequenceManager::setTriggerChannel(uint8_t channel) { m_nTriggerChannel = channel; }

uint8_t SequenceManager::getTriggerDevice() { return m_nTriggerDevice; }

void SequenceManager::setTriggerDevice(uint8_t idev) { m_nTriggerDevice = idev; }

uint16_t SequenceManager::getTriggerSequence(uint8_t note) {
    auto it = m_mTriggers.find(note);
    if (it != m_mTriggers.end())
        return it->second;
    return 0;
}

size_t SequenceManager::getPlayingSequencesCount() { return m_vPlayingSequences.size(); }

void SequenceManager::stop() {
    for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it) {
        getSequence(*it >> 8, *it & 0xff)->setPlayState(STOPPED);
    }
    m_vPlayingSequences.clear();
}

void SequenceManager::cleanPatterns() {
    // Create copy of patterns map
    std::map<uint32_t, Pattern*> mPatterns;
    for (auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        mPatterns[it->first] = it->second;

    // Remove all patterns that are used by tracks
    for (auto itBank = m_mBanks.begin(); itBank != m_mBanks.end(); ++itBank) {
        for (auto itSeq = itBank->second.begin(); itSeq != itBank->second.end(); ++itSeq) {
            uint32_t nTrack = 0;
            while (Track* pTrack = itSeq->second.getTrack(nTrack++)) {
                uint32_t nIndex = 0;
                while (Pattern* pPattern = pTrack->getPatternByIndex(nIndex++))
                    mPatterns.erase(getPatternIndex(pPattern));
            }
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

uint32_t SequenceManager::getSequencesInBank(uint32_t bank) { return m_mBanks[bank].size(); }

void SequenceManager::removeSequence(uint8_t bank, uint8_t sequence) { m_mBanks[bank].erase(sequence); }

void SequenceManager::clearBank(uint32_t bank) { m_mBanks[bank].clear(); }

uint32_t SequenceManager::getBanks() { return m_mBanks.size(); }

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

void SequenceManager::setTimeSig(uint16_t sig) { m_nTimeSig = sig; }