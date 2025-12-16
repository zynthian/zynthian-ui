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
#include <algorithm> // provides remove_if

/** SequenceManager class methods implementation **/

SequenceManager::SequenceManager() {
    for (uint8_t channel = 0; channel < 32; ++ channel)
        m_bEnabled[channel] = false;
    init();
}

void SequenceManager::init() {
    stop();
    m_mTriggers.clear();
    for (auto it = m_mPatterns.begin(); it != m_mPatterns.end(); ++it)
        delete (it->second);
    m_mPatterns.clear();
    for (auto& scene: m_vScenes) {
        for (auto phrase: scene) {
            for (auto seq: phrase->m_aChildSequences) {
                delete seq;
            }
            delete phrase;
        }
    }
    m_vScenes.clear();
    for (uint8_t channel = 0; channel < 32; ++channel)
        enableChannel(channel, m_bEnabled[channel]);
    getPattern(0); // Create pattern 0 so that getNextPattern always has a valid starting point.
    setScene(0);
}

bool SequenceManager::setScene(uint8_t scene) {
    bool bResult = scene >= m_vScenes.size();
    if (bResult) {
        for (uint8_t i = m_vScenes.size(); i <= scene; ++i) {
            m_vScenes.emplace_back();
        }
    }
    m_nScene = scene;
    //fprintf(stderr, "%s scene %u\n", bResult?"Created":"Selected", scene);
    return bResult;
}

uint8_t SequenceManager::getScene() {
    return m_nScene;
}

void SequenceManager::removeScene(uint8_t scene) {
    if (scene >= m_vScenes.size())
        return;
    while (getNumPhrases(scene))
        removePhrase(scene, 0);
    m_vScenes.erase(m_vScenes.begin() + scene);
    if (m_nScene == scene)
        setScene(0);
    else
        setScene(m_nScene);
}

uint8_t SequenceManager::getNumScenes() {
    return m_vScenes.size();
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
    for (auto scene: m_vScenes) {
        for (auto phrase: scene) {
            for (auto pSequence: phrase->m_aChildSequences) {
                if (!pSequence)
                    continue;
                bool bFound = false;
                for (uint32_t nTrack = 0; nTrack < pSequence->getTracks() && !bFound; ++nTrack) {
                    Track* pTrack = pSequence->getTrack(nTrack);
                    for (uint32_t nPattern = 0; nPattern < pTrack->getPatterns() && !bFound; ++nPattern) {
                        if (pTrack->getPatternByIndex(nPattern) == pPattern)
                            bFound = true;
                    }
                    if (bFound) {
                        pTrack->setModified();
                        pSequence->setModified();
                    }
                }
            }
        }
    }
}

Sequence* SequenceManager::getSequence(uint8_t scene, uint8_t phrase, uint8_t sequence) {
    if (scene >= m_vScenes.size())
        return nullptr;
    auto& vPhrases = m_vScenes[scene];
    if (sequence == PHRASE_CHANNEL && phrase < vPhrases.size())
        return vPhrases[phrase];
    if (phrase >= vPhrases.size() || sequence >= 32)
        return nullptr;
    return vPhrases[phrase]->m_aChildSequences[sequence];
}

bool SequenceManager::addPattern(Sequence* pSequence, uint32_t track, uint32_t position, uint32_t pattern, bool force) {
    Track* pTrack = pSequence->getTrack(track);
    if (!pTrack)
        return false;
    bool bUpdated = pTrack->addPattern(position, getPattern(pattern), force);
    pSequence->updateLength();
    return bUpdated;
}

void SequenceManager::removePattern(Sequence* pSequence, uint32_t track, uint32_t position) {
    if (!pSequence)
        return;
    Track* pTrack = pSequence->getTrack(track);
    if (!pTrack)
        return;
    pTrack->removePattern(position);
    pSequence->updateLength();
}

