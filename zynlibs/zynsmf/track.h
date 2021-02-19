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

        /** @brief  Get current event in list
        *   @param  bAdvance True to advance to next event (Default: false)
        *   @retval Event* Pointer to next event
        */
        Event* getEvent(bool bAdvance = false);

        /** @brief  Get the quantity of events
        *   @retval size_t Quantity of events
        */
        size_t getEvents();

        /** @brief  Set position of next event cursor
        *   @param  nTime Time in ticks since start of song
        */
       void setPosition(size_t nTime);

        /** @brief  Mute track
        *   @param  bMute True to mute, false to unmute
        */
        void mute(bool bMute);

        /** @brief  Check if track is muted
        *   @retval bool True if muted
        */
        bool isMuted(); 

    private:
        bool m_bMute = false;
        uint32_t m_nPosition;
    	std::vector<Event*> m_vSchedule;
        size_t m_nNextEvent = 0; // Index of the next event
};
