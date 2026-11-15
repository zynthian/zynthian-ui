/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: zynslicer Library
 *
 * Library providing a sample slicer as a Jack connected device. Each player
 * holds one sample split into slices, and each slice is triggered by its own
 * MIDI note on the player's MIDI channel.
 *
 * Sample loading and the JACK client handling are based on the zynclippy
 * library by Brian Walton and Fernando Moyano.
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

#include "slicer.h"

#include <math.h>       // provides powf, fabsf
#include <stdio.h>      // provides fprintf
#include <stdlib.h>     // provides malloc, free, atexit
#include <string.h>     // provides memset, strncpy
#include <unistd.h>     // provides usleep
#include <stdatomic.h>  // provides atomic variables
#include <jack/jack.h>  // provides jack API
#include <jack/midiport.h> // provides jack midi port API
#include <sndfile.h>    // provides sound file reading
#include <samplerate.h> // provides samplerate convertor

#define FADE_FRAMES 64                  // Length of voice fade-in / fade-out in frames
#define VOICE_SLOTS (MAX_VOICES * 2)    // Voice pool incl. spare slots for stolen voices to fade out

// ----------------------------------------------------------------------------
// Data types
// ----------------------------------------------------------------------------

enum VOICE_STATE {
    VOICE_IDLE,
    VOICE_PLAYING
};

typedef struct {
    uint32_t frames;        // Quantity of frames in loaded sample (at JACK samplerate)
    uint32_t source_frames; // Quantity of frames in source file crop (before SRC)
    uint32_t start;         // Start frame in sample file
    uint32_t end;           // End frame in sample file
    uint8_t quality;        // Re-sample quality
    uint8_t channels;       // Quantity of channels in sample
    char path[256];         // Loaded file path and filename
    float *data[2];         // Sample data for each channel (L,R)
} Sample;

typedef struct {
    uint32_t start;         // Start frame in source sample crop (before SRC)
    uint32_t end;           // End frame in source sample crop (before SRC)
    float gain;             // Linear gain factor
    float rate;             // Playback rate (1.0 = original pitch and speed)
    uint8_t flags;          // Playback flags (SLICE_FLAG_*)
} Slice;

typedef struct {
    uint8_t state;          // VOICE_IDLE or VOICE_PLAYING
    uint8_t note;           // MIDI note that triggered this voice
    uint8_t velocity;       // MIDI velocity
    Slice* slice;           // Slice being played
    double pos;             // Position within slice in loaded sample frames (fractional when tuned)
    uint32_t start_frame;   // Note-on offset within the current JACK cycle
    uint32_t order;         // Voice start order (for latest-voice display)
    uint32_t fade_in;       // Remaining fade-in frames
    uint32_t fade_out;      // Remaining fade-out frames
} Voice;

typedef struct {
    jack_port_t* jack_out_a;    // Left jack output port
    jack_port_t* jack_out_b;    // Right jack output port
    uint8_t polyphony;          // Maximum quantity of simultaneous voices
    uint32_t voice_order;       // Monotonic voice start counter for display
    Sample* sample;             // Loaded sample shared by all slices
    Slice* slices[MAX_SLICES];  // Slice descriptors indexed by MIDI note - 1
    Voice voices[VOICE_SLOTS];  // Voice pool
} Player;

// ----------------------------------------------------------------------------
// Global variables
// ----------------------------------------------------------------------------

static jack_nframes_t samplerate = 48000;
static jack_client_t* jack_client = NULL;
static jack_port_t* midi_input_port = NULL;
static _Atomic(Player*) players[MAX_PLAYERS]; // One player per MIDI channel
static atomic_int player_to_remove = -1;       // Player removed by the next JACK cycle

// Protects players' samples, slices and voices between the JACK process
// thread and the API functions.
static atomic_flag lock = ATOMIC_FLAG_INIT;

static void getLock() {
    while (atomic_flag_test_and_set(&lock))
        usleep(10);
}

static void releaseLock() {
    atomic_flag_clear(&lock);
}

static Player* getPlayer(uint8_t channel) {
    if (channel >= MAX_PLAYERS)
        return NULL;
    return players[channel];
}

// ----------------------------------------------------------------------------
// Voices
// ----------------------------------------------------------------------------

/** @brief  Immediately silence all voices
 *  @param  player Player object
 */
