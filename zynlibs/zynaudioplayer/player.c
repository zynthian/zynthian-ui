/*  Audio file player library for Zynthian
    Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include "player.h"

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
#include "tinyosc.h" //provides OSC interface
#include <arpa/inet.h> // provides inet_pton
#include <fcntl.h> //provides fcntl
#include <math.h> // provides pow

#define MAX_PLAYERS 16 // Maximum quanity of audio players the library can host
#define MAX_OSC_CLIENTS 5 // Maximum quantity of OSC clients
#define OSC_PORT 9000 // UDP/IP port for OSC communication

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

    uint8_t file_open; // 0=file closed, 1=file opening, 2=file open - used to flag thread to close file or thread to flag file failed to open
    uint8_t file_read_status; // File reading status (IDLE|SEEKING|LOADING)
    uint8_t play_state; // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    uint8_t loop; // 1 to loop at end of song
    struct SF_INFO  sf_info; // Structure containing currently loaded file info
    pthread_t file_thread; // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats
    jack_ringbuffer_t * ringbuffer_a; // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t * ringbuffer_b; // Used to pass B samples from file reader to jack process
    jack_nframes_t play_pos_frames; // Current playback position in frames since start of audio
    size_t frames; // Quanity of frames after samplerate conversion
    unsigned int src_quality;
    char filename[128];
    float gain; // Audio level (volume) 0..1
    int playback_track; // Which stereo pair of tracks to playback (-1 to mix all stero pairs)
    unsigned int buffer_size; // Quantity of frames read from file
    unsigned int buffer_count; // Factor by which ring buffer is larger than buffer
    uint8_t last_note_played; // MIDI note number of last note that triggered playback
    double src_ratio; // Samplerate ratio of file
    double pitch_shift; // Factor of pitch shift
};

// **** Global variables ****
struct AUDIO_PLAYER * g_players[MAX_PLAYERS];
jack_nframes_t g_samplerate = 44100; // Playback samplerate set by jackd
uint8_t g_debug = 0;
char g_oscbuffer[1024]; // Used to send OSC messages
char g_oscpath[32]; // OSC path
int g_oscfd = -1; // File descriptor for OSC socket
int g_bOsc = 0; // True if OSC client subscribed
struct sockaddr_in g_oscClient[MAX_OSC_CLIENTS]; // Array of registered OSC clients
pthread_t g_osc_thread; // ID of OSC listener thread
uint8_t g_run_osc = 1; // 1 to keep OSC listening thread running

#define DPRINTF(fmt, args...) if(g_debug) printf(fmt, ## args)
    
// **** Internal (non-public) functions ****

//!@todo Abstract OSC to separate library to allow reuse (used in mixer too)

void sendOscFloat(const char* path, float value) {
    if(g_oscfd == -1)
        return;
    int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "f", value);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscInt(const char* path, int value) {
    if(g_oscfd == -1)
        return;
    int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "i", value);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscString(const char* path, const char* value) {
    if(g_oscfd == -1)
        return;
    if(strlen(value) >= sizeof(g_oscbuffer))
        return;
    int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "s", value);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

int addOscClient(const char* client) {
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr != 0)
            continue;
        if(inet_pton(AF_INET, client, &(g_oscClient[i].sin_addr)) != 1) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynaudioplayer: Failed to register client %s\n", client);
            return -1;
        }
        fprintf(stderr, "libzynaudioplayer: Added OSC client %d: %s\n", i, client);
        for(int player_handle = 0; player_handle < MAX_PLAYERS; ++player_handle) {
            struct AUDIO_PLAYER * pPlayer = g_players[player_handle];
            if(!pPlayer)
                continue;
            sprintf(g_oscpath, "/player%d/open", pPlayer->handle);
            sendOscString(g_oscpath, pPlayer->filename);
            sprintf(g_oscpath, "/player%d/gain", pPlayer->handle);
            sendOscFloat(g_oscpath, pPlayer->gain);
            sprintf(g_oscpath, "/player%d/position", pPlayer->handle);
            sendOscInt(g_oscpath, (int)(get_position(pPlayer->handle)));
            sprintf(g_oscpath, "/player%d/duration", pPlayer->handle);
            sendOscFloat(g_oscpath, get_duration(pPlayer->handle));
            sprintf(g_oscpath, "/player%d/loop", pPlayer->handle);
            sendOscInt(g_oscpath, pPlayer->loop);
        }
        g_bOsc = 1;
        return i;
    }
    fprintf(stderr, "libzynaudioplayer: Not adding OSC client %s - Maximum client count reached [%d]\n", client, MAX_OSC_CLIENTS);
    return -1;
}

void removeOscClient(const char* client) {
    char pClient[sizeof(struct in_addr)];
    if(inet_pton(AF_INET, client, pClient) != 1)
        return;
    g_bOsc = 0;
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(memcmp(pClient, &g_oscClient[i].sin_addr.s_addr, 4) == 0) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynaudioplayer: Removed OSC client %d: %s\n", i, client);
        }
        if(g_oscClient[i].sin_addr.s_addr != 0)
            g_bOsc = 1;
    }
}

static inline struct AUDIO_PLAYER * get_player(int player_handle) {
    if(player_handle > MAX_PLAYERS || player_handle < 0)
        return NULL;
    return g_players[player_handle];
}

void* osc_thread_fn(void * param) {
    char buffer[2048]; // declare a 2Kb buffer to read packet data into
    int len = 0;
    const int osc_fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in sin;
    sin.sin_family = AF_INET;
    sin.sin_port = htons(OSC_PORT);
    sin.sin_addr.s_addr = INADDR_ANY;
    bind(osc_fd, (struct sockaddr *) &sin, sizeof(struct sockaddr_in));
    printf("OSC server listening on port %d\n", OSC_PORT);
    tosc_message osc_msg;

    while(g_run_osc) {
        fd_set readSet;
        FD_ZERO(&readSet);
        FD_SET(osc_fd, &readSet);
        struct timeval timeout = {1, 0}; // select times out after 1 second
        if (select(osc_fd + 1, &readSet, NULL, NULL, &timeout) > 0) {
            struct sockaddr sa; // can be safely cast to sockaddr_in
            socklen_t sa_len = sizeof(struct sockaddr_in);
            int len = 0;
            const char* path;
            size_t player;
            while ((len = (int) recvfrom(osc_fd, buffer, sizeof(buffer), 0, &sa, &sa_len)) > 0) {
                if(!tosc_parseMessage(&osc_msg, buffer, len)) {
                    path = tosc_getAddress(&osc_msg);
                    if(!strncmp(path, "/player", 7)) {
                        path += 7;
                        player = atoi(path);
                        while(path[0] != '\0' && path[0] != '/')
                            ++path;
                        if(path[0] == '/') {
                            if(!strcmp(path, "/transport")) {
                                if(osc_msg.format[0] == 'i')
                                    if(tosc_getNextInt32(&osc_msg))
                                        start_playback(player);
                                    else
                                        stop_playback(player);
                            } else if(!strcmp(path, "/load")) {
                                if(osc_msg.format[0] == 's')
                                    load(player, tosc_getNextString(&osc_msg));
                            } else if(!strcmp(path, "/save")) {
                                if(osc_msg.format[0] == 's')
                                    save(player, tosc_getNextString(&osc_msg));
                            } else if(!strcmp(path, "/unload")) {
                                unload(player);
                            } else if(!strncmp(path, "/position", 9)) {
                                if(osc_msg.format[0] == 'f')
                                    set_position(player, tosc_getNextFloat(&osc_msg));
                            }
                            else if(!strcmp(path, "/loop")) {
                                if(osc_msg.format[0] == 'i')
                                    enable_loop(player, tosc_getNextInt32(&osc_msg));
                            }
                            else if(!strcmp(path, "/quality")) {
                                if(osc_msg.format[0] == 'i')
                                    set_src_quality(player, tosc_getNextInt32(&osc_msg));
                            } else if(!strcmp(path, "/gain")) {
                                if(osc_msg.format[0] == 'f')
                                    set_gain(player, tosc_getNextFloat(&osc_msg));
                            } else if(!strcmp(path, "/track")) {
                                if(osc_msg.format[0] == 'i')
                                    set_playback_track(player, tosc_getNextInt32(&osc_msg));
                            } else if(!strcmp(path, "/buffersize")) {
                                if(osc_msg.format[0] == 'i')
                                    set_buffer_size(player, tosc_getNextInt32(&osc_msg));
                            } else if(!strcmp(path, "/buffercount")) {
                                if(osc_msg.format[0] == 'i')
                                    set_buffer_count(player, tosc_getNextInt32(&osc_msg));
                            }
                        }
                    }
                }
            }
        }
        usleep(100000);
    }
    close(osc_fd);
    printf("OSC server stopped\n");
    pthread_exit(NULL);
}

void* file_thread_fn(void * param) {
    struct AUDIO_PLAYER * pPlayer = (struct AUDIO_PLAYER *) (param);
    pPlayer->sf_info.format = 0; // This triggers sf_open to populate info structure
    SNDFILE* pFile = sf_open(pPlayer->filename, SFM_READ, &pPlayer->sf_info);
    if(!pFile || pPlayer->sf_info.channels < 1) {
        pPlayer->file_open = 0;
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename, sf_strerror(pFile));
        pthread_exit(NULL);
    }
    if(pPlayer->sf_info.channels < 0) {
        pPlayer->file_open = 0;
        fprintf(stderr, "libaudioplayer error: file %s has no tracks\n", pPlayer->filename);
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        pthread_exit(NULL);
    }
    pPlayer->file_open = 2;
    DPRINTF("Opened file '%s' with samplerate %u, duration: %f\n", pPlayer->filename, pPlayer->sf_info.samplerate, get_duration(pPlayer->handle));
    pPlayer->play_pos_frames = 0;
    pPlayer->file_read_status = SEEKING;
    pPlayer->ringbuffer_a = jack_ringbuffer_create(pPlayer->buffer_size * pPlayer->buffer_count * sizeof(float));
    pPlayer->ringbuffer_b = jack_ringbuffer_create(pPlayer->buffer_size * pPlayer->buffer_count * sizeof(float));

    // Initialise samplerate converter
    SRC_DATA srcData;
    float pBufferOut[pPlayer->buffer_size]; // Buffer used to write converted sample data to
    float pBufferIn[pPlayer->buffer_size]; // Buffer used to read sample data from file
    srcData.data_in = pBufferIn;
    srcData.data_out = pBufferOut;
    pPlayer->src_ratio = (float)g_samplerate / pPlayer->sf_info.samplerate;
    srcData.src_ratio = pPlayer->src_ratio;
    pPlayer->pitch_shift = 1.0;
    srcData.output_frames = pPlayer->buffer_size / pPlayer->sf_info.channels;
    size_t nUnusedFrames = 0; // Quantity of samples in input buffer not used by SRC
    size_t nMaxFrames = pPlayer->buffer_size / pPlayer->sf_info.channels;
    if(pPlayer->sf_info.samplerate)
        pPlayer->frames = pPlayer->sf_info.frames * g_samplerate / pPlayer->sf_info.samplerate;
    else
        pPlayer->frames = pPlayer->sf_info.frames;
    int nError;
    SRC_STATE* pSrcState = src_new(pPlayer->src_quality, pPlayer->sf_info.channels, &nError);
    sprintf(g_oscpath, "/player%d/load", pPlayer->handle);
    sendOscString(g_oscpath, pPlayer->filename);
    sprintf(g_oscpath, "/player%d/position", pPlayer->handle);
    size_t position = get_position(pPlayer->handle);
    sendOscInt(g_oscpath, position);
    sprintf(g_oscpath, "/player%d/duration", pPlayer->handle);
    sendOscFloat(g_oscpath, get_duration(pPlayer->handle));
    uint8_t play_state = pPlayer->play_state;
    sprintf(g_oscpath, "/player%d/transport", pPlayer->handle);
    sendOscInt(g_oscpath, play_state);

    while(pPlayer->file_open == 2) {
        if(pPlayer->file_read_status == SEEKING) {
            // Main thread has signalled seek within file
            jack_ringbuffer_reset(pPlayer->ringbuffer_a);
            jack_ringbuffer_reset(pPlayer->ringbuffer_b);
            srcData.src_ratio = pPlayer->src_ratio * pPlayer->pitch_shift;
            size_t nNewPos = pPlayer->play_pos_frames;
            if(srcData.src_ratio)
                nNewPos = pPlayer->play_pos_frames / srcData.src_ratio;
            sf_seek(pFile, nNewPos, SEEK_SET);
            pPlayer->file_read_status = LOADING;
            src_reset(pSrcState);
            nUnusedFrames = 0;
            nMaxFrames = pPlayer->buffer_size / pPlayer->sf_info.channels;
            srcData.end_of_input = 0;
        } else if(pPlayer->file_read_status == LOOPING) {
            // Reached end of file and need to read from start
            sf_seek(pFile, 0, SEEK_SET);
            pPlayer->file_read_status = LOADING;
            src_reset(pSrcState);
            srcData.end_of_input = 0;
            nMaxFrames = pPlayer->buffer_size / pPlayer->sf_info.channels;
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
                nMaxFrames = (pPlayer->buffer_size / pPlayer->sf_info.channels) - nUnusedFrames;
                nFramesRead = sf_readf_float(pFile, pBufferIn + nUnusedFrames * pPlayer->sf_info.channels, nMaxFrames);
            }
            if(nFramesRead == nMaxFrames) {
                // Filled buffer from file so probably more data to read
                srcData.end_of_input = 0;
                DPRINTF("libzynaudioplayer read %u frames into ring buffer\n", nFramesRead);
            }
            else if(pPlayer->loop) {
                // Short read - looping so fill from start of file
                pPlayer->file_read_status = LOOPING;
                srcData.end_of_input = 1;
                DPRINTF("libzynaudioplayer read to end of input file - setting loading status to looping\n");
            } else {
                // Short read - assume at end of file
                pPlayer->file_read_status = IDLE;
                srcData.end_of_input = 1;
                DPRINTF("libzynaudioplayer read to end of input file - setting loading status to IDLE\n");
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
            
            // Wait until there is sufficient space in ring buffer to add new sample data
            while(jack_ringbuffer_write_space(pPlayer->ringbuffer_a) < nFramesRead * sizeof(float)) {
                // Send dynamic OSC notifications within this thread, not jack process
                if(pPlayer->play_state != play_state) {
                    play_state = pPlayer->play_state;
                    sprintf(g_oscpath, "/player%d/transport", pPlayer->handle);
                    sendOscInt(g_oscpath, play_state);
                }
                if((int)(get_position(pPlayer->handle)) != position) {
                    position = get_position(pPlayer->handle);
                    sprintf(g_oscpath, "/player%d/position", pPlayer->handle);
                    sendOscInt(g_oscpath, position);
                }
                usleep(1000);
                if(pPlayer->file_read_status == SEEKING || pPlayer->file_open == 0)
                    break;
            }

            if(pPlayer->file_open == 2 && pPlayer->sf_info.channels > pPlayer->playback_track) {
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
        else
            pPlayer->filename[0] = '\0';
    }
    pPlayer->play_pos_frames = 0;
    jack_ringbuffer_free(pPlayer->ringbuffer_a);
    jack_ringbuffer_free(pPlayer->ringbuffer_b);
    pSrcState = src_delete(pSrcState);
    sprintf(g_oscpath, "/player%d/load", pPlayer->handle);
    sendOscString(g_oscpath, pPlayer->filename);
    DPRINTF("File reader thread ended\n");
    pthread_exit(NULL);
}


/**** player instance functions take handle param to identify player instance****/

