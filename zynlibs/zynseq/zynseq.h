/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020 Brian Walton <brian@riban.co.uk>
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

/*  This file declares the library interface. Only _public_ methods are exposed here.
    Pattern operations apply the currently selected pattern.
    Selecting a pattern that does not exist will create it.
    Empty patterns do not get saved to file.
    Sequence operations act on the sequence indexed by the request.
    Acting on a non existant sequence will create it.
    List of active events (to allow silencing).
    The methods exposed here provide a simplified interface to the hierchical step sequencer classes.
    Those modules are:
        PatternManager:
            Map of patterns indexed by number, Map of sequences, indexed by number, list of players, JACK client (pointer should not use this). Tempo.
        Step Event:
            Individual step within a pattern
            start, duration, command, value1start, value2start, value1end, value2end, progress
        Pattern:
            Organises events into relative time.
            List of events, clock divisor, quantity of steps
        Sequence:
            Organises patterns into time.
            MIDI channel, JACK output, Map of patterns, indexed by start position
            Creates a schedule of events from a sequence. Sends events to StepJackClient at correct time.
            Play status, Play position
        
    Call init() to initialise JACK client
    Call end() to exit //!@todo Can this be done automatically by atexit()
*/

#include "constants.h"
#include "timebase.h"
#include <cstdint>

//-----------------------------------------------------------------------------
// Library Initialization
//-----------------------------------------------------------------------------
#ifdef __cplusplus
extern "C"
{
#endif


// ** Library management functions **

/** @brief  Initialise JACK client
    @@note  Call init() before using other library methods
    @retval bool True on success
*/
bool  init();

/** @brief  Enable debug output
*   @param  bEnable True to enable debug output
*/
void debug(bool bEnable);

/** @brief  Load sequences and patterns from file
*   @param  filename Full path and filename
*   @retval bool True on success
*/
bool load(char* filename);

/** @brief  Save sequences and patterns from file
*   @param  filename Full path and filename
*/
void save(char* filename);


// ** Direct MIDI interface **

/** @brief  Play a note
*   @param  note MIDI note number
*   @param  velocity MIDI velocity
*   @param  channel MIDI channel
*   @parm   duration Duration of note in milliseconds (0 to send note on only)
*/
void playNote(uint8_t note, uint8_t velocity, uint8_t channel, uint32_t duration = 0);

/** @brief  Send MIDI START message
*/
void sendMidiStart();

/** @brief  Send MIDI STOP message
*/
void sendMidiStop();

/** @brief  Send MIDI CONTINUE message
*/
void sendMidiContinue();

/** @brief  Send MIDI song position message
*/
void sendMidiSongPos(uint16_t pos);

/** @brief  Send MIDI song select message
*/
void sendMidiSong(uint32_t pos);

/** @brief  Send MIDI CLOCK message
*/
void sendMidiClock();

/** @brief  Get playing state
*   @retval bool True if any sequence is playing
*/
bool isPlaying();

/** @brief  Get song playing state
*   @retval bool True if song is playing
*/
bool isSongPlaying();

/** @brief  Get MIDI channel used for external trigger of sequences
*   @retval uint8_t MIDI channel
*/
uint8_t getTriggerChannel();

/** @brief  Set MIDI channel used for external trigger of sequences
*   @param channel MIDI channel
*/
void setTriggerChannel(uint8_t channel);

/** @brief  Get MIDI note number used to trigger sequence
*   @param  sequence Index of sequence
*   @retval uint8_t MIDI note number
*/
uint8_t getTriggerNote(uint32_t sequence);

/** @brief  Set MIDI note number used to trigger sequence
*   @param  sequence Index of sequence
*   @param  note MIDI note number [0xFF for none]
*/
void setTriggerNote(uint32_t sequence, uint8_t note);

// ** Pattern management functions - pattern events are quantized to steps **

/** @brief  Select active pattern
*   @note   All subsequent pattern methods act on this pattern
*   @note   Pattern is created if it does not exist
*   @param  pattern Index of pattern to select
*/
void selectPattern(uint32_t pattern);

/** @brief  Get quantity of steps in selected pattern
*   @retval uint32_t Quantity of steps
*/
uint32_t getSteps();

/** @brief  Set quantity of steps in selected pattern
*   @param  steps Quantity of steps
*/
void setSteps(uint32_t steps);

/** @brief  Get quantity of beats in selected pattern
*   @retval uint32_t Quantity of beats
*/
uint32_t getBeatsInPattern();

/** @brief  Set quantity of beats in selected pattern
*   @param  beats Quantity of beats
*/
void setBeatsInPattern(uint32_t beats);

/** @brief  Get pattern length in clock cycles
*   @param  pattern Index of pattern
*   returns Length in clock cycles
*/
uint32_t getPatternLength(uint32_t pattern);

/** @brief  Get clock divisor
*   @retval uint32_t Clock divisor
*/
uint32_t getClocksPerStep();

/** @brief  Set clock divisor
*   @param  divisor Clock divisor
*/
void setClocksPerStep(uint32_t divisor);

/** @brief  Get steps per beat
*   @retval uint32_t Steps per beat
*/
uint32_t getStepsPerBeat();

/** @brief  Set steps per beat
*   @param  steps Steps per beat
*/
void setStepsPerBeat(uint32_t steps);

/** @brief  Get beat type (time signature denominator) for current pattern
*   @retval uint8_t Beat type (power of 2)
*/
uint8_t getBeatType();

/** @brief  Set beat type (time signature denominator) for current pattern
*   @param  beatType Beat type (power of 2)
*/
void setBeatType(uint8_t beatType);

/** @brief  Add note to pattern
*   @param  step Index of step at which to add note
*   @param  note MIDI note number
*   @param  velocity MIDI velocity value
*   @param  duration Quantity of steps note should play for
*/
void addNote(uint32_t step, uint8_t note, uint8_t velocity, uint32_t duration);

/** @brief  Removes note from pattern
*   @param  step Index of step at which to remove note
*   @param  note MIDI note number to remove
*/
void removeNote(uint32_t step, uint8_t note);

/** @brief  Get velocity of note in pattern
*   @param  step Index of step at which note resides
*   @param  note MIDI note number
*/
uint8_t getNoteVelocity(uint32_t step, uint8_t note);

/** @brief  Set velocity of note
*   @param  step Index of step at which note resides
*   @param  note MIDI note number
*   @param  velocity MIDI velocity
*/
void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity);