static void resetVoices(Player* player) {
    player->voice_order = 0;
    memset(player->voices, 0, sizeof(player->voices));
}

/** @brief  Get a free voice, stealing the oldest one if necessary
 *  @param  player Player object
 *  @retval Voice* Pointer to voice
 *  @note   Only the first "polyphony" slots take new voices. A stolen voice is
 *          moved to a spare slot to fade out instead of being cut (a click).
 */
static Voice* getFreeVoice(Player* player) {
    uint8_t limit = player->polyphony;
    if (limit > MAX_VOICES)
        limit = MAX_VOICES;
    if (limit == 0)
        limit = 1;
    for (uint8_t i = 0; i < limit; i++) {
        if (player->voices[i].state == VOICE_IDLE)
            return &player->voices[i];
    }
    // Steal the voice that has progressed furthest through its slice
    Voice* victim = &player->voices[0];
    for (uint8_t i = 1; i < limit; i++) {
        if (player->voices[i].pos > victim->pos)
            victim = &player->voices[i];
    }
    for (uint8_t i = limit; i < VOICE_SLOTS; i++) {
        Voice* spare = &player->voices[i];
        if (spare->state == VOICE_IDLE) {
            *spare = *victim;
            if (!spare->fade_out)
                spare->fade_out = FADE_FRAMES;
            break;
        }
    }
    return victim;
}

/** @brief  Start a voice playing a slice
 *  @param  player Player object
 *  @param  note MIDI note (1..127)
 *  @param  velocity MIDI velocity (1..127)
 *  @param  start_frame Offset within current JACK cycle
 *  @retval Voice* Pointer to started voice or NULL
 */
static Voice* startSlice(Player* player, uint8_t note, uint8_t velocity, uint32_t start_frame) {
    if (!player->sample || note == 0 || note > MAX_SLICES)
        return NULL;
    Slice* slice = player->slices[note - 1];
    if (!slice)
        return NULL;
    Voice* voice = getFreeVoice(player);
    memset(voice, 0, sizeof(Voice));
    voice->state = VOICE_PLAYING;
    voice->note = note;
    voice->velocity = velocity ? velocity : 127;
    voice->slice = slice;
    voice->start_frame = start_frame;
    voice->order = ++player->voice_order;
    voice->fade_in = FADE_FRAMES;
    return voice;
}

/** @brief  Release voices, as a note-off does
 *  @param  player Player object
 *  @param  note MIDI note (1..127), or 0 to stop all voices
 *  @note   For a note, only gate and loop voices stop; one-shot voices play on.
 */
static void stopSliceVoices(Player* player, uint8_t note) {
    for (uint8_t i = 0; i < VOICE_SLOTS; i++) {
        Voice* voice = &player->voices[i];
        if (voice->state != VOICE_PLAYING || !voice->slice || voice->fade_out)
            continue;
        if (note && voice->note != note)
            continue;
        if (note == 0 || (voice->slice->flags & (SLICE_FLAG_GATE | SLICE_FLAG_LOOP)))
            voice->fade_out = FADE_FRAMES;
    }
}

/** @brief  Mix a voice into a player's output buffers
 *  @param  out_a Left output buffer
 *  @param  out_b Right output buffer
 *  @param  sample Loaded sample
 *  @param  voice Voice to process
 *  @param  frames Quantity of frames in JACK cycle
 */
