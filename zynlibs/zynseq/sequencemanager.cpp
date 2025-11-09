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
            for (auto seq: phrase->m_vChildSequences) {
                delete seq;
            }
            delete phrase;
        }
    }
    m_vScenes.clear();
    for (uint8_t channel = 0; channel < 32; ++channel)
        enableChannel(channel, false);
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
            for (auto pSequence: phrase->m_vChildSequences) {
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
    if (phrase >= vPhrases.size() || sequence >= vPhrases[phrase]->m_vChildSequences.size())
        return nullptr;
    return vPhrases[phrase]->m_vChildSequences[sequence];
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
            for (auto pSequence: phrase->m_vChildSequences) {
                if (pSequence)
                    pSequence->updateLength();
            }
        }
    }
}

bool SequenceManager::clock(std::pair<double, double> timeinfo, std::multimap<uint32_t, SEQ_EVENT*>* pSchedule, bool bSync) {
    /** Get events scheduled for next step from all tracks in each playing sequence.
        Populate schedule with start, end and interpolated events
    */
    static uint32_t barPos = 0;
    uint32_t nTime = timeinfo.first;
    double dSamplesPerClock = timeinfo.second;
    ++barPos;
    if(bSync)
        barPos = 0;
    size_t nSequence = 0;
    while (nSequence < m_vPlayingSequences.size()) {
        Sequence* pSequence = m_vPlayingSequences[nSequence];
        uint8_t nGroup = pSequence->getGroup();
        if (pSequence->getPlayState() != STOPPED && pSequence->getPlayState() != CHILD_PLAYING) {
            uint8_t nEventType = pSequence->clock(nTime, bSync, dSamplesPerClock, m_nTimeSig);

            if (nEventType & CLOCK_TRIG_MIDI) {
                // A step event
                while (SEQ_EVENT* pEvent = pSequence->getEvent())
                    pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(pEvent->time, new SEQ_EVENT(*pEvent)));
            }
            if (nEventType & CLOCK_TRIG_TEMPO) {
                // Tempo change
                float tempo = pSequence->getTempo();
                m_bTempoChanged |= m_fTempo != tempo;
                m_fTempo = tempo;
            }
            if (nEventType & CLOCK_TRIG_TIMESIG) {
                // Time signature change
                uint8_t nTimeSig = pSequence->getTimeSig();
                if (nTimeSig > 1) {
                    m_bTimeSigChanged |= m_nTimeSig != nTimeSig;
                    m_nTimeSig = nTimeSig;
                }
            }
            if (nEventType & CLOCK_TRIG_PHRASE) {
                // Phrase change
                if (pSequence->getPlayState() == PLAYING) {
                    for (Sequence* pChildSeq: pSequence->m_vChildSequences) {
                        if (pChildSeq && pChildSeq->getRepeat())
                            setPlayState(pChildSeq, PLAYING);
                    }
                }
            }
            if (nEventType & CLOCK_TRIG_SEQEND) {
                // Reached end of sequence repeats
                Sequence* pFollowSequence = pSequence->getFollowSequence();
                if (pFollowSequence && pFollowSequence->getRepeat())
                    setPlayState(pFollowSequence, STARTING);
            }
            if (nGroup < 32 && pSequence->getLength())
                m_aGroupProgress[nGroup] = (100 * pSequence->getPlayPosition() / pSequence->getLength());
            else if (nGroup == 32)
                m_aGroupProgress[32] = (100 * barPos / 24 / m_nTimeSig);
        }

        if (pSequence->getPlayState() == STOPPED || pSequence->getPlayState() == CHILD_PLAYING) {
            if (nGroup < 33)
                m_aGroupProgress[nGroup] = 0;

            // Stop clippy if no other clippy sequences in same group are running
            Track* pTrack = pSequence->getTrack(0);
            if (pTrack && pTrack->getOutput() == 0xfe && pSequence->getPlayState() == STOPPED) {
                bool bStopClippy = true;
                for (auto seq: m_vPlayingSequences) {
                    if (seq != pSequence && seq->getGroup() == nGroup) {
                        bStopClippy = false;
                        break;
                    }
                }
                if (bStopClippy) {
                    // Send clippy stop event
                    pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nGroup), 0, 100}));
                    pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime + 1, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_OFF | nGroup), 0, 0}));
                }
            }
            m_vPlayingSequences.erase(m_vPlayingSequences.begin() + nSequence);
            continue;
        }
        ++nSequence;
    }

    return m_vPlayingSequences.size() > 0;
}

