/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020-2021 Brian Walton <brian@riban.co.uk>
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
    Acting on a sequence that does not exist will create it.
    The methods exposed here provide a simplified interface to the hierchical step sequencer classes.
    Those modules are:
        SequenceManager:
            Map of patterns indexed by number, Map of sequences, indexed by number, list of players, JACK client (pointer should not use this). Tempo.
        Step Event:
            Individual event within a pattern
        Pattern:
            Organises events into relative time
        Track:
            Organises patterns into relative time
        Sequence:
            A collection of tracks which will play synchronously
        Bank:
            A collection of sequences

    Call init() to initialise JACK client
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

/** @brief  Check if any changes have occured since last save
*   @retval bool True if changed since last save
*/
bool isModified();

/** @brief  Initialise JACK client
*   @param  bTimebaseMaster True to become timebase master (optional - Default: false)
*   @note   Call init() before using other library methods
*   @retval bool True on success
*/
bool init(bool bTimebaseMaster = false);

/** @brief  Enable debug output
*   @param  bEnable True to enable debug output
*/
void enableDebug(bool bEnable);

/** @brief  Load sequences and patterns from file
*   @param  filename Full path and filename
*   @retval bool True on success
*   @note   Pass invalid or empty filename to clear sequences (returns false)
*/
bool load(const char* filename);

/** @brief  Save sequences and patterns from file
*   @param  filename Full path and filename
*/
void save(const char* filename);

/** @brief  Get vertical zoom
*   @retval uint16_t Vertical zoom
*/
uint16_t getVerticalZoom();

/** @brief  Set vertical zoom
*   @param zoom Vertical zoom
*/
void setVerticalZoom(uint16_t zoom);

/** @brief  Get horizontal zoom
*   @retval uint16_t Horizontal zoom
*/
uint16_t getHorizontalZoom();

/** @brief  Set horizontal zoom
*   @param uint16_t Horizontal zoom
*/
void setHorizontalZoom(uint16_t zoom);


// ** Direct MIDI interface **
//!@todo Should direct MIDI output be removed because JACK clients can do that themselves?

/** @brief  Play a note
*   @param  note MIDI note number
*   @param  velocity MIDI velocity
*   @param  channel MIDI channel
*   @param  duration Duration of note in milliseconds (0 to send note on only) Maximum 1 minute
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

/** @brief  Send MIDI command
*   @param  status Status byte
*   @param  value1 Value 1 byte
*   @param  value2 Value 2 byte
*/
void sendMidiCommand(uint8_t status, uint8_t value1, uint8_t value2);

// ** Status **
/** @brief  Get MIDI channel used for external trigger of sequences
*   @retval uint8_t MIDI channel
*/
uint8_t getTriggerChannel();

/** @brief  Set MIDI channel used for external trigger of sequences
*   @param channel MIDI channel [0..15 or other value to disable MIDI trigger]
*/
void setTriggerChannel(uint8_t channel);

/** @brief  Get MIDI note number used to trigger sequence
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @retval uint8_t MIDI note number [0xFF for none]
*/
uint8_t getTriggerNote(uint8_t bank, uint8_t sequence);

/** @brief  Set MIDI note number used to trigger sequence
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @param  note MIDI note number [0xFF for none]
*/
void setTriggerNote(uint8_t bank, uint8_t sequence, uint8_t note);

// ** Pattern management functions - pattern events are quantized to steps **
//!@todo Current implementation selects a pattern then operates on it. API may be simpler to comprehend if patterns were acted on directly by passing the pattern index, e.g. clearPattern(index)

/** @brief  Enable MIDI input to add notes to current pattern
*   @param  enable True to enable MIDI input
*/
void enableMidiInput(bool enable);

/** @brief  Create a new pattern
*   @retval uint32_t Index of new pattern
*/
uint32_t createPattern();

/** @brief  Get quantity of patterns in a track
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @retval uint32_t quantity of patterns in track
*/
uint32_t getPatternsInTrack(uint8_t bank, uint8_t sequence, uint32_t track);

/** @brief  Get index of pattern within a track
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @param  position Quantity of clock cycles from start of sequence where pattern starts
*   @retval uint32_t Pattern index or -1 if not found
*/
uint32_t getPattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position);

