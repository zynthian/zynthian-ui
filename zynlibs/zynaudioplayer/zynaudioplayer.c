/*  Audio file player library for Zynthian
    Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include "zynaudioplayer.h"

#include <stdio.h> //provides printf
#include <string.h> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <jack/midiport.h> //provides JACK MIDI interface
#include <jack/ringbuffer.h> //provides jack ring buffer
#include <sndfile.h> //provides sound file manipulation
#include <samplerate.h> //provides samplerate conversion
#include <pthread.h> //provides multithreading
#include <unistd.h> //provides usleep
#include <stdlib.h> //provides exit

#define AUDIO_BUFFER_SIZE 50000 // 50000 is approx. 1s of audio
#define RING_BUFFER_SIZE AUDIO_BUFFER_SIZE * 2 * sizeof(float)
#define MAX_PLAYERS 16 // Maximum quanity of audio players the library can host

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

struct AUDIO_PLAYER {
    jack_port_t* jack_out_a;
    jack_port_t* jack_out_b;
    jack_port_t * jack_midi_in;
    jack_client_t * jack_client;
    unsigned int handle;

    uint8_t file_open; // 1 whilst file is open - used to flag thread to close file
    uint8_t file_read_status; // File reading status (IDLE|SEEKING|LOADING)
    uint8_t play_state; // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    uint8_t loop; // 1 to loop at end of song
    struct SF_INFO  sf_info; // Structure containing currently loaded file info
    pthread_t file_thread; // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats
    jack_ringbuffer_t * ringbuffer_a; // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t * ringbuffer_b; // Used to pass B samples from file reader to jack process
    jack_nframes_t play_pos_frames; // Current playback position in frames since start of audio
    unsigned int src_quality;
    char filename[128];
    float gain; // Audio level (volume) 0..1
    int playback_track; // Which stereo pair of tracks to playback (-1 to mix all stero pairs)
};

// **** Global variables ****
struct AUDIO_PLAYER * g_players[MAX_PLAYERS];
jack_nframes_t g_samplerate = 44100; // Playback samplerate set by jackd
uint8_t g_debug = 0;

#define DPRINTF(fmt, args...) if(g_debug) printf(fmt, ## args)
    
// **** Internal (non-public) functions ****

static inline struct AUDIO_PLAYER * get_player(int player_handle) {
    if(player_handle > MAX_PLAYERS || player_handle < 0)
        return NULL;
    return g_players[player_handle];
}

void* file_thread_fn(void * param) {
    struct AUDIO_PLAYER * pPlayer = (struct AUDIO_PLAYER *) (param);
    pPlayer->sf_info.format = 0; // This triggers sf_open to populate info structure
    SNDFILE* pFile = sf_open(pPlayer->filename, SFM_READ, &pPlayer->sf_info);
    if(!pFile || pPlayer->sf_info.channels < 1) {
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename, sf_strerror(pFile));
        pthread_exit(NULL);
    }
    if(pPlayer->sf_info.channels < 0) {
        fprintf(stderr, "libaudioplayer error: file %s has no tracks\n", pPlayer->filename);
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        pthread_exit(NULL);
    }
    pPlayer->file_open = 1;
    pPlayer->play_pos_frames = 0;
    pPlayer->file_read_status = SEEKING;
    pPlayer->ringbuffer_a = jack_ringbuffer_create(RING_BUFFER_SIZE);
    pPlayer->ringbuffer_b = jack_ringbuffer_create(RING_BUFFER_SIZE);

    // Initialise samplerate converter
    SRC_DATA srcData;
    float pBufferOut[AUDIO_BUFFER_SIZE]; // Buffer used to write converted sample data to
    float pBufferIn[AUDIO_BUFFER_SIZE]; // Buffer used to read sample data from file
    srcData.data_in = pBufferIn;
    srcData.data_out = pBufferOut;
    srcData.src_ratio = (float)g_samplerate / pPlayer->sf_info.samplerate;
    srcData.output_frames = AUDIO_BUFFER_SIZE / pPlayer->sf_info.channels;
    size_t nUnusedFrames = 0; // Quantity of samples in input buffer not used by SRC
    size_t nMaxFrames = AUDIO_BUFFER_SIZE / pPlayer->sf_info.channels;
    int nError;
    SRC_STATE* pSrcState = src_new(pPlayer->src_quality, pPlayer->sf_info.channels, &nError);

    while(pPlayer->file_open) {
        if(pPlayer->file_read_status == SEEKING) {
            // Main thread has signalled seek within file
            jack_ringbuffer_reset(pPlayer->ringbuffer_a);
            jack_ringbuffer_reset(pPlayer->ringbuffer_b);
            size_t nNewPos = pPlayer->play_pos_frames;
            if(srcData.src_ratio)
                nNewPos = pPlayer->play_pos_frames / srcData.src_ratio;
            sf_seek(pFile, nNewPos, SEEK_SET);
            pPlayer->file_read_status = LOADING;
            src_reset(pSrcState);
            nUnusedFrames = 0;
            nMaxFrames = AUDIO_BUFFER_SIZE / pPlayer->sf_info.channels;
            srcData.end_of_input = 0;
        } else if(pPlayer->file_read_status == LOOPING) {
            // Reached end of file and need to read from start
            sf_seek(pFile, 0, SEEK_SET);
            pPlayer->file_read_status = LOADING;
            src_reset(pSrcState);
            srcData.end_of_input = 0;
            nMaxFrames = AUDIO_BUFFER_SIZE / pPlayer->sf_info.channels;
            nUnusedFrames = 0;
        }
        if(pPlayer->file_read_status == LOADING)
        {
            // Load block of data from file to SRC or output buffer
            int nFramesRead;
            if(srcData.src_ratio == 1.0) {
                // No SRC required so populate SRC output buffer directly
                nFramesRead = sf_readf_float(pFile, pBufferOut, nMaxFrames);
            } else {
                // Populate SRC input buffer before SRC process
                nMaxFrames = (AUDIO_BUFFER_SIZE / pPlayer->sf_info.channels) - nUnusedFrames;
                nFramesRead = sf_readf_float(pFile, pBufferIn + nUnusedFrames * pPlayer->sf_info.channels, nMaxFrames);
            }
            if(nFramesRead == nMaxFrames) {
                // Filled buffer from file so probably more data to read
                srcData.end_of_input = 0;
                DPRINTF("zynaudioplayer read %u frames into ring buffer\n", nFramesRead);
            }
            else if(pPlayer->loop) {
                // Short read - looping so fill from start of file
                pPlayer->file_read_status = LOOPING;
                srcData.end_of_input = 1;
                DPRINTF("zynaudioplayer read to end of input file - setting loading status to looping\n");
            } else {
                // Short read - assume at end of file
                pPlayer->file_read_status = IDLE;
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
                    //DPRINTF("SRC suceeded - %u frames generated, %u frames unused\n", srcData.output_frames_gen, nUnusedFrames);
                }
                // Shift unused samples to start of buffer
                memcpy(pBufferIn, pBufferIn + (nFramesRead - nUnusedFrames) * sizeof(float), nUnusedFrames * sizeof(float));
            } else {
                //DPRINTF("No SRC, read %u frames\n", nFramesRead);
            }
            
            while(jack_ringbuffer_write_space(pPlayer->ringbuffer_a) < nFramesRead * sizeof(float)) {
                // Wait until there is sufficient space in ring buffer to add new sample data
                usleep(1000);
                if(pPlayer->file_read_status == SEEKING || pPlayer->file_open == 0)
                    break;
            }

            if(pPlayer->file_open && pPlayer->sf_info.channels > pPlayer->playback_track) {
                // Demux samples and populate playback ring buffers
                for(size_t frame = 0; frame < nFramesRead; ++frame) {
                    float fA = 0.0, fB = 0.0;
                    size_t sample = frame * pPlayer->sf_info.channels;
                    if(pPlayer->sf_info.channels == 1) {
                        // Mono source so send to both outputs
                        fA = pBufferOut[sample] / 2;
                        fB = pBufferOut[sample] / 2;
                    } else if(pPlayer->playback_track < 0) {
                        // Send sum of odd channels to A and even channels to B
                        for(int track = 0; track < pPlayer->sf_info.channels; ++track) {
                            if(track % 2)
                                fB += pBufferOut[sample + track] / (pPlayer->sf_info.channels / 2);
                            else
                                fA += pBufferOut[sample + track] / (pPlayer->sf_info.channels / 2);
                        }
                    } else {
                        // Send pPlayer->playback_track to A and pPlayer->playback_track + 1 to B
                        fA = pBufferOut[sample];
                        if(pPlayer->playback_track + 1 < pPlayer->sf_info.channels)
                            fB = pBufferOut[sample + 1];
                        else
                            fB = pBufferOut[sample];
                    }
                    jack_ringbuffer_write(pPlayer->ringbuffer_b, (const char*)(&fB), sizeof(float));
                    if(sizeof(float) < jack_ringbuffer_write(pPlayer->ringbuffer_a, (const char*)(&fA), sizeof(float))) {
                         // Shouldn't underun due to previous wait for space but just in case...
                        fprintf(stderr, "Underrun during writing to ringbuffer - this should never happen!!!\n");
                        break;
                    }
                }
            }
        }
        usleep(10000);
    }
pPlayer->play_state = STOPPED; // Already stopped when clearing file_open but let's be sure!
    if(pFile) {
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
    }
    pPlayer->play_pos_frames = 0;
    jack_ringbuffer_free(pPlayer->ringbuffer_a);
    jack_ringbuffer_free(pPlayer->ringbuffer_b);
    pSrcState = src_delete(pSrcState);
    DPRINTF("File reader thread ended\n");
    pthread_exit(NULL);
}


/**** player instance functions take handle param to identify player instance****/

