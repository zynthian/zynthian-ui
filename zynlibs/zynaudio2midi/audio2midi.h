/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio to MIDI converter (zynaudio2midi)
 *
 * JACK client with two audio inputs and two MIDI outputs that convert
 * the notes played into the inputs to MIDI note on / off and, optionally,
 * pitch bend (channel 1). Each output has its own mode.
 * With both inputs connected they are 2 independent channels (input 1 =>
 * output 1, input 2 => output 2). With one input connected, it feeds both
 * outputs (one detection). Nothing is analysed while no input is connected
 * or for inactive outputs, so the client costs nothing until it is used.
 * The JACK client only exists while the converter is started.
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

#define A2M_CLIENT_NAME "audio2midi" // JACK client, ports: "input", "input_2" (audio), "midi_out", "midi_out_2" (MIDI)
#define A2M_NUM_INPUTS 2             // Quantity of audio inputs
#define A2M_NUM_OUTPUTS 2            // Quantity of MIDI outputs, each with its own mode

/** @brief  Start the converter: open and activate the JACK client
 *   @retval uint8_t 1 on success (or already running), 0 on failure
 */
uint8_t start();

/** @brief  Stop the converter: send note off for held notes and close the JACK client */
void stop();

/** @brief  Check if the converter is running
 *   @retval uint8_t 1 if running
 */
uint8_t isRunning();

/** @brief  Set the onset threshold (all outputs): note on when a note's level rises above it
 *   @param  db Level in dBFS RMS (-80..0, default -60)
 */
void setOnsetThreshold(float db);
float getOnsetThreshold();

/** @brief  Set the release threshold (all outputs): note off when a note's level falls below it
 *   @param  db Level in dBFS RMS (-90..0, default -66), limited to the onset threshold
 */
void setReleaseThreshold(float db);
float getReleaseThreshold();

/** @brief  Set the noise filter (all outputs): higher values reject more noise (false notes) but react slower
 *   @param  value 0..100 (default 15)
 */
void setNoiseFilter(float value);
float getNoiseFilter();

/** @brief  Activate an output (e.g. when it is routed to a chain). Only active outputs fed by a connected input are
 *          analysed: detection runs once for each mode used by them, so an inactive output costs nothing.
 *          Held notes are released when deactivated.
 *   @param  output Output index (0..A2M_NUM_OUTPUTS-1)
 *   @param  active 1 to activate (default 0)
 */
void setOutputActive(uint8_t output, uint8_t active);
uint8_t getOutputActive(uint8_t output);

/** @brief  Select monophonic or polyphonic detection for an output. Held notes are released when changed.
 *          Polyphonic outputs all receive the same notes (pitch bend is monophonic only).
 *   @param  output Output index
 *   @param  poly 0: monophonic, 1: polyphonic
 */
void setPolyphonic(uint8_t output, uint8_t poly);
uint8_t getPolyphonic(uint8_t output);

/** @brief  Enable pitch bend for a (monophonic) output: gradual pitch movement of the held note within the bend
 *          range, e.g. string bends, is sent as pitch bend instead of a new note
 *   @param  output Output index
 *   @param  enable 1 to enable (default: on for output 0, off for output 1)
 */
void setPitchBend(uint8_t output, uint8_t enable);
uint8_t getPitchBend(uint8_t output);

/** @brief  Set the pitch bend range of an output, which must match the receiving synth's
 *   @param  output Output index
 *   @param  semitones 1..24 (default 2)
 */
void setBendRange(uint8_t output, float semitones);
float getBendRange(uint8_t output);

/** @brief  Event produced by analyse() */
typedef struct {
    uint32_t frame; // Sample offset from the start of the analysed buffer
    uint8_t output; // Output index
    uint8_t data[3];
} a2m_offline_event_t;

/** @brief  Analyse buffers offline (no JACK) with the current parameters, e.g. for tests
 *   @param  input1 Audio samples of input 1, NULL if not connected
 *   @param  input2 Audio samples of input 2, NULL if not connected
 *   @param  frames Quantity of samples (of each input)
 *   @param  rate Samplerate in Hz
 *   @param  block Processing block size (like a JACK period)
 *   @param  outputs Bitmask of the active outputs (bit 0: output 0), instead of setOutputActive()
 *   @param  events Buffer for the produced events (in time order, output 0 first for the same frame),
 *          held notes are released at the end
 *   @param  max_events Size of events buffer
 *   @retval uint32_t Quantity of events written
 */
uint32_t analyse(const float* input1, const float* input2, uint32_t frames, uint32_t rate, uint32_t block,
                 uint8_t outputs, a2m_offline_event_t* events, uint32_t max_events);
