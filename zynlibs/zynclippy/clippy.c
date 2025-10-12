/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: zynclippy Library
 *
 * Library providing sample clip launcher as a Jack connected device
 *
 * Copyright (C) 2025 Brian Walton <brian@riban.co.uk>
 *
 * ******************************************************************
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * For a full copy of the GNU General Public License see the LICENSE.txt file.
 *
 * ******************************************************************
 */

//#include <stdio.h>
#include <unistd.h> // provides usleep
#include <string.h> // provides memset, memcpy, strcpy
#include <jack/jack.h> // provides jack API
#include <jack/midiport.h> // provides jack midi port API
#include <jack/ringbuffer.h> //provides jack ring buffer
#include <sndfile.h>   //provides sound file manipulation
#include <samplerate.h> //provides samplerate conversion
#include <pthread.h> //provides threading

#define PRELOAD 2048 // Size of preload buffers in frames
#define RINGBUFFER PRELOAD * 2 // Size of ring buffers in frames
#define MAX_CLIPS 32 // Maximum quantity of clips per player/channel

enum STATE {
    STATE_IDLE, // Not ready for use
    STATE_LOAD, // Load new file into preload cache
    STATE_RESET, // Reset clip buffers to start of clip
    STATE_READY, // Cached, ready for use
    STATE_STARTING, // Switch sndfile
    STATE_PLAYING // Buffer in use for playback (may be from preload or ring buffer)
};

// Forward declarations
uint8_t unload(uint8_t player_id, uint32_t id);
uint8_t load(uint8_t channel, uint32_t id, const char* path);
uint8_t addPlayer(uint8_t channel);
uint32_t removePlayer(uint8_t channel);
void setGain(uint8_t channel, uint32_t clip, float gain);
float getGain(uint8_t channel, uint32_t clip);

// Global variables
jack_nframes_t samplerate = 48000;
jack_nframes_t buffersize = 1024;
static jack_port_t* midi_input_port;
static jack_client_t* jack_client;
static volatile uint8_t running = 1;
static volatile uint8_t mutex = 0;
pthread_t file_thread; // ID of file loader thread

enum MIDI_COMMANDS {
    MIDI_NOTE_OFF   = 0x80,
    MIDI_NOTE_ON    = 0x90,
    MIDI_CC         = 0xb0,
    MIDI_POLYTOUCH  = 0xa0,
    MIDI_PROGRAM    = 0xc0,
    MIDI_AFTERTOUCH = 0xd0,
    MIDI_PITCHBEND  = 0xe0
};

typedef struct {
    uint8_t state; // Clip status: IDLE, LOAD, READY
    uint32_t frames; // Quantity of frames in loaded clip
    uint8_t channels; // Quantity of channels in clip
    float gain; // Gain factor
    char path[256]; // Loaded file path and filename
    float preload_buffer_a[PRELOAD]; // Buffer holds start of sample
    float preload_buffer_b[PRELOAD]; // Buffer holds start of sample
} Clip;

typedef struct {
    uint8_t clip; // Index of last played clip
    uint8_t state; // Play state
    uint32_t preload_pos; // Playback position within preload buffer
    uint32_t play_pos; // Position of playhead in frames
    jack_ringbuffer_t* ringbuffer_a; // Ring buffers to pass left data between threads (L/R in each buffer)
    jack_ringbuffer_t* ringbuffer_b; // Ring buffers to pass right data between threads (L/R in each buffer)
    jack_port_t* output_a; // Left jack output port
    jack_port_t* output_b; // Right jack output port
    SNDFILE* sndfile; // Pointer to an open sndfile used to read current clip data
    Clip* clips[MAX_CLIPS]; // Array of clips
} Player;

Player* players[16]; // Up to 16 players, 1 per MIDI channel

static void inline getMutex() {
    while (mutex)
        usleep(100);
    mutex = 1;
}

static void inline releaseMutex() {
    mutex = 0;
}