uint8_t open(int player_handle, const char* filename) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    close_file(player_handle);
    pPlayer->playback_track = 0;
    strcpy(pPlayer->filename, filename);
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

    if(pthread_create(&pPlayer->file_thread, &attr, file_thread_fn, pPlayer)) {
        fprintf(stderr, "zynaudioplayer error: failed to create file reading thread\n");
        close_file(player_handle);
        return 0;
    }
    return 1;
}

void close_file(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    if(pPlayer->file_open == 0)
        return;
    stop_playback(player_handle);
    pPlayer->file_open = 0;
    void* status;
    pthread_join(pPlayer->file_thread, &status);
    pPlayer->filename[0] = '\0';
}

uint8_t save(int player_handle, const char* filename) {
    //!@todo Implement save
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return 0;
}

const char* get_filename(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return "";
    return pPlayer->filename;
}

float get_duration(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0.0;
    if(pPlayer->sf_info.samplerate)
        return (float)pPlayer->sf_info.frames / pPlayer->sf_info.samplerate;
    return 0.0f;
}

void set_position(int player_handle, float time) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL || time >= get_duration(player_handle))
        return;
    pPlayer->play_pos_frames = time * g_samplerate;
    pPlayer->file_read_status = SEEKING;
    DPRINTF("New position requested, setting loading status to SEEKING\n");
}

