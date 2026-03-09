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

#include "clippy.h"
#include <unistd.h> // provides usleep
#include <string.h> // provides memset, memcpy, strcpy
#include <jack/jack.h> // provides jack API
#include <jack/midiport.h> // provides jack midi port API
#include <jack/ringbuffer.h> //provides jack ring buffer
#include <sndfile.h>   // provides sound file manipulation
#include <samplerate.h> // provides samplerate convertor
#include <rubberband/rubberband-c.h> // provides time stretch
#include <pthread.h> // provides threading
#include <math.h> // provides pow for dB calcs

typedef struct {
    uint8_t state; // Clip state
    uint32_t frames; // Quantity of frames in loaded clip
    uint8_t channels; // Quantity of channels in clip
    float gain; // Gain factor
    char path[256]; // Loaded file path and filename
    float preload_buffer_a[PRELOAD_FRAMES]; // Buffer holds start of sample
    float preload_buffer_b[PRELOAD_FRAMES]; // Buffer holds start of sample
} Clip;

typedef struct {
    uint8_t state; // Play state
    uint32_t play_pos; // Position of playhead in frames
    jack_ringbuffer_t* ringbuffer_a; // Ring buffers to pass left data between threads (L/R in each buffer)
    jack_ringbuffer_t* ringbuffer_b; // Ring buffers to pass right data between threads (L/R in each buffer)
    jack_port_t* jack_out_a; // Left jack output port
    jack_port_t* jack_out_b; // Right jack output port
    SNDFILE* sndfile; // Pointer to an open sndfile used to read current clip data
    Clip* current_clip; // Pointer to the currently selected / playing clip
    Clip* clips[MAX_CLIPS]; // Array of pointers to clip objects
} Player;

typedef union {
    uint32_t u32;
    struct {
        uint8_t value2;
        uint8_t value1;
        uint8_t command;
        uint8_t unused;
    };
} MidiMsg;

