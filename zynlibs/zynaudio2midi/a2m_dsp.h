/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio to MIDI converter - DSP core
 *
 * Detects notes in a mono audio signal and produces MIDI note on/off
 * (and optionally pitch bend) on A2M_OUTPUTS outputs, each with its own
 * mode. Outputs share the detection: one detector per mode in use.
 * No JACK dependency: the JACK glue (audio2midi.c) and the offline
 * test entry point both drive this core.
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

#pragma once

#include <stdint.h>

#define A2M_OUTPUTS 2      // Quantity of MIDI outputs
#define A2M_MAX_EVENTS 256 // Maximum quantity of MIDI events produced for each output by one call

typedef struct {
    uint32_t frame;  // Offset of the event (in samples) from the start of the processed block
    uint8_t data[3]; // MIDI message (note on / note off / pitch bend, MIDI channel 1)
} a2m_event_t;

/** @brief  Events produced by one call, for each output, in time order */
typedef struct {
    a2m_event_t ev[A2M_OUTPUTS][A2M_MAX_EVENTS];
    uint32_t count[A2M_OUTPUTS];
} a2m_out_t;

typedef struct a2m_dsp a2m_dsp_t;

/** @brief  Parameters of one output */
typedef struct {
    int active;       // 1: produce events (only outputs in use cost CPU). Held notes are released when deactivated.
    int poly;         // 0: monophonic, 1: polyphonic. Held notes are released when changed.
    int bend;         // 1: monophonic pitch bend follows the pitch of the held note (e.g. string bends)
    float bend_range; // Pitch bend range of the receiving synth in semitones (1..24)
} a2m_output_params_t;

/** @brief  Parameters, applied at the start of the next a2m_dsp_process call */
typedef struct {
    float onset_db;   // Note on when the note level rises above this (dBFS RMS)
    float release_db; // Note off when the note level falls below this (dBFS RMS), limited to onset_db
    float noise;      // Noise filter 0..100: higher values reject more noise but react slower
    a2m_output_params_t out[A2M_OUTPUTS];
} a2m_params_t;

/** @brief  Create a DSP instance (not RT safe). All outputs are inactive.
 *   @param  rate Samplerate in Hz
 *   @retval a2m_dsp_t* New instance or NULL on failure
 */
a2m_dsp_t* a2m_dsp_new(uint32_t rate);

/** @brief  Destroy a DSP instance (not RT safe) */
void a2m_dsp_free(a2m_dsp_t* dsp);

/** @brief  Change samplerate, releasing held notes (RT safe, no allocation)
 *   @param  dsp DSP instance
 *   @param  rate Samplerate in Hz
 *   @param  out Buffer for the note-off events (all at frame 0). Counts are reset first.
 */
void a2m_dsp_set_samplerate(a2m_dsp_t* dsp, uint32_t rate, a2m_out_t* out);

/** @brief  Set parameters (RT safe), applied on the next call to a2m_dsp_process */
void a2m_dsp_set_params(a2m_dsp_t* dsp, const a2m_params_t* params);

/** @brief  Process a block of audio (RT safe)
 *   @param  dsp DSP instance
 *   @param  in Audio samples
 *   @param  frames Quantity of samples
 *   @param  out Buffer for the produced MIDI events. Counts are reset first.
 */
void a2m_dsp_process(a2m_dsp_t* dsp, const float* in, uint32_t frames, a2m_out_t* out);

/** @brief  Send note off for all held notes and reset pitch bend, on all outputs (RT safe)
 *   @param  dsp DSP instance
 *   @param  out Buffer for the events. Counts are reset first.
 *   @param  frame Frame offset for the events
 */
void a2m_dsp_release_all(a2m_dsp_t* dsp, a2m_out_t* out, uint32_t frame);
