/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Zynseq Library
 *
 * Library providing step sequencer as a Jack connected device
 *
 * Copyright (C) 2020-2025 Brian Walton <brian@riban.co.uk>
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
    Sequence operations act on the Index of sequenceed by the request.
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
        Phrase:
            A collection of sequences
        Scene:
            A collection of phrases
*/

#include <cstdint>

#include "constants.h"
#include "pattern.h"
#include "timebase.h"

//-----------------------------------------------------------------------------
// Library Initialization
//-----------------------------------------------------------------------------
#ifdef __cplusplus
extern "C" {
#endif

// ** Library management functions **

/** @brief  Initialise library and connect to jackd server
    @param  name Client name
    @note   Call init() before any other functions will work
*/
void init(char* name);

/** @brief  Get the constant pulses per quarter note resolution
    @retval uint32_t Quantity of pulses in each quater note
*/
uint32_t getPPQN() { return PPQN_INTERNAL; };

/** @brief  Check if any changes have occured since last save
    @retval bool True if changed since last save
*/
bool isModified();

/** @brief  Enable debug output
    @param  bEnable True to enable debug output
*/
void enableDebug(bool bEnable);

/** @brief  Reset to a default state with 17 x 8 single pattern sequences
*/
void reset();

/** @brief  Convert binary sequence file to json
    @param  filename Full path and filename
    @retval const char* State as json string
*/
const char* convertToJson(const char* filename);

/** @brief  Get sequences and patterns
    @retval state State as json string
*/
const char* getState();

/** @brief  Free buffer used to transfer state
    @note   Should be called after getState
*/
void freeState();

/** @brief  Set state of a pattern
    @param  id Pattern index
    @param  patn_state Pattern state as json string
*/
void setPattern(uint32_t id, const char* patn_state);

/** @brief  Set sequences and patterns
    @param  state State as json string
    @retval bool True on success
    @note   Pass empty state to clear sequences (returns false)
*/
bool setState(const char* state);

/** @brief  Load sequences and patterns from file
    @param  filename Full path and filename
    @retval bool True on success
    @note   Pass invalid or empty filename to clear sequences (returns false)
*/
bool load(const char* filename);

/** @brief  Convert a legacy pattern from binary file
    @param  nPattern Pattern number
    @param  filename Full path and filename
    @retval char* JSON representation of pattern as c-string or null on error
*/
const char* convertPattern(uint32_t nPattern, const char* filename);

/** @brief  Save sequences and patterns to file
    @param  filename Full path and filename
*/
void save(const char* filename);

/** @brief  Store current pattern on undo queue
*/
void savePatternSnapshot();

/** Clear pattern undo queue */
void resetPatternSnapshots();

/** Restore previous state of pattern */
bool undoPattern();

/** Restore next state of pattern */
bool redoPattern();

/** Restore first state of pattern */
bool undoPatternAll();

/** Restore last state of pattern */
bool redoPatternAll();

/** Set pattern zoom */
void setPatternZoom(int16_t zoom);

/** Set pattern zoom */
int16_t getPatternZoom();

/** @brief  Get horizontal zoom
    @retval uint16_t Horizontal zoom
*/
uint16_t getHorizontalZoom();

// ** Direct MIDI interface **

//!@todo Should direct MIDI output be removed because JACK clients can do that themselves?

/** @brief  Play a note
    @param  note MIDI note number
    @param  velocity MIDI velocity
    @param  channel MIDI channel
    @param  duration Duration of note in milliseconds (0 to send note on only) Maximum 1 minute
*/
void playNote(uint8_t note, uint8_t velocity, uint8_t channel, uint32_t duration = 0);

/** @brief  Send MIDI command
    @param  status Status byte
    @param  value1 Value 1 byte
    @param  value2 Value 2 byte
*/
void sendMidiCommand(uint8_t status, uint8_t value1, uint8_t value2);

// ** Pattern management functions - pattern events are quantized to steps **
//!@todo Current implementation selects a pattern then operates on it. API may be simpler to comprehend if patterns were acted on directly by passing the
//! pattern index, e.g. clearPattern(index)

/** @brief  Create a new pattern
    @retval uint32_t Index of new pattern
*/
uint32_t createPattern();

/** @brief  Get quantity of patterns in a track
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence
    @param  track Index of track
    @retval uint32_t quantity of patterns in track
*/
uint32_t getPatternsInTrack(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track);

/** @brief  Get index of pattern within a track starting at position
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence
    @param  track Index of track
    @param  position Quantity of clock cycles from start of sequence where pattern starts
    @retval uint32_t Pattern index or -1 if not found
*/
uint32_t getPattern(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position);

/** @brief  Get index of pattern within a track spanning position
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence
    @param  track Index of track
    @param  position Quantity of clock cycles from start of sequence that pattern spans
    @retval uint32_t Pattern index or -1 if not found
*/
uint32_t getPatternAt(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position);

/** @brief  Copy pattern
    @param  source Index of pattern from which to copy
    @param  destination Index of pattern to which to copy
*/
void copyPattern(uint32_t source, uint32_t destination);

/** @brief  Paste (merge) copy/paste buffer into the specified pattern
    @param  pattern Index of pattern
    @param  dstep Quantity of steps to offset
    @param  doffset Fractional time offset
    @param  dnote Note offset
    @param  truncate False to use circular horizontal overflow. True to skip events out of step range.
*/
void pastePatternBuffer(uint32_t pattern, int32_t dstep, float doffset, int8_t dnote, bool truncate=false);

/** @brief  Copy/Cut a selection from the specified pattern to the copy/paste buffer
    @param  pattern Index of pattern
    @param  step1 step-range start
    @param  step2 step-range end
    @param  note1 note-range start
    @param  note2 note-range end
    @param cut True tp delete events from source pattern
    @retval uint32_t Number of events copied (or cutted!)
*/
uint32_t copyPatternBuffer(uint32_t pattern, uint32_t step1=0, uint32_t step2=0xFFFFFFFF, uint8_t note1=0, uint8_t note2=127, bool cut=false);

/** @brief  Get indexes of note events from a specified pattern in the specified step & note range.
    @param  pattern Index of pattern
    @param  ev_indexes pointer to integer array. It will be filled with the list of event indexes
    @param  limit size of integer array (ev_indexes)
    @param  step1 step-range start
    @param  step2 step-range end
    @param  note1 note-range start
    @param  note2 note-range end
    @retval uint32_t the number of event indexes copied into the array ev_indexes.
*/
uint32_t getPatternSelectionIndexes(uint32_t pattern, uint32_t* ev_indexes, uint32_t limit, uint32_t step1=0, uint32_t step2=0xFFFFFFFF, uint8_t note1=0, uint8_t note2=127);


// ** Functions acting on the globally selected pattern **

/** @brief  Select active pattern
    @note   All subsequent pattern methods act on this pattern
    @note   Pattern is created if it does not exist
    @param  pattern Index of pattern to select
*/
void selectPattern(uint32_t pattern);

/** @brief  Get the index of the selected pattern
    @retval uint32_t Index of pattern or -1 if not found
*/
uint32_t getPatternIndex();

/** @brief  Enable record from MIDI input to add notes to current pattern
    @param  enable True to enable MIDI input
*/
void enableMidiRecord(bool enable);

/** @brief  Get MIDI record enable state
    @retval bool True if MIDI record enabled
*/
bool isMidiRecord();

/** @brief  Add note to selected pattern
    @param  step Index of step at which to add note
    @param  note MIDI note number
    @param  velocity MIDI velocity value
    @param  duration Quantity of steps note should play for
    @param  offset Offset factor of start of step
    @retval bool True on success
*/
bool addNote(uint32_t step, uint8_t note, uint8_t velocity, float duration, float offset = 0.0);

/** @brief  Removes note from selected pattern
    @param  step Index of step at which to remove note
    @param  note MIDI note number to remove
*/
void removeNote(uint32_t step, uint8_t note);

/** @brief  Remove all note events from pattern
*/
void clearNotes();

/** @brief  Get data of pattern event at specified index
    @param  index Event index
    @param  data pointer to a struct to contain event data
    @retval int32_t Index of the event. -1 if index is out of range.
*/
int32_t getEventDataAt(uint32_t index, StepEvent* data);

/** @brief  Get data of copy/paste buffer event at specified index
    @param  index Event index
    @param  data pointer to a struct to contain event data
    @retval int32_t Index of the event. -1 if index is out of range.
*/
int32_t getBufferEventDataAt(uint32_t index, StepEvent* data);

/** @brief  Get index of specified note
    @param  position Quantity of steps from start of pattern at which to check for note
    @param  note MIDI note number
    @retval int32_t Index of the note event in the events vector
*/
int32_t getNoteIndex(uint32_t step, uint8_t note);

/** @brief  Get data of specified note
    @param  position Quantity of steps from start of pattern at which to check for note
    @param  note MIDI note number
    @param  data pointer to a struct to contain event data
    @retval int32_t Index of the note event in the events vector
*/
int32_t getNoteData(uint32_t step, uint8_t note, StepEvent* data, bool cp_buffer=false);

/** @brief  Set data of a specified note, excluding position, offset, command and note number (nValue1Start)
    @param  position Quantity of steps from start of pattern at which to check for note
    @param  note MIDI note number
    @param  data pointer to a struct to contain event data
    @retval int32_t Index of the note event in the events vector
*/
int32_t setNoteData(uint32_t step, uint8_t note, StepEvent* data);

/** @brief  Get step that note starts
    @param  position Quantity of steps from start of pattern at which to check for note
    @param  note MIDI note number
    @retval int32_t Quantity of steps from start of pattern that note starts or -1 if note not found
*/
int32_t getNoteStart(uint32_t step, uint8_t note);

/** @brief  Get velocity of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval uint8_t Note velocity (0..127)
*/
uint8_t getNoteVelocity(uint32_t step, uint8_t note);

/** @brief  Set velocity of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  velocity MIDI velocity
*/
void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity);