/** @brief  Get duration of note
*   @param  position Index of step at which note starts
*   @note   note MIDI note number
*   @retval uint32_t Duration in steps or 0 if note does not exist
*/
uint32_t getNoteDuration(uint32_t step, uint8_t note);

/** @brief  Transpose pattern
*   @param  value +/- quantity of notes to transpose
*/
void transpose(int8_t value);

/** @brief  Clears pattern
*/
void clear();

/** @brief  Copy pattern
*   @param  source Index of pattern from which to copy
*   @param  destination Index of pattern to which to copy
*/
void copyPattern(uint32_t source, uint32_t destination);

/** @brief  Set MIDI input channel
*   @param  channel MIDI channel [0..16]
*   @note   >16 to disable MIDI input
*/
void setInputChannel(uint8_t channel);

/** @brief  Get MIDI input channel
*   @retval uint8_t MIDI channel [0..15, 0xFF if disabled]
*/
uint8_t getInputChannel();

/** @brief  Set scale used by pattern editor for current pattern
*   @param  scale Index of scale
*/
void setScale(uint32_t scale);

/** @brief  Get scale used by pattern editor for current pattern
*   @retval uint32_t Index of scale
*/
uint32_t getScale();

/** @brief  Set scale tonic (root note) used by pattern editor for current pattern
*   @param  tonic Scale tonic
*/
void setTonic(uint8_t tonic);

/** @brief  Get scale tonic (root note) used by pattern editor for current pattern
*   @retval uint8_t Tonic
*/
uint8_t getTonic();

/** @brief  Check if pattern has changed since last check
*   @retval bool True if pattern has changed
*/
bool isModified();

// ** Sequence management functions **

/** @brief  Add pattern to a sequence
*   @param  sequence Index of sequence
*   @param  position Quantity of clock cycles from start of sequence at which to add pattern
*   @param  pattern Index of pattern
*   @param  force True to remove overlapping patterns, false to fail if overlapping patterns 
*   @retval True if pattern inserted
*/
bool addPattern(uint32_t sequence, uint32_t position, uint32_t pattern, bool force);

/** @brief  Remove pattern to a sequence
*   @param  sequence Index of sequence
*   @param  position Quantity of clock cycles from start of sequence from which to remove pattern
*/
void removePattern(uint32_t sequence, uint32_t position);

/** @brief  Get index of pattern within a sequence
*   @param  sequence Index of sequence
*   @param  position Quantity of clock cycles from start of sequence
*   @retval uint32_t Pattern index or -1 if not found
*/
uint32_t getPattern(uint32_t sequence, uint32_t position);

/** @brief  Set sequence MIDI channel
*   @param  sequence Sequence ID
*   @param  channel MIDI channel
*/
void setChannel(uint32_t sequence, uint8_t channel);

/** @brief  Get sequence MIDI channel
*   @param  sequence Sequence ID
*   @retval uint8_t MIDI channel
*/
uint8_t getChannel(uint32_t sequence);

/** @brief  Set sequence JACK output
*   @param  sequence Sequence ID
*   @param  output JACK output
*/
void setOutput(uint32_t sequence, uint8_t output);

