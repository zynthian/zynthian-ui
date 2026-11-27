/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio to MIDI converter (zynaudio2midi)
 *
 * JACK glue for the DSP core (a2m_dsp.c)
 *
 * Copyright (C) 2026 Brian Walton <riban@zynthian.org>
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

#include "audio2midi.h"
#include "a2m_dsp.h"

#include <jack/jack.h>
#include <jack/midiport.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static jack_client_t* g_client = NULL;
static jack_port_t* g_input[A2M_NUM_INPUTS] = {NULL};
static jack_port_t* g_midi_out[A2M_NUM_OUTPUTS] = {NULL};
static a2m_dsp_t* g_dsp[A2M_NUM_INPUTS] = {NULL}; // A detector for each input
static a2m_out_t g_out[A2M_NUM_INPUTS];

// Parameters, written by the UI thread, read by the JACK process thread
// Detection parameters of each channel's input (detector)
static _Atomic float g_onset[A2M_NUM_INPUTS] = {-60.0f, -60.0f};
static _Atomic float g_release[A2M_NUM_INPUTS] = {-66.0f, -66.0f};
static _Atomic float g_noise[A2M_NUM_INPUTS] = {15.0f, 15.0f};
static atomic_int g_active[A2M_NUM_OUTPUTS];
static atomic_int g_source[A2M_NUM_OUTPUTS] = {0, 1}; // Input (detector) feeding each output
static atomic_int g_poly[A2M_NUM_OUTPUTS];
static atomic_int g_bend[A2M_NUM_OUTPUTS] = {1, 0};
static _Atomic float g_bend_range[A2M_NUM_OUTPUTS] = {2.0f, 2.0f};
static atomic_uint g_new_rate = 0; // Samplerate change requested by JACK, applied in process thread
static atomic_int g_flush = 0;     // 1: stop requested, release notes; 2: notes released

_Static_assert(A2M_NUM_INPUTS == 2, "split_params() handles 2 inputs");
_Static_assert(A2M_NUM_OUTPUTS == A2M_OUTPUTS, "Quantity of outputs of the JACK client and the DSP core differ");

static float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

// Parameters of the outputs (the detection parameters are set by split_params)
static void get_params(a2m_params_t* p) {
    for (int i = 0; i < A2M_NUM_OUTPUTS; ++i) {
        p->out[i].active = atomic_load(&g_active[i]);
        p->out[i].poly = atomic_load(&g_poly[i]);
        p->out[i].bend = atomic_load(&g_bend[i]);
        p->out[i].bend_range = atomic_load(&g_bend_range[i]);
    }
}

/* Parameters of each input's detector: it feeds the outputs it is the source of (setOutputSource), while its input
 * is connected. By default input 1 => output 1, input 2 => output 2 (2 independent channels). With both outputs fed
 * by one input, it is analysed once. Each detector uses the detection parameters of its input's channel.
 */
static void split_params(const a2m_params_t* base, const int* connected, a2m_params_t* p) {
    for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
        p[in] = *base;
        p[in].onset_db = atomic_load(&g_onset[in]);
        p[in].release_db = atomic_load(&g_release[in]);
        p[in].noise = atomic_load(&g_noise[in]);
        for (int o = 0; o < A2M_NUM_OUTPUTS; ++o)
            if (!connected[in] || atomic_load(&g_source[o]) != in)
                p[in].out[o].active = 0;
    }
}

// Write the events of an output from all detectors, in time order
static void write_events(void* buffer, int o, jack_nframes_t frames) {
    uint32_t idx[A2M_NUM_INPUTS] = {0};
    while (1) {
        int best = -1;
        for (int in = 0; in < A2M_NUM_INPUTS; ++in)
            if (idx[in] < g_out[in].count[o] &&
                (best < 0 || g_out[in].ev[o][idx[in]].frame < g_out[best].ev[o][idx[best]].frame))
                best = in;
        if (best < 0)
            break;
        const a2m_event_t* e = &g_out[best].ev[o][idx[best]++];
        jack_midi_event_write(buffer, e->frame < frames ? e->frame : frames - 1, e->data, 3);
    }
}

static void write_all(void** buffers, jack_nframes_t frames) {
    for (int o = 0; o < A2M_NUM_OUTPUTS; ++o)
        write_events(buffers[o], o, frames);
}