static void processVoice(float* out_a, float* out_b, Sample* sample, Voice* voice, jack_nframes_t frames) {
    if (voice->state != VOICE_PLAYING || !voice->slice || !sample)
        return;

    uint32_t source_frames = sample->source_frames;
    if (!source_frames) {
        voice->state = VOICE_IDLE;
        return;
    }

    // Slice positions are stored in source frames. Scale to loaded sample frames.
    uint64_t start = (uint64_t)voice->slice->start * sample->frames / source_frames;
    uint64_t end = (uint64_t)voice->slice->end * sample->frames / source_frames;
    if (end > sample->frames)
        end = sample->frames;
    if (start >= end) {
        voice->state = VOICE_IDLE;
        return;
    }
    uint32_t length = end - start;
    uint8_t loop = voice->slice->flags & SLICE_FLAG_LOOP;

    if (voice->pos >= length) {
        if (!loop) {
            voice->state = VOICE_IDLE;
            return;
        }
        voice->pos = 0; // Slice was shortened while playing
    }

    // Handle note-on offset within this JACK cycle
    uint32_t offset = 0;
    if (voice->start_frame) {
        if (voice->start_frame >= frames) {
            voice->start_frame -= frames;
            return;
        }
        offset = voice->start_frame;
        voice->start_frame = 0;
    }

    uint32_t n = frames - offset;

    // Looping slices fade at both edges so the jump back to the start
    // doesn't click.
    uint32_t loop_fade = 0;
    if (loop) {
        loop_fade = length / 4;
        if (loop_fade > FADE_FRAMES)
            loop_fade = FADE_FRAMES;
    }

    // Tuned slices step through the sample at a fractional rate and read it
    // with linear interpolation. At rate 1.0 the position stays whole, so the
    // output is the sample data unchanged.
    double rate = voice->slice->rate > 0.0f ? voice->slice->rate : 1.0;
    float* data_a = sample->data[0] + start;
    float* data_b = sample->data[1] + start;
    float gain = voice->slice->gain * (voice->velocity / 127.0f);
    for (uint32_t i = 0; i < n; i++) {
        uint32_t idx = (uint32_t)voice->pos;
        float frac = (float)(voice->pos - idx);
        float g = gain;
        if (loop_fade) {
            double edge = voice->pos < length - 1 - voice->pos ? voice->pos : length - 1 - voice->pos;
            if (edge < 0.0)
                edge = 0.0;
            if (edge < loop_fade)
                g *= (float)(edge + 1) / (loop_fade + 1);
        }
        if (voice->fade_in) {
            g *= 1.0f - (float)voice->fade_in / FADE_FRAMES;
            voice->fade_in--;
        }
        if (voice->fade_out) {
            g *= (float)voice->fade_out / FADE_FRAMES;
            voice->fade_out--;
            if (!voice->fade_out)
                voice->state = VOICE_IDLE;
        }
        float a = data_a[idx];
        float b = data_b[idx];
        if (frac > 0.0f) {
            // The frame after the last one is the slice start when looping
            uint32_t next = idx + 1 < length ? idx + 1 : (loop ? 0 : idx);
            a += (data_a[next] - a) * frac;
            b += (data_b[next] - b) * frac;
        }
        out_a[offset + i] += a * g;
        out_b[offset + i] += b * g;
        voice->pos += rate;
        if (voice->pos >= length) {
            if (loop) {
                voice->pos -= length;
                if (voice->pos >= length)
                    voice->pos = 0; // Rate larger than the slice
            } else {
                voice->state = VOICE_IDLE;
            }
        }
        if (voice->state == VOICE_IDLE)
            break;
    }
}

// ----------------------------------------------------------------------------
// Jack RT process
// ----------------------------------------------------------------------------

static int process(jack_nframes_t frames, __attribute__((unused)) void* arg) {
    getLock();

    // Execute deferred player removal safely
    int remove = atomic_exchange(&player_to_remove, -1);
    if (remove >= 0)
        players[remove] = NULL;

    // MIDI notes start and release voices on the player of their channel
    void* midi_buffer = jack_port_get_buffer(midi_input_port, frames);
    jack_nframes_t num_events = jack_midi_get_event_count(midi_buffer);
    jack_midi_event_t event;
    for (uint32_t i = 0; i < num_events; ++i) {
        if (jack_midi_event_get(&event, midi_buffer, i) != 0 || event.size < 3)
            continue;
        Player* player = players[event.buffer[0] & 0x0f];
        if (!player)
            continue;
        uint8_t command = event.buffer[0] & 0xf0;
        uint8_t note = event.buffer[1];
        uint8_t velocity = event.buffer[2];
        if (command == MIDI_NOTE_ON && velocity) {
            if (note == 0)
                stopSliceVoices(player, 0); // Note 0 stops all voices
            else
                startSlice(player, note, velocity, event.time);
        } else if (command == MIDI_NOTE_OFF || command == MIDI_NOTE_ON) {
            stopSliceVoices(player, note);
        }
    }

    // Mix each player's voices into its outputs
    for (uint8_t channel = 0; channel < MAX_PLAYERS; channel++) {
        Player* player = players[channel];
        if (!player)
            continue;
        float* out_a = jack_port_get_buffer(player->jack_out_a, frames);
        float* out_b = jack_port_get_buffer(player->jack_out_b, frames);
        memset(out_a, 0, frames * sizeof(float));
        memset(out_b, 0, frames * sizeof(float));
        for (uint8_t i = 0; i < VOICE_SLOTS; i++)
            processVoice(out_a, out_b, player->sample, &player->voices[i], frames);
    }

    releaseLock();
    return 0;
}