/** @brief  Get offset of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval float offset Step fraction, from 0.0 to 1.0
*/
float getNoteOffset(uint32_t step, uint8_t note);

/** @brief  Set offset of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  offset Step fraction, from 0.0 to 1.0
*/
void setNoteOffset(uint32_t step, uint8_t note, float offset);

/** @brief  Add control to selected pattern
    @param  step Index of step at which to add control
    @param  control MIDI control number
    @param  valueStart MIDI control value at start of event
    @param  valueEnd MIDI control value at end of event
    @param  duration Quantity of steps control should span (iterate values)
    @param  offset Offset factor of start of step
    @retval bool True on success
*/
bool addControl(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd, float duration, float offset = 0.0);

/** @brief  Removes a control step from selected pattern
    @param  step Index of step at which to remove control
    @param  control MIDI control number to remove
*/
void removeControl(uint32_t step, uint8_t control);

/** @brief  Clean all control steps from selected pattern
    @param  control MIDI control number to remove
*/
void clearControl(uint8_t control);

/** @brief  Get step that control starts
    @param  position Quantity of steps from start of pattern at which to check for control
    @param  control MIDI control number
    @retval int32_t Quantity of steps from start of pattern that control starts or -1 if note not found
*/
int32_t getControlStart(uint32_t step, uint8_t control);

