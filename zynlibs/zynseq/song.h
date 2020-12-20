#pragma once
#include "constants.h"
#include "timebase.h"
#include <cstdio>
#include <vector>

/**	Song class provides a group of sequences
*/
class Song
{
	public:
		/**	@brief	Construct song object
		*/
		Song();

		~Song();

		/**	@breif	Get quantity of tracks
		*	@retval	size_t Quantity of tracks
		*/
		size_t getTracks();

		/**	@brief Get index of track sequences
		*	@param	track Track index
		*	@retval	uint32_t Sequence index (0 if track does not exist)
		*/
		uint32_t getSequence(uint32_t track);

		/**	@brief	Add track to song
		*	@param	sequence Index of sequence to add as track
		*	@retval	Index of new track
		*/
		uint32_t addTrack(uint32_t sequence);

		/**	@brief	Remove track to song
		*	@param	track Index of track to remove
		*/
		void removeTrack(uint32_t track);

		/**	@brief	Set song tempo
		*	@param	tempo Tempo in BPM
		*	@param	bar Bar (measure) at which to set tempo
		*	@param	tick Tick at which to set tempo [Optional - default: 0]
        *   @note   Removes tempo if same as previous tempo
		*/
		void setTempo(uint16_t tempo, uint16_t bar, uint16_t tick=0);

		/**	@brief	Get song tempo
		*	@param	bar Bar (measure) at which to get tempo
		*	@param	beat Tick at which to get tempo [Optional - default: 0]
		*	@retval	uint16_t Tempo in BPM
		*/
		uint16_t getTempo(uint16_t bar, uint16_t tick=0);

		/**	@brief	Set song time signature
		*	@param	timesig Time signature - MSB: Numerator, LSB: Denominator
		*	@param	bar Bar (measure) at which to set time signature
        *   @note   Removes time signature if same as previous time signature
		*/
		void setTimeSig(uint16_t timesig, uint16_t bar);

		/**	@brief	Get song time signature
		*	@param	bar Bar (measure) at which to get time signature
		*	@retval	uint16_t Time signature MSB: Numerator LSB: Denominator
		*/
		uint16_t getTimeSig(uint16_t bar);

		/**	@brief	Set bar / loop  period
		*	@param	period Bar length / loop point in clock cycles
		*/
		void setBar(uint32_t period);

		/**	@brief	Get bar / loop  period
		*	@retval	uint32_t Bar length / loop point in clock cycles
		*/
		uint32_t getBar();

		/**	@brief	Set grid size (quantity of columns)
		*	@param	size Grid size
		*/
		void setGridSize(uint32_t size);

		/**	@brief	Get grid size
		*	@retval	uint32_t Grid size
		*/
		uint32_t getGridSize();

		/**	@brief	Clears content of song, removing all sequences
		*/
		void clear();
		
		/**	@brief	Get timebase map
		*	retval	Timebase* Pointer to timebase map
		*/
		Timebase* getTimebase();

	private:
		std::vector<uint32_t> m_vTracks; // Index of sequences representing each track
		uint32_t m_nBar = 96; // Clock cycles per bar / loop point
		Timebase m_timebase; // Timebase map
};
