/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include "zynsmf.h"

#include <stdio.h> //provides printf
#include <stdlib.h> //provides exit
#include <cstring> //provides strcmp, memset

FILE *g_pFileMidi;
bool g_bDebug = false;
bool g_bTimecodeBased; // True for timecode based time. False for metrical based time.
uint16_t g_nFormat = 0; // MIDI file format [0|1|2]
uint16_t g_nTracks = 0; // Quantity of MIDI tracks
uint8_t g_nSmpteFps = 0; // SMPTE frames per second (for timecode based time)
uint8_t g_nSmpteResolution = 0; // SMPTE subframe resolution  (for timecode based time)
uint16_t g_nTicksPerQuarterNote = 96; // Ticks per quarter note (for metrical based time)
uint16_t g_nManufacturerId = 0; // Manufacturers MIDI ID (if embeded)
uint32_t g_nDurationInTicks = 0; // Duration in seconds
uint32_t g_nMicrosecondsPerQuarterNote = 500000; // Microseconds per quarter note

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)
#define MAX_STRING_SIZE 256

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
		Event(uint32_t nTime, uint8_t nType, uint8_t nSubtype, uint8_t nSize, uint8_t* pData)
		{
			m_nTime = nTime;
			m_nType = nType;
			m_nSubtype = nSubtype;
			m_nSize = nSize;
			m_pData = pData;

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

		~Event()
		{
			delete [] m_pData;
		}

		uint32_t GetInt32()
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

	private:
		uint32_t m_nTime; // Absolute time at which event occurs (relative to start of file)
		uint8_t m_nType; // Event type [EVENT_TYPE_NONE|EVENT_TYPE_MIDI|EVENT_TYPE_SYSEX|EVENT_TYPE_META]
		uint8_t m_nSubtype; // Event subtype type, e.g. MIDI Note On, Song Start, etc.
		uint8_t m_nSize; // Size of event data
		uint8_t* m_pData; // Pointer to event specific data
};

#include <vector>
std::vector<Event*> g_vSchedule;

// Runs on library exit / destroy
void onExit()
{
	unload();
}