/** @brief  Get duration of control in selected pattern
    @param  position Index of step at which control starts
    @note   MIDI control number
    @retval float Duration in steps or 0.0 if control does not exist
*/
float getControlDuration(uint32_t step, uint8_t control);

/** @brief  Get value of control in selected pattern
    @param  step Index of step at which control resides
    @param  control MIDI control number
    @retval uint8_t control value (0..127)
*/
uint8_t getControlValue(uint32_t step, uint8_t control);

/** @brief  Get end value of control in selected pattern
    @param  step Index of step at which control resides
    @param  control MIDI control number
    @retval uint8_t end control value (0..127)
*/
uint8_t getControlValueEnd(uint32_t step, uint8_t control);

/** @brief  Set value of control in selected pattern
    @param  step Index of step at which control resides
    @param  control MIDI control number
    @param  valueStart MIDI value at start of event
    @param  valueEnd MIDI value at end of event
*/
void setControlValue(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd);

/** @brief  Get offset of control in selected pattern
    @param  step Index of step at which control resides
    @param  control MIDI control number
    @retval float offset Step fraction, from 0.0 to 1.0
*/
float getControlOffset(uint32_t step, uint8_t control);

/** @brief  Set offset of control in selected pattern
    @param  step Index of step at which control resides
    @param  control MIDI control number
    @param  offset Step fraction, from 0.0 to 1.0
*/
void setControlOffset(uint32_t step, uint8_t control, float offset);

/** @brief  Set stutter parameters of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  speed Stutter speed
    @param  velfx Stutter velocity FX value (0=none, 1=fadeIn, 2=fadeOut)
    @param  ramp Stutter speed ramp value (0=None, 1=up, 2=down)
*/
void setNoteStutter(uint32_t step, uint8_t note, uint8_t speed, uint8_t velfx, uint8_t ramp);

/** @brief  Get stutter speed of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval uint8_t Stutter speed
*/
uint8_t getNoteStutterSpeed(uint32_t step, uint8_t note);

/** @brief  Set stutter speed of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  speed Stutter speed
*/
void setNoteStutterSpeed(uint32_t step, uint8_t note, uint8_t speed);

/** @brief  Get stutter velocity FX of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval uint8_t Stutter velocity FX value (0=none, 1=fadeIn, 2=fadeOut)
*/
uint8_t getNoteStutterVelfx(uint32_t step, uint8_t note);

/** @brief  Set stutter velocity FX value of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  velfx Stutter velocity FX value (0=none, 1=fadeIn, 2=fadeOut)
*/
void setNoteStutterVelfx(uint32_t step, uint8_t note, uint8_t velfx);

/** @brief  Get stutter speed ramp of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval uint8_t Stutter speed ramp value (0=None, 1=up, 2=down)
*/
uint8_t getNoteStutterRamp(uint32_t step, uint8_t note);

/** @brief  Set stutter speed ramp value of note in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  ramp Stutter speed ramp value (0=None, 1=up, 2=down)
*/
void setNoteStutterRamp(uint32_t step, uint8_t note, uint8_t ramp);

/** @brief  Get note play chance in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval float Note play probability (0..1 for 0%..100%)
*/
float getNotePlayChance(uint32_t step, uint8_t note);

