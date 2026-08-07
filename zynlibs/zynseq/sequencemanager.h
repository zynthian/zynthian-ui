/*  Declares SequenceManager class managing collection of sequences
 *
 *   Copyright (c) 2020-2025 Brian Walton
 *
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the Free Software
 *   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
*/

#pragma once

#include <cstdint>
#include <map>
#include <array>
#include <memory_resource>

#include "pattern.h"
#include "sequence.h"
#include "track.h"

// Event Scheduler => Real-Time Safe!!
class EvSchedule {
  private:
    // We estimate that 100000 events is the maximum number of events scheduled at any given time
    // The 32 extra bytes is for accounting the multimap metada (double linked list or so)
    static constexpr size_t MAX_EVENTS = 100000;
    static constexpr size_t NODE_SIZE = sizeof(uint32_t) + sizeof(SEQ_EVENT) + 32;
    static constexpr size_t BUFFER_SIZE = MAX_EVENTS * NODE_SIZE;

    // The order of declaration matters for initialization/destruction tracking
    // We use usync_pool_resource because monotonic_buffer_resource doesn't
    // manage the dynamic memory deallocation we need for the scheduler
    std::array<std::byte, BUFFER_SIZE> m_buffer;
    std::pmr::monotonic_buffer_resource m_upstream;
    std::pmr::unsynchronized_pool_resource m_pool;

  public:
    std::pmr::multimap<uint32_t, SEQ_EVENT> map;

    EvSchedule()
    : m_upstream(m_buffer.data(), m_buffer.size(), std::pmr::null_memory_resource()),
    m_pool(&m_upstream),
    map(&m_pool) {}

    // std::pmr::null_memory_resource() avoids silently calling to malloc if we go over the limit. It will fail to insert instead!!
};


/** SequenceManager class provides creation, recall, update and delete of patterns which other modules can subseqnetly use. It manages persistent (disk)
 * storage. SequenceManager is implemented as a singleton ensuring a single instance is available to all callers.
*/
class SequenceManager {
  public:
    /** @brief  Instantiate sequence manager object
    */
    SequenceManager();

    /** @brief  Initialise all data
    */
    void init();

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

    /** @brief  Get pointer to a pattern
        @param  index Index of pattern to retrieve
        @retval Pattern* Pointer to pattern
        @note   If pattern does not exist a new, default, empty pattern is created
    */
    Pattern* getPattern(uint32_t index);

    /** @brief  Get the index of a pattern
        @param  pattern Pointer to pattern
        @retval uint32_t Index of pattern or -1 if not found
    */
    uint32_t getPatternIndex(Pattern* pattern);

    /** @brief  Get next populated pattern after current pattern
        @param  pattern Index of current pattern
        @retval uint32_t Index of pattern
    */
    uint32_t getNextPattern(uint32_t pattern);

    /** @brief  Create new pattern
        @param  Number of beats in pattern.
        @retval uint32_t Index of new pattern
        @note   Use getPattern to retrieve pointer to pattern
    */
    uint32_t createPattern(uint32_t beats = DEFAULT_BPB);

    /** @brief  Delete pattern
        @param  index Index of the pattern to delete
    */
    void deletePattern(uint32_t index);

    /** @brief  Copy pattern
        @param  source Index of pattern to copy from
        @param  destination Index of pattern to populate
    */
    void copyPattern(uint32_t source, uint32_t destination);

    /** @brief  Flag pattern as modified - also sets flags in relevant sequences and tracks
        @param  pPattern Pointer to pattern
    */
    void setPatternModified(Pattern* pPattern);

    /** @brief  Update all sequence lengths
        @note   Blunt tool to update each sequence after any pattern length changes
    */
    void updateAllSequenceLengths();

    /** @brief  Handle clock
        @param  nTime Offset since sequence tick epoch for this tick
        @param  pSchedule Pointer to the schedule to populate with events
        @param  bSync True indicates a bar sync pulse
        @param  bBeat True indicates a beat pulse
        @retval uint8_t Bitwise flag indication sumary of playing sequences. [1: Playing 2:Starting]
    */
    uint8_t clock(uint32_t nTime, EvSchedule* pSchedule, bool bSync, bool bBeat);

    /** @brief  Get pointer to sequence
        @param  scene Index of scene
        @param  phrase Index of phrase
        @param  sequence Index of sequence within phrase or PHRASE_CHANNEL to get phrase launcher's sequence
        @retval Sequence* Pointer to sequence or nullptr if not existing
    */
    Sequence* getSequence(uint8_t scene, uint8_t phrase, uint8_t sequence);