// Background file and buffer management
void* file_thread_fn(void* param) {
    //!@todo ***SRC***
    Player* player;
    Clip* clip;
    SNDFILE* sndfile; // Used to refresh preload buffers
    struct SF_INFO info;
    float a, b;

    while (running) {
        for (uint8_t channel = 0; channel < 16; ++channel) {
            player = players[channel];
            if (!player)
                continue;
            // Update clips
            for (uint32_t id = 0; id < MAX_CLIPS; ++id) {
                //!@todo Optimise - event driven rather than round-robin all clips
                clip = player->clips[id];
                if (clip) {
                    if (clip->state== STATE_LOAD) {
                        // Load data from file to preload cache
                        sndfile = sf_open(clip->path, SFM_READ, &info);
                        if (info.samplerate != samplerate)
                            fprintf(stderr, "Mismatched samplerate: %u/%u\n", info.samplerate, samplerate);
                        if (sndfile && info.channels && info.frames) {
                            clip->channels = info.channels;
                            clip->frames = info.frames;
                            float buffer[PRELOAD * info.channels * sizeof(float)];
                            sf_count_t frames = sf_readf_float(sndfile, buffer, PRELOAD);
                            int stereo = info.channels > 1 ? 1 : 0;
                            if (id == player->clip)
                                getMutex();
                            for (uint32_t i = 0; i < PRELOAD; ++i) {
                                if (i < frames) {
                                    clip->preload_buffer_a[i] = buffer[i * info.channels];
                                    clip->preload_buffer_b[i] = buffer[i * info.channels + stereo];
                                } else {
                                    // Silence remaining frames
                                    clip->preload_buffer_a[i] = 0.0f;
                                    clip->preload_buffer_b[i] = 0.0f;
                                }
                            }
                            clip->state = STATE_READY;
                            jack_ringbuffer_reset(player->ringbuffer_a);
                            jack_ringbuffer_reset(player->ringbuffer_b);
                            if (id == player->clip) {
                                player->state = STATE_LOAD;
                                releaseMutex();
                            }
                            sf_close(sndfile);
                        } else {
                            if (id == player->clip)
                                getMutex();
                            clip->state = STATE_IDLE;
                            player->state = STATE_IDLE;
                            if (id == player->clip)
                                releaseMutex();
                        }
                    } else if (clip->state == STATE_RESET) {
                        // Reset clip to start
                        sf_seek(player->sndfile, PRELOAD, SEEK_SET);
                        clip->state = STATE_READY;
                    }
                }
            }

            // Update currently playing sample
            clip = player->clips[player->clip];
            if (!clip)
                continue;
            if (player->state == STATE_STARTING) {
                //!@todo Check if same file already open
                sf_close(player->sndfile);
                player->sndfile = sf_open(clip->path, SFM_READ, &info);
                if (player->sndfile) {
                    sf_seek(player->sndfile, PRELOAD, SEEK_SET);
                    getMutex();
                    player->state = STATE_PLAYING;
                    jack_ringbuffer_reset(player->ringbuffer_a);
                    jack_ringbuffer_reset(player->ringbuffer_b);
                }
                else {
                    getMutex();
                    player->state = STATE_IDLE;
                }
                releaseMutex();
            }
            if (player->state == STATE_PLAYING) {
                // Load data from file to ring buffer
                size_t write_space = jack_ringbuffer_write_space(player->ringbuffer_a); // Assume a & b are the same
                if (write_space) {
                    int free_frames = write_space / sizeof(float);
                    float buffer[free_frames * clip->channels];
                    int frames = sf_readf_float(player->sndfile, buffer, free_frames);
                    int stereo = clip->channels > 1 ? 1 : 0;
                    for (uint32_t i = 0; i < free_frames; ++i) {
                        if (i < frames) {
                            a = buffer[i * clip->channels];
                            b = buffer[i * clip->channels + stereo];
                        } else {
                            a = b = 0.0f; // Silence remaining frames
                        }
                        jack_ringbuffer_write(player->ringbuffer_a, (const char*)(&a), sizeof(float));
                        jack_ringbuffer_write(player->ringbuffer_b, (const char*)(&b), sizeof(float));
                    }
                }
            }
        }
        usleep(100);
    }
    pthread_exit(NULL);
}

