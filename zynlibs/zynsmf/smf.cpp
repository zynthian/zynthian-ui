/** Implementation of standard MIDI file class
*/

#include "smf.h"

#include <stdio.h> //provides printf
#include <cstring> //provides strcmp, memset

#define MAX_TRACKS 16 // Maximum quantity of tracks automatically created
#define DPRINTF(fmt, args...) if(m_bDebug) printf(fmt, ## args)

Smf::~Smf()
{
	unload();
}

void Smf::enableDebug(bool bEnable)
{
    m_bDebug = bEnable;
}

// Private file management functions

int Smf::fileWrite8(uint8_t nValue, FILE *pFile)
{
	int nResult = fwrite(&nValue, 1, 1, pFile);
	return nResult;
}

uint8_t Smf::fileRead8(FILE* pFile)
{
	uint8_t nResult = 0;
	fread(&nResult, 1, 1, pFile);
	return nResult;
}

int Smf::fileWrite16(uint16_t nValue, FILE *pFile)
{
	for(int i = 1; i >=0; --i)
		fileWrite8((nValue >> i * 8), pFile);
	return 2;
}

uint16_t Smf::fileRead16(FILE* pFile)
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

int Smf::fileWrite32(uint32_t nValue, FILE *pFile)
{
	for(int i = 3; i >=0; --i)
		fileWrite8((nValue >> i * 8), pFile);
	return 4;
}

uint32_t Smf::fileRead32(FILE* pFile)
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

int Smf::fileWriteVar(uint32_t nValue, FILE* pFile)
{
	uint8_t aVal[] = {0,0,0,0};
	int nLen = 0;
	for(int i = 3; i >= 0; --i)
	{
		aVal[i] |= nValue & 0x7F;
		if(nValue >0x7F && i)
				aVal[i-1] = 0x80;
		nValue >>= 7;
	}
	for(int i = 0; i< 4; ++i)
	{
		if(aVal[i] || nLen)
		{
			fileWrite8(aVal[i], pFile);
			++nLen;
		}
	}
	if(!nLen)
		return fileWrite8(0, pFile);
	return nLen;
}

uint32_t Smf::fileReadVar(FILE* pFile)
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

size_t Smf::fileWriteString(const char* pString, size_t nSize, FILE *pFile)
{
	return fwrite(pString, 1, nSize, pFile);
}

size_t Smf::fileReadString(char* pString, size_t nSize, FILE *pFile)
{
	size_t nRead = fread(pString, 1, nSize, pFile);
	pString[nRead] = '\0';
	return nRead;
}

uint32_t Smf::getMicrosecondsPerQuarterNote(uint32_t nTime)
{
	for(auto it = m_mTempoMap.begin(); it != m_mTempoMap.end(); ++it)
	{
		if(it->first < nTime)
			continue;
		return it->second;
	}
	return 500000; // Default value for 120bpm
}

void Smf::muteTrack(size_t nTrack, bool bMute)
{
	if(nTrack >= m_vTracks.size())
		return;
	m_vTracks[nTrack]->mute(bMute);
}

bool Smf::isTrackMuted(size_t nTrack)
{
	if(nTrack >= m_vTracks.size())
		return false;
	return m_vTracks[nTrack]->isMuted();
}


/*** Public functions ***/

