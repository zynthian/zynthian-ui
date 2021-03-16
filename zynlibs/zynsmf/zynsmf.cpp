/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include "zynsmf.h"

#include <stdio.h> //provides printf
#include <cstring> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <jack/midiport.h> //provides interface to JACK MIDI ports
#include <map> //provides std::map

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)

enum playState
{
	STOPPED		= 0,
	STARTING	= 1,
	PLAYING		= 2,
	STOPPING	= 3
};

jack_client_t* g_pJackClient = NULL;
jack_port_t* g_pMidiInputPort = NULL;
jack_port_t* g_pMidiOutputPort = NULL;

bool g_bDebug = false;
uint8_t g_nPlayState = STOPPED;
bool g_bRecording = false;
bool g_bLoop = false; // True to loop at end of song
jack_nframes_t g_nSamplerate = 44100;
uint32_t g_nMicrosecondsPerQuarterNote = 500000; // Current tempo
double g_dPlayerTicksPerFrame; // Current tempo
double g_dRecorderTicksPerFrame; // Current tempo
double g_dPosition = 0.0; // Position within song in ticks
uint32_t g_nRecordStartPosition = 0; // Jack frame location when recording started
std::map<uint16_t,uint8_t> m_mHangingMidi; // Map of played (not released) notes indexed by 16-bit word (MIDI channel << 8) | note value

Smf* g_pPlayerSmf = NULL; // Pointer to the SMF object that is attached to player
Smf* g_pRecorderSmf = NULL; // Pointer to the SMF object that is attached to recorder
Smf* g_pSmf = NULL; // Pointer to the SMF containing g_pEvent (current event)
Event* g_pEvent = NULL; // Pointer to the current event

//!@todo If playback is active and the parent process closes then seg fault occurs probably because Jack continutes to try to access the object

// Silly little class to provide a vector of pointers and clean up on exit
class SmfFactory {
	public:
		~SmfFactory()
		{
			for(auto it = m_vSmf.begin(); it != m_vSmf.end(); ++it)
				delete *it;
		}
		std::vector<Smf*>* getVector()
		{
			return &m_vSmf;
		}
	private:
		std::vector<Smf*> m_vSmf;
};

// Create instance of SmfFactory on stack so that it will clean up on exit
SmfFactory g_Smf;
auto g_pvSmf = g_Smf.getVector();

/*** Private functions not exposed as external C functions (not declared in header) ***/

// return true if pointer is in list
bool isSmfValid(Smf* pSmf)
{
	for(auto it = g_pvSmf->begin(); it != g_pvSmf->end(); ++it)
	{
		if(*it == pSmf)
			return true;
	}
	return false;
}

/*** Public functions exposed as external C functions in header ***/

Smf* addSmf()
{
	Smf* pSmf = new Smf();
	g_pvSmf->push_back(pSmf);
	return pSmf;
}

void removeSmf(Smf* pSmf)
{
	for(auto it = g_pvSmf->begin(); it != g_pvSmf->end(); ++it)
	{
		if(*it != pSmf)
			continue;
		delete *it;
		g_pvSmf->erase(it);
		return;
	}
}

size_t getSmfCount()
{
	return g_pvSmf->size();
}

