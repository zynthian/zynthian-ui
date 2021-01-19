#pragma once

#include "event.h"
#include <vector>
#include <cstdint>

class Track
{
    public:
        Track();
        ~Track();
        
        /** @brief  Clears all events from track
        */
        void clear();

        /** @brief  Add an event to end of track
        *   @param  pEvent Pointer to an Event object
        *   @todo   Add ability to insert events
        */
        void addEvent(Event* pEvent);

        /** @brief  Remove event by index
        *   @param  nEvent Index of event to remove
        */
        void removeEvent(size_t nEvent);

        /** @brief  Remove event by pointer
        *   @param  pEvent Pointer to the event to remove
        */
        void removeEvent(Event* pEvent);

        /** @brief  Get specified event
        *   @param  nIndex Index of event (0..quantity of events -1)
        *   @retval Event* Pointer to event or NULL if invalid index
        */
        Event* getEvent(size_t nIndex);

        /** @brief  Get next event in list since last call or other navigation, advance to next event
        *   @param  bAdvance True to advance to next event (Default: true)
        *   @retval Event* Pointer to next event
        */
        Event* getNextEvent(bool bAdvance = true);

        /** @brief  Get index of next event
        *   @retval size_t Index of next event
        */
       size_t getNextEventId();

        /** @brief  Get the quantity of events
        *   @retval size_t Quantity of events
        */
        size_t getEvents();

        /** @brief  Set position of next event cursor
        *   @param  nTime Time in ticks since start of song
        */
       void setPosition(size_t nTime);

    private:
        uint32_t m_nPosition;
    	std::vector<Event*> m_vSchedule;
        size_t m_nNextEvent = 0; // Index of the next event
};