/** @brief  Set note play chance in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  chance Note play probability (0..1 for 0%..100%)
*/
void setNotePlayChance(uint32_t step, uint8_t note, float chance);

/** @brief  Get note play frequency in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval uint8_t Note play frequency: last bit => play/skip, higher bits => n loops to play/skip
                    Can be used for enabling/disabling the event: 0 => play never, 1 => play on every loop
*/
uint8_t getNotePlayFreq(uint32_t step, uint8_t note);

/** @brief  Set note play frequency in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  freq Note play frequency: last bit => play/skip, higher bits => n loops to play/skip
                 Can be used for enabling/disabling the event: 0 => play never, 1 => play on every loop
*/
void setNotePlayFreq(uint32_t step, uint8_t note, uint8_t freq);

/** @brief  Get note stutter chance in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval float Note stutter probability (0..1 for 0%..100%)
*/
float getNoteStutterChance(uint32_t step, uint8_t note);

/** @brief  Set note stutter chance in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  chance Note stutter probability (0..1 for 0%..100%)
*/
void setNoteStutterChance(uint32_t step, uint8_t note, float chance);

/** @brief  Get note stutter frequency in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @retval uint8_t Note stutter frequency: last bit => play/skip, higher bits => n loops to play/skip
*/
uint8_t getNoteStutterFreq(uint32_t step, uint8_t note);

/** @brief  Set stutter frequency in selected pattern
    @param  step Index of step at which note resides
    @param  note MIDI note number
    @param  freq Note stutter frequency: last bit => play/skip, higher bits => n loops to play/skip
*/
void setNoteStutterFreq(uint32_t step, uint8_t note, uint8_t freq);

/** @brief  Get duration of note in selected pattern
    @param  position Index of step at which note starts
    @note   MIDI note number
    @retval float Duration in steps or 0.0 if note does not exist
*/
float getNoteDuration(uint32_t step, uint8_t note);

/** @brief  Add programme change to selected pattern
    @param  step Index of step at which to add program change
    @param  program MIDI program change number
    @retval bool True on success
*/
bool addProgramChange(uint32_t step, uint8_t program);

/** @brief  Removes program change from selected pattern
    @param  step Index of step at which to remove program change
*/
void removeProgramChange(uint32_t );

/** @brief  Get program change in selected pattern
    @param  step Index of step at which program change resides
    @retval uint8_t Program change (0..127, 0xFF if no program change at this step)
*/
uint8_t getProgramChange(uint32_t step);

/** @brief  Transpose selected pattern
    @param  value +/- quantity of notes to transpose
*/
void transpose(int8_t value);

/** @brief  Change velocity of all notes in patterm
    @param  value Offset to adjust +/-127
*/
void changeVelocityAll(int value);

/** @brief  Change velocity of a list of notes in pattern
    @param  value Offset to adjust +/-127
    @param  evi_list Event index list
    @param  n number of events in list
*/
void changeVelocityList(float value, uint32_t* evi_list, uint32_t n);

/** @brief  Change duration of all notes in patterm
    @param  value Offset to adjust +/-100.0 or whatever
*/
void changeDurationAll(float value);

/** @brief  Change duration of a list of notes in pattern
    @param  value Offset to adjust +/-127
    @param  evi_list Event index list
    @param  n number of events in list
*/
void changeDurationList(float value, uint32_t* evi_list, uint32_t n);

/** @brief  Flag pattern as modified - also sets flags in relevant sequences and tracks
    @param  pPattern Pointer to pattern
    @param  bModified True to set pattern modified
    @param  bodfiedTracks True to set tracks modified
*/
void setPatternModified(Pattern* pPattern, bool bModified = true, bool bModifiedTracks = false);

/** @brief  Check if selected pattern has changed since last check
    @retval bool True if pattern has changed
*/
bool isPatternModified();

/** @brief  Get position of playhead within pattern in steps
    @retval uint32_t Quantity of steps from start of pattern to playhead
*/
uint32_t getPatternPlayhead();

/** @brief  Get quantity of steps in pattern
    @retval uint32_t Quantity of steps
*/
uint32_t getSteps();

/** @brief  Get steps per beat from selected pattern
    @retval uint32_t Steps per beat
*/
uint32_t getStepsPerBeat();

/** @brief  Set steps per beat
    @param  pattern Index of pattern
    @param  steps Steps per beat [1,2,3,4,6,8,12,24]
    @note   Calculates pattern length from beats in pattern
*/
void setStepsPerBeat(uint32_t steps);

/** @brief  Get the last populated step
    @retval uint32_t Index of last populated step or -1 if empty
    @note   This may allow checking for empty patterns or whether truncation will have an effect
*/
uint32_t getLastStep();

/** @brief  Get swing division from selected pattern
    @retval uint32_t swing division
*/
uint32_t getSwingDiv();

/** @brief  Set swing division in selected pattern
    @param  swing division, from 1 to pattern's StepsPerBeat
*/
void setSwingDiv(uint32_t div);

