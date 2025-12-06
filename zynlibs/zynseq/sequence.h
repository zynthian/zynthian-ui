/*  Declares Sequence class collection of tracks
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

#include "constants.h"
#include "timebase.h"
#include "track.h"
#include <string>
#include <vector>

/** Sequence class provides a collection of tracks
 *   A collection of tracks that will play in unison / simultaneously
 *   A timebase track which allows change of tempo and time signature during playback
 *   A sequence can be triggered as a linear song or a looping pad
*/
class Sequence {
  public:
    /** @brief  Create Sequence object
    */
    Sequence(Sequence* phraseSequence);

    /** @brief  Get sequence's mutually excusive group
        @retval uint32_t sequence's group
    */
    uint8_t getGroup();

    /** @brief  Set sequence's mutually exclusive group
        @param  group Index of group
    */
    void setGroup(uint8_t group);

    /** @brief  Get play mode
        @retval uint8_t Stop mode (bits 0..1). Start mode (bit 2) modes.
    */
    uint8_t getPlayMode();

    /** @brief  Set play mode
        @param  mode Stop mode (bits 0..1). Start mode (bit 2) modes.
    */
    void setPlayMode(uint8_t mode);

    /** @brief  Get sequence's play state
        @retval uint8_t Play state [STOPPED | PLAYING | STOPPING | STARTING | STOPPING_SYNC]
    */
    uint8_t getPlayState();

    /** @brief  Set sequence's play state
        @param  state Play state [STOPPED | PLAYING | STOPPING]
        @param  updatePhrase True to update phrase play status (default True)
    */
    void setPlayState(uint8_t state, bool updatePhrase = true);

    /** @brief  Get sequence state
        @retval uint32_t Sequence state as 32-bit word [repeat, group, mode, play state]
    */
    uint32_t getState();

    /** @brief  Updates the play state of a phrase
    */
    void updatePhraseState();

    /** @brief  Add new track to sequence
        @param  track Index of track afterwhich to add new track (Optional - default: add to end of sequence)
        @retval uint32_t Index of track added
    */
    uint32_t addTrack(uint32_t track = -1);

    /** @brief  Remove a track from the sequence
        @param  track Index of track within sequence
        @retval bool True on success
    */
    bool removeTrack(size_t track);

    /** @brief  Get quantity of tracks in sequence
        @retval uint32_t Quantity of tracks
    */
    uint32_t getTracks();

    /** @brief  Clear all tracks from sequence
    */
    void clear();

    /** @brief  Get pointer to a track
        @param  index Index of track within sequence
        @retval Track* Pointer to track or NULL if bad index
    */
    Track* getTrack(size_t index);

    /** @brief  Set tempo
        @param  tempo Tempo in BPM
    */
    void setTempo(float tempo);

    /** @brief  Get tempo
        @retval float Tempo in BPM
    */
    float getTempo();

    /** @brief  Set time signature
        @param  sig Time signature (beats per bar)
    */
    void setTimeSig(uint8_t sig);

    /** @brief  Get time signature
        @retval uint8_t Time signature (beats per bar)
    */
    uint8_t getTimeSig();

    /** @brief  Add tempo event to timebase track
        @param  tempo Tempo in BPM
        @param  bar Bar (measure) at which to set tempo [Optional - default: 1]
        @param  tick Tick at which to set tempo [Optional - default: 0]
        @note   Removes tempo if same as previous tempo
    */
    void addTempo(float tempo, uint16_t bar = 1, uint16_t tick = 0);

    /** @brief  Remove tempo event from timebase track
        @param  bar Bar (measure) at which to set tempo [Optional - default: 1]
        @param  tick Tick at which to set tempo [Optional - default: 0]
    */
    void removeTempo(uint16_t bar = 1, uint16_t tick = 0);

    /** @brief  Get tempo from timebase track
        @param  bar Bar (measure) at which to get tempo
        @param  beat Tick at which to get tempo [Optional - default: 0]
        @retval float Tempo in BPM or 0.0 if no tempo in timebase
    */
    float getTempoAt(uint16_t bar, uint16_t tick = 0);

    /** @brief  Add time signature to timebase track
        @param  timeSig Beats per bar
        @param  bar Bar (measure) at which to set time signature [Optional - default: 1]
        @note   Removes time signature if same as previous time signature
    */
    void addTimeSig(uint8_t timeSig, uint16_t bar = 1);

    /** @brief  Remove time signature from timebase track
        @param  bar Bar (measure) at which to remove time signature
        @param  timeSig Beats per bar
    */
    void removeTimeSig(uint16_t bar);

    /** @brief  Get time signature from timebase track
        @param  bar Bar (measure) at which to get time signature
        @retval uint16_t Beats per bar
    */
    uint8_t getTimeSigAt(uint16_t bar);

    /** @brief  Get pointer to timebase track
        @retval Timebase* Pointer to timebase map
    */
    Timebase* getTimebase();

    /** @brief  Handle clock signal
        @param  nTime Time (quantity of samples since JACK epoch)
        @param  bSync True to indicate sync pulse, e.g. to sync tracks
        @param  dSamplesPerClock Samples per clock
        @param  nTimeSig Beats per bar
        @retval uint8_t Bitwise flag of what clock triggers (See CLOCK_TRIG_ constants)
        @note   Sequences are clocked syncronously but not locked to absolute time so depend on start time for absolute timing
        @note   Will clock each track
    */
    uint8_t clock(uint32_t nTime, bool bSync, double dSamplesPerClock, uint8_t nTimeSig);