static int process(jack_nframes_t frames, __attribute__((unused)) void* arg) {
    static Player* player;
    static Clip* clip;
    float* output_a[16];
    float* output_b[16];

    while (mutex)
        usleep(10);
    mutex = 1;

    // Populate player audio output buffers from ring buffers
    for (uint8_t player_id = 0; player_id < 16; ++player_id) {
        player = players[player_id];
        if (player) {
            output_a[player_id] = jack_port_get_buffer(player->output_a, frames);
            output_b[player_id] = jack_port_get_buffer(player->output_b, frames);
            memset(output_a[player_id], 0, frames * sizeof(float));
            memset(output_b[player_id], 0, frames * sizeof(float));
            if (player->state == STATE_PLAYING || player->state == STATE_STARTING) {
                // Play remaining prebuffer
                int frame_count = 0;
                if (player->play_pos < PRELOAD) {
                    frame_count = PRELOAD - player->play_pos;
                    if (frame_count >= frames)
                        frame_count = frames;
                    int count = frame_count * sizeof(float);
                    memcpy(output_a[player_id], clip->preload_buffer_a + player->play_pos, count);
                    memcpy(output_b[player_id], clip->preload_buffer_b + player->play_pos, count);
                    player->play_pos += frame_count;
                }
                // Stream from ringbuffer
                if (frame_count < frames) {
                    int count = (frames - frame_count) * sizeof(float);
                    count = jack_ringbuffer_read(player->ringbuffer_a, (char*)(output_a[player_id]), count);
                    jack_ringbuffer_read(player->ringbuffer_b, (char*)(output_b[player_id]), count);
                    player->play_pos += count / sizeof(float);
                }
            }
            clip = player->clips[player->clip];
            if (clip && player->play_pos >= clip->frames)
                player->state = STATE_RESET;
        } else {
            output_a[player_id] = NULL;
            output_b[player_id] = NULL;
        }
    }

    void* midi_buffer = jack_port_get_buffer(midi_input_port, frames);
    jack_nframes_t numMidiEvents = jack_midi_get_event_count(midi_buffer);
    jack_midi_event_t event;


    // Received MIDI messages
    for (uint32_t i = 0; i < numMidiEvents; ++i) {
        if (jack_midi_event_get(&event, midi_buffer, i) != 0)
            continue;

        if (event.size == 0)
            continue;

        switch (event.buffer[0] & 0xf0) {
        case MIDI_NOTE_ON:
            if (event.buffer[2] != 0) {
                // Note on triggers playback from preload buffer
                uint8_t player_id = event.buffer[0] & 0x0f;
                player = players[player_id];
                if (!player)
                    break;
                if (!player)
                    break;
                if (event.buffer[1] == 0) {
                    if (player->state == STATE_PLAYING)
                        player->state = STATE_RESET;
                } else {
                    // Start playing clip from preload buffer
                    player->clip = event.buffer[1] - 1;
                    clip = player->clips[player->clip];
                    if (!clip || clip->state != STATE_READY)
                        break;
                    // Start audio at frame offset of MIDI event
                    size_t start = event.time * sizeof(float);
                    uint32_t frame_count = frames - event.time;
                    size_t count = frame_count * sizeof(float);
                    memcpy(output_a[player_id] + start, clip->preload_buffer_a, count);
                    memcpy(output_b[player_id] + start, clip->preload_buffer_b, count);
                    player->play_pos = frame_count;
                    //!@todo Crossfade
                    player->state = STATE_STARTING;
                    break;
                }
            }
            [[fallthrough]];
        case MIDI_NOTE_OFF:
            // Not handling note-off
            break;
        case MIDI_CC:
            setGain(event.buffer[0] & 0x0f, event.buffer[1], (float)(event.buffer[2]) / 64);
            break;
        }
    }

    // Adjust volume
    for (uint8_t player_id = 0; player_id < 16; ++player_id) {
        player = players[player_id];
        if (!player)
            continue;
        clip = player->clips[player->clip];
        if (!clip)
            continue;
        for (uint32_t i = 0; i < frames; ++i) {
            output_a[player_id][i] *= clip->gain;
            output_b[player_id][i] *= clip->gain;
        }
    }

    mutex = 0;
    return 0;
}

void reset() {
    getMutex();
    for (uint8_t channel = 0; channel < 16; ++channel) {
        Player* player = players[channel];
        if (!player)
            continue;
        player->state=STATE_LOAD;
        for (uint32_t id = 0; id < MAX_CLIPS; ++id) {
            Clip* clip = player->clips[id];
            if (!clip)
                continue;
            clip->state = STATE_LOAD;
        }
    }
    releaseMutex();
}

static int onBufferSize(jack_nframes_t frames, __attribute__((unused)) void* arg)
{
    buffersize = frames;
    reset();
    return 0;
}

static int onSamplerate(jack_nframes_t frames, __attribute__((unused)) void* arg)
{
    samplerate = frames;
    reset();
    return 0;
}

void end() {
    running = 0;
    void* status;
    pthread_join(file_thread, &status);

    for (uint8_t i = 0; i < 16; ++i)
        removePlayer(i);
    if (jack_client)
        jack_client_close(jack_client);
    fprintf(stderr, "libclippy ended\n");
}

int init() {
    // Register the cleanup function to be called when library exits
    atexit(end);

    // Initialise players
    for (uint8_t i = 0; i < 16; ++i)
        players[i] = NULL;

    // Configure and start event thread
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);
    if (pthread_create(&file_thread, &attr, file_thread_fn, NULL)) {
        fprintf(stderr, "Clippy error: failed to create file reader thread\n");
        return 1;
    }

    // Create jack client
    jack_status_t status;
    jack_client = jack_client_open("clippy", JackNullOption, &status);
    if (jack_client == NULL) {
        fprintf(stderr, "Could not open JACK client\n");
        return 1;
    }

    if (status & JackNameNotUnique) {
        fprintf(stderr, "Name was taken: assigned %s instead\n", jack_get_client_name(jack_client));
    }
    if (status & JackServerStarted) {
        fprintf(stderr, "Connected to JACK\n");
    }

    jack_set_sample_rate_callback(jack_client, onSamplerate, NULL);
    jack_set_buffer_size_callback(jack_client, onBufferSize, NULL);
    jack_set_process_callback(jack_client, process, NULL);

    midi_input_port = jack_port_register(jack_client, "input", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
    if (midi_input_port == NULL) {
        fprintf(stderr, "Could not open MIDI input port\n");
        return 1;
    }

    if (jack_activate(jack_client) != 0) {
        fprintf(stderr, "Could not activate client\n");
        return 1;
    }
    fprintf(stderr, "libclippy started\n");
}

