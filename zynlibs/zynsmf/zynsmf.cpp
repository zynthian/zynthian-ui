/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include "zynsmf.h"

#include <stdio.h> //provides printf
#include <cstring> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <jack/midiport.h> //provides interface to JACK MIDI ports

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)
#define MIDI_CONTROLLER         0xB0 //176
#define MIDI_ALL_SOUND_OFF      0x78 //120
#define MIDI_ALL_NOTES_OFF      0x7B //123

enum playState
{
	STOPPED		= 0,
	STARTING	= 1,
	PLAYING		= 2,
	STOPPING	= 3
};

jack_client_t* g_pJackClient = NULL;
jack_port_t* g_pMidiPort = NULL;

bool g_bDebug = false;
uint32_t g_nStartOfPlayback = 0; // JACK frame position when startback commenced
uint8_t g_nPlayState = STOPPED; // True if playing back
bool g_bLoop = false; // True to loop at end of song
jack_nframes_t g_nSamplerate = 44100;
uint32_t g_nMicrosecondsPerQuarterNote = 500000; // Current tempo
double g_dTicksPerFrame; // Current tempo

Smf* g_pPlayerSmf = NULL; // Pointer to the SMF object that is attached to player
Event* g_pEvent = NULL;

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
	g_pEvent = pSmf->getNextEvent(false);
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

uint16_t getTicksPerQuarterNote(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return 0;
	return pSmf->getTicksPerQuarterNote();
}

bool getNextEvent(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return false;
	g_pEvent = pSmf->getNextEvent();
	return (g_pEvent != NULL);
}

size_t getEventTrack(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return 0;
	return pSmf->getCurrentTrack();
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

// Convert frames to milliseconds
//!@todo framesToMicroseconds is not used
static double framesToMicroseconds(jack_nframes_t nFrames)
{
	if(g_nSamplerate)
		return double(nFrames) * 1000000.0 / g_nSamplerate;
	return 0;
}

// Handle JACK samplerate change (also used to recalculate ticks per frame)
static int onJackSamplerate(jack_nframes_t nFrames, void* args)
{
	g_nSamplerate = nFrames;
	//!@todo This is a nasty use of double precision floating point where we should be able to do most of this with integer maths
	if(g_pPlayerSmf)
		g_dTicksPerFrame = double(g_pPlayerSmf->getTicksPerQuarterNote()) / ((double(g_nMicrosecondsPerQuarterNote) / 1000000) * double(g_nSamplerate));
	return 0;
}

// Handle JACK process callback
static int onJackProcess(jack_nframes_t nFrames, void *notused)
{
	static jack_transport_state_t nPreviousTransportState = JackTransportStopped;
	static uint8_t nPreviousPlayState = STOPPED;

	// Prepare MIDI buffer
	void* pPortBuffer = jack_port_get_buffer(g_pMidiPort, nFrames);
    if(!pPortBuffer)
        return 0; // If we can't get a buffer we can't do anything
    jack_midi_clear_buffer(pPortBuffer);
	if(!g_pPlayerSmf || g_nPlayState == STOPPED)
		return 0; // We don't have a SMF loaded or we are stopped so don't bother processing any data
	jack_midi_data_t* pMidiBuffer;
	// Check if transport running
    jack_transport_state_t nTransportState = jack_transport_query(g_pJackClient, NULL);

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

	// Handle change of play state
	if(nPreviousPlayState != g_nPlayState | g_nPlayState == STOPPING)
	{
		DPRINTF("zysmf::onJackProcess Previous play state: %u New play state: %u\n", nPreviousPlayState, g_nPlayState);
		if(g_nPlayState == STOPPED || g_nPlayState == STOPPING)
		{
			g_nPlayState = STOPPED;
			//!@todo Should we store all note on and send individual note off messages - currently sending all notes off and all sounds off?
			for(uint8_t nChannel = 0; nChannel < 16; ++nChannel)
			{
				//!@todo Sending all notes off and all sound off is excessive and will stop anyother instruments sounding that are not controlled by SMF
				pMidiBuffer = jack_midi_event_reserve(pPortBuffer, 0, 3);
				if(!pMidiBuffer)
					break;
				pMidiBuffer[0] = MIDI_CONTROLLER | nChannel;
				pMidiBuffer[1] = MIDI_ALL_NOTES_OFF;
				pMidiBuffer[2] = 0;
				pMidiBuffer = jack_midi_event_reserve(pPortBuffer, 0, 3);
				if(!pMidiBuffer)
					break;
				pMidiBuffer[0] = MIDI_CONTROLLER | nChannel;
				pMidiBuffer[1] = MIDI_ALL_SOUND_OFF;
				pMidiBuffer[2] = 0;
			}
		}
	}
	if(g_nPlayState == STARTING and nTransportState == JackTransportRolling)
		g_nPlayState = PLAYING;
	nPreviousPlayState = g_nPlayState;

	if(g_nPlayState != PLAYING)
		return 0;

	// Playing so send pending events
	jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);
	//!@todo Store playback position to allow pause / resume
	//!@todo Respond to tempo change
	if(g_nStartOfPlayback == 0)
		g_nStartOfPlayback = nNow;
    // Process all pending smf events
	jack_nframes_t nFramesSinceStart = nNow - g_nStartOfPlayback + nFrames; // Quantity of frames since start of song 
	//!@todo Get the time of the next event
	double dTime = g_dTicksPerFrame * nFramesSinceStart; // Ticks since start of song
	while(Event* pEvent = g_pPlayerSmf->getNextEvent(false))
    {
		if(pEvent->getTime() > dTime)
			break;
		pEvent = g_pPlayerSmf->getNextEvent();
		
		if(pEvent->getType() == EVENT_TYPE_META)
		{
			if(pEvent->getSubtype() == META_TYPE_TEMPO)
			{
				g_nMicrosecondsPerQuarterNote = pEvent->getInt32();
				onJackSamplerate(g_nSamplerate, 0);
			}
			continue;
		}
		//printf("Found MIDI event %02X %02X %02X at %lf with timing %d\n", pEvent->getSubtype(), *(pEvent->getData()), *(pEvent->getData() + 1), dTime, pEvent->getTime());
		jack_nframes_t nOffset = dTime - nNow; //!@todo schedule MIDI events at correct offset within period
		pMidiBuffer = jack_midi_event_reserve(pPortBuffer, nOffset, pEvent->getSize() + 1);
		if(!pMidiBuffer)
			break;
		*pMidiBuffer = pEvent->getSubtype();
		memcpy(pMidiBuffer + 1, pEvent->getData(), pEvent->getSize()); //!@todo May be better to put all data in data buffer rather than split status and value
	}
	if(!g_pPlayerSmf->getNextEvent(false))
	{
		// No more events so must be at end ot song
		stopPlayback();
		if(g_bLoop)
			startPlayback();
	}
	return 0;
}