/** @brief  Get swing amount from selected pattern
    @retval float swing division
*/
float getSwingAmount();

/** @brief  Set swing amount in pattern
    @param  swing amount, from 0 to 1 (0.33 is perfect-triplet swing, >0.5 is not really swing)
*/
void setSwingAmount(float amount);

/** @brief  Get Time Humanization amount from pattern
    @param  pattern Index of pattern
    @retval float
*/
float getHumanTime();

/** @brief  Set Time Humanization amount in pattern
    @param  pattern Index of pattern
    @param  amount, from 0 to FLOAT_MAX
*/
void setHumanTime(float amount);

/** @brief  Get Velocity Humanization amount from pattern
    @retval float
*/
float getHumanVelo();

/** @brief  Set Velocity Humanization amount in pattern
    @param  amount, from 0 to FLOAT_MAX
*/
void setHumanVelo(float amount);

/** @brief  Get PlayChance from pattern
    @retval float
*/
float getPlayChance();

/** @brief  Set PlayChance in pattern
    @param  chance, probability of playing notes
*/
void setPlayChance(float chance);

// ** Functions acting on specified pattern **

/** @brief  Check if selected pattern is empty
    @param  pattern Pattern index
    @retval bool True if pattern is empty
*/
bool isPatternEmpty(uint32_t pattern);

/** @brief  Get quantity of beats in  pattern
    @param  pattern Index of pattern
    @retval uint32_t Quantity of beats
*/
uint32_t getBeatsInPattern(uint32_t pattern);

/** @brief  Set quantity of beats in pattern
    @param  pattern Index of pattern
    @param  beats Quantity of beats
    @note   Adjusts steps to match steps per beat
*/
void setBeatsInPattern(uint32_t pattern, uint32_t beats);

/** @brief  Get pattern length in clock cycles
    @param  pattern Index of pattern
    @retval Length in clock cycles
*/
uint32_t getPatternLength(uint32_t pattern);

/** @brief  Get the note at event index
    @param  pattern Index of pattern
    @param  index Index of event
    @retval uint8_t MIDI note number or 0xff for invalid index
*/
uint8_t getNoteAtIndex(uint32_t pattern, uint32_t index);

/** @brief  Get clocks per step for selected pattern
    @param  pattern Index of paatern
    @retval uint32_t Clock cycles per step
*/
uint32_t getClocksPerStep(uint32_t pattern);

/** @brief  Clears events from pattern
    @note   Does not change other parameters such as pattern length
*/
void clearPattern(uint32_t pattern);

// ** Functions used by pattern editor but not related to the actual pattern **

/** @brief  Set note used as rest when using MIDI input for pattern editing
    @param  note MIDI note number [0..127]
    @note   >127 to disable rest
*/
void setInputRest(uint8_t note);

/** @brief  Get note used as rest when using MIDI input for pattern editing
    @retval uint8_t MIDI note number [0..127, 0xFF if disabled]
*/
uint8_t getInputRest();

/** @brief  Set scale used by pattern editor for selected pattern
    @param  scale Index of scale
*/
void setScale(uint32_t scale);

/** @brief  Get scale used by pattern editor for selected pattern
    @retval uint32_t Index of scale
*/
uint32_t getScale();

/** @brief  Set scale tonic (root note) for selected pattern (used by pattern editor)
    @param  tonic Scale tonic
*/
void setTonic(uint8_t tonic);

/** @brief  Get scale tonic (root note) for selected pattern (used by pattern editor)
    @retval uint8_t Tonic
*/
uint8_t getTonic();

/** @brief  Get the reference note
    @retval uint8_t MIDI note number
    @note   May be used for position within user interface
*/
uint8_t getRefNote();

/** @brief  Set the reference note
    @param  MIDI note number
    @note   May be used for position within user interface
*/
void setRefNote(uint8_t note);

/** @brief  Get the "Quantize Notes" flag
    @retval uint8_t quantize value (0, 1, 2, 3, 4, 6, 8, 12, 16)
*/
uint8_t getQuantizeNotes();

/** @brief  Set the "Quantize Notes" flag
    @param  quantize value (0, 1, 2, 3, 4, 6, 8, 12, 16)
*/
void setQuantizeNotes(uint8_t qn);

/** @brief  Get the "Interpolate CC values" flag for a given CC number
	@param  ccnum
	@retval bool flag
*/
bool getInterpolateCC(uint8_t ccnum);

/** @brief  Set the "Interpolate CC" flag for a given CC number
	@param  ccnum
	@param  flag
*/
void setInterpolateCC(uint8_t ccnum, bool flag);

/** @brief  Set "Interpolate CC" flags to default values for each CC number
*/
void setInterpolateCCDefaults();

// ** Scene management functions **

/** @brief  Select a scene
    @param  scene Index of scene
    @retval bool True if new scene created
*/
bool setScene(uint8_t scene);

