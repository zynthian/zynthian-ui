#include "track.h"

Track::Track()
{
}

Track::~Track()
{
    clear();
}

void Track::clear()
{
    for(auto it = m_vSchedule.begin(); it != m_vSchedule.end(); ++it)
        delete *it;
    m_vSchedule.clear();
}

void Track::addEvent(Event* pEvent)
{
    m_vSchedule.push_back(pEvent);
}

void Track::removeEvent(size_t nEvent)
{
    if(nEvent >= m_vSchedule.size())
        return;
    delete(m_vSchedule[nEvent]);
    m_vSchedule.erase(m_vSchedule.begin() + nEvent);
}

void Track::removeEvent(Event* pEvent)
{
    auto it = m_vSchedule.begin();
    for(; it != m_vSchedule.end(); ++it)
        if(*it == pEvent)
            break;
    if(it != m_vSchedule.end())
    {
        delete *it;
        m_vSchedule.erase(it);
    }
}

Event* Track::getNextEvent(bool bAdvance)
{
    if(m_nNextEvent >= m_vSchedule.size())
        return NULL;
    if(bAdvance)
        return m_vSchedule[m_nNextEvent++];
    return m_vSchedule[m_nNextEvent];
}

Event* Track::getEvent(size_t nPosition)
{
    if(nPosition >= m_vSchedule.size())
        return NULL;
    return m_vSchedule[nPosition];
}

size_t Track::getNextEventId()
{
    return m_nNextEvent;
}

size_t Track::getQuantityOfEvents()
{
    return m_vSchedule.size();
}

void Track::setPosition(size_t nTime)
{
    for(m_nNextEvent = 0; m_nNextEvent < m_vSchedule.size(); ++m_nNextEvent)
    {
        if(m_vSchedule[m_nNextEvent]->getTime() < nTime)
            continue;
        return;
    }
}