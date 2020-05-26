#include "song.h"

/**	Song class methods implementation **/

Song::Song()
{
}

Song::~Song()
{
	for(size_t nEvent = 0; nEvent < m_vMasterTrack.size(); ++nEvent)
		delete m_vMasterTrack[nEvent];
}

size_t Song::getTracks()
{
	return m_vTracks.size();
}

uint32_t Song::getSequence(uint32_t track)
{
	if(track < m_vTracks.size())
		return m_vTracks[track];
	return 0;
}

void Song::addTrack(uint32_t sequence)
{
	m_vTracks.push_back(sequence);
}

void Song::removeTrack(uint32_t track)
{
	if(track < m_vTracks.size())
		m_vTracks.erase(m_vTracks.begin() + track);
}

void Song::setTempo(uint16_t tempo, uint32_t time)
{
	addMasterEvent(time, MASTER_EVENT_TEMPO, tempo);
}

uint16_t Song::getTempo(uint32_t time)
{
	auto it = m_vMasterTrack.begin();
	for(; it != m_vMasterTrack.end(); ++it)
	{
		if(time > (*it)->time || (*it)->command != MASTER_EVENT_TEMPO)
			continue;
		return (*it)->data;
	}
	return 120; // If no tempo set then return default tempo
}

void Song::setBar(uint32_t period)
{
	m_nBar = period;
}

uint32_t Song::getBar()
{
	return m_nBar;
}

void Song::clear()
{
	m_vTracks.clear();
}

uint32_t Song::getMasterEvents()
{
	return m_vMasterTrack.size();
}

uint32_t Song::getMasterEventTime(uint32_t event)
{
	if(event >= m_vMasterTrack.size())
		return 0;
	return m_vMasterTrack[event]->time;
}

uint16_t Song::getMasterEventCommand(uint32_t event)
{
	if(event >= m_vMasterTrack.size())
		return 0;
	return m_vMasterTrack[event]->command;
}

uint16_t Song::getMasterEventData(uint32_t event)
{
	if(event >= m_vMasterTrack.size())
		return 0;
	return m_vMasterTrack[event]->data;
}

void Song::addMasterEvent(uint32_t time, uint16_t command, uint16_t data)
{
	printf("Request to add song master track event\n");
	auto it = m_vMasterTrack.begin();
	for(; it < m_vMasterTrack.end(); ++it)
	{
		printf("Found existing event at time %d...", (*it)->time);
		if((*it)->time == time && (*it)->command == command)
		{
			(*it)->data = data;
			printf("at same time of same type - replaced\n");
			return;
		}
		printf("different type or time\n");
		if((*it)->time > time)
			break;
	}
	printf("Adding a new event to song master track at time %d\n", time);
	MasterEvent* pEvent = new MasterEvent;
	pEvent->time = time;
	pEvent->command = command;
	pEvent->data = data;
	m_vMasterTrack.insert(it, pEvent);
}

void Song::removeMasterEvent(uint32_t time, uint16_t command)
{
	auto it = m_vMasterTrack.begin();
	for(; it < m_vMasterTrack.end(); ++it)
	{
		if((*it)->time == time && (*it)->command == command)
		{
			delete(*it);
			return;
		}
	}
}