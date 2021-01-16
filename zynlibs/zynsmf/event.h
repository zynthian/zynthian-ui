#pragma once

#include <cstdint> //provides uint32_t

enum EVENT_TYPE
{
	EVENT_TYPE_NONE,
	EVENT_TYPE_MIDI,
	EVENT_TYPE_SYSEX,
	EVENT_TYPE_META,
	EVENT_TYPE_ESCAPE
};

class Event
{
	public:
		Event(uint32_t nTime, uint8_t nType, uint8_t nSubtype, uint32_t nSize, uint8_t* pData, bool bDebug = false);

		~Event();

		uint32_t getInt32();

        /** @brief  Get time of event relative to start of track
        *   @retval int Ticks since start of song
        */
        uint32_t getTime();

		/**	@brief	Get event type [EVENT_TYPE_NONE|EVENT_TYPE_MIDI|EVENT_TYPE_SYSEX|EVENT_TYPE_META|EVENT_TYPE_ESCAPE]
		*	@retval	uint8_t Event type
		*/
		uint8_t getType();

		/**	@brief	Get event subtype
		*	@retval	uint8_t Event subtype, e.g. MIDI status byte
		*/
		uint8_t getSubtype();

		/**	@brief	Get size of event data
		*	@retval	uint_8 Size of data in bytes
		*/
		uint32_t getSize();

		/**	@brief	Get pointer to data
		*	@retval	uint8_t* Pointer to data
		*/
		uint8_t* getData();

	private:
		uint32_t m_nTime; // Absolute time at which event occurs (relative to start of file) in milliseconds
		uint8_t m_nType; // Event type [EVENT_TYPE_NONE|EVENT_TYPE_MIDI|EVENT_TYPE_SYSEX|EVENT_TYPE_META]
		uint8_t m_nSubtype; // Event subtype type, e.g. MIDI Note On, Song Start, etc.
		uint8_t m_nSize; // Size of event data
		uint8_t* m_pData; // Pointer to event specific data
		bool m_bDebug; // True to enable debug output
};