    /** @brief  Add pattern to sequence
        @param  pSequence Pointer to sequence
        @param  track Index of track
        @param  position Quantity of clock cycles from start of track at which to add pattern
        @param  pattern Index of pattern
        @param  force True to remove overlapping patterns, false to fail if overlapping patterns
        @retval True if pattern inserted
    */
    bool addPattern(Sequence* pSequence, uint32_t track, uint32_t position, uint32_t pattern, bool force=false);

    /** @brief  Remove pattern from track
        @param  pSequence Pointer to sequence
        @param  track Index of track
        @param  position Quantity of clock cycles from start of track from which to remove pattern
    */
    void removePattern(Sequence* pSequence, uint32_t track, uint32_t position);

    /** @brief  Set sequence play state
        @param  pSequence Pointer to sequence
        @param  state Play state
        @note   Stops other sequences in group
    */
    void setPlayState(Sequence* pSequence, uint8_t state);

    /** @brief  Stop all sequences in group
        @param  group Group ID
    */
    void stopGroup(uint8_t group);

    /** @brief  Get MIDI note number used to trigger sequence
        @param  phraseSeq phrase and sequence encoded into 32-bit word
        @retval uint8_t MIDI note number [0xFF for none]
    */
    uint8_t getTriggerNote(uint32_t phraseSeq);

    /** @brief  Set MIDI note number used to trigger sequence
        @param  phraseSeq Phrase and sequence encoded into 32-bit word
        @param  note MIDI note number [0xFF for none]
    */
    void setTriggerNote(uint16_t phraseSeq, uint8_t note);

    /** @brief  Get MIDI trigger channel
        @retval uint8_t MIDI channel
    */
    uint8_t getTriggerChannel();

    /** @brief  Set MIDI trigger channel
        @param  channel MIDI channel [0..15 or other to disable MIDI trigger]
    */
    void setTriggerChannel(uint8_t channel);

    /** @brief  Get MIDI trigger device
        @retval uint8_t MIDI device index
    */
    uint8_t getTriggerDevice();

    /** @brief  Set MIDI trigger device
        @param  idev MIDI device index [0..15 or other to disable MIDI device]
    */
    void setTriggerDevice(uint8_t idev);

    /** @brief  Get sequence triggered by MIDI note
        @param  note MIDI note number
        @retval uint32_t Phrase and sequence encoded into 32-bit word 0xffffffff if not set
    */
    uint32_t getTriggerSequence(uint8_t note);

    /** @brief  Get overall quantity of playing sequences
        @retval size_t Quantity of sequence staring, playing or stopping. Zero if all sequences are stopped
    */
    size_t getPlayingSequencesCount();

    /** @brief  Stop all collections / sequences
    */
    void stop();

    /** @brief  Check if tempo has changed
        @retval bool True if tempo has changed
    */
    bool isTempoChanged();

    /** @brief  Get current tempo
        @param  clear True to clear current tempo changed flag (default: true)
        @retval float Current tempo
    */
    float getTempo(bool clear = true);

    /** @brief  Set current tempo
        @param  tempo Tempo in bpm
    */
    void setTempo(float tempo);

    /** @brief  Check if time signature has changed
        @retval bool True if time signature has changed
    */
    bool isTimeSigChanged();

    /** @brief  Get current time signature (beats in bar)
        @param  clear True to clear current sig changed flag (default: false)
        @retval uint8_t Current time signature
    */
    uint8_t getTimeSig(bool clear = false);

    /** @brief  Set current time signature (beats in bar)
        @param  sig Current time signature (in quarter notes)
    */
    void setTimeSig(uint8_t sig);

    /** @brief  Get default time signature (beats in bar)
        @retval uint8_t Default time signature
    */
    uint8_t getDefaultTimeSig();

    /** @brief  Set default time signature (beats in bar)
        @param  bpb default time signature (in quarter notes)
    */
    void setDefaultTimeSig(uint8_t bpb);

    /** @brief  Get playback progress percentage
        @param   uint8_t* Pointer to 33 element array containing progress as a percentage of sequence length
        @note   Element 32 (phrase launchers) is a percentage of the current time signature (beats per bar)
    */
    uint8_t* getProgress();

    /** @brief  Enable a channel
        @param  channel MIDI channel
        @param  enable True to enable
    */
    void enableChannel(uint8_t channel, bool enable);

