#pragma once

#include <cstdint> //provides uint32_t

enum EVENT_TYPE
{
	EVENT_TYPE_NONE				= 0x00,
	EVENT_TYPE_MIDI				= 0x01,
	EVENT_TYPE_SYSEX			= 0x02,
	EVENT_TYPE_META				= 0x03,
	EVENT_TYPE_ESCAPE			= 0x04
};

enum META_TYPE
{
	META_TYPE_SEQ_NUMBER		= 0x00,
	META_TYPE_TEXT				= 0x01,
	META_TYPE_COPYRIGHT			= 0x02,
	META_TYPE_TRACK_NAME		= 0x03,
	META_TYPE_INSTUMENT_NAME	= 0x04,
	META_TYPE_LYRIC				= 0x05,
	META_TYPE_MARKER			= 0x06,
	META_TYPE_CUE_POINT			= 0x07,
	META_TYPE_MIDI_CHANNEL		= 0x20,
	META_TYPE_END_OF_TRACK		= 0x2F,
	META_TYPE_TEMPO				= 0x51,
	META_TYPE_SMPTE_OFFSET		= 0x54,
	META_TYPE_TIME_SIGNATURE	= 0x58,
	META_TYPE_KEY_SIGNATURE		= 0x59,
	META_TYPE_SEQ_SPECIFIC		= 0x7F
};

enum MIDI_STATUS
{
	MIDI_NOTE_OFF				= 0x80, //128
	MIDI_NOTE_ON				= 0x90, //144
	MIDI_POLY_PRESSURE			= 0xA0, //160
	MIDI_CONTROLLER         	= 0xB0, //176
	MIDI_PROGRAM_CHANGE			= 0xC0, //192
	CHANNEL_PRESSURE			= 0xD0, //208
	MIDI_PITCH_BEND				= 0xE0, //224
	MIDI_ALL_SOUND_OFF      	= 0x78, //120
	MIDI_ALL_NOTES_OFF      	= 0x7B //123
};

class Event
{
	public:
		/**	@brief	Create an event object
		*	@param	nTime Ticks since start of song
		*	@param	nType Event type [EVENT_TYPE_NONE|EVENT_TYPE_MIDI|EVENT_TYPE_SYSEX|EVENT_TYPE_META|EVENT_TYPE_ESCAPE]
		*	@param	nSubtype Type specific code, e.g. status byte of MIDI event
		*	@param	nSize Size of data in bytes
		*	@param	pData Pointer to event data
		*	@param	bDebug True to enable debug output (Default: false)
		*/
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
		uint32_t m_nTime; // Absolute time at which event occurs (relative to start of file) in ticks
		uint8_t m_nType; // Event type [EVENT_TYPE_NONE|EVENT_TYPE_MIDI|EVENT_TYPE_SYSEX|EVENT_TYPE_META]
		uint8_t m_nSubtype; // Event subtype type, e.g. MIDI Note On, Song Start, meta type, etc.
		uint8_t m_nSize; // Size of event data
		uint8_t* m_pData; // Pointer to event specific data
		bool m_bDebug; // True to enable debug output
};

