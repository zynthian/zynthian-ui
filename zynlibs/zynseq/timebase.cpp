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

uint16_t Timebase::getTempo(uint16_t bar, uint16_t clock)
{
    uint16_t nValue = DEFAULT_TEMPO;
    for(auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it)
    {
        if((*it)->type == TIMEBASE_TYPE_TEMPO && ((*it)->bar < bar || (*it)->bar == bar && (*it)->clock <= clock))
            nValue = (*it)->value;
    }
    return nValue;
}
#include <stdio.h>
uint16_t Timebase::getTimeSig(uint16_t bar, uint16_t clock)
{
    uint16_t nValue = 4;
    for(auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it)
    {
        if((*it)->type == TIMEBASE_TYPE_TIMESIG && ((*it)->bar < bar || (*it)->bar == bar && (*it)->clock <= clock))
            nValue = (*it)->value;
    }
    return nValue;
}

void Timebase::addTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type, uint16_t value)
{
    auto it = m_vEvents.begin();
    for(; it < m_vEvents.end(); ++it)
    {
        if((*it)->bar == bar && (*it)->clock == clock && (*it)->type == type)
        {
            // Replace existing event
            (*it)->value = value;
            return;
        }
        if((*it)->bar > bar || ((*it)->bar == bar && (*it)->clock > clock))
            break; // Found point to insert
    }
    TimebaseEvent* pEvent = new TimebaseEvent;
    pEvent->bar = bar;
    pEvent->clock = clock;
    pEvent->type = type;
    pEvent->value = value;
    m_vEvents.insert(it, pEvent);
}

void Timebase::removeTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type)
{
    for(auto it = m_vEvents.begin(); it < m_vEvents.end(); ++it)
    {
        if((*it)->bar == bar && (*it)->clock == clock && (*it)->type == type)
        {
            delete(*it);
            m_vEvents.erase(it);
            return;
        }
    }
}

TimebaseEvent* Timebase::getNextTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type)
{
    for(auto it = m_vEvents.begin(); it < m_vEvents.end(); ++it)
    {
        if((*it)->bar < bar || ((*it)->bar == bar && (*it)->clock <= clock))
            continue;
        if((*it)->type & type)
            return (*it);
    }
    return NULL;
}

TimebaseEvent* Timebase::getNextTimebaseEvent(TimebaseEvent* pEvent)
{
    if(!pEvent || m_vEvents.size() < 2)
        return NULL;
    for(size_t nIndex = 0; nIndex < m_vEvents.size() - 1; ++nIndex)
    {
        if(m_vEvents[nIndex] != pEvent)
            continue;
        return m_vEvents[nIndex + 1];
    }
    return NULL;
}

TimebaseEvent* Timebase::getPreviousTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type)
{
    TimebaseEvent* pEvent = NULL;
    for(auto it = m_vEvents.begin(); it < m_vEvents.end(); ++it)
    {
        if(!((*it)->type & type))
            continue;
        if((*it)->bar < bar || ((*it)->bar == bar && (*it)->clock < clock))
            pEvent = (*it);
        else
            return pEvent;
    }
    return pEvent;
}

TimebaseEvent* Timebase::getFirstTimebaseEvent()
{
    if(m_vEvents.size())
        return m_vEvents[0];
    return NULL;
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