void enableDebug(bool bEnable)
{
    printf("libsmf setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
	for(auto it = g_pvSmf->begin(); it != g_pvSmf->end(); ++it)
		(*it)->enableDebug(bEnable);
}

bool load(Smf* pSmf, char* filename)
{
	if(!isSmfValid(pSmf))
		return false;
	return pSmf->load(filename);
}

bool save(Smf* pSmf, char* filename)
{
	if(!isSmfValid(pSmf))
		return false;
	return pSmf->save(filename);
}

void unload(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return;
	pSmf->unload();
}

double getDuration(Smf* pSmf)
{
	if(!isSmfValid)
		return 0.0;
	return pSmf->getDuration();
}

void setPosition(Smf* pSmf, uint32_t time)
{
	if(!isSmfValid(pSmf))
		return;
	pSmf->setPosition(time);
	g_pSmf = pSmf;
	g_pEvent = pSmf->getEvent(false);
	g_dPosition = double(time);
}

uint32_t getTracks(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return 0;
	return pSmf->getTracks();
}

uint8_t getFormat(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return 0;
	return pSmf->getFormat();
}

uint32_t getEvents(Smf* pSmf, size_t nTrack)
{
	if(!isSmfValid(pSmf))
		return 0;
	return pSmf->getEvents(nTrack);
}

void addNote(Smf* pSmf, uint32_t nTrack, uint32_t nTime, uint32_t nDuration, uint8_t nChannel, uint8_t nNote, uint8_t nVelocity)
{
	if(!isSmfValid(pSmf))
		return;
	uint8_t* pData = new uint8_t[2];
	*pData = nNote;
	*(pData + 1) = nVelocity;
	Event* pEvent = new Event(nTime, EVENT_TYPE_MIDI, 0x90 | (nChannel & 0x0F), 2, pData);
	pSmf->addEvent(nTrack, pEvent);
	pData = new uint8_t[2];
	*pData = nNote;
	*(pData + 1) = 0;
	pEvent = new Event(nTime + nDuration, EVENT_TYPE_MIDI, 0x90 | (nChannel & 0x0F), 2, pData);
	pSmf->addEvent(nTrack, pEvent);
}

void addTempo(Smf* pSmf, uint32_t nTime, double dTempo)
{
	if(!isSmfValid(pSmf))
		return;
	uint32_t nUspqn = (60000000/dTempo);
	//!@todo Validate tempo calculation
	uint8_t* pData = new uint8_t[3];
	*pData = uint8_t(nUspqn >> 16);
	*(pData + 1) = uint8_t(nUspqn >> 8);
	*(pData + 2) = uint8_t(nUspqn & 0xFF);
	Event* pEvent = new Event(nTime, EVENT_TYPE_META, 0x51, 3, pData);
	pSmf->addEvent(0, pEvent);
}

void setEndOfTrack(Smf* pSmf, uint32_t nTrack, uint32_t nTime)
{
	if(!isSmfValid(pSmf))
		return;
	//!@todo remove existing end of track event
	Event* pEvent = new Event(nTime, EVENT_TYPE_META, 0x2F, 0, NULL);
	pSmf->addEvent(nTrack, pEvent);
}

uint16_t getTicksPerQuarterNote(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return 0;
	return pSmf->getTicksPerQuarterNote();
}

bool getEvent(Smf* pSmf, bool bAdvance)
{
	if(!isSmfValid(pSmf))
		return false;
	g_pSmf = pSmf;
	g_pEvent = pSmf->getEvent(bAdvance);
	return (g_pEvent != NULL);
}

size_t getEventTrack()
{
	if(!isSmfValid(g_pSmf))
		return NO_EVENT;
	return g_pSmf->getCurrentTrack();
}

uint32_t getEventTime()
{
	if(!g_pEvent)
		return NO_EVENT;
	return g_pEvent->getTime();
}

uint8_t getEventType()
{
	if(!g_pEvent)
		return EVENT_TYPE_NONE;
	return g_pEvent->getType();
}

uint8_t getEventChannel()
{
	if(!g_pEvent || g_pEvent->getType() != EVENT_TYPE_MIDI)
		return 0xFF;
	return g_pEvent->getSubtype() & 0x0F;
}

uint8_t getEventStatus()
{
	if(!g_pEvent)// || g_pEvent->getType() != EVENT_TYPE_MIDI)
		return 0x00;
	return g_pEvent->getSubtype();
}

uint8_t getEventValue1()
{
	if(!g_pEvent || g_pEvent->getType() != EVENT_TYPE_MIDI || g_pEvent->getSize() < 1)
		return 0xFF;
	return *(g_pEvent->getData());
}

uint8_t getEventValue2()
{
	if(!g_pEvent || g_pEvent->getType() != EVENT_TYPE_MIDI || g_pEvent->getSize() < 2)
		return 0xFF;
	return *(g_pEvent->getData() + 1);
}

// Handle JACK samplerate change (also used to recalculate ticks per frame)
static int onJackSamplerate(jack_nframes_t nFrames, void* args)
{
	g_nSamplerate = nFrames;
	//!@todo This is a nasty use of double precision floating point where we should be able to do most of this with integer maths
	if(g_pPlayerSmf)
		g_dPlayerTicksPerFrame = double(g_pPlayerSmf->getTicksPerQuarterNote()) / ((double(g_nMicrosecondsPerQuarterNote) / 1000000) * double(g_nSamplerate));
	if(g_pRecorderSmf)
		g_dRecorderTicksPerFrame = 2.0 * double(g_pRecorderSmf->getTicksPerQuarterNote()) / g_nSamplerate;
		//g_dRecorderTicksPerFrame = double(g_pRecorderSmf->getTicksPerQuarterNote()) / ((double(g_nMicrosecondsPerQuarterNote) / 1000000) * double(g_nSamplerate));
	return 0;
}

// Handle JACK process callback
static int onJackProcess(jack_nframes_t nFrames, void *notused)
{
	if(g_pMidiInputPort == NULL && g_pMidiOutputPort == NULL)
		return 0;
	static jack_transport_state_t nPreviousTransportState = JackTransportStopped;
	static uint8_t nPreviousPlayState = STOPPED;
	static uint8_t nStatus;
	static jack_position_t transport_position;
	static double dBeatsPerMinute = 120.0;

	jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);
	jack_transport_state_t nTransportState = jack_transport_query(g_pJackClient, &transport_position);

	// Handle change of tempo
	if(nPreviousTransportState != nTransportState || transport_position.beats_per_minute != dBeatsPerMinute && transport_position.beats_per_minute > 0)
	{
		dBeatsPerMinute = transport_position.beats_per_minute;
		g_nMicrosecondsPerQuarterNote = 60000000.0 / dBeatsPerMinute;
		onJackSamplerate(g_nSamplerate, 0);
	}
	// Handle change of transport state
	if(nTransportState != nPreviousTransportState)
	{
		if(g_nPlayState == STARTING || g_nPlayState == PLAYING)
		{
			if(nTransportState == JackTransportStarting)
				g_nPlayState = STARTING;
			else if(nTransportState == JackTransportRolling)
				g_nPlayState = PLAYING;
			else
				g_nPlayState = STOPPED;
		}
		else
			g_nPlayState = STOPPED;
		nPreviousTransportState = nTransportState;
	}

	void* pMidiBuffer; // Pointer to the memory area used by MIDI input / output ports (reused for each)

	if(g_bRecording && g_pMidiInputPort && (pMidiBuffer = jack_port_get_buffer(g_pMidiInputPort, nFrames)))
	{
		//!@todo Add tempo changes
		jack_midi_event_t midiEvent;
		jack_nframes_t nCount = jack_midi_get_event_count(pMidiBuffer);
		uint8_t* pData;
		if(nCount)
		{
			Event* pEvent;
			uint8_t* pData;
			size_t nSize;
			for(jack_nframes_t i = 0; i < nCount; i++)
			{
				jack_midi_event_get(&midiEvent, pMidiBuffer, i);
				switch(midiEvent.buffer[0] & 0xF0)
				{
					case MIDI_NOTE_ON:
					case MIDI_NOTE_OFF:
					case MIDI_POLY_PRESSURE:
					case MIDI_CONTROLLER:
					case MIDI_PITCH_BEND:
						// 3 byte messages
						nSize = 2;
						pData = new uint8_t[nSize];
						pData[0] = midiEvent.buffer[1];
						pData[1] = midiEvent.buffer[2];
						break;
					case MIDI_PROGRAM_CHANGE:
					case CHANNEL_PRESSURE:
						// 2 byte messages
						nSize = 1;
						pData = new uint8_t[nSize];
						pData[0] = midiEvent.buffer[1];
						break;
					default:
						pData = NULL;
				}
				if(pData)
				{
					if(g_nRecordStartPosition == 0)
						g_nRecordStartPosition = nNow + midiEvent.time; // First MIDI event triggers start of recording
					uint32_t nPosition = nNow + midiEvent.time - g_nRecordStartPosition; // Time of event in samples since start of recording
					pEvent = new Event(g_dRecorderTicksPerFrame * nPosition, EVENT_TYPE_MIDI, midiEvent.buffer[0], nSize, pData);
					g_pRecorderSmf->addEvent(midiEvent.buffer[0] & 0x0F, pEvent); // Add event to a track based on its MIDI channel
				}
			}
		}
	}

	if(g_pMidiOutputPort  && (pMidiBuffer = jack_port_get_buffer(g_pMidiOutputPort, nFrames)))
	{
		jack_midi_clear_buffer(pMidiBuffer);
		if(!g_pPlayerSmf || g_nPlayState == STOPPED)
			return 0; // We don't have a SMF loaded or we are stopped so don't bother processing any data

		// Handle change of play state
		if(nPreviousPlayState != g_nPlayState | g_nPlayState == STOPPING)
		{
			DPRINTF("zysmf::onJackProcess Previous play state: %u New play state: %u\n", nPreviousPlayState, g_nPlayState);
			if(g_nPlayState == STOPPED || g_nPlayState == STOPPING)
			{
				g_nPlayState = STOPPED;
				// Clear hanging notes and controllers set during playback
				for(auto it = m_mHangingMidi.begin(); it != m_mHangingMidi.end(); ++it)
				{
					if(it->second)
					{
						jack_midi_data_t* pBuffer = jack_midi_event_reserve(pMidiBuffer, 0, 3);
						if(!pBuffer)
							break;
						uint8_t nStatus = it->first >> 8;
						uint8_t nValue1 = it->first & 0x00FF;
						*pBuffer = nStatus;
						*(pBuffer + 1) = nValue1;
						*(pBuffer + 2) = 0;
					}
				}
				m_mHangingMidi.clear();
			}
		}
		if(g_nPlayState == STARTING and nTransportState == JackTransportRolling)
			g_nPlayState = PLAYING;
		nPreviousPlayState = g_nPlayState;

		if(g_nPlayState == PLAYING)
		{
			//!@todo Store playback position to allow pause / resume
			// Process all pending smf events
			g_dPosition += g_dPlayerTicksPerFrame * nFrames; // Ticks since start of song
			while(Event* pEvent = g_pPlayerSmf->getEvent(false))
			{
				if(pEvent->getTime() > g_dPosition)
					break;
				pEvent = g_pPlayerSmf->getEvent(true);
				
				if(pEvent->getType() == EVENT_TYPE_META)
				{
					if(pEvent->getSubtype() == META_TYPE_TEMPO)
					{
						g_nMicrosecondsPerQuarterNote = pEvent->getInt32();
						onJackSamplerate(g_nSamplerate, 0);
					}
					continue;
				}
				if(pEvent->getType() == EVENT_TYPE_MIDI)
				{
					jack_nframes_t nOffset = g_dPosition - nNow;
					jack_midi_data_t* pBuffer = jack_midi_event_reserve(pMidiBuffer, nOffset, pEvent->getSize() + 1);
					if(!pBuffer)
						break;
					*pBuffer = pEvent->getSubtype();
					memcpy(pBuffer + 1, pEvent->getData(), pEvent->getSize());

					// Store note and some controller values to allow reset when stopped
					switch(pEvent->getSubtype() & 0xF0)
					{
						case MIDI_CONTROLLER:
							if(*(pEvent->getData()) < 0x64 || *(pEvent->getData()) > 0x69)
								break;
						case MIDI_NOTE_ON:
						case MIDI_PITCH_BEND:
							m_mHangingMidi[pEvent->getSubtype() << 8 | *(pEvent->getData())] = *(pEvent->getData() + 1); //key= 0xSSNN SS=status, NN=note/controller. Value is MIDI value
					}
					
				}
			}
			if(!g_pPlayerSmf->getEvent(false))
			{
				// No more events so must be at end of song
				stopPlayback();
				if(g_bLoop)
					startPlayback();
			}
		}
	}

	return 0;
}

