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
    m_nTimeSig = DEFAULT_BPB;
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

uint32_t SequenceManager::createPattern(uint32_t beats) {
    uint32_t pattern = 0;
    while (m_mPatterns.find(++pattern) != m_mPatterns.end())
        ;
    m_mPatterns[pattern] = new Pattern(beats); // Insert a default pattern
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
    if (phrase >= vPhrases.size() || sequence >= PHRASE_CHANNEL)
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

uint8_t SequenceManager::clock(uint32_t nTime, std::multimap<uint32_t, SEQ_EVENT*>* pSchedule, bool bSync, bool bBeat) {
    /** Get events scheduled for next tick from all tracks in each playing sequence.
        Populate schedule with start, end and interpolated events
    */

    // Clock ticks from start of bar
    static uint32_t barPos = 0;
    static uint8_t beatPos = 0;
    if (bSync) {
        barPos = 0;
        beatPos = 0;
    }
    else {
        barPos++;
        if (bBeat) {
            beatPos++;
        }
    }

    uint8_t nResult = 0; // Summary of playing sequences (0:None, 1:Starting, 2:Playing/stopping)
    size_t nSequence = 0;
    while (nSequence < m_vPlayingSequences.size()) {
        Sequence* pSequence = m_vPlayingSequences[nSequence];
        uint8_t nGroup = pSequence->getGroup();
        uint32_t nPlayState = pSequence->getPlayState();
        bool bIsClippy = nGroup > 15 && nGroup < 32;
        // Audio clip sequence
        if (bIsClippy) {
            uint8_t nChannel = nGroup - 16;
            uint8_t nPhrase = pSequence->getPhrase();
            uint8_t nNote = nPhrase + 1;
            switch (nPlayState) {
                case STARTING:
                    // Start playing clip at bar sync
                    if (bSync) {
                        nPlayState = PLAYING;
                        pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChannel), nNote, 1}));
                        pSequence->setPlayState(PLAYING);
                    }
                    // Send beat sync messages to clippy
                    if (bBeat) {
                        pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_CHAN_PRESSURE | nChannel), beatPos, 0}));
                    }
                    break;
                case PLAYING: {
                    uint32_t nPos = pSequence->getPlayPosition() + 1;
                    if (nPos >= pSequence->getLength()) {
                        nPos = 0;
                        uint8_t nCount = pSequence->getPlayed() + 1;
                        // Looping or still don't reached number of repeats => Triggering repeat
                        if (nCount < pSequence->getRepeat() || (pSequence->getFollowAction() == FOLLOW_ACTION_RELATIVE && pSequence->getFollowParam() == 0)) {
                            pSequence->setPlayed(nCount);
                            pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChannel), nNote, 3}));
                            //pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChannel), nNote, 2}));
                        }
                        // End of repeats...
                        else {
                            pSequence->setPlayState(STOPPED);
                            pSequence->setPlayed(0);
                            pSequence->setPlayPosition(0);
                            nPlayState = STOPPED;
                        }
                    }
                    pSequence->setPlayPosition(nPos);
                    // Send beat sync messages to clippy
                    if (bBeat) {
                        pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_CHAN_PRESSURE | nChannel), beatPos, 0}));
                    }
                    break;
                }
                case STOPPING:
                case STOPPING_SYNC:
                    // Stop clip
                    if (bSync) {
                        pSequence->setPlayState(STOPPED);
                        pSequence->setPlayed(0);
                        pSequence->setPlayPosition(0);
                        nPlayState = STOPPED;
                    }
                    // Send beat sync messages to clippy
                    if (bBeat) {
                        pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_CHAN_PRESSURE | nChannel), beatPos, 0}));
                    }
                    break;
            }
        }
        // Step or phrase sequence
        else if (nPlayState != STOPPED && nPlayState != CHILD_PLAYING) {
            uint8_t nEventType = pSequence->clock(nTime, bSync, m_nTimeSig);

            if (nEventType & CLOCK_TRIG_MIDI) {
                // A step event so iterate all step events starting on this tick
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
                // Phrase start or re-trigger
                if (pSequence->getPlayState() == PLAYING) {
                    for (uint8_t nChild = 0; nChild < 32; ++nChild) {
                        Sequence* pChildSeq = pSequence->m_aChildSequences[nChild];
                        if (pChildSeq && pChildSeq->getRepeat() && pChildSeq->getPlayState() != PLAYING) {
                            // Schedule clippy child trigger MIDI event
                            uint8_t nChildGroup = pChildSeq->getGroup();
                            if (nChildGroup > 15) {
                                uint8_t nChildChan = nChildGroup - 16;
                                uint8_t nChildNote = pSequence->getPhrase() + 1;
                                pSchedule->insert(std::pair<uint32_t, SEQ_EVENT*>(nTime, new SEQ_EVENT{nTime, 0xfe, uint8_t(MIDI_NOTE_ON | nChildChan), nChildNote, 1}));
                            }
                            // Set child sequence to play
                            setPlayState(pChildSeq, PLAYING);
                        }
                    }
                }
            }
            if (nEventType & CLOCK_TRIG_SEQEND) {
                // Reached end of sequence repeats
                if (pSequence->isPhraseLauncher() && pSequence->getFollowAction() == FOLLOW_ACTION_RELATIVE) {
                    // Handle phrase follow actions
                    uint8_t nPhrase = pSequence->getPhrase();
                    int16_t nFollowOffset = pSequence->getFollowParam();
                    if (nFollowOffset) {
                        auto pFollowSequence = pSequence;
                        for (const auto& safety : m_vScenes[m_nScene]) { // limit iterations to avoid infinite loop
                            // Look for the next automated and playable phrase
                            uint8_t nRepeat = pFollowSequence->getFollowRepeat();
                            if (nRepeat && nFollowOffset < 0 && ++m_nFollowCount + 1 > nRepeat) {
                                nFollowOffset = 1;
                                m_nFollowCount = 0;
                            }
                            nPhrase += nFollowOffset;
                            pFollowSequence = getSequence(m_nScene, nPhrase, PHRASE_CHANNEL);
                            if (!pFollowSequence)
                                break;
                            if (pFollowSequence->isFollowPlay(m_nFollowCount)) {
                                pFollowSequence = getSequence(m_nScene, nPhrase, PHRASE_CHANNEL);
                                setPlayState(pFollowSequence, PLAYING);
                                break;
                            }
                            nFollowOffset = pFollowSequence->getFollowParam();
                        }
                    }
                }
            }
        }

        // Stopped sequence
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

        if (pSequence->getPlayState() & 0x01) {
            if (nGroup < 32 && pSequence->getLength())
                m_aGroupProgress[nGroup] = (100 * pSequence->getPlayPosition() / pSequence->getLength());
            else if (nGroup == 32) {
                uint8_t nTimeSig = pSequence->getTimeSig();
                if (nTimeSig)
                    m_aGroupProgress[32] = (100 * barPos / (nTimeSig * PPQN_INTERNAL));
                else
                    m_aGroupProgress[32] = (100 * barPos / (m_nTimeSig * PPQN_INTERNAL));
            }
        }
        nResult |= (pSequence->getPlayState() & 0x3);
        ++nSequence;
    }

    return nResult;
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
    std::vector <Sequence*> vSeq;
    for (auto pSequence: m_vPlayingSequences)
        if (pSequence->getGroup() == group)
            vSeq.push_back(pSequence);
    for (auto pSequence: vSeq)
        setPlayState(pSequence, STOPPED);
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
	m_bTimeSigChanged |= (m_nTimeSig != sig);
    m_nTimeSig = sig;
}

