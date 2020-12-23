#include "song.h"

/**	Song class methods implementation **/

Song::Song()
{
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

void Song::addTempo(uint16_t tempo, uint16_t bar, uint16_t tick)
{
	m_timebase.addTimebaseEvent(bar, tick, TIMEBASE_TYPE_TEMPO, tempo);
}

uint16_t Song::getTempo(uint16_t bar, uint16_t tick)
{
	return m_timebase.getTempo(bar, tick);
}

uint16_t Song::getTempo()
{
	return m_nTempo;
}

void Song::setTempo(uint16_t tempo)
{
	m_nTempo = tempo;
}

void Song::setTimeSig(uint16_t timesig, uint16_t bar)
{
	if(bar < 1)
		bar = 1;
	m_timebase.addTimebaseEvent(bar, 0, TIMEBASE_TYPE_TIMESIG, timesig);
}

uint16_t Song::getTimeSig(uint16_t bar)
{
	if(bar < 1)
		bar = 1;
	TimebaseEvent* pEvent = m_timebase.getPreviousTimebaseEvent(bar, 1, TIMEBASE_TYPE_TIMESIG);
	if(pEvent)
		return pEvent->value;
	return DEFAULT_TIMESIG;
}

Timebase* Song::getTimebase()
{
	return &m_timebase;
}