void removeJackClient()
{
	if(g_pJackClient)
		jack_client_close(g_pJackClient);
	g_pJackClient = NULL;
}

bool createJackClient()
{
	if(!g_pJackClient)
	{
		// Initialise JACK client
		g_pJackClient = jack_client_open("zynsmf", JackNullOption, NULL);
		if(g_pJackClient
			&& !jack_set_process_callback(g_pJackClient, onJackProcess, 0)
			&& !jack_set_sample_rate_callback(g_pJackClient, onJackSamplerate, 0)
			&& !jack_activate(g_pJackClient))
		return true;
		removeJackClient();
		return false;
	}
	return true;
}

bool attachPlayer(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return false;
	if(!createJackClient())
		return false;
	if(!g_pMidiOutputPort)
		g_pMidiOutputPort = jack_port_register(g_pJackClient, "midi_out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
	if(!g_pMidiOutputPort)
	{
		removePlayer();
		DPRINTF("Failed to create JACK output port\n");
		return false;
	}
	DPRINTF("Created new JACK player\n");
	g_pPlayerSmf = pSmf;
	g_nSamplerate = jack_get_sample_rate(g_pJackClient);
	onJackSamplerate(g_nSamplerate, 0); // Set g_dTicksPerFrame

	return true;
}

void removePlayer()
{
	if(g_pMidiOutputPort)
		jack_port_unregister(g_pJackClient, g_pMidiOutputPort);
	g_pMidiOutputPort = NULL;
	if(!g_pRecorderSmf)
		removeJackClient();
	g_pPlayerSmf = NULL;
}

void setLoop(bool bLoop)
{
	g_bLoop = bLoop;
}

void startPlayback()
{
	if(!g_pJackClient)
		return;
	g_dPosition = 0.0;
	g_nPlayState = STARTING;
}

void stopPlayback()
{
	if(g_nPlayState == STOPPED)
		return;
	g_nPlayState = STOPPING;
	if(g_pPlayerSmf)
		g_pPlayerSmf->setPosition(0);
}

uint8_t getPlayState()
{
	return g_nPlayState;
}

bool attachRecorder(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return false;
	if(!createJackClient())
		return false;
	if(!g_pMidiInputPort)
		g_pMidiInputPort = jack_port_register(g_pJackClient, "midi_in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
	if(!g_pMidiInputPort)
	{
		removeRecorder();
		DPRINTF("Failed to create JACK input port\n");
		return false;
	}
	DPRINTF("Created new JACK recorder\n");
	g_pRecorderSmf = pSmf;
	g_nSamplerate = jack_get_sample_rate(g_pJackClient);
	onJackSamplerate(g_nSamplerate, 0); // Set g_dRecorderTicksPerFrame
	return true;
}

void removeRecorder()
{
	if(g_pMidiInputPort)
		jack_port_unregister(g_pJackClient, g_pMidiInputPort);
	g_pMidiInputPort = NULL;
	if(!g_pPlayerSmf)
		removeJackClient();
	g_pRecorderSmf = NULL;
}

void startRecording()
{
	if(!g_pMidiInputPort || !g_pRecorderSmf)
		return;
	g_nRecordStartPosition = 0; // Set start time to 0 so that first MIDI event will update and mark actual start of recording
	g_bRecording = true;
}

void stopRecording()
{
	g_bRecording = false;
}

bool isRecording()
{
	return g_bRecording;
}

double getTempo(Smf* pSmf, uint32_t nTime)
{
	if(!isSmfValid(pSmf))
		return 120.0;
	return 60000000.0 / pSmf->getMicrosecondsPerQuarterNote(nTime);
}

void printEvents(Smf* pSmf, size_t nTrack)
{
	printf("Print events for track %u\n", nTrack);
	if(!isSmfValid(pSmf))
		return;
	setPosition(pSmf, 0);
	while(getEvent(pSmf, true))
	{
		if(pSmf->getCurrentTrack() == nTrack)
		{
			printf("Time: %u ", getEventTime());
			switch(getEventType())
			{
				case EVENT_TYPE_META:
					printf("Meta event 0x%02X\n", getEventStatus());
					break;
				case EVENT_TYPE_MIDI:
					printf("MIDI event 0x%02X 0x%02X 0x%02X\n", getEventStatus(), getEventValue1(), getEventValue2());
					break;
				default:
					printf("Other event type: 0x%02X\n", getEventType());
			}
		}
	}
}

void muteTrack(Smf* pSmf, size_t nTrack, bool bMute)
{
	if(!isSmfValid(pSmf))
		return;
	pSmf->muteTrack(nTrack, bMute);
	//!@todo Clear hanging notes after muting track
}

bool isTrackMuted(Smf* pSmf, size_t nTrack)
{
	if(!isSmfValid(pSmf))
		return false;
	return pSmf->isTrackMuted(nTrack);
}
