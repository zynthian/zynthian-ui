/*  Defines sequence class providing collection of tracks
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

#include "sequence.h"

Sequence::Sequence(Sequence* phraseSequence) {
    m_pPhraseSequence = phraseSequence;
    addTrack(); // Ensure new sequences have at least one track
}

uint8_t Sequence::getGroup() {
    return m_nGroup;
}

void Sequence::setGroup(uint8_t group) {
    if (m_nGroup == group)
        return;
    m_nGroup = group;
    m_bChanged = true;
}

uint32_t Sequence::addTrack(uint32_t track) {
    auto it = m_vTracks.begin();
    uint32_t nReturn = ++track;
    if (track == -1 || track >= m_vTracks.size()) {
        m_vTracks.emplace_back();
        nReturn = m_vTracks.size() - 1;
    } else
        m_vTracks.emplace(it + track);
    m_bChanged = true;
    return nReturn;
}

bool Sequence::removeTrack(size_t track) {
    if (track >= m_vTracks.size())
        return false;
    if (m_vTracks.size() < 2)
        return false;
    m_vTracks.erase(m_vTracks.begin() + track);
    m_bChanged = true;
    return true;
}

uint32_t Sequence::getTracks() { return m_vTracks.size(); }

void Sequence::clear() {
    if (m_vTracks.size())
        m_bChanged = true;
    m_vTracks.clear();
    addTrack();
    m_nLength = 0;
}

Track* Sequence::getTrack(size_t index) {
    if (index < m_vTracks.size()) {
        return &(m_vTracks[index]);
    }
    return NULL;
}

void Sequence::addTempo(float tempo, uint16_t bar, uint16_t tick) {
    m_timebase.addTimebaseEvent(bar, tick, TIMEBASE_TYPE_TEMPO, tempo * 100);
    m_bChanged = true;
}

void Sequence::removeTempo(uint16_t bar, uint16_t tick) {
    m_timebase.removeTimebaseEvent(bar, tick, TIMEBASE_TYPE_TEMPO);
    m_bChanged = true;
}

float Sequence::getTempoAt(uint16_t bar, uint16_t tick) {
    return m_timebase.getTempo(bar, tick);
}

float Sequence::getTempo() {
    return m_fTempo;
}

void Sequence::addTimeSig(uint16_t bar, uint8_t timeSig) {
    if (bar < 1)
        bar = 1;
    m_timebase.addTimebaseEvent(bar, 0, TIMEBASE_TYPE_TIMESIG, timeSig);
    m_bChanged = true;
}

void Sequence::removeTimeSig(uint16_t bar) {
    m_timebase.removeTimebaseEvent(bar, 0, TIMEBASE_TYPE_TIMESIG);
    m_bChanged = true;
}

uint8_t Sequence::getTimeSigAt(uint16_t bar) {
    if (bar < 1)
        bar = 1;
    TimebaseEvent* pEvent = m_timebase.getPreviousTimebaseEvent(bar, 1, TIMEBASE_TYPE_TIMESIG);
    if (pEvent)
        return pEvent->value;
    return 0;
}

uint8_t Sequence::getTimeSig() {
    return m_nTimeSig;
}

Timebase* Sequence::getTimebase() {
    //!@todo Optimise timebase - only add a timebase track as required
    return &m_timebase;
}

uint8_t Sequence::getPlayMode() {
    return m_nMode;
}

void Sequence::setPlayMode(uint8_t mode) {
    m_nMode = mode;
    m_bChanged = true;
}

uint8_t Sequence::getPlayState() {
    return m_nState;
}

void Sequence::setPlayState(uint8_t state) {
    if (state == CHILD_STOPPING) {
        for (auto pSequence: m_vChildSequences) {
            pSequence->setPlayState(STOPPING);
        }
    }
    if (state == STOPPING && m_nState == STOPPED)
        return;
    uint8_t nState = m_nState;
    if (m_nRepeat == 0) // Disabled
        state = STOPPED;
    if (state == m_nState)
        return;
    if ((m_nMode & MODE_END_IMMEDIATE) && (state == STOPPING || state == STOPPING_SYNC)) {
        state = STOPPED;
    }
    m_nState = state;
    if (m_nState == STOPPED)
        m_nPosition = 0;

    updatePhraseState();

    m_bStateChanged |= (nState != m_nState);
    m_bChanged = true;
    if (m_nState == STARTING || m_nState == STOPPED)
        m_nCount = 0;
}

void Sequence::updatePhraseState() {
    Sequence* pPhraseSequence = m_pPhraseSequence;
    if (!pPhraseSequence) {
        if (m_vChildSequences.size() == 0) {
            return;
        }
        pPhraseSequence = this;
    }
    uint8_t state = pPhraseSequence->getPlayState();
    if (state != STOPPED && state != CHILD_PLAYING && state != CHILD_STOPPING) {
        return;
    }
    for (auto pChildSequence: pPhraseSequence->m_vChildSequences) {
        if (pChildSequence && (pChildSequence->getPlayState() & 1)) {
            if (state != CHILD_STOPPING)
                pPhraseSequence->setPlayState(CHILD_PLAYING);
            return;
        }
    }
    pPhraseSequence->setPlayState(STOPPED);
}

uint32_t Sequence::getState() {
    return (m_nRepeat << 24) | (m_nGroup << 16) | (m_nMode << 8) | m_nState;
}

uint8_t Sequence::clock(uint32_t nTime, bool bSync, double dSamplesPerClock, uint8_t nTimeSig) {
    m_nCurrentTrack = 0;
    uint8_t nReturn = 0;
    uint8_t nState = m_nState;
    uint8_t nCountInc = (m_nState == STARTING) ? 0 : 1;
    bool bPhraseLauncher = isPhraseLauncher();
    if (bSync) {
        if (m_nMode & MODE_END_SYNC) {
            if (m_nState == STOPPING) {
                setPlayState(STOPPED);
                m_nPosition = 0;
            }
        }
        if (m_nState == STARTING) {
            setPlayState(PLAYING);
            if (bPhraseLauncher) {
                nReturn |= CLOCK_TRIG_PHRASE;
                uint8_t timeSig = m_timebase.getTimeSig(1, 0);
                if (timeSig > 1) {
                    m_nTimeSig = timeSig;
                    nReturn |= CLOCK_TRIG_TIMESIG;
                }
            }
        } else if (m_nState == STOPPING_SYNC) {
            setPlayState(STOPPED);
            m_nPosition = 0;
        } else if (m_nState == PLAYING && bPhraseLauncher) {
            // Playing at start of bar so must be triggering phrase
            nReturn |= CLOCK_TRIG_PHRASE;
        }
    }

    if (m_nState == PLAYING || m_nState == STOPPING || m_nState == STOPPING_SYNC) {
        // Still playing so iterate through tracks
        bool trig = false;
        for (auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
            trig |= (*it).clock(nTime, m_nPosition, dSamplesPerClock, bSync);
        if (trig)
            nReturn |= CLOCK_TRIG_MIDI;
        ++m_nPosition;
    }
    if ((!bPhraseLauncher && (m_nPosition >= m_nLength)) || (bPhraseLauncher && (m_nPosition >= 24 * nTimeSig))) {
        // End of sequence or phrase
        if (m_nState == PLAYING) {
            m_nCount += nCountInc;
            m_nPosition = 0;
            if (m_nCount >= m_nRepeat) {
                // Follow action
                nReturn |= CLOCK_TRIG_SEQEND;
                if (m_pFollowSequence != this)
                    setPlayState(STOPPED);
            }
        } else {
            setPlayState(STOPPED);
            for (auto pChildSeq: m_vChildSequences) {
                pChildSeq->setPlayState(STOPPING_SYNC); // stopping_sync so that child sequences stop in sync
            }
        }
        m_nPosition = 0;
    }

    m_bStateChanged |= (nState != m_nState);
    if (m_bStateChanged) {
        m_bChanged = true;
        m_bStateChanged = false;
        if (m_nState == PLAYING)
            m_pNextTimebaseEvent = m_timebase.getFirstTimebaseEvent();
    }

    if (nState != STOPPED && m_pNextTimebaseEvent && nTime >= m_pNextTimebaseEvent->clock && m_pNextTimebaseEvent->type == TIMEBASE_TYPE_TEMPO) {
        m_fTempo = m_pNextTimebaseEvent->value / 100;
        nReturn |= CLOCK_TRIG_TEMPO;
    }

    return nReturn;
}

SEQ_EVENT* Sequence::getEvent() {
    // This function is called repeatedly for each clock period until no more events are available to populate JACK MIDI output schedule
    if (m_nState == STOPPED || m_nState == STARTING)
        return NULL; //!@todo Can we stop between note on and note off being processed resulting in stuck note?

    SEQ_EVENT* pEvent;
    while (m_nCurrentTrack < m_vTracks.size()) {
        pEvent = m_vTracks[m_nCurrentTrack].getEvent();
        if (pEvent)
            return pEvent;
        ++m_nCurrentTrack;
    }
    return NULL;
}

void Sequence::updateLength() {
    m_nLength = 0;
    m_bEmpty = true;
    for (auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it) {
        uint32_t nTrackLength = (*it).updateLength();
        if (nTrackLength > m_nLength)
            m_nLength = nTrackLength;
        m_bEmpty &= (*it).isEmpty();
    }
}

uint32_t Sequence::getLength() { return m_nLength; }

bool Sequence::isEmpty() { return m_bEmpty; }

void Sequence::setPlayPosition(uint32_t position) { m_nPosition = position; }

uint32_t Sequence::getPlayPosition() { return m_nPosition; }

void Sequence::setModified() { m_bChanged = true; }

bool Sequence::isModified() {
    bool bChanged = m_bChanged;
    for (auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
        bChanged |= (*it).isModified();
    m_bChanged = false;
    return bChanged;
}

void Sequence::setName(std::string sName) {
    m_sName = sName;
    m_sName.resize(16);
}

std::string Sequence::getName() {
    return m_sName;
}

void Sequence::setFollowSequence(Sequence* sequence, uint8_t action) {
    m_pFollowSequence = sequence;
    m_nFollowAction = action;
}

Sequence* Sequence::getFollowSequence() {
    return m_pFollowSequence;
}

uint8_t Sequence::getFollowAction() {
    return m_nFollowAction;
}

void Sequence::setRepeat(uint8_t repeat) {
    m_nRepeat = repeat;
}

uint8_t Sequence::getRepeat() {
    return m_nRepeat;
}

bool Sequence::isPhraseLauncher() {
    return m_pPhraseSequence == nullptr;
}