bool Smf::load(char* sFilename)
{
	unload();

	FILE *pFile;
	pFile = fopen(sFilename, "r");
	if(pFile == NULL)
	{
		DPRINTF("Failed to open file '%s'\n", sFilename);
		return false;
	}
	char sHeader[4];
	
	
	// Iterate each block within IFF file
	while(fread(sHeader, 4, 1, pFile) == 1)
	{
		uint32_t nPosition = 0;
		double fPosition = 0.0;
		uint32_t nBlockSize = fileRead32(pFile);
		if(memcmp(sHeader, "MThd", 4) == 0)
		{
			// SMF file header
			DPRINTF("Found MThd block of size %u\n", nBlockSize);
			m_nFormat = fileRead16(pFile);
			m_nTracks = fileRead16(pFile);
			uint16_t nDivision = fileRead16(pFile);
			m_bTimecodeBased = ((nDivision & 0x8000) == 0x8000);
			if(m_bTimecodeBased)
			{
				m_nSmpteFps = -(int8_t(nDivision & 0xFF00) >> 8);
				m_nSmpteResolution = nDivision & 0x00FF;
				DPRINTF("Standard MIDI File - Format: %u, Tracks: %u, SMPTE fps: %u, SMPTE subframe resolution: %u\n", m_nFormat, m_nTracks, m_nSmpteFps, m_nSmpteResolution);
				unload();
				printf("zynsmf does not support SMPTE timebase SMF\n");
				//!@todo Add support for SMPTE timebase
				return false;
			}
			else
			{
				m_nTicksPerQuarterNote = nDivision & 0x7FFF;
				DPRINTF("Standard MIDI File - Format: %u, Tracks: %u, Ticks per quarter note: %u\n", m_nFormat, m_nTracks, m_nTicksPerQuarterNote);
			}
			DPRINTF("\n");
			for(size_t i = 0; i < nBlockSize - 6; ++i)
				fileRead8(pFile); // Eat any extra header bytes which might be added in later version of SMF standard
		}
		else if(memcmp(sHeader, "MTrk", 4) == 0)
		{
			// SMF track header
			DPRINTF("Found MTrk block of size %u\n", nBlockSize);
			Track* pTrack = new Track();
			m_vTracks.push_back(pTrack);
			uint8_t nRunningStatus = 0;
			long nEnd = ftell(pFile) + nBlockSize;
			while(ftell(pFile) < nEnd)
			{
				uint32_t nDelta = fileReadVar(pFile);
				nPosition += nDelta;
				fPosition += double(getMicrosecondsPerQuarterNote(nPosition)) * nDelta / m_nTicksPerQuarterNote;
				uint8_t nStatus = fileRead8(pFile);
				DPRINTF("Abs: %u Delta: %u ", nPosition, nDelta);
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
						pEvent = new Event(nPosition, EVENT_TYPE_META, nMetaType, nMessageLength, pData);
						pTrack->addEvent(pEvent);
						if(nMetaType == 0x51)
							m_mTempoMap[nPosition] = pEvent->getInt32();
						else if(nMetaType == 0x7F) // Manufacturer
							m_nManufacturerId = pEvent->getInt32();
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
							pEvent = new Event(nPosition, EVENT_TYPE_ESCAPE, 0, nMessageLength, pData);
							pTrack->addEvent(pEvent);
							nRunningStatus = 0;
						}
						break;
					default:
						// MIDI event
						nChannel = nStatus & 0x0F;
//						nStatus = nStatus & 0xF0;
						nRunningStatus = nStatus;
						switch(nStatus & 0xF0)
						{
							case 0x80: // Note Off
							case 0x90: // Note On
							case 0xA0: // Polyphonic Pressure
							case 0xB0: // Control Change
							case 0xE0: // Pitchbend
								// MIDI commands with 2 parameters
								pData = new uint8_t[2];
								fread(pData, 1, 2, pFile);
								pEvent = new Event(nPosition, EVENT_TYPE_MIDI, nStatus, 2, pData);
								pTrack->addEvent(pEvent);
								break;
							case 0xC0: // Program Change
							case 0xD0: // Channel Pressure
								pData = new uint8_t;
								fread(pData, 1, 1, pFile);
								pEvent = new Event(nPosition, EVENT_TYPE_MIDI, nStatus, 1, pData);
								pTrack->addEvent(pEvent);
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
		if(nPosition > m_nDurationInTicks)
			m_nDurationInTicks = nPosition;
		if(fPosition > m_fDuration * 1000000)
			m_fDuration = fPosition / 1000000;
	}

	fclose(pFile);
	setPosition(0);

	return true;
}

bool Smf::save(char* sFilename)
{
	if(getEvents() == 0)
		return true; // Don't save if empty
	FILE *pFile;
	pFile = fopen(sFilename, "w");
	if(pFile == NULL)
	{
        DPRINTF("Failed to open file '%s'\n", sFilename);
		return false;
	}

	// Write file header IFF chunk
	fileWriteString("MThd", 4, pFile);
	fileWrite32(6, pFile);
	fileWrite16(m_nFormat, pFile);
	fileWrite16(getTracks(), pFile);
	if(m_bTimecodeBased)
		fileWrite16(m_nTicksPerQuarterNote | 0x8000, pFile);
	else
		fileWrite16(m_nTicksPerQuarterNote, pFile);

	// Write each track
	for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
	{
		fileWriteString("MTrk", 4, pFile);
		uint32_t nSizePos = ftell(pFile); // Position of chunk size value within file
		fileWrite32(0, pFile); // Placeholder for chunk size

		// Write each event
		Track* pTrack = *it;
		pTrack->setPosition(0);
		uint32_t nTime = 0;
		uint8_t nRunningStatus = 0x00;
		while(Event* pEvent = pTrack->getEvent(true))
		{
			fileWriteVar(pEvent->getTime() - nTime, pFile);
			nTime = pEvent->getTime();
			switch(pEvent->getType())
			{
				case EVENT_TYPE_MIDI:
//					if(nRunningStatus != pEvent->getSubtype()) // Running status is more complex - need to consider if event from other track will interfere
					{
						fileWrite8(pEvent->getSubtype(), pFile);
						nRunningStatus = pEvent->getSubtype();
					}
					break;
				case EVENT_TYPE_META:
					fileWrite8(0xFF, pFile);
					fileWrite8(pEvent->getSubtype(), pFile);
					fileWrite8(pEvent->getSize(), pFile); //!@todo This should be a variable length quantity
					nRunningStatus = 0x00;
					break;
				case EVENT_TYPE_SYSEX:
					//!@todo Implement SysEx write
					nRunningStatus = 0x00;
					break;
				default:
					nRunningStatus = 0x00;
			}
			fwrite(pEvent->getData(), 1, pEvent->getSize(), pFile);
		}
		uint32_t nSize = ftell(pFile) - nSizePos - 4;
		fseek(pFile, nSizePos, SEEK_SET);
		fileWrite32(nSize, pFile);
		fseek(pFile, 0, SEEK_END);
		//!@todo Add missing end of track events
	}

	fclose(pFile);
	return true;
}

void Smf::unload()
{
	for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
		delete (*it);
	m_vTracks.clear();
	m_bTimecodeBased = false;
	m_nFormat = 0;
	m_nTracks = 0;
	m_nSmpteFps = 0;
	m_nSmpteResolution = 0;
	m_nTicksPerQuarterNote = 96;
	m_nManufacturerId = 0;
	m_nDurationInTicks = 0;
	m_fDuration = 0.0;
}

double Smf::getDuration()
{
	return m_fDuration;
}

Event* Smf::getEvent(bool bAdvance)
{
	size_t nPosition = -1;
	for(size_t nTrack = 0; nTrack < m_vTracks.size(); ++nTrack)
	{
		// Iterate through tracks and find earilest next event
		Event* pEvent = m_vTracks[nTrack]->getEvent(false);
		if(!m_vTracks[nTrack]->isMuted() && pEvent && pEvent->getTime() < nPosition)
		{
			nPosition = pEvent->getTime();
			m_nCurrentTrack = nTrack;
		}
	}
	if(nPosition == -1)
		return NULL;
	if(bAdvance)
		m_nPosition = nPosition;
	return m_vTracks[m_nCurrentTrack]->getEvent(bAdvance);
}

void Smf::addEvent(size_t nTrack, Event* pEvent)
{
	if(nTrack >= m_vTracks.size())
	{
		if(nTrack > MAX_TRACKS)
		return;
		while(m_vTracks.size() <= nTrack)
			addTrack();
	}
	m_vTracks[nTrack]->addEvent(pEvent);
	if(pEvent->getTime() > m_nDurationInTicks)
		m_nDurationInTicks = pEvent->getTime();
}

void Smf::setPosition(size_t nTime)
{
	for(auto it = m_vTracks.begin(); it!= m_vTracks.end(); ++it)
		(*it)->setPosition(nTime);
	m_nPosition = nTime;
}

size_t Smf::getTracks()
{
	return m_vTracks.size();
}

size_t Smf::addTrack()
{
	m_vTracks.push_back(new Track());
	return m_vTracks.size() - 1;
}

bool Smf::removeTrack(size_t nTrack)
{
	if(nTrack >= m_vTracks.size())
		return false;
	delete m_vTracks[nTrack];
	m_vTracks.erase(m_vTracks.begin() + nTrack);
	return true;
}

uint8_t Smf::getFormat()
{
	return m_nFormat;
}

uint32_t Smf::getEvents(size_t nTrack)
{
	if(nTrack == -1)
	{
		uint32_t nCount = 0;
		for(auto it = m_vTracks.begin(); it != m_vTracks.end(); ++it)
			nCount += (*it)->getEvents();
		return nCount;
	}
	if(nTrack >= m_vTracks.size())
		return 0;
	return m_vTracks[nTrack]->getEvents();
}

uint16_t Smf::getTicksPerQuarterNote()
{
	return m_nTicksPerQuarterNote;
}

size_t Smf::getCurrentTrack()
{
	return m_nCurrentTrack;
}