void SequenceManager::updateAllSequenceLengths() {
    for (auto scene: m_vScenes) {
        for (auto phrase: scene) {
            // Update all sequences in phrase
            for (uint8_t nSeq = 0; nSeq < 16; ++nSeq) {
                Sequence* pSequence = phrase->m_aChildSequences[nSeq];
                if (pSequence)
                    pSequence->updateLength();
            }
        }
    }
}

bool SequenceManager::clock(std::pair<uint32_t, uint32_t> timeinfo, std::multimap<uint32_t, SEQ_EVENT*>* pSchedule, bool bSync) {
    /** Get events scheduled for next step from all tracks in each playing sequence.
        Populate schedule with start, end and interpolated events
    */
    static uint32_t barPos = 0;
    uint32_t nTime = timeinfo.first;
    int32_t nSamplesPerClock = timeinfo.second;
    ++barPos;
    if(bSync)
        barPos = 0;
    size_t nSequence = 0;
    while (nSequence < m_vPlayingSequences.size()) {
        Sequence* pSequence = m_vPlayingSequences[nSequence];
        uint8_t nGroup = pSequence->getGroup();
        uint32_t nPlayState = pSequence->getPlayState();
        bool bIsClippy = nGroup > 15 && nGroup < 32;
        if (bIsClippy) {
            uint8_t nChannel = nGroup - 16;
            uint8_t nPhrase = pSequence->getPhrase();
            uint8_t nNote = nPhrase + 1;
            if (nPlayState == STARTING && bSync) {
                nPlayState = PLAYING;
                pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChannel), nNote, 1}));
                pSequence->setPlayState(PLAYING);
            } else if (nPlayState == PLAYING) {
                uint32_t nPos = pSequence->getPlayPosition() + 1;
                if (nPos >= pSequence->getLength()) {
                    nPos = 0;
                    uint8_t nCount = pSequence->getPlayed() + 1;
                    if (nCount >= pSequence->getRepeat()) {
                        // End of repeats...
                        if (pSequence->getFollowSequence() == pSequence)
                            pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChannel), nNote, 2}));
                        pSequence->setPlayed(0);
                    } else {
                    // Triggering repeat
                    pSequence->setPlayed(nCount);
                    pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChannel), nNote, 3}));
                    }
                }
                pSequence->setPlayPosition(nPos);
            } else if (bSync &&(nPlayState == STOPPING || nPlayState == STOPPING_SYNC)) {
                pSequence->setPlayState(STOPPED);
                pSequence->setPlayed(0);
                pSequence->setPlayPosition(0);
                nPlayState = STOPPED;
            }
        } else if (nPlayState != STOPPED && nPlayState != CHILD_PLAYING) {
            uint8_t nEventType = pSequence->clock(nTime, bSync, nSamplesPerClock, m_nTimeSig);

            if (nEventType & CLOCK_TRIG_MIDI) {
                // A step event
                while (SEQ_EVENT* pEvent = pSequence->getEvent())
                    pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(pEvent->time, new SEQ_EVENT(*pEvent)));
            }
            if (nEventType & CLOCK_TRIG_TEMPO) {
                // Tempo change
                float tempo = pSequence->getTempo();
                m_bTempoChanged |= (m_fTempo != tempo);
                m_fTempo = tempo;
            }
            if (nEventType & CLOCK_TRIG_TIMESIG) {
                // Time signature change
                uint8_t nTimeSig = pSequence->getTimeSig();
                if (nTimeSig) {
                    m_bTimeSigChanged |= (m_nTimeSig != nTimeSig);
                    m_nTimeSig = nTimeSig;
                }
            }
            if (nEventType & CLOCK_TRIG_PHRASE) {
                // Phrase change
                if (pSequence->getPlayState() == PLAYING) {
                    uint8_t nNote = pSequence->getPhrase() + 1;
                    for (uint8_t nChild = 0; nChild < 32; ++nChild) {
                        Sequence* pChildSeq = pSequence->m_aChildSequences[nChild];
                        if (pChildSeq && pChildSeq->getRepeat() && pChildSeq->getPlayState() != PLAYING) {
                            if (nChild > 15)
                                pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChild - 16), nNote, 1}));
                            setPlayState(pChildSeq, PLAYING);
                        }
                    }
                }
            }
            if (nEventType & CLOCK_TRIG_SEQEND) {
                // Reached end of sequence repeats
                Sequence* pFollowSequence = pSequence->getFollowSequence();
                if (pFollowSequence && pFollowSequence->getRepeat())
                    setPlayState(pFollowSequence, PLAYING);
            }
        }

        if (nPlayState == STOPPED || nPlayState == CHILD_PLAYING) {
            if (nGroup < 33)
                m_aGroupProgress[nGroup] = 0;

            // Stop clippy if no other clippy sequences in same group are running
            if (bIsClippy && nPlayState == STOPPED) {
                bool bStopClippy = true;
                for (auto seq: m_vPlayingSequences) {
                    if (seq != pSequence && seq->getGroup() == nGroup) {
                        bStopClippy = false;
                        break;
                    }
                }
                if (bStopClippy) {
                    // Send clippy stop event
                    pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nGroup), 0, 1}));
                }
            }
            m_vPlayingSequences.erase(m_vPlayingSequences.begin() + nSequence);
            continue;
        }
        if (nGroup < 32 && pSequence->getLength())
            m_aGroupProgress[nGroup] = (100 * pSequence->getPlayPosition() / pSequence->getLength());
        else if (nGroup == 32)
            m_aGroupProgress[32] = (100 * barPos / 24 / m_nTimeSig);

        ++nSequence;
    }

    return m_vPlayingSequences.size() > 0;
}