/** @brief  Get index of pattern within a track
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @param  position Quantity of clock cycles from start of sequence that pattern spans
*   @retval uint32_t Pattern index or -1 if not found
*/
uint32_t getPatternAt(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position);

/** @brief  Select active pattern
*   @note   All subsequent pattern methods act on this pattern
*   @note   Pattern is created if it does not exist
*   @param  pattern Index of pattern to select
*/
void selectPattern(uint32_t pattern);

/** @brief  Get the index of the selected pattern
*   @retval uint32_t Index of pattern or -1 if not found
*/
uint32_t getPatternIndex();

/** @brief  Get quantity of steps in selected pattern
*   @retval uint32_t Quantity of steps
*/
uint32_t getSteps();

/** @brief  Get quantity of beats in selected pattern
*   @retval uint32_t Quantity of beats
*/
uint32_t getBeatsInPattern();

/** @brief  Set quantity of beats in selected pattern
*   @param  beats Quantity of beats
*   @note   Adjusts steps to match steps per beat
*/
void setBeatsInPattern(uint32_t beats);

/** @brief  Get pattern length in clock cycles
*   @param  pattern Index of pattern
*   returns Length in clock cycles
*/
uint32_t getPatternLength(uint32_t pattern);

/** @brief  Get clocks per step for selected pattern
*   @retval uint32_t Clock cycles per step
*/
uint32_t getClocksPerStep();

/** @brief  Get steps per beat from selected pattern
*   @retval uint32_t Steps per beat
*/
uint32_t getStepsPerBeat();

/** @brief  Set steps per beat
*   @param  steps Steps per beat [1,2,3,4,6,8,12,24]
*   @note   Calculates pattern length from beats in pattern
*/
void setStepsPerBeat(uint32_t steps);

/** @brief  Add note to selected pattern
*   @param  step Index of step at which to add note
*   @param  note MIDI note number
*   @param  velocity MIDI velocity value
*   @param  duration Quantity of steps note should play for
*   @retval bool True on success
*/
bool addNote(uint32_t step, uint8_t note, uint8_t velocity, uint32_t duration);

/** @brief  Removes note from selected pattern
*   @param  step Index of step at which to remove note
*   @param  note MIDI note number to remove
*/
void removeNote(uint32_t step, uint8_t note);

/** @brief  Get velocity of note in selected pattern
*   @param  step Index of step at which note resides
*   @param  note MIDI note number
*/
uint8_t getNoteVelocity(uint32_t step, uint8_t note);

/** @brief  Set velocity of note in selected pattern
*   @param  step Index of step at which note resides
*   @param  note MIDI note number
*   @param  velocity MIDI velocity
*/
void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity);

/** @brief  Get duration of note in selected pattern
*   @param  position Index of step at which note starts
*   @note   note MIDI note number
*   @retval uint32_t Duration in steps or 0 if note does not exist
*/
uint32_t getNoteDuration(uint32_t step, uint8_t note);

/** @brief  Transpose selected pattern
*   @param  value +/- quantity of notes to transpose
*/
void transpose(int8_t value);

/** @brief  Clears events from selected pattern
*   @note   Does not change other parameters such as pattern length
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

/** @brief  Set note used as rest when using MIDI input for pattern editing
*   @param  note MIDI note number [0..127]
*   @note   >127 to disable rest
*/
void setInputRest(uint8_t note);

/** @brief  Get note used as rest when using MIDI input for pattern editing
*   @retval uint8_t MIDI note number [0..127, 0xFF if disabled]
*/
uint8_t getInputRest();

/** @brief  Set scale used by pattern editor for selected pattern
*   @param  scale Index of scale
*/
void setScale(uint32_t scale);

/** @brief  Get scale used by pattern editor for selected pattern
*   @retval uint32_t Index of scale
*/
uint32_t getScale();

/** @brief  Set scale tonic (root note) for selected pattern (used by pattern editor)
*   @param  tonic Scale tonic
*/
void setTonic(uint8_t tonic);

/** @brief  Get scale tonic (root note) for selected pattern (used by pattern editor)
*   @retval uint8_t Tonic
*/
uint8_t getTonic();

/** @brief  Check if selected pattern has changed since last check
*   @retval bool True if pattern has changed
*/
bool isPatternModified();

