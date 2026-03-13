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
#include <sndfile.h>   // provides sound file manipulation
#include <samplerate.h> // provides samplerate convertor
#include <rubberband/rubberband-c.h> // provides time stretch
#include <math.h> // provides pow for dB calcs

typedef struct {
    uint8_t state;    // Clip state
    uint32_t frames;  // Quantity of frames in loaded clip
    uint8_t channels; // Quantity of channels in clip
    float gain;       // Gain factor
    uint16_t nbeats;  // Number of beats
    uint32_t start;   // Start frame in sample file
    uint32_t end;     // End frame in sample file
    uint8_t quality;  // Re-sample quality
    float tempo;      // Tempo to play (used to calculate timestretch ratio). 0 to no timestretch.
    char path[256];   // Loaded file path and filename
    float *data[2];   // Processed sample data for each channel (L,R)
} Clip;

typedef struct {
    uint8_t state;           // Play state
    uint32_t play_pos;       // Position of playhead in frames
    uint32_t beat;           // Beat counter
    jack_port_t* jack_out_a; // Left jack output port
    jack_port_t* jack_out_b; // Right jack output port
    SNDFILE* sndfile;        // Pointer to an open sndfile used to read current clip data
    Clip* clips[MAX_CLIPS];  // Array of pointers to clip objects
    Clip* current_clip;      // Pointer to the currently selected / playing clip
    int current_clip_id;     // Index of current clip
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
static volatile uint8_t mutex = 0;
Player* players[16]; // Up to 16 players, 1 per MIDI channel

static void inline getMutex() {
    while (mutex)
        usleep(100);
    mutex = 1;
}

static void inline releaseMutex() {
    mutex = 0;
}

static int process(jack_nframes_t frames, __attribute__((unused)) void* arg) {
    static Player* player;
    float* out_buff_a[16];
    float* out_buff_b[16];

    while (mutex)
        usleep(10);
    mutex = 1;

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
                        if (player->state == STATE_PLAYING) {
                            player->state = STATE_STOPPING;
                        } else {
                            player->state == STATE_READY;
                        }
                        player->beat = 0;
                    } else {
                        if (player->state == STATE_READY || player->state == STATE_PLAYING) {
                            // Set playing clip
                            uint8_t clip_id = event.buffer[1] - 1;
                            if (clip_id < MAX_CLIPS) {
                                player->current_clip = player->clips[clip_id];
                                player->current_clip_id = clip_id;
                            }
                            // Reset playing position
                            if (player->current_clip) {
                                player->play_pos = event.time;
                                player->state = STATE_STARTING;
                                player->beat = 0;
                            }
                        }
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
            case MIDI_AFTERTOUCH:
                // Used for beat sync
                uint8_t channel = event.buffer[0] & 0x0f;
                player = players[channel];
                if (!player)
                    break;
                // Resume playing at beat sync
                if (player->state == STATE_SYNCYNG && player->current_clip) {
                    player->beat = player->beat % player->current_clip->nbeats;
                    if (player->beat == 0) {
                        player->play_pos = event.time;
                        player->state = STATE_STARTING;
                    }
                    else {
                        player->play_pos = (player->beat * player->current_clip->frames / player->current_clip->nbeats) - event.time;
                        player->state = STATE_PLAYING;
                    }
                    //printf("SYNCYNG AT => %d / %d (NUM BEATS = %d)\n", player->play_pos, player->current_clip->frames, player->current_clip->nbeats);
                }
                player->beat++;
                //printf("Beat => %d\n", player->beat);
                break;
        }
    }

    // Populate player audio output buffers from sample data buffers
    for (uint8_t channel = 0; channel < 16; ++channel) {
        player = players[channel];
        if (!player) continue;
        //printf("PREPLAYING CHANNEL %d, STATE=%d => %d\n", channel, player->state, player->play_pos);
        out_buff_a[channel] = jack_port_get_buffer(player->jack_out_a, frames);
        out_buff_b[channel] = jack_port_get_buffer(player->jack_out_b, frames);
        memset(out_buff_a[channel], 0, frames * sizeof(float));
        memset(out_buff_b[channel], 0, frames * sizeof(float));
        if (player->current_clip) {
            float dGain;
            // Starting sample synced with note event time
            if (player->state == STATE_STARTING) {
                size_t start = player->play_pos * sizeof(float);
                uint32_t count = (frames - player->play_pos) * sizeof(float);
                memcpy(out_buff_a[channel] + start, player->current_clip->data[0], count);
                memcpy(out_buff_b[channel] + start, player->current_clip->data[1], count);
                dGain = 0.0f;
                player->state = STATE_PLAYING;
            }
            else if (player->state == STATE_PLAYING || player->state == STATE_STOPPING) {
                // Playing sample
                if (player->play_pos < player->current_clip->frames - frames) {
                    size_t count = frames * sizeof(float);
                    memcpy(out_buff_a[channel], player->current_clip->data[0] + player->play_pos, count);
                    memcpy(out_buff_b[channel], player->current_clip->data[1] + player->play_pos, count);
                    if (player->state == STATE_STOPPING) {
                        dGain = player->current_clip->gain / frames; // Soft fade
                        player->state = STATE_READY;
                        player->play_pos = 0;
                    } else {
                        dGain = 0.0f;
                        player->play_pos += frames;
                    }
                }
                // Reached end of clip
                else if (player->play_pos < player->current_clip->frames) {
                    uint32_t frame_count = player->current_clip->frames - player->play_pos;
                    size_t count = frame_count * sizeof(float);
                    memcpy(out_buff_a[channel], player->current_clip->data[0] + player->play_pos, count);
                    memcpy(out_buff_b[channel], player->current_clip->data[1] + player->play_pos, count);
                    dGain = player->current_clip->gain / frame_count; // Soft fade
                    player->play_pos = 0;
                    player->state = STATE_READY;
                } else {
                    player->play_pos = 0;
                    player->state = STATE_READY;
                }
            }
            // Adjust volume
            for (uint32_t i = 0; i < frames; ++i) {
                out_buff_a[channel][i] *= (player->current_clip->gain - i * dGain);
                out_buff_b[channel][i] *= (player->current_clip->gain - i * dGain);
            }
            //TODO Crossfade
            //printf("POSTPLAYING CHANNEL %d, STATE=%d => %d\n", channel, player->state, player->play_pos);
        }
    }
    mutex = 0;
    return 0;
}