    /** @brief  Gets next event at current clock cycle
        @retval SEQ_EVENT* Pointer to sequence event at this time or NULL if no more events
        @note   Start, end and interpolated events are returned on each call. Time is offset from start of clock cycle in samples.
    */
    SEQ_EVENT* getEvent();

    /** @brief  Updates sequence length from track lengths
        @param  length Optional length to force sequence to
    */
    void updateLength(uint32_t length=0);

    /** @brief  Get sequence length
        @retval uint32_t Length of sequence (longest track) in clock cycles
    */
    uint32_t getLength();

    /** @brief  Check if sequence is empty
        @retval bool True if empty. False if any patterns have any events)
    */
    bool isEmpty();

    /** @brief  Set position of playback within sequence
        @param  position Postion in clock cycles from start of sequence
    */
    void setPlayPosition(uint32_t position);

    /** @brief  Get position of playback within sequence
        @retval uint32_t Postion in clock cycles from start of sequence
    */
    uint32_t getPlayPosition();

    /** @brief  Flag sequence as modified
    */
    void setModified();

    /** @brief  Check if sequence state has changed since last call
        @retval bool True if changed
        @note   Monitors group, mode, tracks, playstate
    */
    bool isModified();

    /** @brief  Set sequence name
        @param  std::string Sequence name (will be truncated at 16 characters)
    */
    void setName(std::string sName);

    /** @brief  Get sequence name
        @retval std::string Sequence name (maximum 16 characters)
    */
    std::string getName();

    /** @brief  Set follow sequence
        @param  sequence Pointer to follow sequence
        @param  action Follow action @see FOLLOW_ACTION enum
        @param  param Follow action parameter
    */
    void setFollowSequence(Sequence* pSequence, uint8_t action, int16_t param);

    /** @brief  Get follow sequence
        @retval Sequence* Pointer to follow sequence
    */
    Sequence* getFollowSequence();

    /** @brief  Get follow action
        @retval uint8_t Follow action
    */
    uint8_t getFollowAction();

    /** @brief  Get follow action parameter
        @retval uint8_t Follow action parameter
    */
    uint8_t getFollowParam();

    /** @brief  Set times to play
        @param  repeat Quantity of times to play (0 to disable)
    */
    void setRepeat(uint8_t repeat);

    /** @brief  Get times to play
        @retval uint8_t Quantity of times to play (0 to disable)
    */
    uint8_t getRepeat();

    /** @brief Set times played
    */
    void setPlayed(uint8_t played);

    /** @brief Get times played
    */
    uint8_t getPlayed();

    /** @brief  Is this sequence a phrase launcher?
        @retval bool True if phrase launcher
    */
    bool isPhraseLauncher();

    /** @brief  Sets phrase the sequence belongs
        @param  phrase Index of phrase (0xff for none)
    */
    void setPhrase(uint8_t phrase);

    /** @brief  Gets phrase the sequence belongs
        @retval uint8_t Phrase Index of phrase (0xff for none)
    */
    uint8_t getPhrase();

    Sequence* m_aChildSequences[32];   // List of pointers to sequences in phrase

  private:
    std::vector<Track> m_vTracks;               // Vector of tracks within sequence
    Timebase m_timebase;                        // Timebase map
    TimebaseEvent* m_pNextTimebaseEvent = NULL; // Pointer to next timebase event or NULL if none.
    size_t m_nCurrentTrack = 0;                 // Index of track currently being queried for events
    uint32_t m_nPosition = 0;                   // Play position in clock cycles
    uint32_t m_nLength = 0;                     // Length of sequence in clock cycles (longest track)
    float m_fTempo = 0.0;                       // Tempo (0.0 for none) - Only used by phrases
    uint8_t m_nTimeSig = 0;                     // Time signature in ticks per bar (0 for none, 24 ticks per beat) - Only used by phrases
    uint8_t m_nState = STOPPED;                 // Play state of sequence
    uint8_t m_nMode = MODE_END_SYNC;            // Bitwise flags: stop mode (bits 0..1), start mode (bit 2)
    uint8_t m_nGroup = 0;                       // Sequence's mutually exclusive group
    uint8_t m_nRepeat = 0;                      // Quantity of times to play sequence
    uint8_t m_nCount = 0;                       // Quantity of times to sequence has played
    uint8_t m_nPhrase = 0xff;                   // Index of phrase this sequence belongs - 0xff for none
    bool m_bChanged = false;                    // True if sequence content changed
    bool m_bStateChanged = false;               // True if state changed since last clock cycle
    bool m_bEmpty = true;                       // True if all patterns are emtpy (no events)
    std::string m_sName;                        // Sequence name
    uint8_t m_nFollowAction = FOLLOW_ACTION_NONE; // Follow action to perform when sequence ends
    int16_t m_nFollowParam = 0;                 // Follow action parameter
    Sequence* m_pFollowSequence = nullptr;      // Pointer to follow sequence (null for no follow action)
    Sequence* m_pPhraseSequence = nullptr;      // Pointer to phrase sequence (null if not in a phrase, e.g. is a phrase)
};
