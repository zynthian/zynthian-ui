/*  Audio file player library for Zynthian
    Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include "zynaudioplayer.h"

#include <stdio.h> //provides printf
#include <string.h> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <jack/midiport.h> //provides JACK MIDI interface
#include <sndfile.h> //provides sound file manipulation
#include <samplerate.h> //provides samplerate conversion
#include <pthread.h> //provides multithreading
#include <unistd.h> //provides usleep
#include <stdlib.h> //provides exit

#define DPRINTF(fmt, args...) if(g_bDebug) printf(fmt, ## args)

enum playState {
    STOPPED		= 0,
    STARTING	= 1,
    PLAYING		= 2,
    STOPPING	= 3
};

enum seekState {
    IDLE        = 0, // Not seeking
    SEEKING     = 1, // Seeking within file
    LOADING     = 2, // Seek complete, loading data from file
    LOOPING     = 3 // Reached end of file, need to load from start
};

#define AUDIO_BUFFER_SIZE 50000 // 50000 is approx. 1s of audio
#define RING_BUFFER_SIZE AUDIO_BUFFER_SIZE * 2

jack_client_t* g_pJackClient = NULL;
jack_port_t* g_pJackOutA = NULL;
jack_port_t* g_pJackOutB = NULL;
jack_port_t * g_pJackMidiIn = NULL;

uint8_t g_bDebug = 0;
uint8_t g_bFileOpen = 0; // 1 whilst file is open - used to flag thread to close file
uint8_t g_nFileReadStatus = IDLE; // File reading status (IDLE|SEEKING|LOADING)
uint8_t g_nPlayState = STOPPED; // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
uint8_t g_bLoop = 0; // 1 to loop at end of song
jack_nframes_t g_nSamplerate = 44100; // Playback samplerate set by jackd
struct SF_INFO  g_sf_info; // Structure containing currently loaded file info
pthread_t g_threadFile; // ID of file reader thread
struct RING_BUFFER g_ringBuffer; // Used to pass data from file reader to jack process
size_t g_nChannelB = 0; // Offset of samples for channel B (0 for mono source or 1 for multi-channel)
jack_nframes_t g_nPlaybackPosFrames = 0; // Current playback position in frames since start of audio
size_t g_nLastFrame = -1; // Position within ring buffer of last frame or -1 if not playing last buffer iteration
unsigned int g_nSrcQuality = SRC_SINC_FASTEST;
char g_sFilename[128];
float g_fLevel = 1.0; // Audio level (volume) 0..1
int g_nPlaybackTrack = 0; // Which stereo pair of tracks to playback (-1 to mix all stero pairs)

struct RING_BUFFER {
    size_t front; // Offset within buffer for next read
    size_t back; // Offset within buffer for next write
    size_t size; // Quantity of elements in buffer
    float dataA[RING_BUFFER_SIZE];
    float dataB[RING_BUFFER_SIZE];
};

/*  @brief  Initialise ring buffer
*   @param  buffer Pointer to ring buffer
*/
void ringBufferInit(struct RING_BUFFER * buffer) {
    buffer->front = 0;
    buffer->back = 0;
    buffer->size = RING_BUFFER_SIZE;
    memset(buffer->dataA, 0, RING_BUFFER_SIZE * sizeof(float));
    memset(buffer->dataB, 0, RING_BUFFER_SIZE * sizeof(float));
}

/*  @brief  Push data to back of ring buffer
*   @param  buffer Pointer to ring buffer
*   @param  dataA Pointer to start of A data to push
*   @param  dataB Pointer to start of B data to push
*   @param  size Quantity of data to push (size of data buffer)
*   @retval size_t Quantity of data actually added to queue
*/
size_t ringBufferPush(struct RING_BUFFER * buffer, float* dataA, float* dataB, size_t size) {
    size_t count = 0;
    if(buffer->back < buffer->front) {
        // Can populate from back to front
        for(; buffer->back < buffer->front; ++buffer->back) {
            if(count >= size)
                break;
            buffer->dataA[buffer->back] = *(dataA + count);
            buffer->dataB[buffer->back] = *(dataB + count++);
        }
    } else {
        // Populate to end of buffer then wrap and populate to front
        for(; buffer->back < buffer->size; ++buffer->back) {
            if(count >= size)
                break;
            buffer->dataA[buffer->back] = *(dataA + count);
            buffer->dataB[buffer->back] = *(dataB + count++);
        }
        if(count < size) {
            for(buffer->back = 0; buffer->back < buffer->front; ++buffer->back) {
                if(count >= size)
                    break;
                buffer->dataA[buffer->back] = *(dataA + count);
                buffer->dataB[buffer->back] = *(dataB + count++);
            }
        }
    }
    //DPRINTF("ringBufferPush size=%u count=%u front=%u back=%u\n", size, count, buffer->front, buffer->back);
    return count;
}