uint8_t load(int player_handle, const char* filename) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    unload(player_handle);
    pPlayer->playback_track = 0;
    strcpy(pPlayer->filename, filename);
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

    pPlayer->file_open = 1;
    if(pthread_create(&pPlayer->file_thread, &attr, file_thread_fn, pPlayer)) {
        fprintf(stderr, "libzynaudioplayer error: failed to create file reading thread\n");
        unload(player_handle);
        return 0;
    }
    while(pPlayer->file_open == 1) {
        usleep(10000); //!@todo Optimise wait for file open
    }
    return (pPlayer->file_open == 2);
}

void unload(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL || pPlayer->file_open == 0)
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
    if(pPlayer && pPlayer->file_open == 2 && pPlayer->sf_info.samplerate)
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
    sprintf(g_oscpath, "/player%d/position", player_handle);
    sendOscInt(g_oscpath, (int)time);
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
    if(bLoop && pPlayer->file_read_status == IDLE) {
        pPlayer->file_read_status = LOOPING;
        DPRINTF("Looping requested, setting loading status to SEEKING\n");
    }
    sprintf(g_oscpath, "/player%d/loop", player_handle);
    sendOscInt(g_oscpath, bLoop);
}

uint8_t is_loop(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return 0;
    return(pPlayer->loop);
}