// Global variables
jack_nframes_t samplerate = 48000;
jack_nframes_t buffersize = 1024;
static jack_port_t* midi_input_port;
static jack_client_t* jack_client;
static volatile uint8_t running = 1;
static volatile uint8_t mutex = 0;
pthread_t file_thread; // ID of file loader thread

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
    Player* player;
    SNDFILE* sndfile; // Used to refresh preload buffers
    struct SF_INFO info;
    float a, b;
    size_t write_space_a, write_space_b, write_space;

    while (running) {
        for (uint8_t channel = 0; channel < 16; ++channel) {
            player = players[channel];
            if (!player || !player->current_clip)
                continue;
            if (player->state == STATE_STARTING) {
                //!@todo Check if same file already open
                sf_close(player->sndfile);
                player->sndfile = sf_open(player->current_clip->path, SFM_READ, &info);
                if (player->sndfile) {
                    sf_seek(player->sndfile, PRELOAD_FRAMES, SEEK_SET);
                    getMutex();
                    jack_ringbuffer_reset(player->ringbuffer_a);
                    jack_ringbuffer_reset(player->ringbuffer_b);
                    player->state = STATE_PLAYING;
                } else {
                    getMutex();
                    player->state = STATE_IDLE;
                }
                releaseMutex();
            }
            if (player->state == STATE_PLAYING) {
                // Load data from file to ring buffer
                size_t write_space_a = jack_ringbuffer_write_space(player->ringbuffer_a);
                size_t write_space_b = jack_ringbuffer_write_space(player->ringbuffer_b);
                write_space = (write_space_a < write_space_b) ? write_space_a : write_space_b;
                if (write_space > 127) {
                    int free_frames = write_space / sizeof(float);
                    float buffer[free_frames * player->current_clip->channels];
                    int frames = sf_readf_float(player->sndfile, buffer, free_frames);
                    int stereo = player->current_clip->channels > 1 ? 1 : 0;
                    for (uint32_t i = 0; i < free_frames; ++i) {
                        if (i < frames) {
                            a = buffer[i * player->current_clip->channels];
                            b = buffer[i * player->current_clip->channels + stereo];
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
    static char buffer[1048];
    static Player* player;
    float* out_buff_a[16];
    float* out_buff_b[16];

    while (mutex)
        usleep(10);
    mutex = 1;

    // Populate player audio output buffers from preload/ring buffers
    for (uint8_t channel = 0; channel < 16; ++channel) {
        player = players[channel];
        if (player) {
            out_buff_a[channel] = jack_port_get_buffer(player->jack_out_a, frames);
            out_buff_b[channel] = jack_port_get_buffer(player->jack_out_b, frames);
            memset(out_buff_a[channel], 0, frames * sizeof(float));
            memset(out_buff_b[channel], 0, frames * sizeof(float));
            if (player->state == STATE_STARTING || player->state == STATE_PLAYING) {
                if (!player->current_clip)
                    continue;
                int frame_count = 0;
                if (player->play_pos < PRELOAD_FRAMES) {
                    // Play remaining prebuffer
                    frame_count = PRELOAD_FRAMES - player->play_pos;
                    if (frame_count > frames)
                        frame_count = frames;
                    size_t count = frame_count * sizeof(float);
                    memcpy(out_buff_a[channel], player->current_clip->preload_buffer_a + player->play_pos, count);
                    memcpy(out_buff_b[channel], player->current_clip->preload_buffer_b + player->play_pos, count);
                    player->play_pos += frame_count;
                }

                // Stream from ringbuffer
                if (frame_count < frames) {
                    size_t count = (frames - frame_count) * sizeof(float);
                    count = jack_ringbuffer_read(player->ringbuffer_a, (char*)(out_buff_a[channel]), count);
                    if (count % sizeof(float))
                        fprintf(stderr, "Error reading ringbuffer_a: %u\n", count);
                    count = jack_ringbuffer_read(player->ringbuffer_b, (char*)(out_buff_b[channel]), count);
                    if (count % sizeof(float))
                        fprintf(stderr, "Error reading ringbuffer_b: %u\n", count);
                    player->play_pos += count / sizeof(float);
                }
                if (player->play_pos >= player->current_clip->frames) {
                    // Reached end of clip
                    player->state = STATE_STOPPING;
                }
            }
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
                uint8_t channel = event.buffer[0] & 0x0f;
                player = players[channel];
                if (!player)
                    break;
                if (event.buffer[1] == 0) {
                    // Note 0 stops playback
                    if (player->state == STATE_PLAYING || player->state == STATE_STARTING) {
                        player->state = STATE_STOPPING;
                    }
                } else {
                    // Start playing clip from preload buffer
                    player->current_clip = player->clips[event.buffer[1] - 1];
                    if (!player->current_clip || player->current_clip->state != STATE_READY)
                        break;
                    // Start audio at frame offset of MIDI event
                    size_t start = event.time * sizeof(float);
                    uint32_t frame_count = frames - event.time;
                    size_t count = frame_count * sizeof(float);
                    memcpy(out_buff_a[channel] + start, player->current_clip->preload_buffer_a, count);
                    memcpy(out_buff_b[channel] + start, player->current_clip->preload_buffer_b, count);
                    player->play_pos = frame_count;
                    //!@todo Crossfade
                    player->state = STATE_STARTING;
                }
                break;
            }
            [[fallthrough]];
        case MIDI_NOTE_OFF:
            // Not handling note-off
            break;
        case MIDI_CC:
            //setGain(event.buffer[0] & 0x0f, event.buffer[1], (float)(event.buffer[2]) / 64);
            break;
        }
    }

    // Adjust volume
    float dGain;
    for (uint8_t channel = 0; channel < 16; ++channel) {
        player = players[channel];
        if (!player || !player->current_clip)
            continue;
        if (player->state == STATE_STOPPING) {
            dGain = player->current_clip->gain / frames; // Soft fade
            player->state = STATE_READY;
            player->play_pos = 0;
        } else if (player->state == STATE_STARTING || player->state == STATE_PLAYING) {
            dGain = 0.0f;
        } else {
            continue;
        }
        for (uint32_t i = 0; i < frames; ++i) {
            out_buff_a[channel][i] *= (player->current_clip->gain - i * dGain);
            out_buff_b[channel][i] *= (player->current_clip->gain - i * dGain);
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
            if (clip)
                loadClip(channel, id, clip->path);
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
    jack_client = NULL;
}

/** @brief  Initialise the library
    @param  jackname Requested jack client name
    @retval int Error code
*/
int init() {
    int error = ERROR_SUCCESS;
    if (jack_client)
        return ERROR_EXISTS;
    // Register the cleanup function to be called when library exits
    atexit(end);

    // Initialise players
    for (uint8_t i = 0; i < 16; ++i)
        players[i] = NULL;

    // Configure and start event thread
    running = 1;
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);
    if (pthread_create(&file_thread, &attr, file_thread_fn, NULL)) {
        fprintf(stderr, "Clippy error: failed to create file reader thread\n");
        return ERROR_CREATE;
    }

    // Create jack client
    jack_status_t status;
    jack_client = jack_client_open("clippy", JackNullOption, &status);
    if (jack_client == NULL) {
        fprintf(stderr, "Could not open JACK client\n");
        end();
        return ERROR_CREATE;
    }

    midi_input_port = jack_port_register(jack_client, "in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
    if (midi_input_port == NULL) {
        fprintf(stderr, "Could not open MIDI input port\n");
        end();
        return ERROR_PORT;
    }

    jack_set_sample_rate_callback(jack_client, onSamplerate, NULL);
    jack_set_buffer_size_callback(jack_client, onBufferSize, NULL);
    jack_set_process_callback(jack_client, process, NULL);

    if (jack_activate(jack_client) != 0) {
        fprintf(stderr, "Could not activate client\n");
        end();
        return ERROR_ACTIVATE;
    }
    return ERROR_SUCCESS;
}

/** @brief  Get the jack client name
    @retval const char* Jack name
*/
const char* getJackname() {
    return jack_get_client_name(jack_client);
}

uint8_t addPlayer(uint8_t channel) {
    if (channel >= 16) {
        for (channel = 0; channel < 16; ++channel) {
            if (players[channel] == NULL)
                break;
        }
    }
    if (channel > 16)
        return 255;
    Player* player = malloc(sizeof(Player));
    if (!player)
        return ERROR_CREATE;

    memset(player, 0, sizeof(Player));
    char name[16];
    sprintf(name, "out_%02ua", channel + 1);
    player->jack_out_a = jack_port_register(jack_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    sprintf(name, "out_%02ub", channel + 1);
    player->jack_out_b = jack_port_register(jack_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (player->jack_out_a == NULL || player->jack_out_b == NULL)
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
    return channel;
}

uint32_t removePlayer(uint8_t channel) {
    if(channel >= 16)
        return ERROR_RANGE;
    Player* player = players[channel];
    if(player == NULL)
        return ERROR_CREATE;
    getMutex();
    players[channel] = NULL;
    releaseMutex();

    for (uint32_t id = 0; id < MAX_CLIPS; ++id)
        free(player->clips[id]);
    jack_ringbuffer_free(player->ringbuffer_a);
    jack_ringbuffer_free(player->ringbuffer_b);

    jack_port_unregister(jack_client, player->jack_out_a);
    jack_port_unregister(jack_client, player->jack_out_b);
    free(player);
    return ERROR_SUCCESS;
}

uint8_t swapClip(uint8_t channel, uint8_t clip1, uint8_t clip2) {
    if (clip1 >= MAX_CLIPS || clip2 >= MAX_CLIPS || channel > 15)
        return ERROR_RANGE;
    Player* pPlayer = players[channel];
    if (!pPlayer)
        return ERROR_RANGE;
    Clip* pClip1 = pPlayer->clips[clip1];
    Clip* pClip2 = pPlayer->clips[clip2];
    getMutex(); //!@todo Check this won't leave stuck notes
    pPlayer->clips[clip1] = pClip2;
    pPlayer->clips[clip2] = pClip1;
    releaseMutex();
    return ERROR_SUCCESS;
}

uint8_t insertClip(uint8_t channel, uint8_t clip) {
    if (channel > 15 || clip >= MAX_CLIPS)
        return ERROR_RANGE;
    Player* pPlayer = players[channel];
    if (!pPlayer)
        return ERROR_RANGE;
    if (pPlayer->clips[MAX_CLIPS - 1])
        return ERROR_EXISTS;
    for (uint8_t i = MAX_CLIPS - 1; i > clip ; --i) {
        pPlayer->clips[i] = pPlayer->clips[i - 1];
    }
    pPlayer->clips[clip] = NULL;
    return ERROR_SUCCESS;
}

uint8_t removeClip(uint8_t channel, uint8_t clip) {
    if (channel > 15 || clip >= MAX_CLIPS)
        return ERROR_RANGE;
    Player* pPlayer = players[channel];
    if (!pPlayer)
        return ERROR_RANGE;
    unloadClip(channel, clip + 1);
    for (uint8_t i = clip; i < MAX_CLIPS - 1; ++i) {
        pPlayer->clips[i] = pPlayer->clips[i + 1];
    }
    pPlayer->clips[MAX_CLIPS - 1] = NULL;
    return ERROR_SUCCESS;
}

uint8_t getFreeClip(uint8_t channel) {
    if(channel >= 16)
        return 0;
    Player* player = players[channel];
    if (!player)
        return 0;
    for (uint8_t id = 0; id < MAX_CLIPS; ++id) {
        if (player->clips[id] == NULL)
            return id + 1;
    }
    return 0;
}

uint8_t loadClip(uint8_t channel, uint8_t note, const char* path) {
    if(channel >= 16 || note >= MAX_CLIPS)
        return 0;
    Player* player = players[channel];
    if (!player)
        return 0;

    if (note == 0) {
        // Find next available note
        for (note = 0; note < 128; ++ note) {
            if (!player->clips[note])
                break;
        }
        if (++note > 127)
            return 0;
    }
    uint8_t id = note - 1;

    // Load data from file to preload cache
    struct SF_INFO info;
    SNDFILE* sndfile = sf_open(path, SFM_READ, &info);
    Clip* clip = NULL;

    if (sndfile && info.channels && info.frames) {
        if (info.samplerate != samplerate) {
            fprintf(stderr, "File samplerate: %u is not system samplerate %u\n", info.samplerate, samplerate);
            sf_close(sndfile);
            return 0;
        }
        // Create a new clip instance and configure
        clip = malloc(sizeof(Clip));
        if (!clip) {
            fprintf(stderr, "Clippy error: failed to create new clip object\n");
            sf_close(sndfile);
            return 0;
        }

        memset(clip, 0, sizeof(Clip));
        clip->gain = 1.0f;
        strcpy(clip->path, path);
        clip->channels = info.channels;
        clip->frames = info.frames;
        float buffer[PRELOAD_FRAMES * info.channels * sizeof(float)];
        sf_count_t frames = sf_readf_float(sndfile, buffer, PRELOAD_FRAMES);
        int stereo = info.channels > 1 ? 1 : 0;
        for (uint32_t i = 0; i < PRELOAD_FRAMES; ++i) {
            if (i < frames) {
                clip->preload_buffer_a[i] = buffer[i * info.channels];
                clip->preload_buffer_b[i] = buffer[i * info.channels + stereo];
            } else {
                // Silence remaining frames
                clip->preload_buffer_a[i] = 0.0f;
                clip->preload_buffer_b[i] = 0.0f;
            }
        }
        jack_ringbuffer_reset(player->ringbuffer_a);
        jack_ringbuffer_reset(player->ringbuffer_b);
        clip->state = STATE_READY;
        sf_close(sndfile);
    } else {
        sf_close(sndfile);
        return 0;
    }
    if (player->current_clip == player->clips[id] && (player->state == STATE_STARTING || player->state == STATE_PLAYING)) {
        unloadClip(channel, note);
        player->state == STATE_STARTING
        player->clips[id] = clip;
        player->current_clip = clip;
    } else {
        unloadClip(channel, note);
        player->clips[id] = clip;
    }
    //fprintf(stderr, "clippy loadClip(channel=%u, note=%u, path=%s) id=%u\n", channel, note, path, id);
    return note;
}

uint8_t unloadClip(uint8_t channel, uint8_t note) {
    if(channel >= 16)
        return ERROR_RANGE;
    Player* player = players[channel];
    if(player == NULL)
        return ERROR_RANGE;
    uint8_t id = note - 1;
    if(id >= MAX_CLIPS)
        return ERROR_RANGE;
    Clip* clip = player->clips[id];
    if(clip == NULL)
        return ERROR_RANGE;

    if (player->current_clip == player->clips[id]) {
        getMutex();
        player->state = STATE_IDLE;
        releaseMutex();
    }
    player->clips[id] = NULL;
    free(clip);
    return ERROR_SUCCESS;
}

float toDb(float val) {
    return 20.0 * log10(val);
}

float fromDb(float val) {
    return pow(10.0, val / 20.0);
}

uint8_t setGain(uint8_t channel, uint8_t id, float gain) {
    if (channel > 15)
        return ERROR_RANGE;
    Player* player = players[channel];
    if (!player)
        return ERROR_RANGE;
    if (id >= MAX_CLIPS)
        return ERROR_RANGE;
    Clip* clip = player->clips[id];
    if (!clip)
        return ERROR_RANGE;
    clip->gain = fromDb(gain);
    return ERROR_SUCCESS;
}

float getGain(uint8_t channel, uint8_t id) {
    if (channel > 15)
        return 0.0f;
    Player* player = players[channel];
    if (!player)
        return 0.0f;
    if (id >= MAX_CLIPS)
        return 0.0f;
    Clip* clip = player->clips[id];
    if (!clip)
        return 0.0f;
    return toDb(clip->gain);
}

uint32_t getFileSamplerate(const char* path) {
    SF_INFO sf_info;
    memset(&sf_info, 0, sizeof(sf_info));
    SNDFILE* sndfile = sf_open(path, SFM_READ, &sf_info);
    if (!sndfile)
        return 0;
    sf_close(sndfile);
    return sf_info.samplerate;
}

uint32_t getFileFrames(const char* path) {
    SF_INFO sf_info;
    memset(&sf_info, 0, sizeof(sf_info));
    SNDFILE* sndfile = sf_open(path, SFM_READ, &sf_info);
    if (!sndfile)
        return 0;
    sf_close(sndfile);
    return sf_info.frames;
}

int copyFile(const char* src_path, const char* dst_path, uint8_t quality, float ratio, uint32_t start, uint32_t end) {
    uint8_t error = 0;
    if (ratio < 0.001 || ratio > 1000)
        ratio = 1.0; // Default to no stretch if excessive stretch requested.
    if (quality > 4)
        return ERROR_RANGE;

    // Read source file into interleaved float buffer data_in
    SF_INFO sf_info;
    memset(&sf_info, 0, sizeof(sf_info));
    SNDFILE* sndfile = sf_open(src_path, SFM_READ, &sf_info);
    if (!sndfile || sf_info.samplerate < 10 || sf_info.channels < 1 || sf_info.frames < 10)
        return ERROR_OPEN;
    int channels = sf_info.channels;
    sf_count_t frames = sf_info.frames;
    int dur = end - start;
    if (dur < frames && dur > 0)
        frames = dur;
    uint8_t src = samplerate != sf_info.samplerate;

    size_t size = frames * sf_info.channels * sizeof(float);
    if (size == 0) {
        sf_close(sndfile);
        return ERROR_OPEN;
    }
    float* data_in = (float*)malloc(size);
    if (!data_in) {
        sf_close(sndfile);
        return ERROR_CREATE;
    }
    sf_seek(sndfile, start, SEEK_SET);
    sf_count_t count = sf_readf_float(sndfile, data_in, frames);
    sf_close(sndfile);

    if (count != frames) {
        free(data_in);
        return ERROR_OPEN;
    }

    // Deinterleave source audio into array of buffers data_deinterleaved[]
    float* data_deinterleaved[channels];
    for (int ch = 0; ch < channels; ch++) {
        data_deinterleaved[ch] = malloc(frames * sizeof(float));
        for (sf_count_t i = 0; i < frames; i++) {
            data_deinterleaved[ch][i] = data_in[i * channels + ch];
        }
    }
    free(data_in);

    if (samplerate != sf_info.samplerate) {
        // SRC each channel into array of buffers data_resampled[]
        double resample_ratio = (double)samplerate / sf_info.samplerate;
        sf_count_t max_resampled_frames = frames * resample_ratio + 1;

        float* data_resampled[channels];
        sf_count_t resampled_frames = 0;

        int ch;
        for (ch = 0; ch < channels; ++ch) {
            data_resampled[ch] = malloc(max_resampled_frames * sizeof(float));

            SRC_DATA src_data = {
                .data_in = data_deinterleaved[ch],
                .data_out = data_resampled[ch],
                .input_frames = frames,
                .output_frames = max_resampled_frames,
                .src_ratio = resample_ratio,
                .end_of_input = SF_TRUE
            };

            int err;
            SRC_STATE *src = src_new(quality, 1, &err);
            if (!src) {
                error = ERROR_SRC;
                fprintf(stderr, "SRC init error: %s\n", src_strerror(err));
                break;
            }

            if ((err = src_process(src, &src_data))) {
                error = ERROR_SRC;
                fprintf(stderr, "SRC error: %s\n", src_strerror(err));
                break;
            }

            src_delete(src);
            free(data_deinterleaved[ch]);
            data_deinterleaved[ch] = data_resampled[ch];
            if (ch == channels - 1)
                frames = src_data.output_frames_gen;
        }

        if (error) {
            for (int i = ch; i < channels; ++i)
                free(data_deinterleaved[i]);
            return error;
        }
    }

    if (ratio != 1.0) {
        // Stretch into array of buffers data_stretched[]
        RubberBandState rb = rubberband_new(
            samplerate,
            channels,
            //RubberBandOptionEngineFaster |
            RubberBandOptionEngineFiner |
            RubberBandOptionProcessRealTime |
            // Transients Options => Only affect Faster Engine
            //RubberBandOptionTransientsCrisp |   // Default
            //RubberBandOptionTransientsMixed |
            //RubberBandOptionTransientsSmooth |
            //RubberBandOptionDetectorCompound |  // Default
            //RubberBandOptionDetectorSoft |
            //RubberBandOptionDetectorPercussive |
            //RubberBandOptionPhaseLaminar |      // Default
            //RubberBandOptionPhaseIndependent |
            //RubberBandOptionPitchHighSpeed |    // Default
            RubberBandOptionPitchHighQuality |
            //RubberBandOptionFormantShifted |    // Default
            RubberBandOptionFormantPreserved |
            // Stretch Options are Obsolete in version >= 3
            //RubberBandOptionStretchElastic |
            RubberBandOptionThreadingAuto,
            ratio,
            1.0  // No pitch change
        );

        const int block_size = 512;
        sf_count_t max_stretched_frames = frames * ratio + 2048;
        float* data_stretched[channels];
        for (int ch = 0; ch < channels; ch++)
            data_stretched[ch] = calloc(max_stretched_frames, sizeof(float));

        sf_count_t stretched_frames = 0;
        for (sf_count_t i = 0; i < frames; i += block_size) {
            int n, final = 0;
            if (i + block_size > frames) {
                n = frames - i;
                final = 1;
            } else {
                n = block_size;
            }
            float* block_in[channels];
            for (int ch = 0; ch < channels; ch++)
                block_in[ch] = &data_deinterleaved[ch][i];

            rubberband_process(rb, (const float* const*)block_in, n, final);
            int available = rubberband_available(rb);
            if (available > 0) {
                float *block_out[channels];
                for (int ch = 0; ch < channels; ch++)
                    block_out[ch] = data_stretched[ch] + stretched_frames;
                rubberband_retrieve(rb, block_out, available);
                stretched_frames += available;
            }
        }

        int available = rubberband_available(rb);
        if (available > 0) {
            float *block_out[channels];
            for (int ch = 0; ch < channels; ch++) {
                block_out[ch] = data_stretched[ch] + stretched_frames;
            }

            rubberband_retrieve(rb, block_out, available);
            stretched_frames += available;
        }

        for (int ch = 0; ch < channels; ch++) {
            free(data_deinterleaved[ch]);
            data_deinterleaved[ch] = data_stretched[ch];
        }
        frames = stretched_frames;

        rubberband_delete(rb);
    }

    // Interleave into buffer data_out
    float *data_out = malloc(frames * channels * sizeof(float));
    for (int ch = 0; ch < channels; ch++) {
        for (sf_count_t i = 0; i < frames; i++) {
            data_out[i * channels + ch] = data_deinterleaved[ch][i];
        }
        free(data_deinterleaved[ch]);
    }

    // Write output
    sf_info.samplerate = samplerate;
    sf_info.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;

    SNDFILE *outfile = sf_open(dst_path, SFM_WRITE, &sf_info);
    if (!outfile) {
        fprintf(stderr, "Failed to open output file.\n");
        return 1;
    }

    sf_writef_float(outfile, data_out, frames);
    sf_close(outfile);

    free(data_out);
    return 0;
}
