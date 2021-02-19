#include "event.h"
#include <stdio.h> //provides printf
#include <cstring> //provides strcmp, memset

#define DPRINTF(fmt, args...) if(m_bDebug) printf(fmt, ## args)

Event::Event(uint32_t nTime, uint8_t nType, uint8_t nSubtype, uint32_t nSize, uint8_t* pData, bool bDebug)
{
	m_nTime = nTime;
	m_nType = nType;
	m_nSubtype = nSubtype;
	m_nSize = nSize;
	m_pData = pData;
	m_bDebug = bDebug;

	if(nType == EVENT_TYPE_META)
	{
		switch(nSubtype)
		{
			case 0x00:
				DPRINTF("Meta Sequence Number: %u\n", *pData << 8 | *(pData + 1));
				break;
			case 0x01:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Text: %s\n", pData);
				break;
			case 0x02:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Copyright: %s\n", pData);
				break;
			case 0x03:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Seq/Track Name: %s\n", pData);
				break;
			case 0x04:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Instrument Name: %s\n", pData);
				break;
			case 0x05:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Lyric: %s\n", pData);
				break;
			case 0x06:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Marker: %s\n", pData);
				break;
			case 0x07:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Cue Point: %s\n", pData);
				break;
			case 0x08:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Program Name: %s\n", pData);
				break;
			case 0x09:
				memset(m_pData + nSize, 0, 1);
				DPRINTF("Meta Device Name: %s\n", pData);
				break;
			case 0x20:
				DPRINTF("Meta MIDI Channel: %u\n", *pData);
				break;
			case 0x21:
				DPRINTF("Meta MIDI Port: %u\n", *pData);
				break;
			case 0x2F:
				DPRINTF("Meta End Of Track\n");
				break;
			case 0x51:
				DPRINTF("Meta Tempo: %u\n", *pData << 16 | *(pData + 1) << 8 | *(pData + 2));
				break;
			case 0x54:
				DPRINTF("Meta SMPTE Offset: %u:%u:%u.%u.%u\n", *pData, *(pData + 1), *(pData + 2), *(pData + 3), *(pData + 4));
				break;
			case 0x58:
				DPRINTF("Meta Time Signature: %u/%u %u clocks per click, %u 32nd notes per quarter note\n", *(pData), 1<<(*(pData + 1)), *(pData + 2), *(pData + 3));
				break;
			case 0x59:
				DPRINTF("Meta Key Signature: %04x\n", *pData << 8 | *(pData + 1));
				break;
			case 0x7F:
				if(nSize == 0)
					DPRINTF("Meta Sequencer Specific Event, Manufacturer ID: %u\n", *(pData + 1) << 8 | *(pData + 2));
				else
					DPRINTF("Meta Sequencer Specific Event, Manufacturer ID: %u\n", *pData);
				break;
			default:
				DPRINTF("Meta unknown %02X length: %u\n", nType, nSize);
			//!@todo stuff goes here
			/*
			case 0xF1:
				DPRINTF("MIDI Time Code Quater Frame: %04x %04x\n", uint32_t(pData), uint32_t(pData));
				break;
			case 0xF2:
				DPRINTF("MIDI Song PositionPointer\n");
				break;
			case 0xF3:
				DPRINTF("MIDI Song Select: %u\n", uint8_t(pData));
				break;
			case 0xF6:
				DPRINTF("MIDI Tune Request\n");
			case 0xF8:
				DPRINTF("MIDI Timing Clock\n");
				break;
			case 0xFA:
				DPRINTF("MIDI Start\n");
				break;
			case 0xFB:
				DPRINTF("MIDI Continue\n");
				break;
			case 0xFC:
				DPRINTF("MIDI Stop\n");
				break;
			case 0xFE:
				DPRINTF("MIDI Active Sensing\n");
				break;
			default:
				DPRINTF("Unknown escape sequence 0x%02X of length %u\n", nStatus, nMessageLength);
				fseek(pFile, nMessageLength, SEEK_CUR);
			*/
		}
	}
	else if(nType == EVENT_TYPE_MIDI)
	{
		uint8_t nChannel = nSubtype & 0x0F;
		uint8_t nStatus = nSubtype & 0xF0;
		switch(nStatus)
		{
			case 0x80:
				DPRINTF("MIDI Note Off Channel:%u Note: %u Velocity: %u\n", nChannel, *(pData), *(pData + 1));
				// Convert note off to zero velocity note on (used elsewhere, e.g. to silence hanging notes and may offer running status)
				m_nSubtype = 0x90;
				*(m_pData + 1) = 0x00;
				break;
			case 0x90:
				DPRINTF("MIDI Note On Channel:%u Note: %u Velocity: %u\n", nChannel, *(pData), *(pData + 1));
				break;
			case 0xA0:
				DPRINTF("MIDI Poly Key Pressure Channel:%u Note: %u Pressure: %u\n", nChannel, *(pData), *(pData + 1));
				break;
			case 0xB0:
				DPRINTF("MIDI Control Change Channel:%u Controller:%u Value: %u\n", nChannel, *(pData), *(pData + 1));
				break;
			case 0xC0:
				DPRINTF("MIDI Program Change Channel:%u Program: %u\n", nChannel, *(pData));
				break;
			case 0xD0:
				DPRINTF("MIDI Channel Pressure Channel:%u Pressure: %u\n", nChannel, *(pData));
				break;
			case 0xE0:
				DPRINTF("MIDI Pitch Bend Channel:%u Bend: %u\n", nChannel, *(pData) << 7 | *(pData + 1));
				break;
			default:
				DPRINTF("Unexpected MIDI event 0x%02X\n", nStatus);
		}
	}
}

Event::~Event()
{
	delete [] m_pData;
}

uint32_t Event::getInt32()
{
	uint32_t nValue = 0;
	for(int i = 0; i < 4; ++i)
	{
		if(i >= m_nSize)
			break;
		nValue <<= 8;
		nValue |= *(m_pData + i);
	}
	return nValue;
}

uint32_t Event::getTime()
{
	return m_nTime;
}

uint8_t Event::getType()
{
	return m_nType;
}

uint8_t Event::getSubtype()
{
	return m_nSubtype;
}

uint32_t Event::getSize()
{
	return m_nSize;
}

uint8_t* Event::getData()
{
	return m_pData;
}