void reset() {
    getMutex();
    for (uint8_t ch = 0; ch < 16; ch++) {
        Player* player = players[ch];
        if (!player)
            continue;
        player->state=STATE_LOAD;
        for (uint8_t id = 0; id < MAX_CLIPS; ++id) {
            Clip* clip = player->clips[id];
            if (clip) {
                loadClip(ch, id + 1, clip->path, clip->nbeats,
                         clip->start, clip->end, clip->quality, clip->tempo);
            }
        }
        player->state=STATE_READY;
    }
    releaseMutex();
}

void changeTempo(float tempo) {
    // Start by playing ones
    int ids[16];
    for (uint8_t ch = 0; ch < 16; ch++) {
        Player* player = players[ch];
        if (!player) {
            ids[ch] = -1;
            continue;
        }
        if (player->current_clip_id >= 0) {
            ids[ch] = player->current_clip_id;
        } else {
            ids[ch] = 0;
        }
    }
    // Reload clips, recalculating timestretch with new tempo
    for (uint8_t i = 0; i < MAX_CLIPS; i++) {
        for (uint8_t ch = 0; ch < 16; ch++) {
            Player* player = players[ch];
            if (!player || ids[ch] < 0)
                continue;
            uint8_t id = (ids[ch] + i) % MAX_CLIPS;
            Clip* clip = player->clips[id];
            // Don't process clips with tempo=0 (no timestretch)
            if (clip && clip->tempo > 0 && tempo != clip->tempo) {
                loadClip(ch, id + 1, clip->path, clip->nbeats,
                         clip->start, clip->end, clip->quality, tempo);
            }
        }
    }
}

static int onBufferSize(jack_nframes_t frames, __attribute__((unused)) void* arg) {
    buffersize = frames;
    //reset();
    return 0;
}

static int onSamplerate(jack_nframes_t frames, __attribute__((unused)) void* arg) {
    samplerate = frames;
    reset();
    return 0;
}