    /** @brief  Is channel enabled
        @param  channel MIDI channel
        @retval bool True if channel is enabled
    */
    bool isChannelEnabled(uint8_t channel);

    // Phrase handling

    /** @brief  Get quantity of phrases
        @param  scene Index of scene
        @retval uint8_t Quantity of phrases
    */
    uint8_t getNumPhrases(uint8_t scene);

    /** @brief  Add phrase
        @param  scene Index of scene
        @param  phrase Index of phrase to insert before
        @retval Sequence* Pointer to the phrase sequence or nullptr on failure
    */
    Sequence* insertPhrase(uint8_t scene, uint8_t phrase);

    /** @brief  Duplicate phrase
        @param  scene Index of scene
        @param  phrase Index of phrase to duplicate
        @retval Sequence* Pointer to the phrase sequence or nullptr on failure
    */
    Sequence* duplicatePhrase(uint8_t scene, uint8_t phrase);

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

    /** @brief  Set the time signature for a phrase
        @param  scene Index of scene
        @param  phrase Index of phrase
        @param  bpb Time signature in Beats per Bar
    */
    void setPhraseTimeSig(uint8_t scene, uint8_t phrase, uint8_t bpb);

    /** @brief  Set the time signature for a phrase
        @param  scene Index of scene
        @param  phrase Index of phrase
        @retval uint8_t Phrase's time signature in Beats per Bar
    */
    uint8_t getPhraseTimeSig(uint8_t scene, uint8_t phrase);

    /** @brief  Is a phrase empty?
        @param  scene Index of scene
        @param  phrase Index of phrase
        @retval bool True is phrase is empty => all its sequences are empty
    */
    bool isPhraseEmpty(uint8_t scene, uint8_t phrase);

    /** @brief  Set follow action
        @param  scene Index of scene
        @param  sequence Pointer to sequence
        @param  action Follow action @see FOLLOW_ACTION enum
        @param  param Parameter of action, e.g. offset
        @param  flags Bitwise flags indicating which play loops should be skipped
        @param  repeat Quantity of repeats of follow action
        @retval bool True on success
    */
    bool setFollowAction(uint8_t scene, Sequence* sequence, uint8_t action, int16_t param, uint32_t flags, uint8_t repeat);

    /** @brief  Reset all follow repeat counter
    */
    void resetFollowRepeat();

    private:

    int fileWrite32(uint32_t value, FILE* pFile);
    int fileWrite16(uint16_t value, FILE* pFile);
    int fileWrite8(uint8_t value, FILE* pFile);
    uint32_t fileRead32(FILE* pFile);
    uint16_t fileRead16(FILE* pFile);
    uint8_t fileRead8(FILE* pFile);
    void refreshPhrases(uint8_t scene);

    bool m_bTempoChanged = false;     // True if tempo changed by sequence
    float m_fTempo = DEFAULT_TEMPO;   // Current tempo
    bool m_bTimeSigChanged = false;   // True if time signature changed by sequence
    uint8_t m_nTimeSig = DEFAULT_BPB;           // Current time signature in beats (1/4 notes) per bar
    uint8_t m_nDefaultTimeSig = DEFAULT_BPB;    // Default time signature in beats (1/4 notes) per bar
    uint8_t m_nTriggerDevice = 0xFF;  // MIDI device to receive sequence triggers (note-on)
    uint8_t m_nTriggerChannel = 0xFF; // MIDI channel to receive sequence triggers (note-on)
    uint8_t m_aGroupProgress[33];     // Array of group playback progress percentage
    uint8_t m_nBeatsPerBar = 4;       // Time signature in beats
    uint8_t m_bEnabled[32];           // Array indicating if channel is enabled
    uint8_t m_nScene = 0;             // Index of selected scene
    uint8_t m_nFollowCount = 0;           // Quantity of times the current follow loop has repeated
    std::vector<std::vector<Sequence*>> m_vScenes; // Vector of vectors of pointers to phrase sequences, indexed by scene.
        // m_vScenes[scene][phrase] = pPhrase, a sequence with child sequences.

    // Note: Maps are used for patterns and sequences to allow addition and removal of sequences whilst maintaining consistent access to remaining instances
    std::map<uint32_t, Pattern*> m_mPatterns;  // Map of pattern pointers indexed by pattern number
    std::vector<Sequence*> m_vPlayingSequences; // Vector of pointers to currently playing sequences (used to optimise play control)
    std::map<uint8_t, uint16_t> m_mTriggers;   // Map of phrase,sequence indexed by MIDI note triggers
};
