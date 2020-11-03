#include "song.h"

/**	Song class methods implementation **/

Song::Song()
{
	setTempo(120, 1);
}

Song::~Song()
{
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

uint32_t Song::addTrack(uint32_t sequence)
{
	m_vTracks.push_back(sequence);
	return m_vTracks.size() - 1;
}

void Song::removeTrack(uint32_t track)
{
	if(track < m_vTracks.size())
		m_vTracks.erase(m_vTracks.begin() + track);
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

void Song::setTempo(uint16_t tempo, uint16_t measure, uint16_t tick)
{
	m_timebase.addTimebaseEvent(measure, tick, TIMEBASE_TYPE_TEMPO, tempo);
}

uint16_t Song::getTempo(uint16_t measure, uint16_t tick)
{
	TimebaseEvent* pEvent = m_timebase.getPreviousTimebaseEvent(measure, tick, TIMEBASE_TYPE_TEMPO);
	if(pEvent)
		return pEvent->value;
	return DEFAULT_TEMPO; // Default tempo if none found
}

void Song::setTimeSig(uint16_t timesig, uint16_t measure)
{
	m_timebase.addTimebaseEvent(measure, 0, TIMEBASE_TYPE_TIMESIG, timesig);
}

uint16_t Song::getTimeSig(uint16_t measure)
{
	TimebaseEvent* pEvent = m_timebase.getPreviousTimebaseEvent(measure, 1, TIMEBASE_TYPE_TIMESIG);
	if(pEvent)
		return pEvent->value;
	return DEFAULT_TIMESIG;
}

Timebase* Song::getTimebase()
{
	return &m_timebase;
}