// Enable / disable debug output
void enableDebug(bool bEnable)
{
    printf("libsmf setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
}

// File management functions

int fileWrite8(uint8_t value, FILE *pFile)
{
	int nResult = fwrite(&value, 1, 1, pFile);
	return nResult;
}

uint8_t fileRead8(FILE* pFile)
{
	uint8_t nResult = 0;
	fread(&nResult, 1, 1, pFile);
	return nResult;
}

int fileWrite16(uint16_t value, FILE *pFile)
{
	for(int i = 1; i >=0; --i)
		fileWrite8((value >> i * 8), pFile);
	return 2;
}

uint16_t fileRead16(FILE* pFile)
{
	uint16_t nResult = 0;
	for(int i = 1; i >=0; --i)
	{
		uint8_t nValue;
		fread(&nValue, 1, 1, pFile);
		nResult |= nValue << (i * 8);
	}
	return nResult;
}

int fileWrite32(uint32_t value, FILE *pFile)
{
	for(int i = 3; i >=0; --i)
		fileWrite8((value >> i * 8), pFile);
	return 4;
}

uint32_t fileRead32(FILE* pFile)
{
	uint32_t nResult = 0;
	for(int i = 3; i >=0; --i)
	{
		uint8_t nValue;
		fread(&nValue, 1, 1, pFile);
		nResult |= nValue << (i * 8);
	}
	return nResult;
}

uint32_t fileReadVar(FILE* pFile)
{
	uint32_t nValue = 0;
	for(int i = 0; i < 4; ++i)
	{
		uint8_t nByte = fileRead8(pFile);
		nValue <<= 7;
		nValue |= (nByte & 0x7F);
		if((nByte & 0x80) == 0)
			break;
	}
	return nValue;
}

size_t fileReadString(FILE *pFile, char* pString, size_t nSize)
{
	size_t nRead = fread(pString, 1, nSize, pFile);
	pString[nRead] = '\0';
	return nRead;
}

bool load(char* filename)
{
	// Register the cleanup function to be called when program exits
    atexit(onExit);

	unload();

	FILE *pFile;
	pFile = fopen(filename, "r");
	if(pFile == NULL)
	{
        DPRINTF("Failed to open file '%s'\n", filename);
		return false;
	}
	char sHeader[4];
	char sTemp[MAX_STRING_SIZE];
	
    uint16_t nDivision = 0;
	uint8_t nTrack = 0;
	// Iterate each block within IFF file
	while(fread(sHeader, 4, 1, pFile) == 1)
	{
		uint32_t nDuration = 0;
		uint32_t nBlockSize = fileRead32(pFile);
		if(memcmp(sHeader, "MThd", 4) == 0)
		{
			// SMF file header
			DPRINTF("Found MThd block of size %u\n", nBlockSize);
            g_nFormat = fileRead16(pFile);
            g_nTracks = fileRead16(pFile);
            nDivision = fileRead16(pFile);
			g_bTimecodeBased = ((nDivision & 0x8000) == 0x8000);
			if(g_bTimecodeBased)
			{
				g_nSmpteFps = -(int8_t(nDivision & 0xFF00) >> 8);
				g_nSmpteResolution = nDivision & 0x00FF;
				DPRINTF("Standard MIDI File - Format: %u, Tracks: %u, SMPTE fps: %u, SMPTE subframe resolution: %u\n", g_nFormat, g_nTracks, g_nSmpteFps, g_nSmpteResolution);
			}
			else
			{
				g_nTicksPerQuarterNote = nDivision & 0x7FFF;
				DPRINTF("Standard MIDI File - Format: %u, Tracks: %u, Ticks per quarter note: %u\n", g_nFormat, g_nTracks, g_nTicksPerQuarterNote);
			}
			DPRINTF("\n");
		}
		else if(memcmp(sHeader, "MTrk", 4) == 0)
		{
			// SMF track header
			DPRINTF("Found MTrk block of size %u\n", nBlockSize);
			++nTrack;
			uint8_t nRunningStatus = 0;
			long nEnd = ftell(pFile) + nBlockSize;
			while(ftell(pFile) < nEnd)
			{
				uint32_t nDelta = fileReadVar(pFile);
				nDuration += nDelta;
				uint8_t nStatus = fileRead8(pFile);
				DPRINTF("Abs: %u Delta: %u ", nDuration, nDelta);
				if((nStatus & 0x80) == 0)
				{
					nStatus = nRunningStatus;
					fseek(pFile, -1, SEEK_CUR);
				}
				uint32_t nMessageLength;
				uint8_t nMetaType;
				uint8_t nChannel;
				uint8_t* pData;
				Event* pEvent = NULL;
				switch(nStatus)
				{
					case 0xFF:
						// Meta event
						nMetaType = fileRead8(pFile);
						nMessageLength = fileReadVar(pFile);
						pData = new uint8_t[nMessageLength + 1];
						fread(pData, nMessageLength, 1, pFile);
						pEvent = new Event(nDuration, EVENT_TYPE_META, nMetaType, nMessageLength, pData);
						g_vSchedule.push_back(pEvent);
						if(nMetaType == 0x51) // Tempo
							g_nMicrosecondsPerQuarterNote = pEvent->GetInt32();
						else if(nMetaType == 0x7F) // Manufacturer
							g_nManufacturerId = pEvent->GetInt32();
						nRunningStatus = 0;
						break;
					case 0xF0:
						// SysEx event
						//!@todo Store SysEx messages
						nMessageLength = fileReadVar(pFile);
						DPRINTF("SysEx %u bytes\n", nMessageLength);
						if(nMessageLength > 0)
						{
							fseek(pFile, nMessageLength - 1, SEEK_CUR);
							if (fileRead8(pFile) == 0xF7)
								nRunningStatus = 0xF0;
							else
								nRunningStatus = 0;
						}
						else
							nRunningStatus = 0;
						break;
					case 0xF7:
						// End of SysEx or Escape sequence
						nMessageLength = fileReadVar(pFile);
						if(nRunningStatus == 0xF0)
						{
							DPRINTF("SysEx continuation %u bytes\n", nMessageLength);
							if(nMessageLength > 0)
							{
								fseek(pFile, nMessageLength - 1, SEEK_CUR);
								if(fileRead8(pFile) == 0xF7)
									nRunningStatus = 0;
							}
							else
								nRunningStatus = 0;
						}
						else
						{
							DPRINTF("Escape sequence %u bytes\n", nMessageLength);
							pData = new uint8_t[nMessageLength];
							fread(pData, nMessageLength, 1, pFile);
							pEvent = new Event(nDuration, EVENT_TYPE_ESCAPE, 0, nMessageLength, pData);
							nRunningStatus = 0;
						}
						break;
					default:
						// MIDI event
						nChannel = nStatus & 0x0F;
						nStatus = nStatus & 0xF0;
						nRunningStatus = nStatus;
						switch(nStatus)
						{
							case 0x80: // Note Off
							case 0x90: // Note On
							case 0xA0: // Polyphonic Pressure
							case 0xB0: // Control Change
							case 0xE0: // Pitchbend
								// MIDI commands with 2 parameters
								pData = new uint8_t[2];
								fread(pData, 1, 2, pFile);
								g_vSchedule.push_back(new Event(nDuration, EVENT_TYPE_MIDI, nStatus, 1, pData));
								break;
							case 0xC0: // Program Change
							case 0xD0: // Channel Pressure
								pData = new uint8_t;
								fread(pData, 1, 1, pFile);
								g_vSchedule.push_back(new Event(nDuration, EVENT_TYPE_MIDI, nStatus, 2, pData));
								break;
							default:
								DPRINTF("Unexpected MIDI event 0x%02X\n", nStatus);
								nRunningStatus = 0;
						}
				}
			}
		}
		else
		{
			// Ignore unknown block
			DPRINTF("Found unsupported %c%c%c%c block of size %u\n", sHeader[0], sHeader[1], sHeader[2], sHeader[3], nBlockSize);
			fseek(pFile, nBlockSize, SEEK_CUR);
		}
		if(nDuration > g_nDurationInTicks)
			g_nDurationInTicks = nDuration;
	}

	fclose(pFile);
	if(!g_bTimecodeBased)
	{
		uint32_t nSeconds = g_nDurationInTicks / g_nTicksPerQuarterNote * g_nMicrosecondsPerQuarterNote  / 1000000;
		uint32_t nMinutes = (nSeconds / 60) % 60;
		uint32_t nHours = nSeconds / 3600;
		DPRINTF("Duration: %u ticks, %u quater notes, %u:%02u:%02u (assuming constant tempo)\n",  g_nDurationInTicks, g_nDurationInTicks / g_nTicksPerQuarterNote, nHours, nMinutes, nSeconds % 60);
		DPRINTF("g_nDurationInTicks: %u, g_nTicksPerQuarterNote: %u, g_nMicrosecondsPerQuarterNote: %u, nSeconds: %u\n", g_nDurationInTicks, g_nTicksPerQuarterNote, g_nMicrosecondsPerQuarterNote, nSeconds);
	}

	return true; //!@todo Return duration of longest track
}

void unload()
{
	for(auto it = g_vSchedule.begin(); it != g_vSchedule.end(); ++it)
		delete (*it);
	g_vSchedule.clear();
	g_bTimecodeBased = false;
	g_nFormat = 0;
	g_nTracks = 0;
	g_nSmpteFps = 0;
	g_nSmpteResolution = 0;
	g_nTicksPerQuarterNote = 96;
	g_nManufacturerId = 0;
	g_nDurationInTicks = 0;
	g_nMicrosecondsPerQuarterNote = 500000;
}

int getDuration()
{
	return g_nDurationInTicks / g_nTicksPerQuarterNote * g_nMicrosecondsPerQuarterNote  / 1000000;
}