float get_position(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0.0;
    return (float)pPlayer->play_pos_frames / g_samplerate;
}

void enable_loop(int player_handle, uint8_t bLoop) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    pPlayer->loop = bLoop;
    if(bLoop) {
        pPlayer->file_read_status = LOOPING;
        DPRINTF("Looping requested, setting loading status to SEEKING\n");
    }
}

uint8_t is_loop(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return(pPlayer->loop);
}

void start_playback(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->jack_client && pPlayer->file_open && pPlayer->play_state != PLAYING)
        pPlayer->play_state = STARTING;
}

void stop_playback(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->play_state != STOPPED)
        pPlayer->play_state = STOPPING;
}

uint8_t get_playback_state(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer)
        return pPlayer->play_state;
    return STOPPED;
}

int get_samplerate(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return g_samplerate;
    return pPlayer->sf_info.samplerate;
}

int get_channels(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return pPlayer->sf_info.channels;
}

int get_frames(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return pPlayer->sf_info.frames;
}

int get_format(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return pPlayer->sf_info.format;
}

/*** Private functions not exposed as external C functions (not declared in header) ***/

// Clean up before library unloads
void end() {
    for(int player_handle = 0; player_handle < MAX_PLAYERS; ++player_handle)
        remove_player(player_handle);
}

