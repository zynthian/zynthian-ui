/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include "zynsmf.h"
#include "smf.h"

#include <stdio.h> //provides printf
#include <stdlib.h> //provides exit
#include <cstring> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <jack/midiport.h> //provides interface to JACK MIDI ports

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)
#define MIDI_CONTROLLER         0xB0 //176
#define MIDI_ALL_SOUND_OFF      0x78 //120

enum playState
{
	STOPPED,
	STARTING,
	PLAYING,
	STOPPING
};

Smf* g_pSmf = NULL;
jack_client_t* g_pJackClient = NULL;
jack_port_t* g_pMidiPort = NULL;

bool g_bDebug = false;
uint32_t g_nStartOfPlayback = 0; // JACK frame position when startback commenced
uint8_t g_nPlayState = STOPPED; // True if playing back
bool g_bLoop = false; // True to loop at end of song

Event* g_pEvent = NULL;



// Runs on library exit / destroy
void onExit()
{
	DPRINTF("zynsmf library exit\n");
}


// Enable / disable debug output
void enableDebug(bool bEnable)
{
    printf("libsmf setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
	if(g_pSmf)
		g_pSmf->enableDebug(bEnable);
}


bool load(char* filename)
{
	// Register the cleanup function to be called when library exits
    atexit(onExit);

	// Create new SFM object
	g_pEvent = NULL;
	delete g_pSmf;
	g_pSmf = new Smf();
	if(!g_pSmf)
		return false;
	g_pSmf->enableDebug(g_bDebug);

	if(!g_pSmf->load(filename))
		return false; //!@todo Check if failure to load can leav
	setPosition(0);
	return true;
}

bool open(char* filename)
{
    atexit(onExit);
	delete g_pSmf;
	g_pSmf = new Smf();
	if(!g_pSmf)
		return false;
	g_pSmf->enableDebug(g_bDebug);

	if(!g_pSmf->load(filename, false))
		return false; //!@todo Check if failure to load can leav
	setPosition(0);
	return true;
}

double getDuration()
{
	if(!g_pSmf)
		return 0.0;
	return g_pSmf->getDuration();
}

void setPosition(uint32_t time)
{
	if(!g_pSmf)
		return;
	g_pSmf->setPosition(time);
	g_pEvent = g_pSmf->getNextEvent(false);
}

uint32_t getTracks()
{
	if(!g_pSmf)
		return 0;
	return g_pSmf->getTracks();
}

uint8_t getFormat()
{
	if(!g_pSmf)
		return 0;
	return g_pSmf->getFormat();
}

bool getNextEvent()
{
	if(!g_pSmf)
		return false;
	g_pEvent = g_pSmf->getNextEvent();
	return (g_pEvent != NULL);
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
	if(!g_pEvent || g_pEvent->getType() != EVENT_TYPE_MIDI)
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
static double framesToMilliseconds(jack_nframes_t nFrames)
{
	jack_nframes_t nSamplerate = jack_get_sample_rate(g_pJackClient); //!@todo Set samplerate once
	if(nSamplerate)
		return (nFrames * 1000.0) / (double)nSamplerate;
	return 0;
}

// Handle JACK process callback
static int onJackProcess(jack_nframes_t nFrames, void *notused)
{
	static jack_transport_state_t nPreviousTransportState = JackTransportStopped;
	if(!g_pSmf || g_nPlayState == STOPPED)
		return 0; // We don't have a SMF loaded so don't bother processing any data

	// Prepare MIDI buffer
	void* pPortBuffer = jack_port_get_buffer(g_pMidiPort, nFrames);
    if(!pPortBuffer)
        return 0; // If we can't get a buffer we can't do anything
    jack_midi_clear_buffer(pPortBuffer);
	// Check if transport running
    jack_transport_state_t nTransportState = jack_transport_query(g_pJackClient, NULL);
	if(nTransportState == JackTransportStopped || g_nPlayState == STOPPING)
    {
        if(nPreviousTransportState == JackTransportRolling || g_nPlayState != STOPPED)
		{
			unsigned char *pBuffer;
			for(uint8_t nChannel = 0; nChannel < 16; ++nChannel)
			{
				pBuffer = jack_midi_event_reserve(pPortBuffer, 0, 2);
				if(!pBuffer)
					break;
				pBuffer[0] = MIDI_CONTROLLER | nChannel;
				pBuffer[1] = MIDI_ALL_SOUND_OFF;
			}
		}
		g_nPlayState = STOPPED;
        nPreviousTransportState = nTransportState;
        return 0;
    }
    nPreviousTransportState = nTransportState;
	
	jack_nframes_t nNow = jack_last_frame_time(g_pJackClient);
	//!@todo Store playback position to allow pause / resume
	//!@todo Respond to tempo change
	if(g_nStartOfPlayback == 0)
		g_nStartOfPlayback = nNow;
    // Process all pending smf events
	uint32_t nTime =  framesToMilliseconds(nNow - g_nStartOfPlayback + nFrames); // Time in ms since start of song until end of next period
	while(Event* pEvent = g_pSmf->getNextEvent(false))
    {
		if(pEvent->getTime() > nTime)
			break;
		g_pSmf->getNextEvent();
		/* Skip over metadata events. */
		if(pEvent->getType() != EVENT_TYPE_MIDI)
			continue;
		printf("Found MIDI event %02X %02X %02X at %u with timing %d\n", pEvent->getSubtype(), *(pEvent->getData()), *(pEvent->getData() + 1), nTime, pEvent->getTime());
		jack_nframes_t nOffset = 0; //!@todo schedule MIDI events at correct offset within period
		jack_midi_data_t* pBuffer = jack_midi_event_reserve(pPortBuffer, nOffset, pEvent->getSize() + 1);
		if(!pBuffer)
			break;
		*pBuffer = pEvent->getSubtype();
		memcpy(pBuffer + 1, pEvent->getData(), pEvent->getSize()); //!@todo May be better to put all data in data buffer rather than split status and value
	}
	if(!g_pSmf->getNextEvent(false))
	{
		// No more events so must be at end ot song
		stopPlayback();
		if(g_bLoop)
			startPlayback(g_bLoop);
	}
	return 0;
}

static int onJackSync(jack_transport_state_t nState, jack_position_t* pPosition, void* args)
{
	return 0;
}


bool addPlayer()
{
	// Initialise JACK client
	if(g_pJackClient)
		return false;
	g_pJackClient = jack_client_open("zynmidiplayer", JackNullOption, NULL);
	if(!g_pJackClient)
		return false;
	g_pMidiPort = jack_port_register(g_pJackClient, "midi_out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
    if(!g_pMidiPort
		|| jack_set_process_callback(g_pJackClient, onJackProcess, 0)
		|| jack_set_sync_callback(g_pJackClient, onJackSync, 0)
		|| jack_activate(g_pJackClient))
	{
		DPRINTF("Failed to create JACK client\n");
		removePlayer();
		return false;
	}
	DPRINTF("Created new JACK player\n");

	return true;
}

void removePlayer()
{
	if(!g_pJackClient)
		return;
	jack_client_close(g_pJackClient);
	g_pJackClient = NULL;
	g_pMidiPort = NULL;
}

void startPlayback(bool bLoop)
{
	if(!g_pJackClient)
		return;
	g_nStartOfPlayback = 0;
	g_bLoop = bLoop;
	g_nPlayState = PLAYING;
}

void stopPlayback()
{
	if(g_nPlayState == STOPPED || g_nPlayState == STOPPING)
		return;
	g_nPlayState = STOPPING;
	if(g_pSmf)
		g_pSmf->setPosition(0);
}