void SequenceManager::setPlayState(Sequence* pSequence, uint8_t state) {
    if (!pSequence)
        return;
    if (state == STARTING || state == PLAYING) {
        bool bAddToList = true;
        // Stop other sequences in same group
        size_t nInsert = 0;
        for (auto it = m_vPlayingSequences.begin(); it != m_vPlayingSequences.end(); ++it) {
            Sequence* pPlayingSequence = *it;
            if (pSequence == pPlayingSequence)
                bAddToList = false;
            else if (pPlayingSequence->getGroup() == pSequence->getGroup()) {
                if (pPlayingSequence->getPlayState() == STARTING)
                    pPlayingSequence->setPlayState(STOPPED);
                else if (pPlayingSequence->getPlayState() != STOPPED) {
                    pPlayingSequence->setPlayState(state == STARTING?STOPPING:STOPPED);
                }
                if (pPlayingSequence->isPhraseLauncher())
                    ++nInsert;
            }
        }
        if (bAddToList) {
            // Need phrase launchers before sequences to avoid a sequence playing its first event before a follow action stops that sequence
            if (pSequence->isPhraseLauncher())
                m_vPlayingSequences.insert(m_vPlayingSequences.begin() + nInsert, pSequence);
            else
                m_vPlayingSequences.push_back(pSequence);
        }
    }
    pSequence->setPlayState(state);

    // Start child sequences
    if (state == STARTING) {
        for (auto pChildSequence: pSequence->m_aChildSequences) {
            if (pChildSequence && pChildSequence->getRepeat()) {
                pChildSequence->setPlayState(STARTING);
            }
        }
    }   
}

void SequenceManager::stopGroup(uint8_t group) {
    for (auto pSequence: m_vPlayingSequences) {
        if (pSequence->getGroup() == group) {
            pSequence->setPlayState(STOPPED);
        }
    }
}

uint8_t SequenceManager::getTriggerNote(uint32_t phraseSeq) {
    for (auto it = m_mTriggers.begin(); it != m_mTriggers.end(); ++it)
        if (it->second == phraseSeq)
            return it->first;
    return 0xFF;
}

