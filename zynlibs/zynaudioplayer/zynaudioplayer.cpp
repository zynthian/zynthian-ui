/*  Audio file player library for Zynthian
*/

#include "zynaudioplayer.h"

#include <stdio.h> //provides printf
#include <cstring> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <sndfile.h> //provides sound file manipulation
#include <pthread.h> //provides multithreading
#include <stdlib.h> //provides exit

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)

enum playState
{
	STOPPED		= 0,
	STARTING	= 1,
	PLAYING		= 2,
	STOPPING	= 3
};

jack_client_t* g_pJackClient = NULL;
jack_port_t* g_pJackOutA = NULL;
jack_port_t* g_pJackOutB = NULL;

bool g_bDebug = false;
uint8_t g_nPlayState = STOPPED;
bool g_bLoop = false; // True to loop at end of song
jack_nframes_t g_nSamplerate = 44100;
double g_dPosition = 0.0; // Position within audio in ms
SNDFILE* g_pFile = NULL; // Pointer to the currently open sound file
SF_INFO  g_sf_info; // Structure containing currently loaded file info
pthread_t g_threadFile; // Thread handling file reading

/*** Public functions exposed as external C functions in header ***/

void enableDebug(bool bEnable) {
    printf("libaudioplayer setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
}


bool open(const char* filename) {
    if(g_pFile)
        close();
    g_sf_info.format = 0; // This triggers open to populate info structure
    g_pFile = sf_open(filename, SFM_READ, &g_sf_info);
    return (g_pFile != NULL);
}

double getFileDuration(const char* filename) {
    SF_INFO info;
    info.format = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if(info.samplerate)
        return static_cast<double>(info.frames) / info.samplerate;
    return 0.0f;
}

bool close() {
    if(g_pFile) {
        if(sf_close(g_pFile) == 0) {
            g_pFile = NULL;
            return true;
        }
    }
    return false;
}

bool save(const char* filename) {
    //!@todo Implement save
    if(!g_pFile)
        return false;
    return false;
}

double getDuration() {
    //!@todo Implement getDuration
    if(g_sf_info.samplerate)
        return static_cast<double>(g_sf_info.frames) / g_sf_info.samplerate;
    return 0.0f;
}

void setPosition(uint32_t time)
{
    //!@todo Implement setPosition
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
}

uint8_t getPlayState()
{
	return g_nPlayState;
}

int getSamplerate() {
    return g_sf_info.samplerate;
}

int getChannels() {
    return g_sf_info.channels;
}

int getFrames() {
    return g_sf_info.frames;
}

int getFormat() {
    return g_sf_info.format;
}

/*** Private functions not exposed as external C functions (not declared in header) ***/

void onExit() {
    DPRINTF("libaudioplayer exit\n");
    if(g_pJackClient)
        jack_client_close(g_pJackClient);
    close();
}

// Handle JACK process callback
static int onJackProcess(jack_nframes_t nFrames, void *notused)
{
	if(g_pJackOutA == NULL || g_pJackOutB == NULL)
		return 0;
    //!@todo Implement onJackProcess
	return 0;
}

// Handle JACK process callback
int onJackSamplerate(jack_nframes_t nFrames, void *pArgs)
{
    DPRINTF("zynaudioplayer: Jack sample rate: %u\n", nFrames);
    g_nSamplerate = nFrames;
    return 0;
}

void *fileThread(void*) {
    return NULL;
}

void init() {
    printf("zynaudioplayer init\n");

	// Register with Jack server
	char *sServerName = NULL;
	jack_status_t nStatus;
	jack_options_t nOptions = JackNoStartServer;

	if ((g_pJackClient = jack_client_open("zynaudioplayer", nOptions, &nStatus, sServerName)) == 0) {
		fprintf(stderr, "libaudioplayer failed to start jack client: %d\n", nStatus);
		exit(1);
	}

	// Create output ports
	if (!(g_pJackOutA = jack_port_register(g_pJackClient, "output_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
		fprintf(stderr, "libaudioplayer cannot register output port A\n");
		exit(1);
	}
	if (!(g_pJackOutB = jack_port_register(g_pJackClient, "output_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
		fprintf(stderr, "libaudioplayer cannot register output port B\n");
		exit(1);
	}

	// Register the cleanup function to be called when program exits
	atexit(onExit);

	// Register the callback to calculate peak sample
	jack_set_process_callback(g_pJackClient, onJackProcess, 0);

	if (jack_activate(g_pJackClient)) {
		fprintf(stderr, "libaudioplayer cannot activate client\n");
		exit(1);
	}

    if(pthread_create(&g_threadFile, NULL, fileThread, NULL)) {
        fprintf(stderr, "Failed to create file reading thread\n");
        exit(1);
    }
}
