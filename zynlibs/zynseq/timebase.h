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

#pragma once

#include "constants.h"
#include <cstdint> //provides uint data types
#include <vector>

// Timebase event types
#define TIMEBASE_TYPE_TEMPO     1
#define TIMEBASE_TYPE_TIMESIG   2
#define TIMEBASE_TYPE_ANY       0xFF // Bitwise mask

struct TimebaseEvent {
    uint16_t bar; // Bar at which event occurs in timeline
    uint16_t clock; // Clock at which event occurs within bar (0 for timesig)
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
        
        /** @brief  Get tempo at specified time
        *   @param  bar Bar at which to get tempo
        *   @param  clock Clock cycle within bar at which to get tempo
        *   @retval uint16_t Tempo in beats per minute
        */
        uint16_t getTempo(uint16_t bar, uint16_t clock);
        
        /** @brief  Get t at specified time
        *   @param  bar Bar at which to get time signature
        *   @param  clock Clock cycle within bar at which to get time signature
        *   @retval uint16_t Time signature in beats per bar
        */
        uint16_t getTimeSig(uint16_t bar, uint16_t clock);
        
        /** @brief  Add timebase event to map
        *   @param  bar Bar within which event occurs
        *   @param  clock Clock within bar at which event occurs
        *   @param  type Event type [TIMEBASE_TYPE_TEMPO | TIMEBASE_TYPE_TIMESIG]
        *   @param  value Event value
        */
        void addTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type, uint16_t value);

        /** @brief  Remove timebase event from map
        *   @param  bar Bar within which event occurs
        *   @param  clock Clock within bar at which event occurs
        *   @param  type Event type [TIMEBASE_TYPE_TEMPO | TIMEBASE_TYPE_TIMESIG]
        */
        void removeTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type);

        /** @brief  Get next timebase event
        *   @param  bar Bar from which to search
        *   @param  clock Clock within bar from which to search
        *   @param  type Event type mask [TIMEBASE_TYPE_TEMPO | TIMEBASE_TYPE_TIMESIG | TIMEBASE_TYPE_ANY]
        *   @retval TimebaseEvent* Pointer to timebase event or NULL if none found
        */
        TimebaseEvent* getNextTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type);

        /** @brief  Get next timebase event
        *   @param  pEvent Pointer to the event from which to search
        *   @retval TimebaseEvent* Pointer to next timebase event or NULL if none found
        */
        TimebaseEvent* getNextTimebaseEvent(TimebaseEvent* pEvent);

        /** @brief  Get previous timebase event
        *   @param  bat Bar from which to search
        *   @param  clock Clock within bar from which to search
        *   @param  type Event type mask [TIMEBASE_TYPE_TEMPO | TIMEBASE_TYPE_TIMESIG | TIMEBASE_TYPE_ANY]
        *   @retval TimebaseEvent* Pointer to timebase event or NULL if none found
        */
        TimebaseEvent* getPreviousTimebaseEvent(uint16_t bar, uint16_t clock, uint16_t type);

        /** @brief  Get first timebase event
        *   @retval TimebaseEvent* Pointer to first timebase event or NULL if none found
        */
        TimebaseEvent* getFirstTimebaseEvent();
        
        /** @brief  Get first event at specified time
        *   @param  bar Bar within which event occurs
        *   @param  clock Clock pulse within bar at which event occurs
        *   @retval TimebaseEvent* Pointer to the first timebase event at this time or NULL if none found
        */
        TimebaseEvent* GetEvent(uint16_t bar, uint16_t clock);

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