/**    @brief    Get the reference note
*    @retval uint8_t MIDI note number
*    @note    May be used for position within user interface
*/
uint8_t getRefNote();

/**    @brief    Set the reference note
*    @param    MIDI note number
*    @note    May be used for position within user interface
*/
void setRefNote(uint8_t note);

/**    @brief    Get the last populated step
*    @retval    uint32_t Index of last populated step or -1 if empty
*    @note    This may allow checking for empty patterns or whether truncation will have an effect
*/
uint32_t getLastStep();

// ** Track management functions **

/** @brief  Get position of playhead within pattern in steps
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @retval uint32_t Quantity of steps from start of pattern to playhead
*   @todo   Function names confusing getPatternPlayhead / getStep (within Track)
*/
uint32_t getPatternPlayhead(uint8_t bank, uint8_t sequence, uint32_t track);

/** @brief  Add pattern to a track
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @param  position Quantity of clock cycles from start of track at which to add pattern
*   @param  pattern Index of pattern
*   @param  force True to remove overlapping patterns, false to fail if overlapping patterns 
*   @retval True if pattern inserted
*/
bool addPattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force);

/** @brief  Remove pattern from track
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @param  position Quantity of clock cycles from start of track from which to remove pattern
*/
void removePattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position);

/** @brief  Removes unused empty patterns
*/
void cleanPatterns();

/**	@brief	Toggle mute of track
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*/
void toggleMute(uint8_t bank, uint8_t sequence, uint32_t track);

/**	@brief	Get track mute state
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*	@retval	bool True if muted
*/
bool isMuted(uint8_t bank, uint8_t sequence, uint32_t track);


// ** Sequence management functions **

/** @brief  Set sequence MIDI channel
*   @param  bank Index of bank
*   @param  sequence Sequence ID
*   @param  track Index of track
*   @param  channel MIDI channel
*/
void setChannel(uint8_t bank, uint8_t sequence, uint32_t track, uint8_t channel);

/** @brief  Get track MIDI channel
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*   @retval uint8_t MIDI channel
*/
uint8_t getChannel(uint8_t bank, uint8_t sequence, uint32_t track);

/** @brief  Get current play mode for a sequence
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @retval uint8_t Play mode [DISABLED | ONESHOT | LOOP | ONESHOTALL | LOOPALL]
*/
uint8_t getPlayMode(uint8_t bank, uint8_t sequence);

/** @brief  Set play mode of a sequence
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @param  mode Play mode [DISABLED | ONESHOT | LOOP | ONESHOTALL | LOOPALL]
*/
void setPlayMode(uint8_t bank, uint8_t sequence, uint8_t mode);

/** @brief  Get play state
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @retval uint8_t Play state [STOPPED | STARTING | PLAYING | STOPPING]
*/
uint8_t getPlayState(uint8_t bank, uint8_t sequence);

/** @brief  Set play state
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @param  uint8_t Play state [STOPPED | STARTING | PLAYING | STOPPING]
*   @note   STARTING will reset to start of sequence. PLAYING resumes at last played position.
*   @note   If all sequences have stopped and no external clients have registered for transport then transport is stopped.
*/
void setPlayState(uint8_t bank, uint8_t sequence, uint8_t state);

/** @brief  Toggles starting / stopping
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*/
void togglePlayState(uint8_t bank, uint8_t sequence);

/** @brief  Get quantity of tracks in a sequence
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*/
size_t getTracksInSequence(uint8_t bank, uint8_t sequence);

/** @brief  Stops all sequences
*/
void stop();

/** @brief  Get the currently playing clock cycle
*   @param  bank Index of bank
*   @param  Sequence ID
*   @retval uint32_t Playhead position in clock cycles
*/
uint32_t getPlayPosition(uint8_t bank, uint8_t sequence);

/** @brief  Set the currently playing clock cycle
*   @param  bank Index of bank containing sequence
*   @param  sequence Index (sequence) of sequence within bank
*   @param  clock Clock cycle to position play head
*/
void setPlayPosition(uint8_t bank, uint8_t sequence, uint32_t clock);

