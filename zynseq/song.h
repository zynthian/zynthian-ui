#pragma once
#include "constants.h"
#include <cstdio>
#include <vector>

/**	Master track event type */
struct MasterEvent {
	uint32_t time;
	uint16_t command;
	uint16_t data;
};

#define MASTER_EVENT_TEMPO 1

/**	Song class provides a group of sequences
*/
class Song
{
	public:
		/**	@brief	Construct song object
		*	@param	Tracks Quantity of tracks in song
		*/
		Song();

		~Song();

		/**	@breif	Get quantity of tracks
		*	@retval	size_t Quantity of tracks
		*/
		size_t getTracks();

		/**	@brief Get index of track sequences
		*	@param	track Track index
		*	@retval	uint32_t Sequence index
		*/
		uint32_t getSequence(uint32_t track);

		/**	@brief	Add track to song
		*	@param	sequence Index of sequence to add as track
		*/
		void addTrack(uint32_t sequence);

		/**	@brief	Remove track to song
		*	@param	track Index of track to remove
		*/
		void removeTrack(uint32_t track);

		/**	@brief	Set song tempo
		*	@param	tempo Tempo in BPM
		*	@param	time Time at which to add the tempo to the master track [Optional - default: 0]
		*/
		void setTempo(uint16_t tempo, uint32_t time = 0);

		/**	@brief	Get song tempo
		*	@param	time Time at which to query tempo [Optional - default: 0]
		*	@retval	uint16_t Tempo in BPM
		*/
		uint16_t getTempo(uint32_t time = 0);

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

		/**	@brief	Get quantity of events in master track
		*	@retval	uint32_t Quantity of events
		*/
		uint32_t getMasterEvents();

		/**	@brief	Get time of master track event
		*	@param	event Index of event
		*	@retval	uint32_t Time of event
		*/
		uint32_t getMasterEventTime(uint32_t event);

		/**	@brief	Get command of master track event
		*	@param	event Index of event
		*	@retval	uint16_t Event command
		*/
		uint16_t getMasterEventCommand(uint32_t event);

		/**	@brief	Get data of master track event
		*	@param	event Index of event
		*	@retval	uint16_t Event data
		*/
		uint16_t getMasterEventData(uint32_t event);

		/**	@brief	Add master track event
		*	@param	time Time of event
		*	@param	command Event command
		*	@param	data Event data
		*/
		void addMasterEvent(uint32_t time, uint16_t command, uint16_t data);

		/**	@brief	Remove master track event
		*	@param	time Time of event
		*	@param	command Event command
		*/
		void removeMasterEvent(uint32_t time, uint16_t command);

	private:
		std::vector<uint32_t> m_vTracks; // Index of sequences representing each track
		uint32_t m_nSongPosition = 0;
		uint32_t m_nBar = 96; // Clock cycles per bar / loop point
		std::vector<MasterEvent*> m_vMasterTrack; // List of master track events
};