static int onJackSync(jack_transport_state_t nState, jack_position_t* pPosition, void* args)
{
	//!@todo Handle jack sync callback
	return true;
}


bool attachPlayer(Smf* pSmf)
{
	if(!isSmfValid(pSmf))
		return false;
	if(!g_pJackClient)
	{
		// Initialise JACK client
		g_pJackClient = jack_client_open("zynmidiplayer", JackNullOption, NULL);
		if(!g_pJackClient)
			return false;
		g_pMidiPort = jack_port_register(g_pJackClient, "midi_out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
		if(!g_pMidiPort
			|| jack_set_process_callback(g_pJackClient, onJackProcess, 0)
			|| jack_set_sync_callback(g_pJackClient, onJackSync, 0)
			|| jack_set_sample_rate_callback(g_pJackClient, onJackSamplerate, 0)
			|| jack_activate(g_pJackClient))
		{
			DPRINTF("Failed to create JACK client\n");
			removePlayer();
			return false;
		}
	}
	DPRINTF("Created new JACK player\n");
	g_pPlayerSmf = pSmf;
	g_nSamplerate = jack_get_sample_rate(g_pJackClient);
	onJackSamplerate(g_nSamplerate, 0); // Set g_dTicksPerFrame

	return true;
}

void removePlayer()
{
	if(!g_pJackClient)
		return;
	jack_client_close(g_pJackClient);
	g_pJackClient = NULL;
	g_pMidiPort = NULL;
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
	g_nStartOfPlayback = 0;
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

void printEvents(Smf* pSmf, size_t nTrack)
{
	printf("Print events for track %u\n", nTrack);
	if(!isSmfValid(pSmf))
		return;
	setPosition(pSmf, 0);
	while(getEventTime() != -1)
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
		getNextEvent(pSmf);
	}
}