/*  @brief  Pop data from front of ring buffer
*   @param  buffer Pointer to ring buffer
*   @param  dataA Pointer to A data buffer to receive popped data
*   @param  dataB Pointer to B data buffer to receive popped data
*   @param  size Quantity of data to pop (size of data buffer)
*   @retval size_t Quantity of data actually removed from queue
*/
size_t ringBufferPop(struct RING_BUFFER * buffer, float* dataA, float* dataB, size_t size) {
    //DPRINTF("ringBuffPop size=%u, front=%u, back=%u\n", size, buffer->front, buffer->back);
    if(buffer->back == buffer->front)
        return 0;
    size_t count = 0;
    if(buffer->back > buffer->front) {
        for(; buffer->back > buffer->front; ++buffer->front) {
            if(count >= size)
                break;
            *(dataA + count) = buffer->dataA[buffer->front];
            *(dataB + count++) = buffer->dataB[buffer->front];
        }
    } else {
        // Pop to end of buffer then wrap and pop to back
        for(; buffer->front < buffer->size; ++buffer->front) {
            if(count >= size)
                break;
            *(dataA + count) = buffer->dataA[buffer->front];
            *(dataB + count++) = buffer->dataB[buffer->front];
        }
        if (count < size) {
            for(buffer->front = 0; buffer->front <= buffer->back; ++buffer->front) {
                if(count >= size)
                    break;
                *(dataA + count) = buffer->dataA[buffer->front];
                *(dataB + count++) = buffer->dataB[buffer->front];
            }
        }
    }
    return count;
}

/*  @brief  Get available space within ring buffer
*   @param  buffer Pointer to ring buffer
*   @retval size_t Quantity of free elements in ring buffer
*/
size_t ringBufferGetFree(struct RING_BUFFER * buffer) {
    if(buffer->front > buffer->back)
        return buffer->front - buffer->back;
    return buffer->size - buffer->back + buffer->front;
} 

/*  @brief  Get quantity of elements used within ring buffer
*   @param  buffer Pointer to ring buffer
*   @retval size_t Quantity of used elements in ring buffer
*/
size_t ringBufferGetUsed(struct RING_BUFFER * buffer) {
    if(buffer->back >= buffer->front)
        return buffer->back - buffer->front;
    return buffer->size - buffer->front + buffer->back;
} 

/*** Public functions exposed as external C functions in header ***/

void enableDebug(uint8_t bEnable) {
    printf("libaudioplayer setting debug mode %s\n", bEnable?"on":"off");
    g_bDebug = bEnable;
}

uint8_t open(const char* filename) {
    closeFile();
    g_nPlaybackTrack = 0;
    strcpy(g_sFilename, filename);
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

    if(pthread_create(&g_threadFile, &attr, fileThread, NULL)) {
        fprintf(stderr, "zynaudioplayer error: failed to create file reading thread\n");
        closeFile();
        return 0;
    }
    return 1;
}

float getFileDuration(const char* filename) {
    SF_INFO info;
    info.format = 0;
    info.samplerate = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if(info.samplerate)
        return (float)info.frames / info.samplerate;
    return 0.0f;
}

void closeFile() {
    stopPlayback();
    g_bFileOpen = 0;
    void* status;
    pthread_join(g_threadFile, &status);
    g_sFilename[0] = '\0';
}

uint8_t save(const char* filename) {
    //!@todo Implement save
    return 0;
}

const char* getFilename() {
    return g_sFilename;
}

float getDuration() {
    if(g_sf_info.samplerate)
        return (float)g_sf_info.frames / g_sf_info.samplerate;
    return 0.0f;
}

void setPosition(float time) {
    g_nPlaybackPosFrames = time * g_nSamplerate;
    g_nFileReadStatus = SEEKING;
    DPRINTF("New position requested, setting loading status to SEEKING\n");
}

float getPosition() {
    return (float)g_nPlaybackPosFrames / g_nSamplerate;
}

void setLoop(uint8_t bLoop) {
    g_bLoop = bLoop;
    if(bLoop) {
        g_nFileReadStatus = LOOPING;
        DPRINTF("Looping requested, setting loading status to SEEKING\n");
    }
}