// ----------------------------------------------------------------------------
// Sample loading
// ----------------------------------------------------------------------------

/** @brief  Read, deinterleave and resample a range of an audio file
 *  @param  path Full (or relative) path and filename
 *  @param  start Start frame in source file
 *  @param  end End frame in source file (0 for end of file)
 *  @param  quality Re-sample quality (0..4)
 *  @param  out_frames Quantity of frames after re-sampling
 *  @param  out_source_frames Quantity of frames in source crop before re-sampling
 *  @param  out_channels Quantity of output channels (1 or 2)
 *  @param  out_data Output sample data pointers
 *  @retval uint8_t Error code
 */
static uint8_t loadAudioData(const char* path, uint32_t start, uint32_t end, uint8_t quality,
                             uint32_t* out_frames, uint32_t* out_source_frames,
                             uint8_t* out_channels, float* out_data[2]) {
    *out_frames = 0;
    *out_source_frames = 0;
    *out_channels = 0;
    out_data[0] = NULL;
    out_data[1] = NULL;

    SF_INFO sf_info;
    memset(&sf_info, 0, sizeof(sf_info));
    SNDFILE* sndfile = sf_open(path, SFM_READ, &sf_info);
    if (!sndfile || sf_info.samplerate < 11000 || sf_info.channels < 1 || sf_info.frames < MIN_FRAMES) {
        fprintf(stderr, "loadAudioData(): Wrong sample file '%s'.\n", path);
        if (sndfile)
            sf_close(sndfile);
        return ERROR_OPEN;
    }

    int channels = sf_info.channels;
    sf_count_t source_frames = sf_info.frames;
    if (end == 0 || end > source_frames)
        end = source_frames;
    if (start >= end) {
        fprintf(stderr, "loadAudioData(): Invalid sample range %u..%u.\n", start, end);
        sf_close(sndfile);
        return ERROR_RANGE;
    }
    sf_count_t frames = end - start;
    *out_source_frames = frames;

    float* data_in = (float*)malloc(frames * channels * sizeof(float));
    if (!data_in) {
        fprintf(stderr, "loadAudioData(): Can't reserve memory (%d bytes).\n", (int)(frames * channels * sizeof(float)));
        sf_close(sndfile);
        return ERROR_CREATE;
    }
    sf_seek(sndfile, start, SEEK_SET);
    sf_count_t count = sf_readf_float(sndfile, data_in, frames);
    sf_close(sndfile);
    if (count != frames) {
        fprintf(stderr, "loadAudioData(): Error reading %d frames of sample data.\n", (int)frames);
        free(data_in);
        return ERROR_OPEN;
    }

    // Deinterleave up to two channels
    int out_ch = channels < 2 ? channels : 2;
    float* data_deinterleaved[2] = {NULL, NULL};
    for (int ch = 0; ch < out_ch; ch++) {
        data_deinterleaved[ch] = malloc(frames * sizeof(float));
        if (!data_deinterleaved[ch]) {
            fprintf(stderr, "loadAudioData(): Can't reserve memory for channel %d.\n", ch);
            for (int i = 0; i < ch; i++)
                free(data_deinterleaved[i]);
            free(data_in);
            return ERROR_CREATE;
        }
        for (sf_count_t i = 0; i < frames; i++)
            data_deinterleaved[ch][i] = data_in[i * channels + ch];
    }
    free(data_in);

    // Re-sample each channel to the JACK samplerate
    if (samplerate != (jack_nframes_t)sf_info.samplerate) {
        double resample_ratio = (double)samplerate / sf_info.samplerate;
        sf_count_t max_resampled_frames = frames * resample_ratio + 1;
        sf_count_t resampled_frames = 0;
        if (quality > 4)
            quality = 4;
        for (int ch = 0; ch < out_ch; ch++) {
            float* data_resampled = malloc(max_resampled_frames * sizeof(float));
            if (!data_resampled) {
                for (int i = 0; i < out_ch; i++)
                    free(data_deinterleaved[i]);
                return ERROR_CREATE;
            }
            SRC_DATA src_data = {
                .data_in = data_deinterleaved[ch],
                .data_out = data_resampled,
                .input_frames = frames,
                .output_frames = max_resampled_frames,
                .src_ratio = resample_ratio,
                .end_of_input = SF_TRUE
            };
            int err;
            SRC_STATE *src = src_new(quality, 1, &err);
            if (!src) {
                free(data_resampled);
                for (int i = 0; i < out_ch; i++)
                    free(data_deinterleaved[i]);
                fprintf(stderr, "loadAudioData(): SRC init error: %s\n", src_strerror(err));
                return ERROR_SRC;
            }
            if ((err = src_process(src, &src_data))) {
                src_delete(src);
                free(data_resampled);
                for (int i = 0; i < out_ch; i++)
                    free(data_deinterleaved[i]);
                fprintf(stderr, "loadAudioData(): SRC process error: %s\n", src_strerror(err));
                return ERROR_SRC;
            }
            src_delete(src);
            free(data_deinterleaved[ch]);
            data_deinterleaved[ch] = data_resampled;
            if (ch == out_ch - 1)
                resampled_frames = src_data.output_frames_gen;
        }
        frames = resampled_frames;
    }

    *out_frames = frames;
    *out_channels = out_ch;
    out_data[0] = data_deinterleaved[0];
    out_data[1] = out_ch > 1 ? data_deinterleaved[1] : data_deinterleaved[0];
    return ERROR_SUCCESS;
}

