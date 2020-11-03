/*  Declares Timebase class providing tempo / time signature map
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

#include <cstdint> //provides uint data types

#pragma once

#include <vector>

// Timebase event types
#define TIMEBASE_TYPE_TEMPO     1
#define TIMEBASE_TYPE_TIMESIG   2

struct TimebaseEvent {
    uint16_t measure; // Measure at which event occurs in timeline
    uint16_t tick; // Tick at which event occurs within measure (0 for timesig)
    uint16_t type; // Event type [TIMEBASE_TYPE_TEMPO | TIMEBASE_TYPE_TIMESIG]
    uint16_t value; // Value
};

/** Timebase class provides timebase event map
*/
class Timebase
{
    public:
        /** @brief  Construct jack transport object
        *   @param  client Pointer to jack client
        */
        Timebase();

        /** @brief  Destruction called when object destroyed
        */
        ~Timebase();
        
        /** @brief  Add timebase event to map
        *   @param  measure Measure within which event occurs
        *   @param  tick Tick within measure at which event occurs
        *   @param  type Event type
        *   @param  value Event value
        */
        void addTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type, uint16_t value);

        /** @brief  Remove timebase event from map
        *   @param  measure Measure within which event occurs
        *   @param  tick Tick within measure at which event occurs
        *   @param  type Event type mask
        */
        void removeTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type);

        /** @brief  Get next timebase event
        *   @param  measure Measure from which to search
        *   @param  tick Tick within measure from which to search
        *   @param  type Timebase event type mask
        *   @retval TimebaseEvent* Pointer to timebase event or NULL if none found
        */
        TimebaseEvent* getNextTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type);

        /** @brief  Get previous timebase event
        *   @param  measure Measure from which to search
        *   @param  tick Tick within measure from which to search
        *   @param  type Timebase event type
        *   @retval TimebaseEvent* Pointer to timebase event or NULL if none found
        */
        TimebaseEvent* getPreviousTimebaseEvent(uint16_t measure, uint16_t tick, uint16_t type);

        /** @brief  Get quantity of timebase events
        *   @retval uint32_t Quanity of timebase events in map
        */
        uint32_t getEventQuant();
        
        /** @brief  Get timebase event by index
        *   @param  index Index of event
        *   @retval TimebaseEvent* Pointer to event. Null if invalid index
        */
        TimebaseEvent* getEvent(size_t index);

    private:
        std::vector<TimebaseEvent*> m_vEvents; // List of pointers to timebase events ordered by time
};