static int on_process(jack_nframes_t frames, void* arg) {
    (void)arg;
    void* midi[A2M_NUM_OUTPUTS];
    for (int o = 0; o < A2M_NUM_OUTPUTS; ++o) {
        midi[o] = jack_port_get_buffer(g_midi_out[o], frames);
        jack_midi_clear_buffer(midi[o]);
    }
    if (atomic_load(&g_flush)) {
        for (int in = 0; in < A2M_NUM_INPUTS; ++in)
            a2m_dsp_release_all(g_dsp[in], &g_out[in], 0);
        write_all(midi, frames);
        atomic_store(&g_flush, 2);
        return 0;
    }
    unsigned rate = atomic_exchange(&g_new_rate, 0);
    if (rate) {
        for (int in = 0; in < A2M_NUM_INPUTS; ++in)
            a2m_dsp_set_samplerate(g_dsp[in], rate, &g_out[in]);
        write_all(midi, frames);
    }
    a2m_params_t base, params[A2M_NUM_INPUTS];
    int connected[A2M_NUM_INPUTS];
    get_params(&base);
    for (int in = 0; in < A2M_NUM_INPUTS; ++in)
        connected[in] = jack_port_connected(g_input[in]) > 0;
    split_params(&base, connected, params);
    for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
        // A detector whose outputs are all inactive returns at once (no analysis)
        a2m_dsp_set_params(g_dsp[in], &params[in]);
        a2m_dsp_process(g_dsp[in], jack_port_get_buffer(g_input[in], frames), frames, &g_out[in]);
    }
    write_all(midi, frames);
    return 0;
}

static int on_samplerate(jack_nframes_t rate, void* arg) {
    (void)arg;
    atomic_store(&g_new_rate, rate);
    return 0;
}

uint8_t start() {
    if (g_client)
        return 1;
    jack_status_t status;
    g_client = jack_client_open(A2M_CLIENT_NAME, JackNoStartServer, &status);
    if (!g_client) {
        fprintf(stderr, "libzynaudio2midi: Failed to open JACK client (0x%02x)\n", status);
        return 0;
    }
    int ports_ok = 1;
    for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
        char name[16];
        if (in)
            snprintf(name, sizeof(name), "input_%d", in + 1);
        else
            snprintf(name, sizeof(name), "input");
        g_dsp[in] = a2m_dsp_new(jack_get_sample_rate(g_client));
        g_input[in] = jack_port_register(g_client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
        ports_ok &= g_dsp[in] != NULL && g_input[in] != NULL;
    }
    for (int o = 0; o < A2M_NUM_OUTPUTS; ++o) {
        char name[16];
        if (o)
            snprintf(name, sizeof(name), "midi_out_%d", o + 1);
        else
            snprintf(name, sizeof(name), "midi_out");
        g_midi_out[o] = jack_port_register(g_client, name, JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
        ports_ok &= g_midi_out[o] != NULL;
    }
    atomic_store(&g_flush, 0);
    atomic_store(&g_new_rate, 0);
    if (!ports_ok || jack_set_process_callback(g_client, on_process, NULL) ||
        jack_set_sample_rate_callback(g_client, on_samplerate, NULL) || jack_activate(g_client)) {
        fprintf(stderr, "libzynaudio2midi: Failed to start JACK client\n");
        jack_client_close(g_client);
        g_client = NULL;
        for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
            a2m_dsp_free(g_dsp[in]);
            g_dsp[in] = NULL;
        }
        return 0;
    }
    return 1;
}

void stop() {
    if (!g_client)
        return;
    // Let the process thread send note off for held notes (up to 200 ms)
    atomic_store(&g_flush, 1);
    for (int i = 0; i < 40 && atomic_load(&g_flush) != 2; ++i)
        usleep(5000);
    jack_deactivate(g_client);
    jack_client_close(g_client);
    g_client = NULL;
    for (int o = 0; o < A2M_NUM_OUTPUTS; ++o)
        g_midi_out[o] = NULL;
    for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
        g_input[in] = NULL;
        a2m_dsp_free(g_dsp[in]);
        g_dsp[in] = NULL;
    }
}

uint8_t isRunning() {
    return g_client != NULL;
}

void setOnsetThreshold(uint8_t channel, float db) {
    if (channel < A2M_NUM_INPUTS)
        atomic_store(&g_onset[channel], clampf(db, -80.0f, 0.0f));
}

float getOnsetThreshold(uint8_t channel) {
    return channel < A2M_NUM_INPUTS ? atomic_load(&g_onset[channel]) : 0.0f;
}

void setReleaseThreshold(uint8_t channel, float db) {
    if (channel < A2M_NUM_INPUTS)
        atomic_store(&g_release[channel], clampf(db, -90.0f, 0.0f));
}

float getReleaseThreshold(uint8_t channel) {
    return channel < A2M_NUM_INPUTS ? atomic_load(&g_release[channel]) : 0.0f;
}

void setNoiseFilter(uint8_t channel, float value) {
    if (channel < A2M_NUM_INPUTS)
        atomic_store(&g_noise[channel], clampf(value, 0.0f, 100.0f));
}

float getNoiseFilter(uint8_t channel) {
    return channel < A2M_NUM_INPUTS ? atomic_load(&g_noise[channel]) : 0.0f;
}