/** @brief  Free a sample and its buffers
 *  @param  sample Sample to free
 */
static void freeSample(Sample* sample) {
    if (!sample)
        return;
    for (int i = 0; i < sample->channels; i++)
        free(sample->data[i]);
    free(sample);
}

/** @brief  Free all slice descriptors in a player
 *  @param  player Player object
 */
static void freeSlices(Player* player) {
    for (uint8_t i = 0; i < MAX_SLICES; i++) {
        free(player->slices[i]);
        player->slices[i] = NULL;
    }
}

/** @brief  Reload all samples at the current samplerate, keeping their slices
 */
static void reloadSamples() {
    for (uint8_t channel = 0; channel < MAX_PLAYERS; channel++) {
        Player* player = players[channel];
        if (!player || !player->sample)
            continue;
        char path[256];
        strncpy(path, player->sample->path, sizeof(path) - 1);
        path[sizeof(path) - 1] = 0;
        uint32_t start = player->sample->start;
        uint32_t end = player->sample->end;
        uint8_t quality = player->sample->quality;
        // loadSample() frees the slices, so keep them aside meanwhile
        Slice* saved[MAX_SLICES];
        getLock();
        memcpy(saved, player->slices, sizeof(saved));
        memset(player->slices, 0, sizeof(player->slices));
        releaseLock();
        loadSample(channel, path, start, end, quality);
        getLock();
        memcpy(player->slices, saved, sizeof(saved));
        releaseLock();
    }
}

// ----------------------------------------------------------------------------
// Library management
// ----------------------------------------------------------------------------

static int onSamplerate(jack_nframes_t frames, __attribute__((unused)) void* arg) {
    if (frames != samplerate) {
        samplerate = frames;
        reloadSamples();
    }
    return 0;
}