/** @brief  Get length of sequence in clock cycles
*   @param  bank Index of bank
*   @param  sequence Sequence ID
*   @retval uint32_t Quantity of clock cycles in sequence
*/
uint32_t getSequenceLength(uint8_t bank, uint8_t sequence);

/** @brief  Remove all patterns from sequence
*   @param  bank Index of bank
*   @param  sequence Sequence number
*/
void clearSequence(uint8_t bank, uint8_t sequence);

/** @brief  Get sequence group
*   @param  bank Index of bank
*   @param  sequence Sequence number
*   @retval uint8_t Group
*/
uint8_t getGroup(uint8_t bank, uint8_t sequence);

/** @brief  Set sequence group
*   @param  bank Index of bank
*   @param  sequence Sequence number
*   @param  group Group index
*/
void setGroup(uint8_t bank, uint8_t sequence, uint8_t group);

/** @brief  Check if a sequence play state, group or mode has changed since last checked
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @retval bool True if changed
*/
bool hasSequenceChanged(uint8_t bank, uint8_t sequence);

/** @brief  Adds a track to a sequence
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track to add new track after (Optional - default: add to end of sequence)
*   @retval uint32_t Index of track added
*/
uint32_t addTrackToSequence(uint8_t bank, uint8_t sequence, uint32_t track=-1);

/** @brief  Removes a track from a sequence
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track
*/
void removeTrackFromSequence(uint8_t bank, uint8_t sequence, uint32_t track);

/** @brief  Add tempo to sequence timebase track
*   @param  bank Index of bank
*   @param  sequence  Sequence index
*   @param  tempo Tempo in BPM
*   @param  bar Bar of sequence at which to add tempo change [Optional - default: 1]
*   @param  tick Tick within bar at which to add tempo change [Optional - default: 0]
*/
void addTempoEvent(uint8_t bank, uint8_t sequence, uint32_t tempo, uint16_t bar=1, uint16_t tick=0);

/** @brief  Get tempo at position within sequence
*   @param  bank Index of bank
*   @param  sequence Sequence index
*   @param  bar Bar at which to get tempo [Optional - default: 1]
*   @param  tick Tick within bar at which to get tempo [Optional - default: 0]
'   @todo   getTempo without time parameter should get time at current play position???
*   @retval uint32_t Tempo in BPM
*/
uint32_t getTempoAt(uint8_t bank, uint8_t sequence, uint16_t bar=1, uint16_t tick=0);

/** @brief  Add time signature to sequence
*   @param  bank Index of bank
*   @param  sequence Sequence index
*   @param  beats Beats per bar (numerator)
*   @param  type Beat type (denominator)
*   @param  bar Bar at which to add time signature change
*   @param  tick Tick within bar at which to add time signature change
*/
void addTimeSigEvent(uint8_t bank, uint8_t sequence, uint8_t beats, uint8_t type, uint16_t bar);

/** @brief  Get time signature at position
*   @param  bank Index of bank
*   @param  sequence Sequence index
*   @param  bar Bar at which to time signature
*   @retval uint16_t Time signature - MSB numerator, LSB denominator
*/
uint16_t getTimeSigAt(uint8_t bank, uint8_t sequence, uint16_t bar);

/** @brief  Enable MIDI learn for a sequence trigger
*   @param  bank Index of bank or 0 to disable learning
*   @param  sequence Sequence index or 0 to disable learning
*   @note   Whilst in learn mode the next MIDI note-on event received on trigger channel will set the pad's trigger note
*/
void enableMidiLearn(uint8_t bank, uint8_t sequence);

/** @brief  Get bank currently in MIDI learn mode
*   @retval uint8_t Bank index or 0 if disabled
*/
uint8_t getMidiLearnBank();

/** @brief  Get sequence currently in MIDI learn mode
*   @retval uint8_t Sequence index
*/
uint8_t getMidiLearnSequence();

/** @brief  Set sequence name
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  name Sequence name (truncated at 16 characters)
*/
void setSequenceName(uint8_t bank, uint8_t sequence, const char* name);

/** @brief  Get sequence name
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @retval const char* Pointer to sequence name
*/
const char* getSequenceName(uint8_t bank, uint8_t sequence);