uint8_t SequenceManager::getDefaultTimeSig() {
    return m_nDefaultTimeSig;
}

void SequenceManager::setDefaultTimeSig(uint8_t bpb) {
    m_nDefaultTimeSig = bpb;
    // Change timesig on empty phrases
    for (auto& scene: m_vScenes) {
        for (auto& phrase: scene) {
			if (phrase->isPhraseEmpty())
		        if (phrase->setTimeSig(bpb))
                    updateAllSequenceLengths();
		}
	}
}

uint8_t* SequenceManager::getProgress() {
    return m_aGroupProgress;
}

void SequenceManager::enableChannel(uint8_t channel, bool enable) {
    if (channel >= 32)
        return;
    m_bEnabled[channel] = enable;
    // Configure (enable/disable) sequences in the channel
    for (uint8_t nScene = 0; nScene < m_vScenes.size(); ++nScene) {
        for (uint8_t nPhrase = 0; nPhrase < m_vScenes[nScene].size(); ++nPhrase) {
            Sequence* pSequence = getSequence(nScene, nPhrase, channel);
            if (pSequence) {
                pSequence->setRepeat(enable ? 1 : 0);
                setPlayState(pSequence, STOPPED);
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
    pPhrase->setGroup(32);
    pPhrase->setRepeat(255);
    pPhrase->setTimeSig(m_nDefaultTimeSig);
    if (phrase + 1 < vPhrases.size()) {
        auto pPrevPhrase = vPhrases[phrase + 1];
        uint8_t nFollowAction = pPrevPhrase->getFollowAction();
        int16_t nFollowParam = pPrevPhrase->getFollowParam();
        if (nFollowAction == FOLLOW_ACTION_RELATIVE && nFollowParam) {
            pPhrase->setTimeSig(pPrevPhrase->getTimeSig());
            pPhrase->setFollowAction(FOLLOW_ACTION_RELATIVE, 1, 0, 0);
        }
    }
    for (uint8_t chan = 0; chan < 32; ++chan) {
        Sequence* pSequence = new Sequence(pPhrase);
        pSequence->setGroup(chan);
        //pSequence->setName(s  + std::to_string(chan + 1));
        if (chan < 16) {
           Track* pTrack = pSequence->getTrack(0);
           pTrack->setChannel(chan);
           uint32_t nPattern = createPattern(m_nDefaultTimeSig);
           addPattern(pSequence, 0, 0, nPattern);
        }
        pPhrase->m_aChildSequences[chan] = pSequence;
        setFollowAction(scene, pSequence, FOLLOW_ACTION_RELATIVE, 0, 0, 0); // Loop
        if (m_bEnabled[chan])
            pSequence->setRepeat(1);
    }
    // Extend loop if required
    for (uint8_t p = phrase; p < m_vScenes[m_nScene].size(); ++p) {
        auto pSeq = m_vScenes[m_nScene][p];
        int16_t nParam = pSeq->getFollowParam();
        if (pSeq->getFollowAction() == FOLLOW_ACTION_RELATIVE && nParam < 0) {
            if (nParam + p <= phrase + 1)
                setFollowAction(scene, pSeq, pSeq->getFollowAction(), nParam - 1, pSeq->getPlayFlags(), pSeq->getFollowRepeat());
            break;
        }
    }
    refreshPhrases(scene);
    return pPhrase;
}

// TODO: Could be implemented as assignation operator / constructor in Sequence class?
Sequence* SequenceManager::duplicatePhrase(uint8_t scene, uint8_t phrase) {
    for (uint8_t i = m_vScenes.size(); i <= scene; ++i)
        m_vScenes.emplace_back(); // Create missing scenes
    auto& vPhrases = m_vScenes[scene];
    Sequence* pSrcPhrase = vPhrases[phrase];
    auto pPhrase = insertPhrase(scene, phrase);
    if (!pPhrase)
        return nullptr;
    pPhrase->setName(pSrcPhrase->getName());
    pPhrase->setGroup(32);
    pPhrase->setRepeat(pSrcPhrase->getRepeat());
    setFollowAction(scene, pPhrase, pSrcPhrase->getFollowAction(), pSrcPhrase->getFollowParam(), pSrcPhrase->getPlayFlags(), pSrcPhrase->getFollowRepeat());
    pPhrase->setTimeSig(pSrcPhrase->getTimeSig());
    pPhrase->setTempo(pSrcPhrase->getTempo());
    for (uint8_t chan = 0; chan < 32; ++chan) {
        Sequence* pSrcSeq = pSrcPhrase->m_aChildSequences[chan];
        Sequence* pSequence = new Sequence(pPhrase);
        pPhrase->m_aChildSequences[chan] = pSequence;
        pSequence->setGroup(chan);
        pSequence->setName(pSrcSeq->getName());
        pSequence->setRepeat(pSrcSeq->getRepeat());
        setFollowAction(scene, pSequence, pSrcSeq->getFollowAction(), pSrcSeq->getFollowParam(), 0, 0);
        if (chan < 16) {
            Track* pTrack = pSequence->getTrack(0);
            pTrack->setChannel(chan);
            uint32_t nPattern = createPattern(m_nDefaultTimeSig);
            // Copy pattern from source sequence
            *(getPattern(nPattern)) = *(pSrcSeq->getTrack(0)->getPatternByIndex(0));
            // Add pattern
            addPattern(pSequence, 0, 0, nPattern);
        }
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

    // Delete phrase launcher sequence
    delete pPhrase;
    vPhrases.erase(vPhrases.begin() + phrase);

    // Reduce loop if requred
    for (uint8_t p = phrase; p < vPhrases.size(); ++p) {
        auto pSeq = vPhrases[p];
        int16_t nParam = pSeq->getFollowParam();
        if (pSeq->getFollowAction() == FOLLOW_ACTION_RELATIVE && nParam < 0) {
            if (nParam + p < phrase)
                setFollowAction(scene, pSeq, pSeq->getFollowAction(), nParam + 1, pSeq->getPlayFlags(), pSeq->getFollowRepeat());
            break;
        }
    }

    refreshPhrases(scene);
}

void SequenceManager::nudgePhrase(uint8_t scene, uint8_t phrase, bool forward) {
    if (scene >= m_vScenes.size())
        return;
    int nDiff = forward ? 1 : -1;
    int phrase2 = phrase + nDiff;
    auto& vPhrases = m_vScenes[scene];
    if (phrase >= vPhrases.size() || phrase2 >= vPhrases.size() || phrase2 < 0)
        return;
    std::iter_swap(vPhrases.begin() + phrase, vPhrases.begin() + phrase2);
    auto pPhrase = m_vScenes[scene][phrase];
    int16_t nParam = pPhrase->getFollowParam();
    if (pPhrase->getFollowAction() == FOLLOW_ACTION_RELATIVE && pPhrase->getFollowParam() < 0)
        setFollowAction(scene, pPhrase, pPhrase->getFollowAction(), nParam - nDiff, pPhrase->getPlayFlags(), pPhrase->getFollowRepeat());
    pPhrase = m_vScenes[scene][phrase2];
    nParam = pPhrase->getFollowParam();
    if (pPhrase->getFollowAction() == FOLLOW_ACTION_RELATIVE && pPhrase->getFollowParam() < 0)
        setFollowAction(scene, pPhrase, pPhrase->getFollowAction(), nParam + nDiff, pPhrase->getPlayFlags(), pPhrase->getFollowRepeat());
    refreshPhrases(scene);
}

void SequenceManager::setPhraseTimeSig(uint8_t scene, uint8_t phrase, uint8_t bpb) {
    if (scene >= m_vScenes.size())
        return;
    auto& vPhrases = m_vScenes[scene];
    if (phrase >= vPhrases.size())
        return;
    bool bLenChange = false;
    // Change timesig of selected phrase
    bLenChange |= vPhrases[phrase]->setTimeSig(bpb);
    // Change timesig on next consecutive empty phrases
    while (++phrase < vPhrases.size()) {
        if (vPhrases[phrase]->isPhraseEmpty())
            bLenChange |= vPhrases[phrase]->setTimeSig(bpb);
        else
            break;
    }
    // Update lengths if needed
    if (bLenChange)
        updateAllSequenceLengths();
}

uint8_t SequenceManager::getPhraseTimeSig(uint8_t scene, uint8_t phrase) {
    if (scene >= m_vScenes.size())
        return 0;
    auto& vPhrases = m_vScenes[scene];
    if (phrase >= vPhrases.size())
        return 0;

    Sequence* pPhrase = vPhrases[phrase];
    return pPhrase->getTimeSig();
}

bool SequenceManager::isPhraseEmpty(uint8_t scene, uint8_t phrase) {
    if (scene >= m_vScenes.size())
        return 0;
    auto& vPhrases = m_vScenes[scene];
    if (phrase >= vPhrases.size())
        return 0;

    return vPhrases[phrase]->isPhraseEmpty();
}

bool SequenceManager::setFollowAction(uint8_t scene, Sequence* sequence, uint8_t action, int16_t param, uint32_t flags, uint8_t repeat) {
    if (sequence && scene < m_vScenes.size()) {
        auto& vPhrases = m_vScenes[scene];
        switch (action) {
            case FOLLOW_ACTION_ABSOLUTE:
                if (param < 0 || param > vPhrases.size())
                    return false;
                sequence->setFollowAction(action, param, flags, 0);
                return true;
                break;
            case FOLLOW_ACTION_RELATIVE:
                if (param == 0) {
                    // Loop
                    sequence->setFollowAction(action, param, flags, repeat);
                    return true;
                } else {
                    // Find index of sequence - this should already be known by caller!!!
                    for (uint32_t i = 0; i < vPhrases.size(); ++i) {
                        if (vPhrases[i] == sequence) {
                            int16_t offset = param + i;
                            if (offset >= 0 && offset < vPhrases.size()) {
                                sequence->setFollowAction(action, param, flags, repeat);
                                return true;
                            } else {
                                // Attempt to select non-existing phrase so set to none.
                                sequence->setFollowAction(0, 0, 0, 0);
                            }
                            break;
                        }
                    }
                }
                break;
            default:
                sequence->setFollowAction(0, 0, 0, 0);
        }
    }
    return false;
}

void SequenceManager::resetFollowRepeat() {
    m_nFollowCount = 0;
}
