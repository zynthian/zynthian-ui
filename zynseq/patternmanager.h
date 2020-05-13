#pragma once
#include "pattern.h"
#include "sequence.h"
#include <map>


/**	PatternManager class provides creation, recall, update and delete of patterns which other modules can subseqnetly use. It manages persistent (disk) storage. PatternManager is implemented as a singleton ensuring a single instance is available to all callers.
*/
class PatternManager
{
	public:
		/**	@brief	Get a pointer to the Pattern Manager singleton instance
		*	@retval	PatternManager* Pointer to singlton
		*/
		static PatternManager* getPatternManager();

		/**	@brief	Load patterns from file
		*	@param	filename Full or relative path and name of file
		*/
		void load(const char* filename);

		/**	@brief	Save patterns to file
		*	@param	filename Full or relative path and name of file
		*/
		void save(const char* filename);

		/**	@brief	Get pointer to a pattern
		*	@param	index Index of pattern retrieve
		*	@retval	Pattern* Pointer to pattern
		*	@note	If pattern does not exist a new, default, empty pattern is created
		*/
		Pattern* getPattern(size_t index);

		/**	@brief	Get the index of a pattern
		*	@param	pattern Pointer to pattern
		*	@retval	uint32_t Index of pattern
		*/
		uint32_t getPatternIndex(Pattern* pattern);

		/**	@brief	Create new pattern
		*	@retval	size_t Index of new pattern
		*	@note	Use getPattern to retrieve pointer to pattern
		*/
		size_t createPattern();

		/**	@brief	Delete pattern
		*	@param	index Index of the pattern to delete
		*/
		void deletePattern(size_t index);

		/**	@brief	Copy pattern
		*	@param	source Pointer to pattern to copy from
		*	@param	destination Pointer to pattern to populate
		*/
		void copyPattern(Pattern* source, Pattern* destination);
		
		/**	@param	Get sequence
		*	@param	Index of sequence
		*	@retval	Sequence* Pointer to sequence
		*/
		Sequence* getSequence(uint32_t sequence);

		/**	@brief	Update all sequence lengths
		*	@note	Blunt tool to update each sequence after any pattern length changes
		*/
		void updateSequenceLengths();

		/**	@brief	Handle clock
		*	@param	nTime Offset since JACK epoch for start of next period
		*	@param	pSchedule Pointer to the schedule to populate with events
		*/
		void clock(uint32_t nTime, std::map<uint32_t,MIDI_MESSAGE*>* pSchedule);

		/**	@brief	Set the clock rates for all sequences in samples per clock
		*	@param	samples (samples per clock)
		*/
		void setSequenceClockRates(uint32_t samples);

	private:
		PatternManager(); // Private constructor to avoid public instantiation
		PatternManager(const PatternManager&); // Do not allow public copying
		PatternManager& operator = (const PatternManager&); // Do not allow public copying
		int fileWrite32(uint32_t value, FILE *pFile);
		int fileWrite8(uint8_t value, FILE *pFile);
		uint32_t fileRead32(FILE* pFile);
		uint8_t fileRead8(FILE* pFile);

		static PatternManager* m_pPatternManager; // Pointer to the singleton
		// Note: Maps are used for patterns and sequences to allow addition and removal of sequences whilst maintaining consistent access to remaining instances
		std::map<size_t,Pattern> m_mPatterns; // Map of patterns indexed by pattern number
		std::map<size_t,Sequence> m_mSequences; // Map of sequences indexed by sequence number
};