/** @brief  Get currently selected scene
    @retval uint8_t Index of scene
*/
uint8_t getScene();

/** @brief  Get quantity of scenes
    @retval uint8_t Quantity of scenes
*/
uint8_t getNumScenes();

/** @brief  Remove a scene
    @param  scene Inde of scene
    @note   Subsequenct scenes are renumbered. If selected scene is higher, select scene zero.
*/
void removeScene(uint8_t scene);

// ** Track management functions **

/** @brief  Add pattern to a track
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
    @param  position Quantity of clock cycles from start of track at which to add pattern
    @param  pattern Index of pattern
    @param  force True to remove overlapping patterns, false to fail if overlapping patterns
    @retval True if pattern inserted
*/
bool addPattern(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force);

/** @brief  Remove pattern from track
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
    @param  position Quantity of clock cycles from start of track from which to remove pattern
*/
void removePattern(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint32_t position);

/** @brief  Toggle mute of track
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
*/
void toggleMute(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track);

/** @brief  Get track mute state
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
    @retval bool True if muted
*/
bool isMuted(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track);

// ** Sequence & Track management functions **

/** @brief  Set track output
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Sequence ID
    @param  track Index of track
    @param  output Track output: 0xfe for clippy output. 0xff for no output.
*/
void setTrackOutput(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint8_t output);

/** @brief  Get track output
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
    @retval uint8_t Track output: 0xfe for clippy output. 0xff for no output.
*/
uint8_t getTrackOutput(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track);

/** @brief  Set track MIDI channel
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Sequence ID
    @param  track Index of track
    @param  channel MIDI channel
*/
void setChannel(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track, uint8_t channel);

/** @brief  Get track MIDI channel
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
    @retval uint8_t MIDI channel
*/
uint8_t getChannel(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track);