void SequenceManager::setTriggerNote(uint16_t phraseSeq, uint8_t note) {
    m_mTriggers.erase(getTriggerNote(phraseSeq));
    if (note < 128)
        m_mTriggers[note] = phraseSeq;
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
    for (auto pSequence: m_vPlayingSequences) {
        pSequence->setPlayState(STOPPED);
    }
    m_vPlayingSequences.clear();
}

bool SequenceManager::isTempoChanged() { return m_bTempoChanged; }

float SequenceManager::getTempo(bool clear) {
    if (clear)
        m_bTempoChanged = false;
    return m_fTempo;
}

void SequenceManager::setTempo(float tempo) {
    if (tempo > 10.0)
        m_fTempo = tempo;
}

bool SequenceManager::isTimeSigChanged() { return m_bTimeSigChanged; }

uint8_t SequenceManager::getTimeSig(bool clear) {
    if (clear)
        m_bTimeSigChanged = false;
    return m_nTimeSig;
}

void SequenceManager::setTimeSig(uint8_t sig) {
    m_nTimeSig = sig;
}

uint8_t* SequenceManager::getProgress() {
    return m_aGroupProgress;
}

void SequenceManager::enableChannel(uint8_t channel, bool enable) {
    if (channel >= 32)
        return;
    m_bEnabled[channel] = enable;
    for (uint8_t nScene = 0; nScene < m_vScenes.size(); ++nScene) {
        for (uint8_t nPhrase = 0; nPhrase < m_vScenes[nScene].size(); ++nPhrase) {
            Sequence* pSequence = getSequence(nScene, nPhrase, channel);
            if (pSequence) {
                pSequence->setRepeat(enable ? 1 : 0);
                pSequence->setPlayState(STOPPED);
            }
        }
    }
}

bool SequenceManager::isChannelEnabled(uint8_t channel) {
    if (channel < 32)
        return m_bEnabled[channel];
    return false;
}

// Phrase handling

uint8_t SequenceManager::getNumPhrases(uint8_t scene) {
    return m_vScenes[scene].size();
}

void SequenceManager::refreshPhrases(uint8_t scene) {
    for (uint8_t phrase = 0; phrase < m_vScenes[scene].size(); ++phrase) {
        Sequence* pPhraseSeq = m_vScenes[scene][phrase];
        pPhraseSeq->setPhrase(phrase);
        for (auto pSequence: pPhraseSeq->m_aChildSequences) {
            if (pSequence)
                pSequence->setPhrase(phrase);
        }
    }
}

Sequence* SequenceManager::insertPhrase(uint8_t scene, uint8_t phrase) {
    for (uint8_t i = m_vScenes.size(); i <= scene; ++i)
        m_vScenes.emplace_back(); // Create missing scenes
    auto& vPhrases = m_vScenes[scene];
    Sequence* pPhrase = new Sequence(nullptr);
    if (!pPhrase)
        return nullptr;
    if (phrase >= vPhrases.size()) {
        phrase = vPhrases.size();
        vPhrases.push_back(pPhrase);
    } else {
        vPhrases.insert(vPhrases.begin() + phrase, pPhrase);
    }
    std::string s;
    s = 'A' + phrase;
    pPhrase->setName(s);
    pPhrase->setGroup(32);
    pPhrase->setRepeat(1);
    for (uint8_t chan = 0; chan < 32; ++chan) {
        Sequence* pSequence = new Sequence(pPhrase);
        pSequence->setGroup(chan);
        pSequence->setName(s  + std::to_string(chan + 1));
        if (chan < 16) {
           Track* pTrack = pSequence->getTrack(0);
            pTrack->setChannel(chan);
            uint32_t nPattern = createPattern();
            addPattern(pSequence, 0, 0, nPattern);
        }
        pPhrase->m_aChildSequences[chan] = pSequence;
        setFollowAction(scene, pSequence, FOLLOW_ACTION_RELATIVE, 0); // Loop
        if (m_bEnabled[chan])
            pSequence->setRepeat(1);
    }
    refreshPhrases(scene);
    return pPhrase;
}