void startPlayback() {
    if(!g_pJackClient)
        return;
    if(g_bFileOpen && g_nPlayState != PLAYING)
        g_nPlayState = STARTING;
}

void stopPlayback() {
    if(g_nPlayState == STOPPED)
        return;
    if(g_bFileOpen && g_nPlayState != STOPPED)
        g_nPlayState = STOPPING;
}

uint8_t getPlayState() {
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

size_t getQueueFront() {
    return g_ringBuffer.front;
}

size_t getQueueBack() {
    return g_ringBuffer.back;
}

/*** Private functions not exposed as external C functions (not declared in header) ***/

// Clean up before library unloads
void end() {
    closeFile();
    if(g_pJackClient)
        jack_client_close(g_pJackClient);
}

// Handle JACK process callback
static int onJackProcess(jack_nframes_t nFrames, void *notused) {
    static size_t count;
    jack_default_audio_sample_t *pOutA = (jack_default_audio_sample_t*)jack_port_get_buffer(g_pJackOutA, nFrames);
    jack_default_audio_sample_t *pOutB = (jack_default_audio_sample_t*)jack_port_get_buffer(g_pJackOutB, nFrames);
    count = 0;

    if(g_nPlayState == STARTING && g_nFileReadStatus != SEEKING)
        g_nPlayState = PLAYING;

    if(g_nPlayState == PLAYING || g_nPlayState == STOPPING)
        count = ringBufferPop(&g_ringBuffer, pOutA, pOutB, nFrames);
    for(size_t offset = 0; offset < count; ++offset) {
        // Set volume / gain / level
        pOutA[offset] *= g_fLevel;
        pOutB[offset] *= g_fLevel;
    }
    if(g_nPlayState == STOPPING || g_nPlayState == PLAYING && g_nLastFrame == g_ringBuffer.front) {
        // Soft mute (not perfect for short last period of file but better than nowt)
        for(size_t offset = 0; offset < count; ++offset) {
            pOutA[offset] *= 1.0 - ((float)offset / count);
            pOutB[offset] *= 1.0 - ((float)offset / count);
        }
        g_nPlayState = STOPPED;
        g_nLastFrame = -1;
        g_nPlaybackPosFrames = 0;
        g_nFileReadStatus = SEEKING;

        DPRINTF("zynaudioplayer: Stopped. Used %u frames from %u in buffer to soft mute (fade). Silencing remaining %u frames (%u bytes)\n", count, nFrames, nFrames - count, (nFrames - count) * sizeof(jack_default_audio_sample_t));
    }

    // Silence remainder of frame
    memset(pOutA + count, 0, (nFrames - count) * sizeof(jack_default_audio_sample_t));
    memset(pOutB + count, 0, (nFrames - count) * sizeof(jack_default_audio_sample_t));

    // Process MIDI input
    void* pMidiBuffer = jack_port_get_buffer(g_pJackMidiIn, nFrames);
    jack_midi_event_t midiEvent;
    jack_nframes_t nCount = jack_midi_get_event_count(pMidiBuffer);
    for(jack_nframes_t i = 0; i < nCount; i++)
    {
        jack_midi_event_get(&midiEvent, pMidiBuffer, i);
        if((midiEvent.buffer[0] & 0xF0) == 0xB0)
        {
            switch(midiEvent.buffer[1])
            {
                case 1:
                    setPosition(midiEvent.buffer[2] * getDuration() / 127);
                    break;
                case 7:
                    g_fLevel = (float)midiEvent.buffer[2] / 100.0;
                    break;
                case 68:
                    if(midiEvent.buffer[2] > 63)
                        startPlayback();
                    else
                        stopPlayback();
                    break;
                case 69:
                    setLoop(midiEvent.buffer[2] > 63);
                    break;
            }
        }
    }
    return 0;
}

// Handle JACK process callback
int onJackSamplerate(jack_nframes_t nFrames, void *pArgs) {
    DPRINTF("zynaudioplayer: Jack sample rate: %u\n", nFrames);
    g_nSamplerate = nFrames;
    return 0;
}

void* fileThread(void* param) {
    g_sf_info.format = 0; // This triggers sf_open to populate info structure
    SNDFILE* pFile = sf_open(g_sFilename, SFM_READ, &g_sf_info);
    if(!pFile || g_sf_info.channels < 1) {
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", g_sFilename, sf_strerror(pFile));
        pthread_exit(NULL);
    }
    if(g_sf_info.channels < 0) {
        fprintf(stderr, "libaudioplayer error: file %s has no tracks\n", g_sFilename);
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        pthread_exit(NULL);
    }
    if(g_sf_info.frames < 100) {
        fprintf(stderr, "libaudioplayer error: file %s too short (%u frames)\n", g_sFilename, g_sf_info.frames);
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        pthread_exit(NULL);
    }
    g_bFileOpen = 1;
    g_nFileReadStatus = SEEKING;
    g_nPlaybackPosFrames = 0;

    // Initialise samplerate converter
    SRC_DATA srcData;
    float pBufferOut[AUDIO_BUFFER_SIZE]; // Buffer used to write converted sample data to
    float pBufferIn[AUDIO_BUFFER_SIZE]; // Buffer used to read sample data from file
    srcData.data_in = pBufferIn;
    srcData.data_out = pBufferOut;
    srcData.src_ratio = (float)g_nSamplerate / g_sf_info.samplerate;
    srcData.output_frames = AUDIO_BUFFER_SIZE;
    size_t nUnusedFrames = 0; // Quantity of samples in input buffer not used by SRC
    size_t nMaxFrames = AUDIO_BUFFER_SIZE / g_sf_info.channels;
    int nError;
    SRC_STATE* pSrcState = src_new(g_nSrcQuality, g_sf_info.channels, &nError);

    while(g_bFileOpen) {
        if(g_nFileReadStatus == SEEKING) {
            // Main thread has signalled seek within file
            ringBufferInit(&g_ringBuffer);
            size_t nNewPos = g_nPlaybackPosFrames;
            if(srcData.src_ratio)
                nNewPos = g_nPlaybackPosFrames / srcData.src_ratio;
            sf_seek(pFile, nNewPos, SEEK_SET);
            g_nFileReadStatus = LOADING;
            src_reset(pSrcState);
            nUnusedFrames = 0;
            nMaxFrames = AUDIO_BUFFER_SIZE / g_sf_info.channels;
            srcData.end_of_input = 0;
        } else if(g_nFileReadStatus == LOOPING) {
            // Reached end of file and need to read from start
            sf_seek(pFile, 0, SEEK_SET);
            g_nFileReadStatus = LOADING;
            src_reset(pSrcState);
            srcData.end_of_input = 0;
            nMaxFrames = AUDIO_BUFFER_SIZE / g_sf_info.channels;
            nUnusedFrames = 0;
        }
        if(g_nFileReadStatus == LOADING)
        {
            g_nLastFrame = -1;
            // Load block of data from file to SRC or output buffer
            int nFramesRead;
            if(srcData.src_ratio == 1.0) {
                // No SRC required so populate SRC output buffer directly
                nFramesRead = sf_readf_float(pFile, pBufferOut, nMaxFrames);
            } else {
                // Populate SRC input buffer before SRC process
                nMaxFrames = (AUDIO_BUFFER_SIZE / g_sf_info.channels) - nUnusedFrames;
                nFramesRead = sf_readf_float(pFile, pBufferIn + nUnusedFrames * g_sf_info.channels, nMaxFrames);
            }
            if(nFramesRead == nMaxFrames) {
                // Filled buffer from file so probably more data to read
                srcData.end_of_input = 0;
            }
            else if(g_bLoop) {
                // Short read - looping so fill from start of file
                g_nFileReadStatus = LOOPING;
                srcData.end_of_input = 1;
                DPRINTF("zynaudioplayer read to end of input file - setting loading status to looping\n");
            } else {
                // Short read - assume at end of file
                g_nFileReadStatus = IDLE;
                srcData.end_of_input = 1;
                DPRINTF("zynaudioplayer read to end of input file - setting loading status to IDLE\n");
            }
            if(srcData.src_ratio != 1.0) {
                // We need to perform SRC on this block of code
                srcData.input_frames = nFramesRead;
                int rc = src_process(pSrcState, &srcData);
                nFramesRead = srcData.output_frames_gen;
                nUnusedFrames = nMaxFrames - srcData.input_frames_used;
                if(rc) {
                    DPRINTF("SRC failed with error %d, %u frames generated\n", nFramesRead, srcData.output_frames_gen);
                } else {
                    DPRINTF("SRC suceeded - %u frames generated, %u frames unused\n", srcData.output_frames_gen, nUnusedFrames);
                }
                // Shift unused samples to start of buffer
                memcpy(pBufferIn, pBufferIn + (nFramesRead - nUnusedFrames) * sizeof(float), nUnusedFrames * sizeof(float));
            } else {
                DPRINTF("No SRC, read %u frames\n", nFramesRead);
            }
            
            while(ringBufferGetFree(&g_ringBuffer) < nFramesRead) {
                // Wait until there is sufficient space in ring buffer to add new sample data
                usleep(1000);
                if(g_nFileReadStatus == SEEKING || g_bFileOpen == 0)
                    break;
            }

            if(g_bFileOpen && g_sf_info.channels > g_nPlaybackTrack) {
                // Demux samples and populate playback ring buffers
                for(size_t frame = 0; frame < nFramesRead; ++frame) {
                    float fA = 0.0, fB = 0.0;
                    size_t sample = frame * g_sf_info.channels;
                    if(g_sf_info.channels == 1) {
                        // Mono source so send to both outputs
                        fA = pBufferOut[sample] / 2;
                        fB = pBufferOut[sample] / 2;
                    } else if(g_nPlaybackTrack < 0) {
                        // Send sum of odd channels to A and even channels to B
                        for(int track = 0; track < g_sf_info.channels; ++track) {
                            if(track % 2)
                                fB += pBufferOut[sample + track] / (g_sf_info.channels / 2);
                            else
                                fA += pBufferOut[sample + track] / (g_sf_info.channels / 2);
                        }
                    } else {
                        // Send g_nPlaybackTrack to A and g_nPlaybackTrack + 1 to B
                        fA = pBufferOut[sample];
                        if(g_nPlaybackTrack + 1 < g_sf_info.channels)
                            fB = pBufferOut[sample + 1];
                        else
                            fB = pBufferOut[sample];
                    }
                    if(0 == ringBufferPush(&g_ringBuffer, &fA, &fB, 1))
                        break; // Shouldn't underun due to previous wait for space but just in case...
                }
            }
            if(g_nFileReadStatus == IDLE)
                g_nLastFrame = g_ringBuffer.back;
        }
        usleep(10000);
    }
    if(pFile) {
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
    }
    ringBufferInit(&g_ringBuffer); // Don't want audio playing from closed file
    g_nPlaybackPosFrames = 0;
    g_nLastFrame = -1;
    pSrcState = src_delete(pSrcState);
    DPRINTF("File reader thread ended\n");
    pthread_exit(NULL);
}

void init(const char* jackName) {
    printf("zynaudioplayer init\n");
    ringBufferInit(&g_ringBuffer);

    // Register with Jack server
    char *sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;

    if ((g_pJackClient = jack_client_open(jackName, nOptions, &nStatus, sServerName)) == 0) {
        fprintf(stderr, "libaudioplayer error: failed to start jack client: %d\n", nStatus);
        exit(1);
    }

    g_nSamplerate = jack_get_sample_rate(g_pJackClient);

    // Create audio output ports
    if (!(g_pJackOutA = jack_port_register(g_pJackClient, "output_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port A\n");
        exit(1);
    }
    if (!(g_pJackOutB = jack_port_register(g_pJackClient, "output_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port B\n");
        exit(1);
    }

    // Create MIDI input port
    if(!(g_pJackMidiIn = jack_port_register(g_pJackClient, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0)))
    {
        fprintf(stderr, "libzynaudioplayer error: cannot register MIDI input port\n");
        exit(1);
    }

    // Register the cleanup function to be called when program exits
    //atexit(end);

    // Register the callback to process audio and MIDI
    jack_set_process_callback(g_pJackClient, onJackProcess, 0);

    if (jack_activate(g_pJackClient)) {
        fprintf(stderr, "libaudioplayer error: cannot activate client\n");
        exit(1);
    }
}

const char* getFileInfo(const char* filename, int type) {
    SF_INFO info;
    info.format = 0;
    info.samplerate = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    const char* pValue = sf_get_string(pFile, type);
    if(pValue) {
        sf_close(pFile);
        return pValue;
    }
    sf_close(pFile);
    return "";
}

uint8_t setSrcQuality(unsigned int quality) {
    if(quality > SRC_LINEAR)
        return 0;
    g_nSrcQuality = quality;
    return 1;
}

void setVolume(float level) {
    if(level < 0 || level > 2)
        return;
    g_fLevel = level;
}

float getVolume() {
    return g_fLevel;
}

void setPlaybackTrack(int track) {
    if(g_bFileOpen && track < g_sf_info.channels) {
        if(g_sf_info.channels == 1)
            g_nPlaybackTrack = 0;
        else
            g_nPlaybackTrack = track;
    }
}

int getPlaybackTrack() {
    return g_nPlaybackTrack;
}