/** @brief  Get current play mode for a sequence
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
    @retval uint8_t Stop mode (bits 0..1). Start mode (bit 2) modes
*/
uint8_t getSequenceMode(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set play mode of a sequence
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
    @param  mode Stop mode (bits 0..1). Start mode (bit 2) modes
*/
void setSequenceMode(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t mode);

/** @brief  Get play state
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
    @retval uint8_t Play state [STOPPED | PLAYING | STOPPING | STARTING | STOPPING_SYNC]
*/
uint8_t getPlayState(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Check if sequence is empty (all patterns have no events)
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
    @retval bool True if sequence empty else false if any pattern in sequence has any events
*/
bool isEmpty(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set play state
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
    @param  state Play state [STOPPED | STARTING | PLAYING | STOPPING]
    @note   STARTING will reset to start of sequence. PLAYING resumes at last played position.
    @note   If all sequences have stopped and no external clients have registered for local transport then local transport is stopped.
*/
void setPlayState(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t state);

/** @brief  Toggles starting / stopping
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
*/
void togglePlayState(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Get sequence states encoded as 32-bit word
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence within phrase
    @retval uint32_t State encode as 4 bytes: [repeat, group, mode, play state]
*/
uint32_t getSequenceState(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Get state of changed sequences in scene
    @param  states Pointer to array of uint32_t to hold results
    @param  max Maximum number of states to return
    @retval uint32_t Quantity of changed sequences
    @note   State is represented as 4 bytes encoded as single 32-bit word: [phrase, sequence, mode, play state]
    @note   mode bits: [0..1] stop mode. [2] start mode. [7] enabled
*/
uint32_t getStateChange(uint32_t* states, uint32_t max);

/** @brief  Get progress of each group
    @retval uint8_t* Pointer to array of uint8_t holding results in percentage played
*/
uint8_t* getProgress();

/** @brief  Get current beat in bar
    @retval uint8_t Beat
*/
uint32_t getBeat();

/** @brief  Get quantity of tracks in a sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence
    @retval uint32_t Quantity of tracks in sequence
*/
uint32_t getTracksInSequence(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set the times sequence will play
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence
    @param  repeat Quantity of repeats (0 to disable, 1 for play once, etc.)
    @note   This is actually the number of times the sequence will play, not repeat.
*/
void setSequenceRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t repeat);

/** @brief  get the times sequence will play
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence
    @retval uint8_t Quantity of repeats (0 if disabled, 1 for play once, etc.)
    @note   This is actually the number of times the sequence will play, not repeat.
*/
uint8_t getSequenceRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Stops all sequences
*/
void stop();

/** @brief  Get the currently playing clock cycle
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence of sequence within phrase
    @retval uint32_t Playhead position in clock cycles
*/
uint32_t getSequencePlayPosition(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set the currently playing clock cycle
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence of sequence within phrase
    @param  clock Clock cycle to position play head
*/
void setSequencePlayPosition(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t clock);

/** @brief  Get length of sequence in clock cycles
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence of sequence within phrase
    @retval uint32_t Quantity of clock cycles in sequence
*/
uint32_t getSequenceLength(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence length (used mostly for clippy)
    @param  scene Index of scene containing sequence
    @param  phrase Index of phrase containing sequence
    @param  sequence Index of sequence (sequence) of sequence within phrase
    @param  length Quantity of clock cycles in sequence
*/
void setSequenceLength(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t length);

/** @brief  Remove all patterns from sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Sequence number
*/
void clearSequence(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Get the quantity of playing sequences
    @retval size_t Quantity of playing sequences
*/
size_t getPlayingSequences();

/** @brief  Get sequence group
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Sequence number
    @retval uint8_t Group
*/
uint8_t getSequenceGroup(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence group
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Sequence number
    @param  group Group index
*/
void setSequenceGroup(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t group);

/** @brief  Check if a sequence play state, group or mode has changed since last checked
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval bool True if changed
*/
bool hasSequenceChanged(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Adds a track to a sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track to add new track after (Optional - default: add to end of sequence)
    @retval uint32_t Index of track added
*/
uint32_t addTrackToSequence(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track = -1);

/** @brief  Removes a track from a sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
*/
void removeTrackFromSequence(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t track);

/** @brief  Add tempo to sequence timebase track
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence  Index of sequence
    @param  tempo Tempo in BPM
    @param  bar Bar of sequence at which to add tempo change [Optional - default: 1]
    @param  tick Tick within bar at which to add tempo change [Optional - default: 0]
*/
void addTempoEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, float tempo, uint16_t bar = 1, uint16_t tick = 0);

/** @brief  Remove tempo from sequence timebase track
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence  Index of sequence
    @param  bar Bar of sequence at which to add tempo change [Optional - default: 1]
    @param  tick Tick within bar at which to add tempo change [Optional - default: 0]
*/
void removeTempoEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar = 1, uint16_t tick = 0);

/** @brief  Get tempo at position within sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  bar Bar at which to get tempo [Optional - default: 1]
    @param  tick Tick within bar at which to get tempo [Optional - default: 0]
    @retval float Tempo in BPM or 0.0 if no tempo in timebase
*/
float getTempoAt(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar = 1, uint16_t tick = 0);

/** @brief  Add time signature to sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  bar Bar at which to add time signature change
    @param  timeSig Beats per bar
*/
void addTimeSigEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar, uint8_t timeSig);

/** @brief  Remove time signature from sequence
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  bar Bar at which to remove time signature change
*/
void removeTimeSigEvent(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar);

/** @brief  Get time signature at position
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  bar Bar at which to get time signature
    @retval uint8_t Time signature in quarter notes (beats per bar)
*/
uint8_t getTimeSigAt(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t bar);

/** @brief  Get sequence currently in MIDI learn mode
    @retval uint32_t Index of sequence
*/
uint8_t getMidiLearnSequence();

/** @brief  Set the pattern editor sequence
    @param  scene Index of scene
    @param  phrase Phrase index
    @param  sequence Index of sequence
    @retval bool True on sucess (if sequence exists)
*/
bool selectSequence(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence name
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  name Sequence name (truncated at 16 characters)
*/
void setSequenceName(uint8_t scene, uint8_t phrase, uint8_t sequence, const char* name);

/** @brief  Get sequence name
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval const char* Pointer to sequence name
*/
const char* getSequenceName(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence tempo
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  tempo Tempo or 0.0 to disable
*/
void setSequenceTempo(uint8_t scene, uint8_t phrase, uint8_t sequence, float tempo);

/** @brief  Get sequence tempo
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval float Tempo or 0.0 if disabled
*/
float getSequenceTempo(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence beats per bar (time signature)
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  sig Beats per bar (time signature) or 0 to disable
*/
void setSequenceBpb(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t bpb);

/** @brief  Get sequence beats per bar (time signature)
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval uint8_t Beats per bar (time signature) or 0 if disabled
*/
uint8_t getSequenceBpb(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence follow action
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  action Follow action @see FOLLOW_ACTION enum
*/
void setSequenceFollowAction(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t action);

/** @brief  Get the action to perform when sequence ends
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval uint8_t Follow action
*/
uint8_t getSequenceFollowAction(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence follow action parameter
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  param  Follow action parameter
*/
void setSequenceFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence, int16_t param);

/** @brief  Get the parameter of follow action, e.g. offset
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval int16_t Follow action parameter
*/
int16_t getSequenceFollowParam(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence follow play flags
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  flags Bitwise flags indicating which play loops should be skipped
*/
void setSequencePlayFlags(uint8_t scene, uint8_t phrase, uint8_t sequence, uint32_t flags);

/** @brief  Get the follow play flags
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval uint32_t Bitwise flags indicating which play loops should be skipped
*/
uint32_t getSequencePlayFlags(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Set sequence follow repeat
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  repeat Quantity of times follow action is repeated
*/
void setSequenceFollowRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence, uint8_t repeat);

/** @brief  Get the follow repeat
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @retval uint8_t Quantity of times follow action is repeated
*/
uint8_t getSequenceFollowRepeat(uint8_t scene, uint8_t phrase, uint8_t sequence);

/** @brief  Get phrase schedule
    @param  scene Index of scene
    @retval
*/

/** @brief  Update all sequence lengths and empty status
*/
void updateSequenceInfo();

/** @brief  Selects a track to solo, muting other tracks in phrase
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track (sequence) within sequence
    @param  solo True to solo, false to clear solo
*/
void solo(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t track, bool solo);

/** @brief  Check if track is soloed
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  sequence Index of sequence
    @param  track Index of track
    @retval bool True if solo
*/
bool isSolo(uint8_t scene, uint8_t phrase, uint8_t sequence, uint16_t track);

// ** Transport control **

/** @brief  Start local transport rolling
    @param  id Id  of client requesting change
 **/
void transportStart(uint8_t id);

/** @brief  Stop local transport rolling
    @param  id Id  of client requesting change
*/
void transportStop(uint8_t id);

/** @brief  Toggle between play and stop state
    @param  id Id of client requesting change
*/
void transportToggle(uint8_t id);

/** @brief  Force Jack's position update
*/
void updateJackPosition();

/** @brief  Set transport tempo
    @param  tempo Beats per minute
    @todo   Using integer for tempo to simplify Python interface but should use float
    @note   Tempo is saved with song but tempo map events override this
*/
void setTempo(double tempo);

/** @brief  Get transport tempo
    @retval double Tempo in beats per minute
*/
double getTempo();

/** @brief  Set beats per bar
    @retval uint8_t beats Beats per bar
*/
void setBpb(uint8_t beats);

/** @brief  Get Beats per bar
    @retval uint8_t Beats per bar
*/
uint8_t getBpb();

/** @brief  Set default beats per bar
    @retval uint8_t beats Beats per bar
*/
void setDefaultBpb(uint8_t beats);

/** @brief  Get default Beats per bar
    @retval uint8_t Beats per bar
*/
uint8_t getDefaultBpb();

/** @brief  Set metronome mode
    @param  mode 0: Disabled. 1: Play when transport running. 2: Play always (starts local transport)
*/
void setMetronomeMode(uint8_t mode);

/** @brief  Get metronome mode
    @retval uint8_t Metronome mode
*/
uint8_t getMetronomeMode();

/** @brief  Set level of metronome
    @param  level Level [0.0 - 1.0]
*/
void setMetronomeVolume(float level);

/** @brief  Set level of metronome
    @retval float Level [0.0 - 1.0]
*/
float getMetronomeVolume();

/** @brief  Get external clock PPQN
    @retval uint32_t External clock pulse per quater note (beat)
*/
uint8_t getExtClockPPQN();

/** @brief  Set external clock PPQN
    @param  ppqn PPQN (>0)
*/
void setExtClockPPQN(uint8_t ppqn);

/** @brief  React to a tempo tap event
*/
void tapTempo();

/** @brief  Enable a channel
    @param  channel MIDI channel
    @param  bool True to enable
*/
void enableChannel(uint8_t channel, bool enable);

/** @brief  Is a channel enabled
    @param  channel MIDI channel
    @retval bool True if channel is enabled
*/
bool isChannelEnabled(uint8_t channel);

/** @brief  Update the quantity of frames in each tick and clock
*/
void updateClockTiming();

/* Phrase handling */

/** @brief  Get quantity of phrases
    @param  scene Index of scene
    @retval uint8_t Quantity of phrases
*/
uint8_t getNumPhrases(uint8_t scene);

/** @brief  Add phrase
    @param  scene Index of scene
    @param  phrase Index of phrase to insert before
*/
void insertPhrase(uint8_t scene, uint8_t phrase);

/** @brief  Duplicate phrase
    @param  scene Index of scene
    @param  phrase Index of phrase to duplicate
*/
void duplicatePhrase(uint8_t scene, uint8_t phrase);

/** @brief  Remove phrase
    @param  scene Index of scene
    @param  phrase Index of phrase to remove
*/
void removePhrase(uint8_t scene, uint8_t phrase);

/** @brief  Nudge a phrase up of down
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  forward True to move forward, else move backward
*/
void nudgePhrase(uint8_t scene, uint8_t phrase, bool forward);

/** @brief  Set phrase time signature in Beats per Bar
    @param  scene Index of scene
    @param  phrase Index of phrase
    @param  bpb Time signature in Beats per Bar
*/
void setPhraseBPB(uint8_t scene, uint8_t phrase, uint8_t bpb);

/** @brief  Get phrase time signature in Beats per Bar
    @param  scene Index of scene
    @param  phrase Index of phrase
    @retval uint8_t Beats per Bar
*/
uint8_t getPhraseBPB(uint8_t scene, uint8_t phrase);


#ifdef __cplusplus
}
#endif