void SequenceManager::setPlayState(Sequence* pSequence, uint8_t state) {
    if (!pSequence)
        return;
    uint8_t nGroup = pSequence->getGroup();
    if (state == STARTING || state == PLAYING) {
        bool bAddToList = true;
        // Stop other sequences in same group
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
            }
        }
        if (bAddToList) {
            if (pSequence->isPhraseLauncher())
                // Need phrase launchers to be at head of queue to act before child sequences
                m_vPlayingSequences.insert(m_vPlayingSequences.begin(), pSequence);
            else
                m_vPlayingSequences.push_back(pSequence);
        }
    }
    pSequence->setPlayState(state);

    // Start child sequences
    if (state == STARTING) {
        for (auto pChildSequence: pSequence->m_vChildSequences) {
            if (pChildSequence->getRepeat()) {
                pChildSequence->setPlayState(PLAYING);
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
        Track* pTrack = pSequence->getTrack(0);
        pTrack->setChannel(chan % 16);
        pTrack->setOutput(chan < 16?0:0xfe);
        pSequence->setName(s  + std::to_string(chan + 1));
        addPattern(pSequence, 0, 0, createPattern());
        pPhrase->m_vChildSequences.push_back(pSequence);
        setFollowAction(scene, pSequence, FOLLOW_ACTION_RELATIVE, 0); // Loop
        if (m_bEnabled[chan])
            pSequence->setRepeat(1);
    }
    return pPhrase;
}

void SequenceManager::removePhrase(uint8_t scene, uint8_t phrase) {
    if (scene >= m_vScenes.size())
        return;
    auto& vPhrases = m_vScenes[scene];
    if (phrase >= vPhrases.size())
        return;
    for (auto it = vPhrases[phrase]->m_vChildSequences.begin(); it != vPhrases[phrase]->m_vChildSequences.end(); ++it) {
        for (auto it_playing = m_vPlayingSequences.begin(); it_playing != m_vPlayingSequences.end(); ++it_playing) {
            if (*it == *it_playing) {
                m_vPlayingSequences.erase(it_playing);
                break;
            }
        }
        delete *it;
        it = vPhrases[phrase]->m_vChildSequences.erase(it);
    }
    Track* pTrack = vPhrases[phrase]->getTrack(0);
    if (pTrack) {
       Pattern* pPattern = pTrack->getPattern(0);
       if (pPattern) {
           deletePattern(getPatternIndex(pPattern));
       }
    }
    delete vPhrases[phrase];
    vPhrases.erase(vPhrases.begin() + phrase);
}

void SequenceManager::swapPhrase(uint8_t scene, uint8_t phrase1, uint8_t phrase2) {
    if (scene >= m_vScenes.size())
        return;
    auto& vPhrases = m_vScenes[scene];
    if (phrase1 == phrase2 || phrase1 >= vPhrases.size() || phrase2 >= vPhrases.size())
        return;
    std::iter_swap(vPhrases[phrase1], vPhrases[phrase2]);
}

bool SequenceManager::setFollowAction(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t action) {
    Sequence* pSequence = getSequence(scene, phrase, sequence);
    if (pSequence) {
        uint16_t param = getFollowParam(scene, pSequence);
        return setFollowAction(scene, pSequence, action, param);
    }
    return false;
}

bool SequenceManager::setFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence, int16_t param) {
    Sequence* pSequence = getSequence(scene, phrase, sequence);
    if (pSequence) {
        uint8_t action = pSequence->getFollowAction();
        return setFollowAction(scene, pSequence, action, param);
    }
    return false;
}

bool SequenceManager::setFollowAction(uint8_t scene, Sequence* sequence, uint8_t action, int16_t param) {
    Sequence* pSequence = sequence;
    if (pSequence) {
        auto& vPhrases = m_vScenes[scene];
        switch (action) {
            case FOLLOW_ACTION_ABSOLUTE:
                if (param < 0 || param > vPhrases.size())
                    return false;
                pSequence->setFollowSequence(vPhrases[param], action);
                return true;
                break;
            case FOLLOW_ACTION_RELATIVE:
                if (param == 0) {
                    // Loop
                    pSequence->setFollowSequence(pSequence, action);
                    return true;
                } else {
                    // Find index of sequence
                    for (uint32_t i = 0; i < vPhrases.size(); ++i) {
                        if (vPhrases[i] == pSequence) {
                            uint16_t offset = param + i;
                            if (offset >= 0 && offset < vPhrases.size()) {
                                pSequence->setFollowSequence(vPhrases[offset], action);
                                return true;
                            }
                            break;
                        }
                    }
                }
                break;
            default:
                pSequence->setFollowSequence(nullptr, 0);
        }
    }
    return false;
}

int16_t SequenceManager::getFollowParam(uint8_t scene, Sequence* sequence) {
    if (sequence) {
        auto& vPhrases = m_vScenes[scene];
        uint8_t nAction = sequence->getFollowAction();
        if (nAction == FOLLOW_ACTION_NONE)
            return 0;
        Sequence* pFollowSequence = sequence->getFollowSequence();
        uint8_t phraseIndex = 0xff;
        uint8_t nextPhraseIndex = 0xff;
        for (uint32_t i = 0; i < vPhrases.size(); ++i) {
            if (vPhrases[i] == sequence)
                phraseIndex = i;
            if (vPhrases[i] && vPhrases[i] == pFollowSequence) {
                if (nAction == FOLLOW_ACTION_ABSOLUTE)
                    return i;
                nextPhraseIndex = i;
            }
        }
        if (phraseIndex == 0xff || nextPhraseIndex == 0xff)
            return 0;
        if (nAction == FOLLOW_ACTION_RELATIVE)
            return nextPhraseIndex - phraseIndex;
    }
    return 0;
}