int init() {
    if (jack_client)
        return ERROR_EXISTS;
    // Register the cleanup function to be called when the library exits
    atexit(end);

    for (uint8_t i = 0; i < MAX_PLAYERS; ++i)
        players[i] = NULL;

    jack_status_t status;
    jack_client = jack_client_open("zynslicer", JackNullOption, &status);
    if (jack_client == NULL) {
        fprintf(stderr, "zynslicer: Could not open JACK client\n");
        return ERROR_CREATE;
    }
    samplerate = jack_get_sample_rate(jack_client);

    midi_input_port = jack_port_register(jack_client, "in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);
    if (midi_input_port == NULL) {
        fprintf(stderr, "zynslicer: Could not open MIDI input port\n");
        end();
        return ERROR_PORT;
    }

    jack_set_sample_rate_callback(jack_client, onSamplerate, NULL);
    jack_set_process_callback(jack_client, process, NULL);

    if (jack_activate(jack_client) != 0) {
        fprintf(stderr, "zynslicer: Could not activate JACK client\n");
        end();
        return ERROR_ACTIVATE;
    }
    return ERROR_SUCCESS;
}

void end() {
    if (!jack_client)
        return;
    for (uint8_t i = 0; i < MAX_PLAYERS; ++i)
        removePlayer(i);
    jack_client_close(jack_client);
    jack_client = NULL;
}

const char* getJackname() {
    if (!jack_client)
        return NULL;
    return jack_get_client_name(jack_client);
}

uint8_t addPlayer(uint8_t channel) {
    if (!jack_client)
        return 255;
    // If the requested channel is in use, or the caller asked for any free
    // player (channel >= MAX_PLAYERS), use the first free channel.
    if (channel >= MAX_PLAYERS || players[channel] != NULL) {
        for (channel = 0; channel < MAX_PLAYERS; ++channel) {
            if (players[channel] == NULL)
                break;
        }
    }
    if (channel >= MAX_PLAYERS)
        return 255;
    Player* player = malloc(sizeof(Player));
    if (!player)
        return 255;
    memset(player, 0, sizeof(Player));
    char name[16];
    snprintf(name, sizeof(name), "out_%02ua", channel + 1);
    player->jack_out_a = jack_port_register(jack_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    snprintf(name, sizeof(name), "out_%02ub", channel + 1);
    player->jack_out_b = jack_port_register(jack_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0);
    if (player->jack_out_a == NULL || player->jack_out_b == NULL) {
        fprintf(stderr, "zynslicer: Failed to create jack output ports\n");
        if (player->jack_out_a)
            jack_port_unregister(jack_client, player->jack_out_a);
        if (player->jack_out_b)
            jack_port_unregister(jack_client, player->jack_out_b);
        free(player);
        return 255;
    }
    player->polyphony = MAX_VOICES;
    atomic_store(&players[channel], player);
    return channel;
}

uint8_t removePlayer(uint8_t channel) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;
    // Let the JACK process thread drop the player at the start of a cycle,
    // so it is never freed while being processed.
    atomic_store(&player_to_remove, channel);
    while (atomic_load(&player_to_remove) >= 0)
        usleep(1000);
    freeSlices(player);
    freeSample(player->sample);
    jack_port_unregister(jack_client, player->jack_out_a);
    jack_port_unregister(jack_client, player->jack_out_b);
    free(player);
    return ERROR_SUCCESS;
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

// ----------------------------------------------------------------------------
// Sample and slices
// ----------------------------------------------------------------------------

uint8_t setPolyphony(uint8_t channel, uint8_t voices) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;
    if (voices < 1)
        voices = 1;
    if (voices > MAX_VOICES)
        voices = MAX_VOICES;
    getLock();
    player->polyphony = voices;
    for (uint8_t i = voices; i < VOICE_SLOTS; i++)
        player->voices[i].state = VOICE_IDLE;
    releaseLock();
    return ERROR_SUCCESS;
}

uint8_t loadSample(uint8_t channel, const char* path, uint32_t start, uint32_t end, uint8_t quality) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;

    uint32_t frames;
    uint32_t source_frames;
    uint8_t channels;
    float* data[2];
    uint8_t error = loadAudioData(path, start, end, quality, &frames, &source_frames, &channels, data);
    if (error)
        return error;

    Sample* sample = malloc(sizeof(Sample));
    if (!sample) {
        for (int i = 0; i < channels; i++)
            free(data[i]);
        return ERROR_CREATE;
    }
    memset(sample, 0, sizeof(Sample));
    sample->frames = frames;
    sample->source_frames = source_frames;
    sample->start = start;
    sample->end = start + source_frames;
    sample->quality = quality;
    sample->channels = channels;
    strncpy(sample->path, path, sizeof(sample->path) - 1);
    sample->data[0] = data[0];
    sample->data[1] = data[1];

    getLock();
    resetVoices(player);
    freeSlices(player);
    Sample* old_sample = player->sample;
    player->sample = sample;
    releaseLock();

    freeSample(old_sample);
    return ERROR_SUCCESS;
}

uint8_t unloadSample(uint8_t channel) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;
    getLock();
    resetVoices(player);
    freeSlices(player);
    Sample* old_sample = player->sample;
    player->sample = NULL;
    releaseLock();
    freeSample(old_sample);
    return ERROR_SUCCESS;
}

uint32_t getSampleFrames(uint8_t channel) {
    Player* player = getPlayer(channel);
    if (!player)
        return 0;
    getLock();
    uint32_t frames = player->sample ? player->sample->source_frames : 0;
    releaseLock();
    return frames;
}