void setOutputActive(uint8_t output, uint8_t active) {
    if (output < A2M_NUM_OUTPUTS)
        atomic_store(&g_active[output], active ? 1 : 0);
}

uint8_t getOutputActive(uint8_t output) {
    return output < A2M_NUM_OUTPUTS ? atomic_load(&g_active[output]) : 0;
}

void setOutputSource(uint8_t output, uint8_t input) {
    if (output < A2M_NUM_OUTPUTS && input < A2M_NUM_INPUTS)
        atomic_store(&g_source[output], input);
}

uint8_t getOutputSource(uint8_t output) {
    return output < A2M_NUM_OUTPUTS ? atomic_load(&g_source[output]) : 0;
}

void setPolyphonic(uint8_t output, uint8_t poly) {
    if (output < A2M_NUM_OUTPUTS)
        atomic_store(&g_poly[output], poly ? 1 : 0);
}

uint8_t getPolyphonic(uint8_t output) {
    return output < A2M_NUM_OUTPUTS ? atomic_load(&g_poly[output]) : 0;
}

void setPitchBend(uint8_t output, uint8_t enable) {
    if (output < A2M_NUM_OUTPUTS)
        atomic_store(&g_bend[output], enable ? 1 : 0);
}

uint8_t getPitchBend(uint8_t output) {
    return output < A2M_NUM_OUTPUTS ? atomic_load(&g_bend[output]) : 0;
}

void setBendRange(uint8_t output, float semitones) {
    if (output < A2M_NUM_OUTPUTS)
        atomic_store(&g_bend_range[output], clampf(semitones, 1.0f, 24.0f));
}

float getBendRange(uint8_t output) {
    return output < A2M_NUM_OUTPUTS ? atomic_load(&g_bend_range[output]) : 0.0f;
}

// Append the events of one block to the offline event list, merging outputs and detectors in time order
static uint32_t append_events(const a2m_out_t* out, uint32_t offset, a2m_offline_event_t* events, uint32_t count,
                              uint32_t max_events) {
    uint32_t idx[A2M_NUM_INPUTS][A2M_NUM_OUTPUTS] = {{0}};
    while (count < max_events) {
        int bi = -1, bo = -1;
        for (int in = 0; in < A2M_NUM_INPUTS; ++in)
            for (int o = 0; o < A2M_NUM_OUTPUTS; ++o)
                if (idx[in][o] < out[in].count[o] &&
                    (bi < 0 || out[in].ev[o][idx[in][o]].frame < out[bi].ev[bo][idx[bi][bo]].frame))
                    bi = in, bo = o;
        if (bi < 0)
            break;
        const a2m_event_t* e = &out[bi].ev[bo][idx[bi][bo]++];
        events[count].frame = offset + e->frame;
        events[count].output = bo;
        memcpy(events[count].data, e->data, 3);
        ++count;
    }
    return count;
}

uint32_t analyse(const float* input1, const float* input2, uint32_t frames, uint32_t rate, uint32_t block,
                 uint8_t outputs, a2m_offline_event_t* events, uint32_t max_events) {
    if (!block)
        return 0;
    const float* in_buf[A2M_NUM_INPUTS] = {input1, input2};
    a2m_dsp_t* dsp[A2M_NUM_INPUTS];
    static a2m_out_t out[A2M_NUM_INPUTS];
    a2m_params_t base, params[A2M_NUM_INPUTS];
    int connected[A2M_NUM_INPUTS];
    get_params(&base);
    for (int o = 0; o < A2M_NUM_OUTPUTS; ++o)
        base.out[o].active = (outputs >> o) & 1;
    for (int in = 0; in < A2M_NUM_INPUTS; ++in)
        connected[in] = in_buf[in] != NULL;
    split_params(&base, connected, params);
    for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
        dsp[in] = a2m_dsp_new(rate);
        if (!dsp[in]) {
            for (int j = 0; j < in; ++j)
                a2m_dsp_free(dsp[j]);
            return 0;
        }
        a2m_dsp_set_params(dsp[in], &params[in]);
    }
    uint32_t count = 0;
    for (uint32_t pos = 0; pos < frames + block; pos += block) {
        uint32_t offset = pos < frames ? pos : frames;
        for (int in = 0; in < A2M_NUM_INPUTS; ++in) {
            if (pos >= frames)
                a2m_dsp_release_all(dsp[in], &out[in], 0); // End of buffer
            else if (in_buf[in])
                a2m_dsp_process(dsp[in], in_buf[in] + pos, frames - pos < block ? frames - pos : block, &out[in]);
            else
                memset(out[in].count, 0, sizeof(out[in].count));
        }
        count = append_events(out, offset, events, count, max_events);
    }
    for (int in = 0; in < A2M_NUM_INPUTS; ++in)
        a2m_dsp_free(dsp[in]);
    return count;
}
