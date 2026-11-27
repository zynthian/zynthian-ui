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
#include <unistd.h>

static jack_client_t* g_client = NULL;
static jack_port_t* g_input = NULL;
static jack_port_t* g_midi_out = NULL;
static a2m_dsp_t* g_dsp = NULL;
static a2m_event_t g_events[A2M_MAX_EVENTS];

// Parameters, written by the UI thread, read by the JACK process thread
static _Atomic float g_onset = -40.0f;
static _Atomic float g_release = -50.0f;
static _Atomic float g_noise = 50.0f;
static atomic_int g_poly = 0;
static atomic_uint g_new_rate = 0; // Samplerate change requested by JACK, applied in process thread
static atomic_int g_flush = 0;     // 1: stop requested, release notes; 2: notes released

static float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static void get_params(a2m_params_t* p) {
    p->onset_db = atomic_load(&g_onset);
    p->release_db = atomic_load(&g_release);
    p->noise = atomic_load(&g_noise);
    p->poly = atomic_load(&g_poly);
}

static void write_events(void* buffer, uint32_t count, jack_nframes_t frames) {
    for (uint32_t i = 0; i < count; ++i) {
        jack_nframes_t frame = g_events[i].frame < frames ? g_events[i].frame : frames - 1;
        jack_midi_event_write(buffer, frame, g_events[i].data, 3);
    }
}

static int on_process(jack_nframes_t frames, void* arg) {
    (void)arg;
    void* midi = jack_port_get_buffer(g_midi_out, frames);
    jack_midi_clear_buffer(midi);
    if (atomic_load(&g_flush)) {
        write_events(midi, a2m_dsp_release_all(g_dsp, g_events, 0), frames);
        atomic_store(&g_flush, 2);
        return 0;
    }
    unsigned rate = atomic_exchange(&g_new_rate, 0);
    if (rate)
        write_events(midi, a2m_dsp_set_samplerate(g_dsp, rate, g_events), frames);
    a2m_params_t params;
    get_params(&params);
    a2m_dsp_set_params(g_dsp, &params);
    const float* in = jack_port_get_buffer(g_input, frames);
    write_events(midi, a2m_dsp_process(g_dsp, in, frames, g_events), frames);
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
    g_dsp = a2m_dsp_new(jack_get_sample_rate(g_client));
    g_input = jack_port_register(g_client, "input", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
    g_midi_out = jack_port_register(g_client, "midi_out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
    atomic_store(&g_flush, 0);
    atomic_store(&g_new_rate, 0);
    if (!g_dsp || !g_input || !g_midi_out || jack_set_process_callback(g_client, on_process, NULL) ||
        jack_set_sample_rate_callback(g_client, on_samplerate, NULL) || jack_activate(g_client)) {
        fprintf(stderr, "libzynaudio2midi: Failed to start JACK client\n");
        jack_client_close(g_client);
        g_client = NULL;
        a2m_dsp_free(g_dsp);
        g_dsp = NULL;
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
    g_input = g_midi_out = NULL;
    a2m_dsp_free(g_dsp);
    g_dsp = NULL;
}

uint8_t isRunning() {
    return g_client != NULL;
}

void setOnsetThreshold(float db) {
    atomic_store(&g_onset, clampf(db, -80.0f, 0.0f));
}

float getOnsetThreshold() {
    return atomic_load(&g_onset);
}

void setReleaseThreshold(float db) {
    atomic_store(&g_release, clampf(db, -90.0f, 0.0f));
}

float getReleaseThreshold() {
    return atomic_load(&g_release);
}

void setPolyphonic(uint8_t poly) {
    atomic_store(&g_poly, poly ? 1 : 0);
}

uint8_t getPolyphonic() {
    return atomic_load(&g_poly);
}

void setNoiseFilter(float value) {
    atomic_store(&g_noise, clampf(value, 0.0f, 100.0f));
}

float getNoiseFilter() {
    return atomic_load(&g_noise);
}

uint32_t analyse(const float* buffer, uint32_t frames, uint32_t rate, uint32_t block,
                 a2m_offline_event_t* events, uint32_t max_events) {
    a2m_dsp_t* dsp = a2m_dsp_new(rate);
    if (!dsp || !block)
        return 0;
    static a2m_event_t ev[A2M_MAX_EVENTS];
    a2m_params_t params;
    get_params(&params);
    a2m_dsp_set_params(dsp, &params);
    uint32_t count = 0;
    for (uint32_t pos = 0; pos < frames + block; pos += block) {
        uint32_t n, offset = pos < frames ? pos : frames;
        if (pos < frames) {
            uint32_t len = frames - pos < block ? frames - pos : block;
            n = a2m_dsp_process(dsp, buffer + pos, len, ev);
        } else {
            n = a2m_dsp_release_all(dsp, ev, 0); // End of buffer
        }
        for (uint32_t i = 0; i < n && count < max_events; ++i) {
            events[count].frame = offset + ev[i].frame;
            events[count].data[0] = ev[i].data[0];
            events[count].data[1] = ev[i].data[1];
            events[count].data[2] = ev[i].data[2];
            ++count;
        }
    }
    a2m_dsp_free(dsp);
    return count;
}