/** @brief  Create a new clip player
    @brief  channel MIDI channel for new player
    @retval uint8_t Error code [0=success, 1=out of range, 2=cannot create player, 3=cannot create jack ports]
*/
uint8_t addPlayer(uint8_t channel) {
    if (channel >= 16)
        return 1;
    if (players[channel])
        return 0;
    Player* player = malloc(sizeof(Player));
    if (!player)
        return 2;

    memset(player, 0, sizeof(Player));
    char name[16];
    sprintf(name, "output_%02ua", channel + 1);
    player->output_a = jack_port_register(jack_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    sprintf(name, "output_%02ub", channel + 1);
    player->output_b = jack_port_register(jack_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (player->output_a == NULL || player->output_b == NULL)
        fprintf(stderr, "Clippy error: failed to create jack output ports\n");
    for (uint32_t id = 0; id < MAX_CLIPS; ++id)
        player->clips[id] = NULL;
    player->ringbuffer_a = jack_ringbuffer_create(RINGBUFFER * sizeof(float));
    player->ringbuffer_b = jack_ringbuffer_create(RINGBUFFER * sizeof(float));
    jack_ringbuffer_mlock(player->ringbuffer_a);
    jack_ringbuffer_mlock(player->ringbuffer_b);
    getMutex();
    players[channel] = player;
    releaseMutex();
    return 0;
}

/** @brief  Remove a clip player
    @param  channel MIDI channel
    @retval uint8_t Error code [0=success, 1=out of range]
*/
uint32_t removePlayer(uint8_t channel) {
    if(channel >= 16)
        return 1;
    Player* player = players[channel];
    if(player == NULL)
        return 0;
    getMutex();
    players[channel] = NULL;
    releaseMutex();
    
    for (uint32_t id = 0; id < MAX_CLIPS; ++id)
        free(player->clips[id]);
    jack_ringbuffer_free(player->ringbuffer_a);
    jack_ringbuffer_free(player->ringbuffer_b);

    jack_port_unregister(jack_client, player->output_a);
    jack_port_unregister(jack_client, player->output_b);
    free(player);
    return 0;
}

/** @brief  Load a file into a player
    @param  channel MIDI channel
    @param  id Clip id [0..MAX_CLIPS]
    @param  path Full (or relative) path and filename
    @retval uint8_t Error code: [0:OK 1:Play not exist 2:Invalid channel 3:Failed to create clip object]
*/
uint8_t load(uint8_t channel, uint32_t id, const char* path) {
    if(channel >= 16)
        return 2;
    if(id >= MAX_CLIPS)
        return 4;
    Player* player = players[channel];
    if (!player)
        return 1;

    // Create a new clip instance and configure
    Clip* clip = malloc(sizeof(Clip));
    if (!clip) {
        fprintf(stderr, "Clippy error: failed to create new clip object\n");
        return 3;
    }
    memset(clip, 0, sizeof(Clip));
    clip->gain = 1.0f;
    strcpy(clip->path, path);
    clip->state = STATE_LOAD;

    unload(channel, id);
    getMutex();
    player->clips[id] = clip;
    releaseMutex();
    return 0;
}

uint8_t unload(uint8_t channel, uint32_t id) {
    if(channel >= 16)
        return 2;
    Player* player = players[channel];
    if(player == NULL)
        return 1;
    if(id >= MAX_CLIPS)
        return 4;
    Clip* clip = player->clips[id];
    if(clip == NULL)
        return 3;

    if (player->clip == id) {
        getMutex();
        player->state = STATE_IDLE;
        releaseMutex();
    }
    player->clips[id] = NULL;
    free(clip);
    return 0;
}

void setGain(uint8_t channel, uint32_t clip, float gain) {
    if (channel < 16 && players[channel] && players[channel]->clips[players[channel]->clip])
        players[channel]->clips[players[channel]->clip]->gain = gain;
}

float getGain(uint8_t channel, uint32_t clip) {
    if (channel < 16 && players[channel] && players[channel]->clips[players[channel]->clip])
        return players[channel]->clips[players[channel]->clip]->gain;
    return 0.0f;
}