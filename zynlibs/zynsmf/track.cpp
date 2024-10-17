#include "track.h"

Track::Track() {}

Track::~Track() { clear(); }

void Track::clear() {
    for (auto it = m_vSchedule.begin(); it != m_vSchedule.end(); ++it)
        delete *it;
    m_vSchedule.clear();
}

void Track::addEvent(Event* pEvent) {
    if (m_vSchedule.size() && (m_vSchedule.back()->getType() == 0x2F))
        m_vSchedule.pop_back(); // Remove end of track event
    for (size_t index = m_vSchedule.size(); index > 0; --index) {
        if (m_vSchedule[index - 1]->getTime() > pEvent->getTime())
            continue;
        auto it = m_vSchedule.begin();
        it += index;
        m_vSchedule.insert(it, pEvent);
        return;
    }
    m_vSchedule.insert(m_vSchedule.begin(), pEvent);
}

void Track::removeEvent(size_t nEvent) {
    if (nEvent >= m_vSchedule.size())
        return;
    delete (m_vSchedule[nEvent]);
    m_vSchedule.erase(m_vSchedule.begin() + nEvent);
}

void Track::removeEvent(Event* pEvent) {
    auto it = m_vSchedule.begin();
    for (; it != m_vSchedule.end(); ++it)
        if (*it == pEvent)
            break;
    if (it != m_vSchedule.end()) {
        delete *it;
        m_vSchedule.erase(it);
    }
}

Event* Track::getEvent(bool bAdvance) {
    if (m_nNextEvent >= m_vSchedule.size())
        return NULL;
    if (bAdvance)
        return m_vSchedule[m_nNextEvent++];
    return m_vSchedule[m_nNextEvent];
}

size_t Track::getEvents() { return m_vSchedule.size(); }

void Track::setPosition(size_t nTime) {
    for (m_nNextEvent = 0; m_nNextEvent < m_vSchedule.size(); ++m_nNextEvent) {
        if (m_vSchedule[m_nNextEvent]->getTime() < nTime)
            continue;
        return;
    }
}

void Track::mute(bool bMute) { m_bMute = bMute; }

bool Track::isMuted() { return m_bMute; }