void start_playback(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->jack_client && pPlayer->file_open == 2 && pPlayer->play_state != PLAYING)
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
    g_run_osc = 0;
    void* status;
    pthread_join(g_osc_thread, &status);
}

void remove_player(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    unload(player_handle);
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
    if(pPlayer->play_pos_frames > pPlayer->frames)
        pPlayer->play_pos_frames %= pPlayer->frames;

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

        DPRINTF("libzynaudioplayer: Stopped. Used %u frames from %u in buffer to soft mute (fade). Silencing remaining %u frames (%u bytes)\n", count, nFrames, nFrames - count, (nFrames - count) * sizeof(jack_default_audio_sample_t));
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
        uint8_t cmd = midiEvent.buffer[0] & 0xF0;
        if((cmd == 0x80 || cmd == 0x90 && midiEvent.buffer[2] == 0) && pPlayer->last_note_played == midiEvent.buffer[1]) {
            // Note off
            stop_playback(pPlayer->handle);
            pPlayer->pitch_shift = 1.0;
            pPlayer->last_note_played = 0;
        } else if(cmd == 0x90) {
            // Note on
                stop_playback(pPlayer->handle);
                pPlayer->pitch_shift = pow(1.059463094359, (60 - midiEvent.buffer[1]));
                set_position(pPlayer->handle, 0);
                start_playback(pPlayer->handle);
                pPlayer->last_note_played = midiEvent.buffer[1];
        } else if(cmd == 0xB0) {
            // CC
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
    DPRINTF("libzynaudioplayer: Jack sample rate: %u\n", nFrames);
    g_samplerate = nFrames;
    return 0;
}
 
static void lib_init(void) { 
    // Initialise OSC clients
    g_oscfd = socket(AF_INET, SOCK_DGRAM, 0);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        memset(g_oscClient[i].sin_zero, '\0', sizeof g_oscClient[i].sin_zero);
        g_oscClient[i].sin_family = AF_INET;
        g_oscClient[i].sin_port = htons(OSC_PORT);
        g_oscClient[i].sin_addr.s_addr = 0;
    }
    fcntl(g_oscfd, F_SETFL, O_NONBLOCK); // set the socket to non-blocking

    // Initialise OSC server
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);
    if(pthread_create(&g_osc_thread, &attr, osc_thread_fn, NULL))
        fprintf(stderr, "libzynaudioplayer error: failed to create OSC listening thread\n");

    printf("libzynaudioplayer initialised\n");
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
    pPlayer->filename[0] = '\0';
    pPlayer->gain = 1.0;
    pPlayer->playback_track = 0;
    pPlayer->handle = player_handle;
    pPlayer->buffer_size = 48000;
    pPlayer->buffer_count = 5;
    pPlayer->frames = 0;
    pPlayer->last_note_played = 0;

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

unsigned int get_src_quality(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer)
        return pPlayer->src_quality;
    return 2;
}

void set_gain(int player_handle, float gain) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer == NULL)
        return;
    if(gain < 0 || gain > 2)
        return;
    pPlayer->gain = gain;
    sprintf(g_oscpath, "/player%d/gain", player_handle);
    sendOscFloat(g_oscpath, gain);
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
    if(pPlayer->file_open == 2 && track < pPlayer->sf_info.channels) {
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

void set_buffer_size(int player_handle, unsigned int size) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->file_open == 0)
        pPlayer->buffer_size = size;
}

unsigned int get_buffer_size(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer)
        return pPlayer->buffer_size;
    return 0;
}

void set_buffer_count(int player_handle, unsigned int count) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->file_open == 0 && count > 1)
        pPlayer->buffer_count = count;
}

unsigned int get_buffer_count(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer)
        return pPlayer->buffer_count;
    return 0;
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
