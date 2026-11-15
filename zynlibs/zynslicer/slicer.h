/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: zynslicer Library
 *
 * Library providing a sample slicer as a Jack connected device. Each player
 * holds one sample split into slices, and each slice is triggered by its own
 * MIDI note on the player's MIDI channel.
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

#include <stdint.h> // Provides fixed width integer definitions

#define MAX_PLAYERS 16  // One player per MIDI channel
#define MAX_SLICES 127  // One slice per MIDI note 1..127
#define MAX_VOICES 16   // Maximum quantity of simultaneous voices per player
#define MIN_FRAMES 4096 // Minimum quantity of frames to allow in audio files
#define MAX_TUNE 48     // Maximum slice tuning in semitones, up or down

// Slice playback flags (one-shot when no flag is set)
#define SLICE_FLAG_GATE 0x01    // Note-off stops the slice
#define SLICE_FLAG_LOOP 0x02    // Repeat the slice until note-off

enum ERROR {
    ERROR_SUCCESS,      // No error
    ERROR_EXISTS,       // Already exists
    ERROR_RANGE,        // Parameter out of range
    ERROR_CREATE,       // Cannot create object
    ERROR_PORT,         // Cannot create port
    ERROR_OPEN,         // Error opening file
    ERROR_ACTIVATE,     // Cannot activate jack
    ERROR_SRC,          // Error during samplerate conversion
};

enum MIDI_COMMANDS {
    MIDI_NOTE_OFF   = 0x80,
    MIDI_NOTE_ON    = 0x90,
};

// ----------------------------------------------------------------------------
// Library management
// ----------------------------------------------------------------------------

/** @brief  Initialise the library: create and activate the JACK client
    @retval int Error code
*/
int init();

/** @brief  Remove all players and close the JACK client
*/
void end();

/** @brief  Get the JACK client name
    @retval const char* JACK client name
*/
const char* getJackname();

/** @brief  Create a player
    @param  channel MIDI channel for the new player, or 255 for the first free one
    @retval uint8_t MIDI channel of the player, or 255 on error
    @note   If the requested channel is in use, the first free one is used.
*/
uint8_t addPlayer(uint8_t channel);

/** @brief  Remove a player, its sample and its slices
    @param  channel MIDI channel
    @retval uint8_t Error code
*/
uint8_t removePlayer(uint8_t channel);

/** @brief  Get the quantity of frames in an audio file
    @param  path Full (or relative) path and filename
    @retval uint32_t Quantity of frames or 0 on error
*/
uint32_t getFileFrames(const char* path);

// ----------------------------------------------------------------------------
// Sample and slices
// ----------------------------------------------------------------------------

/** @brief  Set player polyphony
    @param  channel MIDI channel
    @param  voices Quantity of simultaneous voices (1..MAX_VOICES)
    @retval uint8_t Error code
*/
uint8_t setPolyphony(uint8_t channel, uint8_t voices);

/** @brief  Load a sample into a player, removing its slices
    @param  channel MIDI channel
    @param  path Full (or relative) path and filename
    @param  start Start frame in source file
    @param  end End frame in source file (0 for end of file)
    @param  quality Re-sample quality (0..4)
    @retval uint8_t Error code
    @note   Slice positions are relative to the start of the cropped sample.
*/
uint8_t loadSample(uint8_t channel, const char* path, uint32_t start, uint32_t end, uint8_t quality);

/** @brief  Unload the sample and all slices from a player
    @param  channel MIDI channel
    @retval uint8_t Error code
*/
uint8_t unloadSample(uint8_t channel);

/** @brief  Get the quantity of source frames in the loaded sample crop
    @param  channel MIDI channel
    @retval uint32_t Quantity of frames or 0
*/
uint32_t getSampleFrames(uint8_t channel);

/** @brief  Define a slice, or update it without stopping its voices
    @param  channel MIDI channel
    @param  note MIDI note that triggers the slice (1..127)
    @param  start Start frame in source sample crop
    @param  end End frame in source sample crop
    @param  gain Linear gain factor
    @param  flags Playback flags (SLICE_FLAG_*)
    @retval uint8_t Error code
*/
uint8_t setSlice(uint8_t channel, uint8_t note, uint32_t start, uint32_t end,
                 float gain, uint8_t flags);

/** @brief  Tune a slice, changing its pitch and playback speed together
    @param  channel MIDI channel
    @param  note MIDI note of the slice (1..127)
    @param  semitones Tuning in semitones, fractions for cents (clamped to +/-MAX_TUNE)
    @retval uint8_t Error code
    @note   +12 plays an octave higher at double speed. Playing voices follow
            immediately. New slices start untuned; updating a slice with
            setSlice() keeps its tuning.
*/
uint8_t setSliceTune(uint8_t channel, uint8_t note, float semitones);

/** @brief  Remove all slices from a player
    @param  channel MIDI channel
    @retval uint8_t Error code
*/
uint8_t clearSlices(uint8_t channel);

// ----------------------------------------------------------------------------
// Playback
// ----------------------------------------------------------------------------

/** @brief  Play a slice without MIDI input, as a note-on would
    @param  channel MIDI channel
    @param  note MIDI note of slice
    @param  velocity MIDI velocity (1..127)
    @retval uint8_t Error code
*/
uint8_t auditionSlice(uint8_t channel, uint8_t note, uint8_t velocity);

/** @brief  Release a slice as a MIDI note-off would (gate and loop slices fade out)
    @param  channel MIDI channel
    @param  note MIDI note of slice
    @retval uint8_t Error code
*/
uint8_t releaseSlice(uint8_t channel, uint8_t note);

/** @brief  Fade out all active voices
    @param  channel MIDI channel
    @retval uint8_t Error code
*/
uint8_t stopSlices(uint8_t channel);

/** @brief  Get active voices and their playback progress
    @param  channel MIDI channel
    @param  notes Array to receive MIDI notes
    @param  progress Array to receive progress through the slice (0.0..1.0)
    @param  order Array to receive voice start order (higher is newer)
    @param  max Maximum quantity of entries to write
    @retval uint8_t Quantity of active voices written
*/
uint8_t getSlicePlayheads(uint8_t channel, uint8_t* notes, float* progress,
                          uint32_t* order, uint8_t max);
