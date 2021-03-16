#pragma once
#include "pattern.h"
#include <map>
#include <forward_list>

struct SEQ_EVENT
{
    uint32_t time;
    MIDI_MESSAGE msg;
};

/** Track class provides an arbritary quantity of non-overlapping patterns.
*   One or more tracks are grouped into a sequence and played in unison.
*   Each track may be muted / soloed and drive a different MIDI channel
*/
class Track
{
    public:
        /** @brief   Add pattern to track
        *   @param   position Quantity of clock cycles from start of track at which to add pattern
        *   @param   pattern Pointer to pattern to add
        *   @param   force True to remove overlapping patterns, false to fail if overlapping patterns (Default: false)
        *   @retval bool True if pattern added
        *   @todo   Handle pattern pointer becoming invalid
        */
        bool addPattern(uint32_t position, Pattern* pattern, bool force = false);

        /** @brief  Remove pattern from track
        *   @param  position Quantity of clock cycles from start of track at which pattern starts
        */
        void removePattern(uint32_t position);

        /** @brief  Get pattern starting at position
        *   @param  position Quantity of clock cycles from start of track at which pattern starts
        *   @retval Pattern* Pointer to pattern or NULL if no pattern starts at this position
        */
        Pattern* getPattern(uint32_t position);

        /** @brief  Get pattern spanning position
        *   @param  position Quantity of clock cycles from start of track at which pattern spans
        *   @retval Pattern* Pointer to pattern or NULL if no pattern starts at this position
        */
        Pattern* getPatternAt(uint32_t position);

        /** @brief  Get MIDI channel
        *   @retval uint8_t MIDI channel
        */
        uint8_t getChannel();

        /** @brief  Set MIDI channel
        *   @param  channel MIDI channel
        */
        void setChannel(uint8_t channel);

        /** @brief  Get JACK output
        *   @retval uint8_t JACK output
        */
        uint8_t getOutput();

        /** @brief  Set JACK output
        *   @param  channel JACK output
        */
        void setOutput(uint8_t output);

        /** @brief  Handle clock signal
        *   @param  nTime Time (quantity of samples since JACK epoch)
        *   @param  nPosition Play position within sequence in clock cycles
        *   @param  dSamplesPerClock Samples per clock
        *   @param  bSync True if sync point
        *   @retval uint8_t 1 if a step needs processing for this track
        *   @note   Tracks are clocked syncronously but not locked to absolute time so depend on start time for absolute timing
        */
        uint8_t clock(uint32_t nTime, uint32_t nPosition,  double dSamplesPerClock, bool bSync);

        /** @brief  Gets next event at current clock cycle
        *   @retval SEQ_EVENT* Pointer to sequence event at this time or NULL if no more events
        *   @note    Start, end and interpolated events are returned on each call. Time is offset from start of clock cycle in samples.
        */
        SEQ_EVENT* getEvent();

        /** @brief  Update length of track by iterating through all patterns to find last clock cycle
        *   @retval uint32_t Duration of track in clock cycles
        */
        uint32_t updateLength();

        /** @brief  Get duration of track in clock cycles
        *   @retval uint32_t Length of track in clock cycles
        */
        uint32_t getLength();

        /** @brief  Remove all patterns from track
        */
        void clear();

        /** @brief  Get position of playhead within currently playing pattern
        *   @retval uint32_t Quantity of steps from start of pattern to playhead
        */
        uint32_t getPatternPlayhead();

        /** @brief  Set position of playhead within currently playing pattern
        *   @param  uint32_t Quantity of steps from start of pattern to playhead
        */
        void setPatternPlayhead(uint32_t step);

        /** @brief  Set position
        *   @param  position Quantity of clocks since start of track
        */
        void setPosition(uint32_t position);

        /** @brief  Get position of next pattern in track
        *   @param  previous Position of previous pattern (Empty to get first pattern)
        *   @retval uint32_t Position of next pattern or 0xFFFFFFFF if no more patterns
        */
        uint32_t getNextPattern(uint32_t previous = 0xFFFFFFFF);

        /** @brief  Get quantity of patterns in track
        *   @retval uint32_t Quantity of patterns in track
        */
        size_t getPatterns();

        /** @brief  Set map / scale index
        *   @param  map
        */
        void setMap(uint8_t map);

        /** @brief  Get map / scale index
        *   @retval uint8_t Map / scale index
        */
        uint8_t getMap();

        /** @brief  Solo track
        *   @param  solo True to solo [Default: true]
        */
        void solo(bool solo=true);

        /** @brief  Get solo state of track
        *   @retval bool True if solo
        */
        bool isSolo();

        /** @brief  Mute track
        *   @param  mute True to solo [Default: true]
        */
        void mute(bool mute=true);

        /** @brief  Get mute state of track
        *   @retval bool True if muted
        */
        bool isMuted();

        /** @brief  Check if a parameter has changed since last call
        *   @retval bool True if changed
        *   @note    monitors: state, mode, group
        */
        bool hasChanged();

        /** @brief  Gets the pattern defined by index
        *   @param  index Index of pattern
        *   @retval Pattern* Pointer to pattern or Null if no pattern at index.
        *   @note    Adding, removing or moving patterns may invalidate the index 
        */
        Pattern* getPatternByIndex(size_t index);

        /** @brief  Get position of pattern defined by index
        *   @param  index Index of pattern
        *   @retval uint32_t Position in clock cycles or -1 if invalid index
        */
        uint32_t getPatternPositionByIndex(size_t index);

        /** @brief  Get position of pattern defined by pattern pointer
        *   @param  pattern Pointer to pattern
        *   @retval uint32_t Position in clock cycles or -1 if invalid index
        */
        uint32_t getPatternPosition(Pattern* pattern);

    private:
        uint8_t m_nChannel = 0; // MIDI channel
        uint8_t m_nOutput = 0; // JACK output
        uint8_t m_nMap = 0; // Map / scale index
        uint32_t m_nClkPerStep = 1; // Clock cycles per step
        uint32_t m_nDivCount = 0; // Current count of clock cycles within divisor
        std::map<uint32_t,Pattern*> m_mPatterns; // Map of pointers to patterns, indexed by start position
        int m_nCurrentPatternPos = -1; // Start position of pattern currently being played
        int m_nNextEvent = -1; // Index of next event to process or -1 if no more events at this clock cycle
        int8_t m_nEventValue = -1; // Value of event at current interpolation point or -1 if no event
        uint32_t m_nLastClockTime = 0; // Time of last clock pulse (sample)
        uint32_t m_nCurrentStep = 0; // Postion within pattern (step)
        uint32_t m_nTrackLength = 0; // Quantity of clock cycles in track (last pattern start + length)
        double m_dSamplesPerClock; // Quantity of samples per MIDI clock cycle used to schedule future events, e.g. note off / interpolation
        bool m_bSolo = false; // True if track is solo
        bool m_bMute = false; // True if track is muted
        bool m_bChanged = true; // True if state changed since last hasChanged()
};
