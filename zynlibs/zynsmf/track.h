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

        /** @brief  Get event at position
        *   @param  nPosition Index of event
        *   @retval Event* Pointer to event or NULL if invalid position
        */
        Event* getEvent(size_t nPosition);

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
        size_t getQuantityOfEvents();

        /** @brief  Set position
        *   @param  nTime Time in milliseconds
        */
       void setPosition(size_t nTime);

    private:
        uint32_t m_nPosition;
    	std::vector<Event*> m_vSchedule;
        size_t m_nNextEvent = 0; // Index of the next event
};