/** @brief  Move sequence (change order of sequences)
*   @param  bank Index of bank
*   @param  sequence Index of sequence to move
*   @param  position Index of sequence to move this sequence, e.g. 0 to insert as first sequence
*   @note   Sequences after insert point are moved up by one. Bank grows if sequence or position are higher than size of bank
*   @retval bool True on success
*/
bool moveSequence(uint8_t bank, uint8_t sequence, uint8_t position);

/** @brief  Insert new sequence in bank
*   @param  bank Index of bank
*   @param  sequence Index at which to insert sequence , e.g. 0 to insert as first sequence
*   @note   Sequences after insert point are moved up by one. Bank grows if sequence is higher than size of bank
*/
void insertSequence(uint8_t bank, uint8_t sequence);

/** @brief  Remove sequence from bank
*   @param  bank Index of bank
*   @param  sequence Index of sequence to remove
*   @note   Sequences after remove point are moved down by one. Bank grows if sequence is higher than size of bank
*/
void removeSequence(uint8_t bank, uint8_t sequence);


// ** Bank management functions **

/** @brief  Set quantity of sequences in a bank
*   @param  bank Bank index
*   @param  sequences Quantity of sequences
*   @note   Sequences are created or destroyed as required
*/
void setSequencesInBank(uint8_t bank, uint8_t sequences);

/** @brief  Get quantity of sequences in bank
*   @param  bank Bank index
*   @retval uint32_t Quantity of sequences
*/
uint32_t getSequencesInBank(uint32_t bank);

/** @brief  Clear bank
*   @param  bank Bank index
*/
void clearBank(uint32_t bank);

/** @brief  Sets the transport to start of the current bar
*/
void setTransportToStartOfBar();

/** @brief  Selects a track to solo, muting other tracks in bank
*   @param  bank Index of bank
*   @param  sequence Index of sequence
*   @param  track Index of track (sequence) within sequence
*   @param  solo True to solo, false to clear solo
*/
void solo(uint8_t bank, uint8_t sequence, uint32_t track, bool solo);

/** @brief  Check if track is soloed
*   @param  bank Index of bank
*   @param  seqeunce Index of sequence
*   @param  track Index of track
*   @retval bool True if solo
*/
bool isSolo(uint8_t bank, uint8_t sequence, uint32_t track);

// ** Transport control **
/** @brief  Locate transport to frame
*   @param  frame Quantity of frames (samples) from start of song to locate
*/
void transportLocate(uint32_t frame);

/** @brief  Get frame sequence at BBT position
*   @param  bar Bar [>0]
*   @param  beat Beat within bar [>0, <=beats per bar]
*   @param  tick Tick within beat [<ticks per beat]
*   @retval uint32_t Frames since start of song until requested position
*/
uint32_t transportGetLocation(uint32_t bar, uint32_t beat, uint32_t tick);

/** @brief  Register as timebase master
*   @retval bool True if successfully became timebase master
*/
bool transportRequestTimebase();

/** @brief Release timebase master
*/
void transportReleaseTimebase();

/** @brief  Start transport rolling
*   @param  client Name of client requesting change
**/
void transportStart(const char* client);

/** @brief  Stop transport rolling
*   @param  client Name of client requesting change
*/
void transportStop(const char* client);

/** @brief  Toggle between play and stop state
*   @param  client Name of client requesting change
*/
void transportToggle(const char* client);

/** @brief  Get play status
*   @retval uint8_t Status [JackTransportStopped | JackTransportRolling | JackTransportStarting]
*/
uint8_t transportGetPlayStatus();

/** @brief  Set transport tempo
*   @param  tempo Beats per minute
*   @todo   Using integer for tempo to simplify Python interface but should use float
*   @note   Tempo is saved with song but tempo map events override this
*/
void setTempo(double tempo);

/** @brief  Get transport tempo
*   @retval double Tempo in beats per minute
*/
double getTempo();

/** @breif  Set beats per bar
*   @uint32_t beats Beats per bar
*/
void setBeatsPerBar(uint32_t beats);

/** @brief  Get Beats per bar
*   @retval uint8_t Beats per bar
*/
uint32_t getBeatsPerBar();

/** @brief  Set sync timeout
*   @param  timeout Quantity of microseconds to wait for slow sync clients at start of play
*/
void transportSetSyncTimeout(uint32_t timeout);


#ifdef __cplusplus
}
#endif