void remove_player(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    close_file(player_handle);
    jack_client_close(pPlayer->jack_client);

    unsigned int count = 0;
    for(size_t i = 0; i < MAX_PLAYERS; ++i) {
        if(g_players[i] == pPlayer)
            g_players[i] = NULL;
        if(g_players[i])
            ++count;
    }
    free(pPlayer);
    if(count == 0)
        end();
}

// Handle JACK process callback
int on_jack_process(jack_nframes_t nFrames, void * arg) {
    size_t count;
    uint8_t eof = 0;
    struct AUDIO_PLAYER * pPlayer = (struct AUDIO_PLAYER *) (arg);
    if(!pPlayer)
        return 0;
    jack_default_audio_sample_t *pOutA = (jack_default_audio_sample_t*)jack_port_get_buffer(pPlayer->jack_out_a, nFrames);
    jack_default_audio_sample_t *pOutB = (jack_default_audio_sample_t*)jack_port_get_buffer(pPlayer->jack_out_b, nFrames);
    count = 0;

    if(pPlayer->play_state == STARTING && pPlayer->file_read_status != SEEKING)
        pPlayer->play_state = PLAYING;

    if(pPlayer->play_state == PLAYING || pPlayer->play_state == STOPPING) {
        count = jack_ringbuffer_read(pPlayer->ringbuffer_a, (char*)pOutA, nFrames * sizeof(float));
        jack_ringbuffer_read(pPlayer->ringbuffer_b, (char*)pOutB, count);
        eof = (pPlayer->file_read_status == IDLE && jack_ringbuffer_read_space(pPlayer->ringbuffer_a) == 0);
    }
    count /= sizeof(float);
    for(size_t offset = 0; offset < count; ++offset) {
        // Set volume / gain / level
        pOutA[offset] *= pPlayer->gain;
        pOutB[offset] *= pPlayer->gain;
    }
    pPlayer->play_pos_frames += count;

if(pPlayer->play_state == STOPPING || pPlayer->play_state == PLAYING && eof) {
        // Soft mute (not perfect for short last period of file but better than nowt)
        for(size_t offset = 0; offset < count; ++offset) {
            pOutA[offset] *= 1.0 - ((float)offset / count);
            pOutB[offset] *= 1.0 - ((float)offset / count);
        }
        pPlayer->play_state = STOPPED;
        if(eof) {
            // Recue to start if played to end of file
            pPlayer->play_pos_frames = 0;
            pPlayer->file_read_status = SEEKING;
        }

        DPRINTF("zynaudioplayer: Stopped. Used %u frames from %u in buffer to soft mute (fade). Silencing remaining %u frames (%u bytes)\n", count, nFrames, nFrames - count, (nFrames - count) * sizeof(jack_default_audio_sample_t));
    }

    // Silence remainder of frame
    memset(pOutA + count, 0, (nFrames - count) * sizeof(jack_default_audio_sample_t));
    memset(pOutB + count, 0, (nFrames - count) * sizeof(jack_default_audio_sample_t));

    // Process MIDI input
    void* pMidiBuffer = jack_port_get_buffer(pPlayer->jack_midi_in, nFrames);
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
                    set_position(pPlayer->handle, midiEvent.buffer[2] * get_duration(pPlayer->handle) / 127);
                    break;
                case 7:
                    pPlayer->gain = (float)midiEvent.buffer[2] / 100.0;
                    break;
                case 68:
                    if(midiEvent.buffer[2] > 63)
                        start_playback(pPlayer->handle);
                    else
                        stop_playback(pPlayer->handle);
                    break;
                case 69:
                    enable_loop(pPlayer->handle, midiEvent.buffer[2] > 63);
                    break;
            }
        }
    }
    return 0;
}

// Handle JACK process callback
int on_jack_samplerate(jack_nframes_t nFrames, void *pArgs) {
    DPRINTF("zynaudioplayer: Jack sample rate: %u\n", nFrames);
    g_samplerate = nFrames;
    return 0;
}