uint8_t setSlice(uint8_t channel, uint8_t note, uint32_t start, uint32_t end,
                 float gain, uint8_t flags) {
    Player* player = getPlayer(channel);
    if (!player || note == 0 || note > MAX_SLICES || start >= end)
        return ERROR_RANGE;

    uint8_t error = ERROR_SUCCESS;
    getLock();
    if (!player->sample || end > player->sample->source_frames) {
        error = ERROR_RANGE;
    } else {
        // Update an existing slice in place so its voices follow gain and
        // flag changes without being retriggered or stopped.
        Slice* slice = player->slices[note - 1];
        if (!slice) {
            slice = malloc(sizeof(Slice));
            player->slices[note - 1] = slice;
            if (slice)
                slice->rate = 1.0f; // A new slice plays untuned until setSliceTune()
        }
        if (slice) {
            slice->start = start;
            slice->end = end;
            slice->gain = gain < 0.0f ? 0.0f : gain;
            slice->flags = flags;
        } else {
            error = ERROR_CREATE;
        }
    }
    releaseLock();
    return error;
}

uint8_t setSliceTune(uint8_t channel, uint8_t note, float semitones) {
    Player* player = getPlayer(channel);
    if (!player || note == 0 || note > MAX_SLICES || !isfinite(semitones))
        return ERROR_RANGE;
    if (semitones < -MAX_TUNE)
        semitones = -MAX_TUNE;
    if (semitones > MAX_TUNE)
        semitones = MAX_TUNE;
    float rate = fabsf(semitones) < 1e-6f ? 1.0f : powf(2.0f, semitones / 12.0f);

    uint8_t error = ERROR_SUCCESS;
    getLock();
    Slice* slice = player->slices[note - 1];
    if (slice)
        slice->rate = rate; // Playing voices follow on their next frame
    else
        error = ERROR_RANGE;
    releaseLock();
    return error;
}

uint8_t clearSlices(uint8_t channel) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;
    getLock();
    resetVoices(player);
    freeSlices(player);
    releaseLock();
    return ERROR_SUCCESS;
}

// ----------------------------------------------------------------------------
// Playback
// ----------------------------------------------------------------------------

uint8_t auditionSlice(uint8_t channel, uint8_t note, uint8_t velocity) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;
    getLock();
    Voice* voice = startSlice(player, note, velocity, 0);
    releaseLock();
    return voice ? ERROR_SUCCESS : ERROR_RANGE;
}

uint8_t releaseSlice(uint8_t channel, uint8_t note) {
    Player* player = getPlayer(channel);
    if (!player || note == 0)
        return ERROR_RANGE;
    getLock();
    stopSliceVoices(player, note);
    releaseLock();
    return ERROR_SUCCESS;
}

uint8_t stopSlices(uint8_t channel) {
    Player* player = getPlayer(channel);
    if (!player)
        return ERROR_RANGE;
    getLock();
    stopSliceVoices(player, 0);
    releaseLock();
    return ERROR_SUCCESS;
}

uint8_t getSlicePlayheads(uint8_t channel, uint8_t* notes, float* progress,
                          uint32_t* order, uint8_t max) {
    Player* player = getPlayer(channel);
    if (!player || !notes || !progress || !order || max == 0)
        return 0;

    uint8_t count = 0;
    getLock();
    Sample* sample = player->sample;
    uint32_t source_frames = sample ? sample->source_frames : 0;
    uint32_t sample_frames = sample ? sample->frames : 0;
    for (uint8_t i = 0; i < VOICE_SLOTS && count < max && source_frames && sample_frames; i++) {
        Voice* voice = &player->voices[i];
        if (voice->state != VOICE_PLAYING || !voice->slice)
            continue;
        uint64_t start = (uint64_t)voice->slice->start * sample_frames / source_frames;
        uint64_t end = (uint64_t)voice->slice->end * sample_frames / source_frames;
        if (end > sample_frames)
            end = sample_frames;
        if (start >= end)
            continue;
        float pos = (float)voice->pos / (float)(end - start);
        notes[count] = voice->note;
        progress[count] = pos > 1.0f ? 1.0f : pos;
        order[count] = voice->order;
        count++;
    }
    releaseLock();
    return count;
}