/** @brief  Get current play mode for a sequence
*   @param  sequence Sequence ID
*   @retval uint8_t Play mode [DISABLED | ONESHOT | LOOP | ONESHOTALL | LOOPALL]
*/
uint8_t getPlayMode(uint32_t sequence);

/** @brief  Set play mode of a sequence
*   @param  sequence Index of sequence to control
*   @param  mode Play mode [DISABLED | ONESHOT | LOOP | ONESHOTALL | LOOPALL]
*/
void setPlayMode(uint32_t sequence, uint8_t mode);

/** @brief  Get play state
*   @param  sequence Index of sequence
*   @retval uint8_t Play state [STOPPED | PLAYING | STOPPING]
*/
uint8_t getPlayState(uint32_t sequence);

/** @brief  Set play state
*   @param  sequence Index of sequence
*   @param  uint8_t Play state [STOPPED | PLAYING | STOPPING]
*/
void setPlayState(uint32_t sequence, uint8_t state);

/** @brief  Toggles play / stop
*   @retval uint32_t sequence
*/
void togglePlayState(uint32_t sequence);

/** @brief  Stops all sequences and songs
*/
void stop();

/** @brief  Get the currently playing clock cycle
*   @param  Sequence ID
*   @retval uint32_t Playhead position in clock cycles
*/
uint32_t getPlayPosition(uint32_t sequence);

/** @brief  Set the currently playing clock cycle
*   @param  Sequence ID
*   @param  clock Clock cycle to position play head
*/
void setPlayPosition(uint32_t sequence, uint32_t clock);

/** @brief  Get length of sequence in clock cycles
*   @param  sequence Sequence ID
*   @retval uint32_t Quantity of clock cycles in sequence
*/
uint32_t getSequenceLength(uint32_t sequence);

/** @brief  Remove all patterns from sequence
*   @param  sequence Sequence number
*/
void clearSequence(uint32_t sequence);

/** @brief  Get the position of playhead within pattern
*   @param  sequence Sequence number
*   @retval uint32_t Quantity of steps from start of pattern
*/
uint32_t getStep(uint32_t sequence);


/** @brief  Get sequence group
*   @param  sequence Sequence number
*   @retval uint8_t Group
*/
uint8_t getGroup(uint32_t sequence);

/** @brief  Set sequence group
*   @param  sequence Sequence number
*   @param group Group index
*/
void setGroup(uint32_t sequence, uint8_t group);

/** @brief  Get MIDI channel used to send sequence play status, e.g. to light controller pads
*   @param  sequence Index of sequence
*   @retval uint8_t MIDI channel [0..15, 255 for none]
*/
uint8_t getTallyChannel(uint32_t sequence);

/** @brief  Set MIDI channel used to send sequence play status, e.g. to light controller pads
*   @param  sequence Index of sequence
*   @param channel MIDI channel [0..15, 255 for none]
*/
void setTallyChannel(uint32_t sequence, uint8_t channel);

/** @brief  Set MIDI note used to send sequence play status, e.g. to light controller pads
*   @param  sequence Index of sequence
*   @param note MIDI note [0..127]
*/
void setTallyNote(uint32_t sequence, uint8_t note);

/** @brief  Get MIDI note used to send sequence play status, e.g. to light controller pads
*   @param  sequence Index of sequence
*   @retval uint8_t MIDI note [0..127]
*/
uint8_t getTallyNote(uint32_t sequence);


// ** Song management functions **

/** @brief  Add track to song
*   @param  song Song index
*   @retval uint32_t Index of new track
*/
uint32_t addTrack(uint32_t song);

/** @brief  Remove track from song
*   @param  song Song index
*   @param  track Track index
*/
void removeTrack(uint32_t song, uint32_t track);

/** @brief  Add tempo to song tempo map
*   @param  song Song index
*   @param  tempo Tempo in BPM
*   @param  measure Measure (bar) of song at which to add tempo change [Optional - default: 1]
*   @param  tick Tick within measure at which to add tempo change [Optional - default: 0]
*/
void setTempo(uint32_t song, uint32_t tempo, uint16_t measure=1, uint16_t tick=0);

/** @brief  Get tempo at position within song
*   @param  song Song index
*   @param  measure Measure (bar) of song at which to get tempo [Optional - default: 1]
*   @param  tick Tick within measure at which to get tempo [Optional - default: 0]
'   @todo   getTempo without time parameter should get time at current play position???
*   @retval uint32_t Tempo in BPM
*/
uint32_t getTempo(uint32_t song, uint16_t measure=1, uint16_t tick=0);

/** @brief  Add time signature to song
*   @param  song Song index
*   @param  beats Beats per bar (numerator)
*   @param  type Beat type (denominator)
*   @param  measure Measure (bar) of song at which to add tempo change [Optional - default: 1]
*   @param  tick Tick within measure at which to add tempo change [Optional - default: 0]
*/
void setTimeSig(uint32_t song, uint8_t beats, uint8_t type, uint16_t measure);

