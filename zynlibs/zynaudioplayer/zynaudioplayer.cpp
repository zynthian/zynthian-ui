/*  Audio file player library for Zynthian
*/

#include "zynaudioplayer.h"

#include <stdio.h> //provides printf
#include <cstring> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <sndfile.h> //provides sound file manipulation
#include <pthread.h> //provides multithreading
#include <unistd.h> //provides usleep
#include <stdlib.h> //provides exit

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)

enum playState
{
	STOPPED		= 0,
	STARTING	= 1,
	PLAYING		= 2,
	STOPPING	= 3
};

#define AUDIO_BUFFER_SIZE 1024 * 1024 * 8
struct AUDIO_BUFFER {
    size_t size = AUDIO_BUFFER_SIZE;
    size_t end = 0;
    bool isEmpty = true;
    float data_a[AUDIO_BUFFER_SIZE];
    float data_b[AUDIO_BUFFER_SIZE];
};

size_t g_nBufferPos = 0; // Postion within buffer of read cursor
size_t g_nActiveBuffer = 0; // Index of the currently active buffer

jack_client_t* g_pJackClient = NULL;
jack_port_t* g_pJackOutA = NULL;
jack_port_t* g_pJackOutB = NULL;

bool g_bDebug = false;
bool g_bFileOpen = false; // True whilst file is open - used to flag thread to close file
uint8_t g_nPlayState = STOPPED;
bool g_bLoop = false; // True to loop at end of song
jack_nframes_t g_nSamplerate = 44100;
double g_dPosition = 0.0; // Position within audio in ms
SNDFILE* g_pFile = NULL; // Pointer to the currently open sound file
SF_INFO  g_sf_info; // Structure containing currently loaded file info
pthread_t g_threadFile; // ID of file reader thread
AUDIO_BUFFER g_audioBuffer[2]; // Double-buffer for transfering audio from file to player
float g_buffer[AUDIO_BUFFER_SIZE];

/*** Public functions exposed as external C functions in header ***/

void enableDebug(bool bEnable) {
    printf("libaudioplayer setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
}

bool open(const char* filename) {
    if(g_bFileOpen || g_pFile)
        return false; // Must close file before opening again
    //!@todo Ensure existing file reader thread ends
    g_sf_info.format = 0; // This triggers open to populate info structure
    g_pFile = sf_open(filename, SFM_READ, &g_sf_info);
    if(!g_pFile)
        return false;
    g_bFileOpen = true;
    int rc = pthread_create(&g_threadFile, NULL, fileThread, NULL);
    if(rc) {
        fprintf(stderr, "Failed to create file reading thread\n");
        close_file();
        return false;
    }
    return true;
}

double getFileDuration(const char* filename) {
    SF_INFO info;
    info.format = 0;
    info.samplerate = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if(info.samplerate)
        return static_cast<double>(info.frames) / info.samplerate;
    return 0.0f;
}

bool close_file() {
    g_bFileOpen = false;
    return true; //!@todo No benefit in returning value
}

bool save(const char* filename) {
    //!@todo Implement save
    if(!g_pFile)
        return false;
    return false;
}

double getDuration() {
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
    close_file();
}

// Handle JACK process callback
static int onJackProcess(jack_nframes_t nFrames, void *notused)
{
	if(g_pJackOutA == NULL || g_pJackOutB == NULL)
		return 0;
    jack_default_audio_sample_t *pOutA = (jack_default_audio_sample_t*)jack_port_get_buffer(g_pJackOutA, nFrames);
    jack_default_audio_sample_t *pOutB = (jack_default_audio_sample_t*)jack_port_get_buffer(g_pJackOutB, nFrames);
    for(size_t nOffset = 0; nOffset < nFrames; ++nOffset) {
        pOutA[nOffset] = 0.0;
        pOutB[nOffset] = 0.0;
    }
    if(g_nPlayState == STARTING)
        g_nPlayState = PLAYING;
    if(g_nPlayState == PLAYING) {
        // Read nFrames from active buffer from current position
        // If reach end of buffer, swap buffer and continue
        // If less than nFrames read, STOP
        //!@todo Replays end of last buffer then does not stop
        size_t nLastFrame = g_nBufferPos + nFrames;
        bool bSecondBuffer = false;
        for(size_t nOffset = 0; nOffset < nFrames; ++nOffset) {
            pOutA[nOffset] = g_audioBuffer[g_nActiveBuffer].data_a[g_nBufferPos];
            pOutB[nOffset] = g_audioBuffer[g_nActiveBuffer].data_b[g_nBufferPos];
            if(++g_nBufferPos > g_audioBuffer[g_nActiveBuffer].end) {
                g_audioBuffer[g_nActiveBuffer].isEmpty = true;
                g_nActiveBuffer = (++g_nActiveBuffer) % 2;
                g_nBufferPos = 0;
                DPRINTF("zynaudioplayer switching playback to buffer %d\n", g_nActiveBuffer);
                if(bSecondBuffer) {
                    g_nPlayState = STOPPED;
                    break;
                }
                bSecondBuffer = true;
            }
        }
    }
	return 0;
}

// Handle JACK process callback
int onJackSamplerate(jack_nframes_t nFrames, void *pArgs)
{
    DPRINTF("zynaudioplayer: Jack sample rate: %u\n", nFrames);
    g_nSamplerate = nFrames;
    return 0;
}

void* fileThread(void*) {
    int nChannelB = (g_sf_info.channels == 1)?0:1; // Mono or stereo based on first one or two channels
    //g_audioBuffer[0].size = AUDIO_BUFFER_SIZE / g_sf_info.channels;
    //g_audioBuffer[1].size = AUDIO_BUFFER_SIZE / g_sf_info.channels;
    bool bMore = true;

    while(g_bFileOpen) {
        if(bMore) //!@todo This should be related to play position and file read
            for(int nDbuffer = 0; nDbuffer < 2; ++nDbuffer) {
                // Populate each empty double-buffer
                int nOffset = 0;
                if(g_audioBuffer[nDbuffer].isEmpty) {
                    int nRead = sf_read_float(g_pFile, g_buffer, AUDIO_BUFFER_SIZE);
                    if(nRead)
                        g_audioBuffer[nDbuffer].isEmpty = false;
                    else
                        bMore = false;
                    // Demux channels and fill channel audio buffers
                    for(int offset = 0; offset < AUDIO_BUFFER_SIZE; offset += g_sf_info.channels) {
                        g_audioBuffer[nDbuffer].data_a[nOffset] = g_buffer[offset];
                        g_audioBuffer[nDbuffer].data_b[nOffset] = g_buffer[offset + nChannelB];
                        ++nOffset;
                    }
                    g_audioBuffer[nDbuffer].end = nOffset;
                    printf("zynaudioplayer::fileThread read %d samples into double-buffer %d\n", nRead, nDbuffer);
                }
            }
        usleep(100);
    }
    g_bFileOpen = false;
    if(g_pFile) {
        int nError = sf_close(g_pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer failed to close file with error code %d\n", nError);
        g_pFile = NULL;
    }
    pthread_exit(NULL);
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
}