void end() {
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
    player->current_clip_id = -1;
    player->state = STATE_READY;
    getMutex();
    players[channel] = player;
    releaseMutex();
    return channel;
}

uint8_t removePlayer(uint8_t channel) {
    if(channel >= 16)
        return ERROR_RANGE;
    Player* player = players[channel];
    if(player == NULL)
        return ERROR_CREATE;
    getMutex();
    players[channel] = NULL;
    releaseMutex();
    for (uint32_t id = 0; id < MAX_CLIPS; ++id) {
        if (player->clips[id]) {
            for (int i=0; i < player->clips[id]->channels; i++)
                free(player->clips[id]->data[i]);
            free(player->clips[id]);
        }
    }
    jack_port_unregister(jack_client, player->jack_out_a);
    jack_port_unregister(jack_client, player->jack_out_b);
    free(player);
    return ERROR_SUCCESS;
}

uint8_t idlePlayerClip(uint8_t channel, uint8_t clip) {
    if (channel >= 16 || clip >= MAX_CLIPS)
        return ERROR_RANGE;
    Player* player = players[channel];
    if(player == NULL)
        return ERROR_CREATE;
    if (player->current_clip == player->clips[clip] && player->state == STATE_PLAYING) {
        getMutex();
        player->state = STATE_IDLE;
        releaseMutex();
    }
    return ERROR_SUCCESS;
}

uint8_t nudgeClip(uint8_t channel, uint8_t clip, uint8_t forward) {
    int nDiff = forward ? 1 : -1;
    int clip2 = clip + nDiff;
    if (clip >= MAX_CLIPS || clip2 >= MAX_CLIPS || channel > 15)
        return ERROR_RANGE;
    Player* pPlayer = players[channel];
    if (!pPlayer)
        return ERROR_RANGE;
    Clip* pClip = pPlayer->clips[clip];
    Clip* pClip2 = pPlayer->clips[clip2];
    getMutex(); //!@todo Check this won't leave stuck notes
    pPlayer->clips[clip] = pClip2;
    pPlayer->clips[clip2] = pClip;
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
    pPlayer->state = STATE_READY;
    return ERROR_SUCCESS;
}