void SequenceManager::removePhrase(uint8_t scene, uint8_t phrase) {
    if (scene >= m_vScenes.size())
        return;
    auto& vPhrases = m_vScenes[scene];
    if (phrase >= vPhrases.size())
        return;

    Sequence* pPhrase = vPhrases[phrase];
    // Iterate each sequence in phrase
    for (uint8_t nSeq = 0; nSeq < 32; ++nSeq) {
        Sequence* pChildSeq = pPhrase->m_aChildSequences[nSeq];
        if (!pChildSeq)
            continue;
        // Iterate each playing sequence
        for (auto it_playing = m_vPlayingSequences.begin(); it_playing != m_vPlayingSequences.end(); ++it_playing) {
            if (pChildSeq == *it_playing) {
                // Remove from playing sequences
                m_vPlayingSequences.erase(it_playing);
                break;
            }
        }
        delete pChildSeq;
        pPhrase->m_aChildSequences[nSeq] = nullptr;
    }

    // Delete the pattern used by phrase launcher
    Track* pTrack = pPhrase->getTrack(0);
    if (pTrack) {
       Pattern* pPattern = pTrack->getPattern(0);
       if (pPattern) {
           deletePattern(getPatternIndex(pPattern));
       }
    }

    // Delete phrase launcher sequence
    delete pPhrase;
    vPhrases.erase(vPhrases.begin() + phrase);

    // Refresh follow actions
    for (auto& pPhrase2: vPhrases)
        setFollowAction(scene, pPhrase2, pPhrase2->getFollowAction(), pPhrase2->getFollowParam());
    refreshPhrases(scene);
}

void SequenceManager::swapPhrase(uint8_t scene, uint8_t phrase1, uint8_t phrase2) {
    if (scene >= m_vScenes.size())
        return;
    auto& vPhrases = m_vScenes[scene];
    if (phrase1 == phrase2 || phrase1 >= vPhrases.size() || phrase2 >= vPhrases.size())
        return;
    std::iter_swap(vPhrases.begin() + phrase1, vPhrases.begin() + phrase2);
    // Update follow actions for all phrases in this scene to handle jumps into and out of these phrases
    for (auto& phraseSeq: m_vScenes[scene])
        setFollowAction(scene, phraseSeq, phraseSeq->getFollowAction(), phraseSeq->getFollowParam());
    refreshPhrases(scene);
}

bool SequenceManager::setFollowAction(uint8_t scene, Sequence* sequence, uint8_t action, int16_t param) {
    if (sequence && scene < m_vScenes.size()) {
        auto& vPhrases = m_vScenes[scene];
        switch (action) {
            case FOLLOW_ACTION_ABSOLUTE:
                if (param < 0 || param > vPhrases.size())
                    return false;
                sequence->setFollowSequence(vPhrases[param], action, param);
                return true;
                break;
            case FOLLOW_ACTION_RELATIVE:
                if (param == 0) {
                    // Loop
                    sequence->setFollowSequence(sequence, action, param);
                    return true;
                } else {
                    // Find index of sequence - this should already be known by caller!!!
                    for (uint32_t i = 0; i < vPhrases.size(); ++i) {
                        if (vPhrases[i] == sequence) {
                            int16_t offset = param + i;
                            if (offset >= 0 && offset < vPhrases.size()) {
                                sequence->setFollowSequence(vPhrases[offset], action, param);
                                return true;
                            } else {
                                // Attempt to select non-existing phrase so set to none.
                                sequence->setFollowSequence(nullptr, 0, 0);
                            }
                            break;
                        }
                    }
                }
                break;
            default:
                sequence->setFollowSequence(nullptr, 0, 0);
        }
    }
    return false;
}
