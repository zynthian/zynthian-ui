/*  Defines Timebase class providing tempo / time signature map
*
*   Copyright (c) 2020 Brian Walton 
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

#include "timebase.h"

Timebase::Timebase()
{
}

Timebase::~Timebase()
{
    for(auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it)
        delete *it;
}

void Timebase::addTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type, uint16_t value)
{
    auto it = m_vEvents.begin();
    for(; it < m_vEvents.end(); ++it)
    {
        if((*it)->measure ==measure && (*it)->tick == tick && (*it)->type == type)
        {
            // Replace existing event
            (*it)->value = value;
            return;
        }
        if((*it)->measure > measure || ((*it)->measure == measure && (*it)->tick > tick))
            break; // Found point to insert
    }
    TimebaseEvent* pEvent = new TimebaseEvent;
    pEvent->measure = measure;
    pEvent->tick = tick;
    pEvent->type = type;
    pEvent->value = value;
    m_vEvents.insert(it, pEvent);
}

void Timebase::removeTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type)
{
    auto it = m_vEvents.begin();
    for(; it < m_vEvents.end(); ++it)
    {
        if((*it)->measure == measure && (*it)->tick == tick && (*it)->type == type)
        {
            delete(*it);
        }
    }
}

TimebaseEvent* Timebase::getNextTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type)
{
    for(size_t nIndex = 0; nIndex < m_vEvents.size(); ++nIndex)
    {
        if(m_vEvents[nIndex]->type != type)
            continue;
        if(m_vEvents[nIndex]->measure < measure || (m_vEvents[nIndex]->measure == measure && m_vEvents[nIndex]->tick <= tick))
            continue;
        return m_vEvents[nIndex];
    }
    return NULL;
}

TimebaseEvent* Timebase::getPreviousTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type)
{
    TimebaseEvent* pEvent = NULL;
    for(size_t nIndex = 0; nIndex < m_vEvents.size(); ++nIndex)
    {
        if(m_vEvents[nIndex]->type != type)
            continue;
        if(m_vEvents[nIndex]->measure < measure)
        if(m_vEvents[nIndex]->measure < measure || (m_vEvents[nIndex]->measure == measure && m_vEvents[nIndex]->tick < tick))
            pEvent = m_vEvents[nIndex];
        else
            return pEvent;
    }
    return pEvent;
}

uint32_t Timebase::getEventQuant()
{
    return m_vEvents.size();
}

TimebaseEvent* Timebase::getEvent(size_t index)
{
    if(index >= m_vEvents.size())
        return NULL;
    return m_vEvents[index];
}