/** @brief  Get time signature at position within song
*   @param  song Song index
*   @param  measure Measure (bar) of song at which to time signature
*   @retval uint16_t Time signature - MSB numerator, LSB denominator
*/
uint16_t getTimeSig(uint32_t song, uint16_t measure);

/** @brief  Get quantity of tracks in song
*   @param  song Song index
*   @retval uint32_t Quantity of tracks
*/
uint32_t getTracks(uint32_t song);

/** @brief  Get song track sequence ID
*   @param  song Song index
*   @param  track Track index
*   @retval uint32_t Sequence index
*/
uint32_t getSequence(uint32_t song, uint32_t track);

/** @brief  Clears song
*   @param  song Song index
*/
void clearSong(uint32_t song);

/** @brief  Copy song
*   @param  source Index of song from which to copy
*   @param  destination Index of song to which to copy
*/
void copySong(uint32_t source, uint32_t destination);

/** @brief  Get position of playhead within song
*   @retval uint32_t Position in clock cycles
*   @note   This is global for all songs
*/
uint32_t getSongPosition();

/** @brief  Set position of playhead within song
*   @param  position Position of playhead in clock cycles
*/
void setSongPosition(uint32_t position);

/** @brief  Sets the song position to the start of the current measure (bar)
*/
void setSongToStartOfMeasure();

/** @brief  Get bar length / loop duration
*   @param  song Song index
*   @retval uint32_t Clock cycles per bar / loop
*/
uint32_t getBarLength(uint32_t song);

/** @brief  Set bar length / loop duration
*   @param  song Song index
*   @param  period Clock cycles per bar / loop
*/
void setBarLength(uint32_t song, uint32_t period);

/** @brief  Start song playing - resume from current position
*   @param  bFast True to start playing immediately. False to wait for next sync pulse.
*/
void startSong(bool bFast = false);

/** @brief  Pause song - do not recue
*/
void pauseSong();

/** @brief  Stop song playing
*   @note   Sets play position to start of song
*/
void stopSong();

/** @brief  Toggle song state between play and pause
*/
void toggleSong();

/** @brief  Check if song is playing
*   @retval True if playing
*/
bool isSongPlaying();

/** @brief  Get current song
*   @retval uint32_t Index of selected song
*/
uint32_t getSong();

/** @brief  Select song
*   @param  song Index of song to select
*   @Note   Song 0 is reserved for pattern editor. Songs 1-128 may be selected with MIDI song select.
*   @todo   Limit quantity of songs to 128 (MIDI limit) and use appropriate sized data (uint8_t)
*/
void selectSong(uint32_t song);

/** @brief  Selects a track to solo, muting other tracks in song
*   @brief  song Index of song
*   @param  track Index of track to solo
*   @param  solo True to solo, false to clear solo
*/
void solo(uint32_t song, uint32_t track, int solo);

// ** Transport control **
/** @brief  Locate transport to frame
*   @param  frame Quantity of frames (samples) from start of song to locate
*/
void transportLocate(uint32_t frame);

/** @brief  Get frame offset at BBT position
*   @param  measure Measure (bar) [>0]
*   @param  beat Beat within bar [>0, <=beats per bar]
*   @param  tick Tick within beat [<ticks per beat]
*   @retval uint32_t Frames since start of song until requested position
*/
uint32_t transportGetLocation(uint32_t measure, uint32_t beat, uint32_t tick);

/** @brief  Register as timebase master
*   @retval bool True if successfully became timebase master
*/
bool transportRequestTimebase();

/** @brief Release timebase master
*/
void transportReleaseTimebase();

/** @brief  Start transport rolling
**/
void transportStart();

/** @brief  Stop transport rolling
*/
void transportStop();

/** @brief  Toggle between play and stop state
*/
void transportToggle();

/** @brief  Get play status
*   @retval uint8_t Status [JackTransportStopped | JackTransportRolling | JackTransportStarting]
*/
uint8_t transportGetPlayStatus();

/** @brief  Set tempo
*   @param  tempo Beats per minute
*   @todo   Using integer for tempo to simplify Python interface but should use float
*/
void transportSetTempo(uint32_t tempo);

/** @brief  get tempo
*   @retval uint32_t Tempo in beats per minute
*/
uint32_t transportGetTempo();
     
/** @brief  Set sync timeout
*   @param  timeout Quantity of microseconds to wait for slow sync clients at start of play
*/
void transportSetSyncTimeout(uint32_t timeout);

/** @brief  Set timebase map
*   @param  timebase Pointer to Timebase object to use for timebase map
*/
void transportSetTimebaseMap(Timebase* timebase);


#ifdef __cplusplus
}
#endif

