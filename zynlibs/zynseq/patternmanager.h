#pragma once
#include "pattern.h"
#include "sequence.h"
#include "song.h"
#include <map>

#define DEFAULT_TRACK_COUNT 4
#define FILE_VERSION 2

/** PatternManager class provides creation, recall, update and delete of patterns which other modules can subseqnetly use. It manages persistent (disk) storage. PatternManager is implemented as a singleton ensuring a single instance is available to all callers.
*/
class PatternManager
{
    public:
        /** @brief  Get a pointer to the Pattern Manager singleton instance
        *   @retval PatternManager* Pointer to singlton
        */
        static PatternManager* getPatternManager();

        /** @brief  Initialise pattern manager
        */
        void init();

        /** @brief  Load patterns from file
        *   @param  filename Full or relative path and name of file
        *   @retval bool True on success
        */
        bool load(const char* filename);

        /** @brief  Save patterns to file
        *   @param  filename Full or relative path and name of file
        */
        void save(const char* filename);

        /** @brief  Get pointer to a pattern
        *   @param  index Index of pattern to retrieve
        *   @retval Pattern* Pointer to pattern
        *   @note   If pattern does not exist a new, default, empty pattern is created
        */
        Pattern* getPattern(size_t index);

        /** @brief  Get the index of a pattern
        *   @param  pattern Pointer to pattern
        *   @retval uint32_t Index of pattern or -1 if not found
        */
        uint32_t getPatternIndex(Pattern* pattern);

        /** @brief  Create new pattern
        *   @retval size_t Index of new pattern
        *   @note   Use getPattern to retrieve pointer to pattern
        */
        size_t createPattern();

        /** @brief  Delete pattern
        *   @param  index Index of the pattern to delete
        */
        void deletePattern(size_t index);

        /** @brief  Copy pattern
        *   @param  source Index of pattern to copy from
        *   @param  destination Index of pattern to populate
        */
        void copyPattern(uint32_t source, uint32_t destination);
        
        /** @param  Get sequence
        *   @param  Index of sequence
        *   @retval Sequence* Pointer to sequence
        */
        Sequence* getSequence(uint32_t sequence);

        /** @brief  Update sequence lengths in current song
        /** @param  song Index of song to update
        *   @retval uint32_t Clock cycle of end of last sequence in current song
        *   @note   Blunt tool to update each sequence after any pattern length changes
        */
        uint32_t updateSequenceLengths(uint32_t song);

        /** @brief  Update all sequence lengths
        *   @note   Blunt tool to update each sequence after any pattern length changes
        */
        void updateAllSequenceLengths();

        /** @brief  Handle clock
        *   @param  nTime Offset since JACK epoch for start of next period
        *   @param  pSchedule Pointer to the schedule to populate with events
        *   @param  bSync True indicates a sync pulse
        *   @param  dSamplesPerClock Quantity of samples in each clock cycle
        *   @retval bool True if pattern is not stopped
        */
        bool clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync, double dSamplesPerClock);

        /** @brief  Get pointer to a song
        *   @param  index Index of song to retrieve
        *   @retval Song* Pointer to song
        *   @note   If song does not exist a new, default, empty song is created
        */
        Song* getSong(size_t index);

        /** @brief  Add sequence to song as new track
        *   @param  song Index of song
        *   @retval Index of new track
        */
        uint32_t addTrack(uint32_t song);

        /** @brief  Remove track from song
        *   @param  song Index of song
        *   @param  track Indx of track
        */
        void removeTrack(uint32_t song, uint32_t track);

        /** @brief  Copy song
        *   @param  source Index of song to copy from
        *   @param  destination Index of song to populate
        */
        void copySong(uint32_t source, uint32_t destination);

        /** @brief  Clear all tracks from song
        *   @param  song Song index
        */
        void clearSong(uint32_t song);

        /** Start song playing
        *	@param	bFast True to start playing immediately. False to wait for next sync pulse.
        */
        void startSong(bool bFast = false);

        /** Stop song playing
        */
        void stopSong();

        /** Set song play position
        *   @param pos Song position
        */
        void setSongPosition(uint32_t pos);

        /** Set sequence play state
        *   @param sequence Sequence index
        *   @param state Play state
        *   @note  Stops other sequences in group
        */
        void setSequencePlayState(uint32_t sequence, uint8_t state);

        /** @brief  Get MIDI note number used to trigger sequence
        *   @param  sequence Index of sequence
        *   @retval uint8_t MIDI note number [0xFF for none]
        */
        uint8_t getTriggerNote(uint32_t sequence);

        /** @brief  Set MIDI note number used to trigger sequence
        *   @param  sequence Index of sequence
        *   @param  note MIDI note number [0xFF for none]
        */
        void setTriggerNote(uint32_t sequence, uint8_t note);

        /** @brief  Get MIDI trigger channel
        *   @retval uint8_t MIDI channel
        */
        uint8_t getTriggerChannel();

        /** @brief  Set MIDI trigger channel
        *   @param  channel MIDI channel
        */
        void setTriggerChannel(uint8_t channel);

        /** @brief  Trigger sequence
        *   @param  note MIDI note number
        *   @retval uint32_t Index of sequence triggered (or stopped) or 0 if no sequence triggered (can't trigger sequence 9)
        */
        uint32_t trigger(uint8_t note);

        /** @brief  Set the current song
        *   @param  song Song to select
        */
        void setCurrentSong(uint32_t song);

        /** @brief  Get current song
        *   @retval  uint32_t Index of current song
        */
        uint32_t getCurrentSong();

        /** @brief  Get overall play state
        *   @retval bool True if any sequence is staring, playing or stopping. False if all sequences are stopped
        */
        bool isPlaying();

        /** @brief  Stop all sequences
        */
        void stop();

    private:
        PatternManager(); // Private constructor to avoid public instantiation
        PatternManager(const PatternManager&); // Do not allow public copying
        PatternManager& operator = (const PatternManager&); // Do not allow public copying
        int fileWrite32(uint32_t value, FILE *pFile);
        int fileWrite16(uint16_t value, FILE *pFile);
        int fileWrite8(uint8_t value, FILE *pFile);
        uint32_t fileRead32(FILE* pFile);
        uint16_t fileRead16(FILE* pFile);
        uint8_t fileRead8(FILE* pFile);
        bool doClock(uint32_t nSong, uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync, double dSamplesPerClock);

        uint8_t m_nTriggerChannel = 15; // MIDI channel to recieve sequence triggers (note-on)
        uint32_t m_nCurrentSong = 0; // Currently selected song (ZynPad uses +1000)

        static PatternManager* m_pPatternManager; // Pointer to the singleton
        // Note: Maps are used for patterns and sequences to allow addition and removal of sequences whilst maintaining consistent access to remaining instances
        std::map<size_t,Pattern> m_mPatterns; // Map of patterns indexed by pattern number
        std::map<size_t,Sequence> m_mSequences; // Map of sequences indexed by sequence number
        std::map<size_t,Song> m_mSongs; // Map of songs indexed by song number
        std::map<uint32_t, uint32_t> m_mSongSequences; // Map of songs indexed by sequences
        std::map<uint8_t, uint32_t> m_mTriggers; // Map of sequences indexed by MIDI note triggers
};
