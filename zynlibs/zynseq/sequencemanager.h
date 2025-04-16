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
#include "pattern.h"
#include "sequence.h"
#include "track.h"
#include <map>

#define DEFAULT_TRACK_COUNT 4

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

    /** @brief  Get pointer to a pattern
        @param  index Index of pattern to retrieve
        @retval Pattern* Pointer to pattern
        @note   If pattern does not exist a new, default, empty pattern is created
    */
    Pattern* getPattern(uint32_t index);

    /** @brief  Get the index of a pattern
        @param  pattern Pointer to pattern
        @retval uint32_t Index of bank<<24|pattern or -1 if not found
    */
    uint32_t getPatternIndex(Pattern* pattern);

    /** @brief  Get next populated pattern after current pattern
        @param  pattern Index of current pattern
        @retval uint32_t Index of pattern
    */
    uint32_t getNextPattern(uint32_t pattern);

    /** @brief  Create new pattern
        @retval uint32_t Index of new pattern
        @note   Use getPattern to retrieve pointer to pattern
    */
    uint32_t createPattern();

    /** @brief  Delete pattern
        @param  index Index of the pattern to delete
    */
    void deletePattern(uint32_t index);

    /** @brief  Copy pattern
        @param  source Index of pattern to copy from
        @param  destination Index of pattern to populate
    */
    void copyPattern(uint32_t source, uint32_t destination);

    /** @brief  Update sequence lengths in current bank
        @param  bank Index of bank
        @param  sequence Index of sequence
    */
    void updateSequenceLength(uint8_t bank, uint8_t sequence);

    /** @brief  Update all sequence lengths
        @note   Blunt tool to update each sequence after any pattern length changes
    */
    void updateAllSequenceLengths();

    /** @brief  Handle clock
        @param  timeinfo Pair: Offset since JACK epoch for start of next period, duration of clock cycle in frames
        @param  pSchedule Pointer to the schedule to populate with events
        @param  bSync True indicates a sync pulse
        @param  dSamplesPerClock Quantity of samples in each clock cycle
        @retval size_t Quantity of playing sequences
    */
    size_t clock(std::pair<double, double> timeinfo, std::multimap<uint32_t, MIDI_MESSAGE*>* pSchedule, bool bSync);

    /** @brief  Get pointer to sequence
        @param  bank Index of bank containing sequence
        @param  sequence Index of sequence
        @param  create_pattern True to create pattern when creating new sequence
        @retval Sequence* Pointer to sequence
        @note   Creates new bank and/or sequence if not existing
    */
    Sequence* getSequence(uint8_t bank, uint8_t sequence, bool create_pattern = false);

    /** @brief  Get follow action for a sequence
        @param  bank In dex of bank containing sequence
        @param  sequence Index of sequence
        @retval uint8_t Follow action
    */
    uint8_t getFollowAction(uint8_t bank, uint8_t sequence);

    /** @brief  Add pattern to sequence
        @param  bank Index of bank
        @param  sequence Index of sequence
        @param  track Index of track
        @param  position Quantity of clock cycles from start of track at which to add pattern
        @param  pattern Index of pattern
        @param  force True to remove overlapping patterns, false to fail if overlapping patterns
        @retval True if pattern inserted
    */
    bool addPattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position, uint32_t pattern, bool force);

    /** @brief  Remove pattern from track
        @param  bank Index of bank
        @param  sequence Index of sequence
        @param  track Index of track
        @param  position Quantity of clock cycles from start of track from which to remove pattern
    */
    void removePattern(uint8_t bank, uint8_t sequence, uint32_t track, uint32_t position);

    /** @brief Set sequence play state
        @param  bank Index of bank containing sequence
        @param  sequence Index of sequence
        @param  state Play state
        @note   Stops other sequences in group
    */
    void setSequencePlayState(uint8_t bank, uint8_t sequence, uint8_t state);

    /** @brief  Move sequence
        @param  bank Index of bank
        @param  sequence Index of sequence
        @param  newSeq Index of new sequence
        @note   Existing sequence with id newSeq will be replace and old sequence will be deleted.
    */
    void moveSequence(uint8_t bank, uint8_t sequence, uint8_t newSeq);

    /** @brief  Get MIDI note number used to trigger sequence
        @param  bank Index of bank containing sequence
        @param  offset Index (offset) of sequence within bank
        @retval uint8_t MIDI note number [0xFF for none]
    */
    uint8_t getTriggerNote(uint8_t bank, uint8_t sequence);

    /** @brief  Set MIDI note number used to trigger sequence
        @param  bank Index of bank containing sequence
        @param  offset Index (offset) of sequence within bank
        @param  note MIDI note number [0xFF for none]
    */
    void setTriggerNote(uint8_t bank, uint8_t sequence, uint8_t note);

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
        @retval uint16_t Bank (MSB) and Sequence (LSB) or 0 if not configured
    */
    uint16_t getTriggerSequence(uint8_t note);

    /** @brief  Set the current bank
        @param  bank Bank to select
    */
    void setCurrentBank(uint32_t bank);

    /** @brief  Get current bank
        @retval uint32_t Index of current bank
    */
    uint32_t getCurrentBank();

    /** @brief  Get overall quantity of playing sequences
        @retval size_t Quantity of sequence staring, playing or stopping. Zero if all sequences are stopped
    */
    size_t getPlayingSequencesCount();

    /** @brief  Stop all collections / sequences
    */
    void stop();

    /** @brief  Remove all unused empty patterns
    */
    void cleanPatterns();

    /** @brief  Get quantity of sequences in a bank
        @param  bank Index of bank
    */
    uint32_t getSequencesInBank(uint32_t bank);

    /** @brief  Remove sequence from bank
        @param  bank Index of bank
        @param  sequence Index of sequence to remove
        @note   Sequences after remove point are moved down by one. Bank grows if sequence is higher than size of bank
    */
    void removeSequence(uint8_t bank, uint8_t sequence);

    /** @brief  Remove all sequences from bank
        @param  bank Index of bank
    */
    void clearBank(uint32_t bank);

    /** @brief  Get quantity of banks
        @retval uint32_t Quantity of populated banks
    */
    uint32_t getBanks();

    /** @brief  Check if tempo has changed
        @retval bool True if tempo has changed
    */
    bool isTempoChanged();

    /** @brief  Get current tempo
        @param  clear True to clear current tempo changed flag (default: true)
        @retval float Current tempo
    */
    float getTempo(bool clear = true);

    /** @brief  Check if time signature has changed
        @retval bool True if time signature has changed
    */
    bool isTimeSigChanged();

    /** @brief  Get current time signature (beats in bar)
        @param  clear True to clear current sig changed flag (default: true)
        @retval uint16_t Current time signature
    */
    uint16_t getTimeSig(bool clear = true);

    /** @brief  Set current time signature (beats in bar)
        @param  sig Current time signature
    */
    void setTimeSig(uint16_t sig);

  private:
    int fileWrite32(uint32_t value, FILE* pFile);
    int fileWrite16(uint16_t value, FILE* pFile);
    int fileWrite8(uint8_t value, FILE* pFile);
    uint32_t fileRead32(FILE* pFile);
    uint16_t fileRead16(FILE* pFile);
    uint8_t fileRead8(FILE* pFile);
    bool checkBlock(FILE* pFile, uint32_t nActualSize, uint32_t nExpectedSize);

    bool m_bTempoChanged = false;     // True if tempo changed by sequence
    float m_fTempo = DEFAULT_TEMPO;   // Current tempo
    bool m_bTimeSigChanged = false;   // True if time signature changed by sequence
    uint8_t m_nTimeSig = 4;           // Current time signature
    uint8_t m_nTriggerDevice = 0xFF;  // MIDI device to receive sequence triggers (note-on)
    uint8_t m_nTriggerChannel = 0xFF; // MIDI channel to receive sequence triggers (note-on)

    // Note: Maps are used for patterns and sequences to allow addition and removal of sequences whilst maintaining consistent access to remaining instances
    std::map<uint32_t, Pattern*> m_mPatterns;  // Map of pattern pointers indexed by pattern number
    std::vector<uint16_t> m_vPlayingSequences; // Vector of <bank<<8|sequence>for currently playing sequences (used to optimise play control)
    std::map<uint8_t, uint16_t> m_mTriggers;   // Map of bank<<8|sequence indexed by MIDI note triggers
    std::map<uint8_t, std::map<uint8_t, Sequence>>
        m_mBanks; // Map of banks of sequences, indexed by bank number. Sequences map of sequences, mapped by sequence number.
};