uint8_t getFreeClip(uint8_t channel) {
    if (channel >= 16)
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

const char * getClipPath(uint8_t channel, uint8_t clip) {
    if (channel >= 16 || clip >= MAX_CLIPS)
        return NULL;
    Player* player = players[channel];
    if (!player)
        return NULL;
    if (player->clips[clip] == NULL)
        return NULL;
    return player->clips[clip]->path;
}

uint32_t getClipFrames(uint8_t channel, uint8_t clip) {
    if (channel >= 16 || clip >= MAX_CLIPS)
        return 0;
    Player* player = players[channel];
    if (!player)
        return 0;
    if (player->clips[clip] == NULL)
        return 0;
    return player->clips[clip]->frames;
}

uint8_t loadClip(uint8_t channel, uint8_t note, const char* path, uint16_t nbeats,
                 uint32_t start, uint32_t end, uint8_t quality, float tempo) {

    if (channel >= 16) {
        fprintf(stderr,"loadClip(): Channel/note out of range.\n");
        return 0;
    }
    Player* player = players[channel];
    if (!player) {
        fprintf(stderr,"loadClip(): No player in channel %d.\n", channel);
        return 0;
    }

    if (note == 0) {
        // Find next available note
        for (note = 0; note < MAX_CLIPS; ++ note) {
            if (!player->clips[note])
                break;
        }
        note++;
    }
    if (note >= MAX_CLIPS) {
        fprintf(stderr,"loadClip(): Note %d out of range.\n", note);
        return 0;
    }

    uint8_t error = 0;

    // --------------------------------------------------------------
    // Read data and deinterleave
    // --------------------------------------------------------------

    // Read source file into interleaved float buffer data_in
    SF_INFO sf_info;
    memset(&sf_info, 0, sizeof(sf_info));
    SNDFILE* sndfile = sf_open(path, SFM_READ, &sf_info);
    if (!sndfile || sf_info.samplerate < 11000 || sf_info.channels < 1 || sf_info.frames < MIN_FRAMES) {
        fprintf(stderr,"loadClip(): Wrong sample file.\n");
        sf_close(sndfile);
        return 0;
    }
    int channels = sf_info.channels;
    sf_count_t frames = sf_info.frames;
    if (end == 0)
        end = frames;
    int dur = end - start;
    if (dur < frames && dur > 0)
        frames = dur;
    uint8_t src = samplerate != sf_info.samplerate;
    size_t size = frames * sf_info.channels * sizeof(float);
    if (size == 0) {
        fprintf(stderr,"loadClip(): Sample file has no data.\n");
        sf_close(sndfile);
        return 0;
    }

    float* data_in = (float*)malloc(size);
    if (!data_in) {
        fprintf(stderr,"loadClip(): Can't reserve memory (%d bytes) to load sample data.\n", size);
        sf_close(sndfile);
        return 0;
    }
    sf_seek(sndfile, start, SEEK_SET);
    sf_count_t count = sf_readf_float(sndfile, data_in, frames);
    sf_close(sndfile);

    if (count != frames) {
        fprintf(stderr,"loadClip(): Error reading %d frames of sample data.\n", frames);
        free(data_in);
        return 0;
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

    // --------------------------------------------------------------
    // Re-sample
    // --------------------------------------------------------------

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

            if (quality > 4)
                quality = 4;

            int err;
            SRC_STATE *src = src_new(quality, 1, &err);
            if (!src) {
                free(data_resampled[ch]);
                error = ERROR_SRC;
                fprintf(stderr, "loadClip(): SRC init error: %s\n", src_strerror(err));
                break;
            }

            if ((err = src_process(src, &src_data))) {
                src_delete(src);
                free(data_resampled[ch]);
                error = ERROR_SRC;
                fprintf(stderr, "loadClip(): SRC process error: %s\n", src_strerror(err));
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
            return 0;
        }
    }

    // --------------------------------------------------------------
    // Time stretch
    // --------------------------------------------------------------

    // Calculate timestretch ratio from playing tempo, number of beats and duration
    uint8_t timestretch;
    float ratio;
    if (tempo == 0) {
        timestretch = 0;
        ratio = 1.0;
    } else {
        ratio = (60 * samplerate * nbeats) / (tempo * frames);
        if (ratio < 0.01 || ratio > 100) {
            // Don't stretch if excessive stretch requested.
            ratio = 1.0;
            timestretch = 0;
        } else {
            timestretch = (fabs(ratio - 1.0) > 0.0001);
        }
    }

    printf("loadClip('%s', %d BEATS at %f BPM) => RATIO=%f (%d)\n", path, nbeats, tempo, ratio, timestretch);

    if (timestretch) {
        // Rubberband Options
        uint32_t rb_options =
            //RubberBandOptionEngineFaster |
            RubberBandOptionEngineFiner |
            RubberBandOptionProcessOffline |
            //RubberBandOptionProcessRealTime |
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
            RubberBandOptionThreadingAuto;

        // Create and setup rubberband stretcher object
        RubberBandState rb = rubberband_new(
            samplerate,
            channels,
            rb_options,
            ratio,
            1.0  // No pitch change
        );
        rubberband_set_expected_input_duration(rb, frames);
        // Study stage (off-line processing)
        //printf("Rubberband Study ...\n");
        rubberband_study(rb, (const float* const*)data_deinterleaved, frames, 1);

        // Calculate result size and setup an array for the result
        const int block_size = MIN_FRAMES;
        sf_count_t max_stretched_frames = (int)(frames * ratio) + block_size;
        float* data_stretched[channels];
        for (int ch = 0; ch < channels; ch++)
            data_stretched[ch] = malloc(max_stretched_frames * sizeof(float));

        // Timestretch the sample data (off-line processing)
        //rubberband_set_max_process_size(rb, block_size);
        sf_count_t frames_stretched = 0;
        for (sf_count_t i = 0; i < frames; i += block_size) {
            int n, final = 0;
            if (i + block_size >= frames) {
                n = frames - i;
                final = 1;
            } else {
                n = block_size;
            }
            float* block_in[channels];
            for (int ch = 0; ch < channels; ch++)
                block_in[ch] = data_deinterleaved[ch] + i;

            rubberband_process(rb, (const float* const*)block_in, n, final);
            int available = rubberband_available(rb);
            if (available > 0) {
                float *block_out[channels];
                for (int ch = 0; ch < channels; ch++)
                    block_out[ch] = data_stretched[ch] + frames_stretched;
                rubberband_retrieve(rb, block_out, available);
                frames_stretched += available;
            }
        }
        //printf("Stretched frames => %d (calc %d)\n", frames_stretched, (int)(frames * ratio));
        // Move the result array to the right place
        for (int ch = 0; ch < channels; ch++) {
            free(data_deinterleaved[ch]);
            data_deinterleaved[ch] = data_stretched[ch];
        }
        frames = frames_stretched;    // = (int)(frames * ratio) =>  Offline processing. With RT processing this is not true.

        rubberband_delete(rb);
    }

    //---------------------------------------------------------------
    // Create & setup new clip with the processed sample data
    //---------------------------------------------------------------

    uint8_t id = note - 1;

    // Create a new clip instance
    Clip* clip = NULL;
    clip = malloc(sizeof(Clip));
    if (!clip) {
        fprintf(stderr, "loadClip(): Clippy error: failed to create new clip object\n");
        sf_close(sndfile);
        return 0;
    }
    // Setup Clip parameters
    clip->gain = 1.0f;
    strcpy(clip->path, path);
    if (channels <= 2)
        clip->channels = channels;
    else
        clip->channels = 2;
    for (int i = 0; i < channels; i++) {
        if (i < clip->channels)
            // Assign channel data to the clip
            clip->data[i] = data_deinterleaved[i];
        else {
            // Free uneeded channel data => TODO Limit this above in the process!!
            free(data_deinterleaved[i]);
            data_deinterleaved[i] = NULL;
        }
    }
    if (clip->channels == 1)
        clip->data[1] = clip->data[0];
    clip->frames = frames;
    clip->nbeats = nbeats;
    clip->start = start;
    clip->end = end;
    clip->quality = quality;
    clip->tempo = tempo;
    clip->state = STATE_READY;

    // Re-sync if playing
    uint8_t curclip = (player->current_clip == player->clips[id]);
    unloadClip(channel, note);
    player->clips[id] = clip;
    if (curclip) {
        getMutex();
        player->current_clip = clip;
        player->current_clip_id = id;
        if (player->state == STATE_IDLE)
            player->state = STATE_SYNCYNG;
        releaseMutex();
    }
    //fprintf(stderr, "loadClip(channel=%u, note=%u, path=%s) id=%u\n", channel, note, path, id);
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
        player->current_clip = NULL;
        player->current_clip_id = -1;
        if (player->state == STATE_PLAYING)
            clip->state = STATE_IDLE;
        releaseMutex();
    }
    player->clips[id] = NULL;
    for (int i=0; i < clip->channels; i++)
        free(clip->data[i]);
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

int saveFile(const char* dst_path, float *data[], int samplerate, int channels, uint32_t frames) {
    // Interleave into buffer data_out
    float *data_out = malloc(frames * channels * sizeof(float));
    if (!data_out) {
        fprintf(stderr, "saveFile(): Failed to reserve memory (%d bytes).\n", frames * channels * sizeof(float));
        return 1;
    }
    for (int ch = 0; ch < channels; ch++) {
        for (sf_count_t i = 0; i < frames; i++) {
            data_out[i * channels + ch] = data[ch][i];
        }
    }
    // Write output
    SF_INFO sf_info;
    memset(&sf_info, 0, sizeof(sf_info));
    sf_info.samplerate = samplerate;
    sf_info.channels = channels;
    //sf_info.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;
    sf_info.format = SF_FORMAT_WAV | SF_FORMAT_FLOAT;
    SNDFILE *outfile = sf_open(dst_path, SFM_WRITE, &sf_info);
    if (!outfile) {
        free(data_out);
        fprintf(stderr, "saveFile(): Failed to open output file '%s'.\n", dst_path);
        return 1;
    }
    sf_writef_float(outfile, data_out, frames);
    sf_close(outfile);
    free(data_out);

    return 0;
}
