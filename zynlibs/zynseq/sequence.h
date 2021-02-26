#pragma once

#include "constants.h"
#include "track.h"
#include "timebase.h"
#include <vector>
#include <string>

/** Sequence class provides a collection of tracks
*   A collection of tracks that will play in unison / simultaneously
*   A timebase track which allows change of tempo and time signature during playback
*   A sequence can be triggered as a linear song or a looping pad
*/
class Sequence
{
    public:
        /** @brief  Create Sequence object
        */
        Sequence();
        
        /** @brief  Get sequence's mutually excusive group
        *   @retval uint32_t sequence's group
        */
        uint8_t getGroup();

        /** @brief  Set sequence's mutually exclusive group
        *   @param  group Index of group
        */
       void setGroup(uint8_t group);

        /** @brief  Get play mode
        *   @retval uint8_t Play mode
        */
        uint8_t getPlayMode();

        /** @brief  Set play mode
        *   @param  mode Play mode [DISABLED | ONESHOT | LOOP | ONESHOTALL | LOOPALL | ONESHOTSYNC | LOOPSYNC]
        */
        void setPlayMode(uint8_t mode);

        /** @brief  Get sequence's play state
        *   @retval uint8_t Play state [STOPPED | PLAYING | STOPPING]
        */
        uint8_t getPlayState();

        /** @brief  Set sequence's play state
        *   @param  state Play state [STOPPED | PLAYING | STOPPING]
        */
        void setPlayState(uint8_t state);

        /** @brief  Add new track to sequence
        *   @param  track Index of track afterwhich to add new track (Optional - default: add to end of sequence)
        *   @retval uint32_t Index of track added
        */
        uint32_t  addTrack(uint32_t track = -1);
        
        /** @brief  Remove a track from the sequence
        *   @param  track Index of track within sequence
        *   @retval bool True on success
        */
        bool removeTrack(size_t track);
        
        /** @brief  Get quantity of tracks in sequence
        *   @retval size_t  Quantity of tracks
        */
        size_t getTracks();

        /** @brief  Clear all tracks from sequence
        */
        void clear();

        /** @brief  Get pointer to a track
        *   @param  index Index of track within sequence
        *   @retval Track* Pointer to track or NULL if bad index
        */
        Track* getTrack(size_t index);
    
        /** @brief  Add tempo event to timebase track
        *   @param  tempo Tempo in BPM
        *   @param  bar Bar (measure) at which to set tempo
        *   @param  tick Tick at which to set tempo [Optional - default: 0]
        *   @note   Removes tempo if same as previous tempo
        */
        void addTempo(uint16_t tempo, uint16_t bar, uint16_t tick=0);
        
        /** @brief  Get tempo from timebase track
        *   @param  bar Bar (measure) at which to get tempo
        *   @param  beat Tick at which to get tempo [Optional - default: 0]
        *   @retval uint16_t Tempo in BPM
        */
        uint16_t getTempo(uint16_t bar, uint16_t tick=0);

        /** @brief  Add time signature to timebase track
        *   @param  beatsPerBar Beats per bar
        *   @param  bar Bar (measure) at which to set time signature
        *   @note   Removes time signature if same as previous time signature
        */
        void addTimeSig(uint16_t beatsPerBar, uint16_t bar);

        /** @brief  Get time signature from timebase track
        *   @param  bar Bar (measure) at which to get time signature
        *   @retval uint16_t Beats per bar
        */
        uint16_t getTimeSig(uint16_t bar);

        /** @brief  Get pointer to timebase track
        *   @retval Timebase* Pointer to timebase map
        */
        Timebase* getTimebase();

        /** @brief  Handle clock signal
        *   @param  nTime Time (quantity of samples since JACK epoch)
        *   @param  bSync True to indicate sync pulse, e.g. to sync tracks
        *   @param  dSamplesPerClock Samples per clock
        *   @retval uint8_t Bitwise flag of what clock triggers [1=track step | 2=change of state]
        *     @note    Sequences are clocked syncronously but not locked to absolute time so depend on start time for absolute timing
        *   @note   Will clock each track
        */
        uint8_t clock(uint32_t nTime, bool bSync, double dSamplesPerClock);

        /** @brief  Gets next event at current clock cycle
        *   @retval SEQ_EVENT* Pointer to sequence event at this time or NULL if no more events
        *   @note   Start, end and interpolated events are returned on each call. Time is offset from start of clock cycle in samples.
        */
        SEQ_EVENT* getEvent();

        /** @brief  Updates sequence length from track lengths
        */
        void updateLength();

        /** @brief  Get sequence length
        *   @retval uint32_t Length of sequence (longest track) in clock cycles
        */
        uint32_t getLength();

        /** @brief  Set position of playback within sequence
        *   @param  position Postion in clock cycles from start of sequence
        */
        void setPlayPosition(uint32_t position);

        /** @brief  Get position of playback within sequence
        *   @retval uint32_t Postion in clock cycles from start of sequence
        */
        uint32_t getPlayPosition();

        /** @brief  Check if sequence state has changed since last call
        *   @retval bool True if changed
        *   @note   Monitors group, mode, tracks, playstate 
        */
        bool hasChanged();

        /** @brief  Set sequence name
        *   @param  std::string Sequence name (will be truncated at 16 characters)
        */
        void setName(std::string sName);

        /** @brief  Get sequence name
        *   @retval std::string Sequence name (maximum 16 characters)
        */
        std::string getName();

    private:
        std::vector<Track> m_vTracks; // Vector of tracks within sequence
        Timebase m_timebase; // Timebase map
        uint8_t m_nState = STOPPED; // Play state of sequence
        uint8_t m_nMode = LOOPALL; // Play mode of sequence
        size_t m_nCurrentTrack = 0; // Index of track currently being queried for events
        uint32_t m_nPosition = 0; // Play position in clock cycles
        uint32_t m_nLastSyncPos = 0; // Position of last sync pulse in clock cycles
        uint32_t m_nLength = 0; // Length of sequence in clock cycles (longest track)
        uint8_t m_nGroup = 0; // Sequence's mutually exclusive group
        uint16_t m_nTempo = 120; // Default tempo (overriden by tempo events in timebase map)
        bool m_bChanged = false; // True if sequence content changed
        bool m_bStateChanged = false; // True if state changed since last clock cycle
        std::string m_sName; // Sequence name
};