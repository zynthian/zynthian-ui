#pragma once
#include "pattern.h"
#include "sequence.h"
#include "track.h"
#include <map>

#define DEFAULT_TRACK_COUNT 4

/** SequenceManager class provides creation, recall, update and delete of patterns which other modules can subseqnetly use. It manages persistent (disk) storage. SequenceManager is implemented as a singleton ensuring a single instance is available to all callers.
*/
class SequenceManager
{
    public:
        /** @brief  Instantiate sequence manager object
        */
        SequenceManager();

        /** @brief  Initialise all data
        */
        void init();

        /** @brief  Get pointer to a pattern
        *   @param  index Index of pattern to retrieve
        *   @retval Pattern* Pointer to pattern
        *   @note   If pattern does not exist a new, default, empty pattern is created
        */
        Pattern* getPattern(uint32_t index);

        /** @brief  Get the index of a pattern
        *   @param  pattern Pointer to pattern
        *   @retval uint32_t Index of pattern or -1 if not found
        */
        uint32_t getPatternIndex(Pattern* pattern);

        /** @brief  Get next populated pattern after current pattern
        *   @param  pattern Index of current pattern
        *   @retval uint32_t Index of pattern
        */
       uint32_t getNextPattern(uint32_t pattern);

        /** @brief  Create new pattern
        *   @retval uint32_t Index of new pattern
        *   @note   Use getPattern to retrieve pointer to pattern
        */
        uint32_t createPattern();

        /** @brief  Delete pattern
        *   @param  index Index of the pattern to delete
        */
        void deletePattern(uint32_t index);

        /** @brief  Copy pattern
        *   @param  source Index of pattern to copy from
        *   @param  destination Index of pattern to populate
        */
        void copyPattern(uint32_t source, uint32_t destination);
        
        /** @brief  Update sequence lengths in current bank
        *   @param  bank Index of bank
        *   @param  sequence Index of sequence
        */
        void updateSequenceLength(uint8_t bank, uint8_t sequence);

        /** @brief  Update all sequence lengths
        *   @note   Blunt tool to update each sequence after any pattern length changes
        */
        void updateAllSequenceLengths();

        /** @brief  Handle clock
        *   @param  nTime Offset since JACK epoch for start of next period
        *   @param  pSchedule Pointer to the schedule to populate with events
        *   @param  bSync True indicates a sync pulse
        *   @param  dSamplesPerClock Quantity of samples in each clock cycle
        *   @retval size_t Quantity of playing sequences
        */
        size_t clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule, bool bSync, double dSamplesPerClock);

        /** @brief  Get pointer to sequence
        *   @param  bank Index of bank containing sequence
        *   @param  offset Index (offset) of sequence within bank
        *   @retval Sequence* Pointer to sequence or NULL if invalid offset
        *   @note   Creates new bank and sequence if not existing
        */
       Sequence* getSequence(uint8_t bank, uint8_t sequence);

        /** @brief  Add pattern to sequence
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

        /** Set sequence play state
        *   @param  bank Index of bank containing sequence
        *   @param  offset Index (offset) of sequence within bank
        *   @param  state Play state
        *   @note   Stops other sequences in group
        */
        void setSequencePlayState(uint8_t bank, uint8_t sequence, uint8_t state);

        /** @brief  Get MIDI note number used to trigger sequence
        *   @param  bank Index of bank containing sequence
        *   @param  offset Index (offset) of sequence within bank
        *   @retval uint8_t MIDI note number [0xFF for none]
        */
        uint8_t getTriggerNote(uint8_t bank, uint8_t sequence);

        /** @brief  Set MIDI note number used to trigger sequence
        *   @param  bank Index of bank containing sequence
        *   @param  offset Index (offset) of sequence within bank
        *   @param  note MIDI note number [0xFF for none]
        */
        void setTriggerNote(uint8_t bank, uint8_t sequence, uint8_t note);

        /** @brief  Get MIDI trigger channel
        *   @retval uint8_t MIDI channel
        */
        uint8_t getTriggerChannel();

        /** @brief  Set MIDI trigger channel
        *   @param  channel MIDI channel [0..15 or other to disable MIDI trigger]
        */
        void setTriggerChannel(uint8_t channel);

        /** @brief  Get sequence triggered by MIDI note
        *   @param  note MIDI note number
        *   @retval uint16_t Bank (MSB) and Sequence (LSB) or 0 if not configured
        */
        uint16_t getTriggerSequence(uint8_t note);

        /** @brief  Set the current bank
        *   @param  bank Bank to select
        */
        void setCurrentBank(uint32_t bank);

        /** @brief  Get current bank
        *   @retval  uint32_t Index of current bank
        */
        uint32_t getCurrentBank();

        /** @brief  Get overall quantity of playing sequences
        *   @retval size_t Quantity of sequence staring, playing or stopping. Zero if all sequences are stopped
        */
        size_t getPlayingSequencesCount();

        /** @brief  Stop all colections / sequences
        */
        void stop();
        
        /** @brief  Remove all unused empty patterns
        */
        void cleanPatterns();

        /** @brief  Set quantity of sequences in a bank
        *   @param  bank Bank index
        *   @param  sequences Quantity of sequences
        *   @note   Sequences are created or destroyed as required
        */
        void setSequencesInBank(uint8_t bank, uint8_t sequences);

        /** @brief  Get quantity of sequences in a bank
        *   @param  bank Index of bank
        */
        uint32_t getSequencesInBank(uint32_t bank);

        /** @brief  Move sequence (change order of sequences)
        *   @param  bank Index of bank
        *   @param  sequence Index of sequence to move
        *   @param  position Index of sequence to move this sequence, e.g. 0 to insert as first sequence
        *   @note   Sequences after insert point are moved up by one. Bank grows if sequence or position is higher than size of bank
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

        /**    @brief    Remove all sequences from bank
        *   @param  bank Index of bank
        */
        void clearBank(uint32_t bank);

        /** @brief  Get quantity of banks
        *   @retval uint32_t Quantity of populated banks
        */
       uint32_t getBanks();

    private:

        int fileWrite32(uint32_t value, FILE *pFile);
        int fileWrite16(uint16_t value, FILE *pFile);
        int fileWrite8(uint8_t value, FILE *pFile);
        uint32_t fileRead32(FILE* pFile);
        uint16_t fileRead16(FILE* pFile);
        uint8_t fileRead8(FILE* pFile);
        bool checkBlock(FILE* pFile, uint32_t nActualSize,  uint32_t nExpectedSize);

        uint8_t m_nTriggerChannel = 15; // MIDI channel to recieve sequence triggers (note-on)

        // Note: Maps are used for patterns and sequences to allow addition and removal of sequences whilst maintaining consistent access to remaining instances
        std::map<uint32_t, Pattern> m_mPatterns; // Map of patterns indexed by pattern number
        std::vector<std::pair<uint32_t,uint32_t>> m_vPlayingSequences; //Vector of <bank,sequence> pairs for currently playing seqeunces (used to optimise play control)
        std::map<uint8_t, uint16_t> m_mTriggers; // Map of bank<<8|sequence indexed by MIDI note triggers
        std::map<uint32_t, std::vector<Sequence*>> m_mBanks; // Map of banks: vectors of pointers to sequences indexed by bank
};