int init() {
    int player_handle;
    struct AUDIO_PLAYER * pPlayer = NULL;
    for(player_handle = 0; player_handle < MAX_PLAYERS; ++player_handle) {
        if(g_players[player_handle])
            continue;
        pPlayer = malloc(sizeof(struct AUDIO_PLAYER));
        break;
    }
    if(!pPlayer) {
        fprintf(stderr, "Failed to create instance of audio player\n");
        return -1;
    }

    pPlayer->file_open = 0;
    pPlayer->file_read_status = IDLE;
    pPlayer->play_state = STOPPED;
    pPlayer->loop = 0;
    pPlayer->play_pos_frames = 0;
    pPlayer->src_quality = SRC_SINC_FASTEST;
    pPlayer->gain = 1.0;
    pPlayer->playback_track = 0;
    pPlayer->handle = player_handle;

    char *sServerName = NULL;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;
    char client_name[] = "audioplayer_xxx";
    sprintf(client_name, "audio_player_%03d", player_handle);

    if((pPlayer->jack_client = jack_client_open(client_name, nOptions, &nStatus, sServerName)) == 0) {
        fprintf(stderr, "libaudioplayer error: failed to start jack client: %d\n", nStatus);
        return -1;
    }

    // Create audio output ports
    if (!(pPlayer->jack_out_a = jack_port_register(pPlayer->jack_client, "output_a", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port A\n");
        return -1;
    }
    if (!(pPlayer->jack_out_b = jack_port_register(pPlayer->jack_client, "output_b", JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port B\n");
        jack_port_unregister(pPlayer->jack_client, pPlayer->jack_out_a);
        return -1;
    }

    // Create MIDI input port
    if(!(pPlayer->jack_midi_in = jack_port_register(pPlayer->jack_client, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0)))
    {
        fprintf(stderr, "libzynaudioplayer error: cannot register MIDI input port\n");
        jack_port_unregister(pPlayer->jack_client, pPlayer->jack_out_a);
        jack_port_unregister(pPlayer->jack_client, pPlayer->jack_out_b);
        return -1;
    }

    // Register the callback to process audio and MIDI
    jack_set_process_callback(pPlayer->jack_client, on_jack_process, pPlayer);
    jack_set_sample_rate_callback(pPlayer->jack_client, on_jack_samplerate, 0);

    if(jack_activate(pPlayer->jack_client)) {
        fprintf(stderr, "libaudioplayer error: cannot activate client\n");
        return -1;
    }

    g_players[player_handle] = pPlayer;
    g_samplerate = jack_get_sample_rate(pPlayer->jack_client);
    //printf("libzynaudioplayer: Created new audio player\n");
    return player_handle;
}

const char* get_jack_client_name(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return "";
    return jack_get_client_name(pPlayer->jack_client);
}

uint8_t set_src_quality(int player_handle, unsigned int quality) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    if(quality > SRC_LINEAR)
        return 0;
    pPlayer->src_quality = quality;
    return 1;
}

void set_gain(int player_handle, float gain) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    if(gain < 0 || gain > 2)
        return;
    pPlayer->gain = gain;
}

float get_gain(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0.0;
    return pPlayer->gain;
}

void set_playback_track(int player_handle, int track) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    if(pPlayer->file_open && track < pPlayer->sf_info.channels) {
        if(pPlayer->sf_info.channels == 1)
            pPlayer->playback_track = 0;
        else
            pPlayer->playback_track = track;
    }
}

int get_playback_track(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return pPlayer->playback_track;
}


/**** Global functions ***/

float get_file_duration(const char* filename) {
    SF_INFO info;
    info.format = 0;
    info.samplerate = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if(info.samplerate)
        return (float)info.frames / info.samplerate;
    return 0.0f;
}

const char* get_file_info(const char* filename, int type) {
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

void enable_debug(int enable) {
    printf("libaudioplayer setting debug mode %s\n", enable?"on":"off");
    g_debug = enable;
}

int is_debug() {
    return g_debug;
}

unsigned int get_player_count() {
    int count = 0;
    for(int i = 0; i < MAX_PLAYERS; ++i)
        if(g_players)
            ++count;
    return count;
}
