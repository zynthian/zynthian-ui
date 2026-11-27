/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio to MIDI converter (zynaudio2midi)
 *
 * JACK client with one audio input and one MIDI output that converts
 * the notes played into the input to MIDI note on / off and, optionally,
 * pitch bend (channel 1).
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

#define A2M_CLIENT_NAME "audio2midi" // JACK client, ports: "input" (audio), "midi_out" (MIDI)

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

/** @brief  Set the onset threshold: note on when a note's level rises above it
 *   @param  db Level in dBFS RMS (-80..0)
 */
void setOnsetThreshold(float db);
float getOnsetThreshold();

/** @brief  Set the release threshold: note off when a note's level falls below it
 *   @param  db Level in dBFS RMS (-90..0), limited to the onset threshold
 */
void setReleaseThreshold(float db);
float getReleaseThreshold();

/** @brief  Select monophonic or polyphonic detection. Held notes are released when changed.
 *   @param  poly 0: monophonic, 1: polyphonic
 */
void setPolyphonic(uint8_t poly);
uint8_t getPolyphonic();

/** @brief  Set the noise filter: higher values reject more noise (false notes) but react slower
 *   @param  value 0..100
 */
void setNoiseFilter(float value);
float getNoiseFilter();

/** @brief  Enable pitch bend (monophonic only): gradual pitch movement of the held note within the bend range,
 *          e.g. string bends, is sent as pitch bend instead of a new note
 *   @param  enable 1 to enable
 */
void setPitchBend(uint8_t enable);
uint8_t getPitchBend();

/** @brief  Set the pitch bend range, which must match the receiving synth's
 *   @param  semitones 1..24 (default 2)
 */
void setBendRange(float semitones);
float getBendRange();

/** @brief  Event produced by analyse() */
typedef struct {
    uint32_t frame; // Sample offset from the start of the analysed buffer
    uint8_t data[3];
} a2m_offline_event_t;

/** @brief  Analyse a buffer offline (no JACK) with the current parameters, e.g. for tests
 *   @param  buffer Audio samples
 *   @param  frames Quantity of samples
 *   @param  rate Samplerate in Hz
 *   @param  block Processing block size (like a JACK period)
 *   @param  events Buffer for the produced events, held notes are released at the end
 *   @param  max_events Size of events buffer
 *   @retval uint32_t Quantity of events written
 */
uint32_t analyse(const float* buffer, uint32_t frames, uint32_t rate, uint32_t block,
                 a2m_offline_event_t* events, uint32_t max_events);
