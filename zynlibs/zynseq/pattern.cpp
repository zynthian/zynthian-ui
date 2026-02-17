#include <cmath>
#include <cstring>
#include <string>

#include "pattern.h"

/**    Pattern class methods implementation **/

Pattern::Pattern(uint32_t beats, uint32_t stepsPerBeat) : m_nBeats(beats), m_nStepsPerBeat(stepsPerBeat) {
    setStepsPerBeat(stepsPerBeat);
    resetSnapshots();
	setInterpolateCCDefaults();
}

Pattern::Pattern(Pattern* pattern) { *this = *pattern; }

Pattern::~Pattern() {
    clear();
    for (StepEventVector* sev : m_vSnapshots) {
        clearStepEventVector(sev);
        delete (sev);
    }
}

// copy assignment
Pattern& Pattern::operator=(Pattern& p) {
    // Guard self assignment
    if (this == &p)
        return *this;
    clear();
    m_nBeats = p.getBeatsInPattern();
    setStepsPerBeat(p.getStepsPerBeat());
    m_nScale = p.m_nScale;
    m_nTonic = p.m_nTonic;
    m_nRefNote = p.m_nRefNote;
    m_nQuantizeNotes = p.m_nQuantizeNotes;
    m_nSwingDiv = p.m_nSwingDiv;
    m_fSwingAmount = p.m_fSwingAmount;
    m_fHumanTime = p.m_fHumanTime;
    m_fHumanVelo = p.m_fHumanVelo;
    m_fPlayChance = p.m_fPlayChance;
    m_nZoom = p.m_nZoom;
    // Copy flags array
    for (int i; i<128; i++) m_bInterpolateCC[i] = p.m_bInterpolateCC[i];
    // Copy Events
    uint32_t i = 0;
    while (StepEvent* ev = p.getEventAt(i)) {
        addEvent(ev);
        i++;
    }
    resetSnapshots();
    return *this;
}

// add assignment (merge)
Pattern& Pattern::operator+=(Pattern& p) {
    pastePattern(&p, 0, 0.0, 0, true);
    return *this;
}

// Paste (merge) a pattern into this
void Pattern::pastePattern(Pattern* p, int32_t dpos, float doffset, int8_t dnote, bool truncate) {
    // Add note events from argument pattern into this pattern. Ignore other events.
    uint32_t nsteps = getSteps();
    int32_t pos;
    float offset;
    int16_t note;
    uint32_t i = 0;
    while (StepEvent* ev = p->getEventAt(i++)) {
        if (ev->m_nCommand != MIDI_NOTE_ON) continue;
        // Calculate time offset
        pos = ev->m_nPosition + dpos;
        offset = ev->m_fOffset + doffset;
        if (offset >= 1.0) {
            pos++;
            offset -= 1.0;
        } else if (offset <= -1.0) {
            pos--;
            offset = 1.0 - offset;
        }
        // Skip notes out off time-range
        if (truncate) {
            if (pos < 0 || pos >= nsteps) continue;
        }
        // Implement circular overflow
        else {
            // Move left overflowed notes to the end of pattern
            if (pos < 0) {
                pos = nsteps - pos;
            }
            // Move right overflowed notes to the beggining of pattern
            else if (pos >= nsteps) {
                pos = pos - nsteps;
            }
        }
        // Calculate note offset
        note = int16_t(ev->m_nValue1start) + dnote;
        // Skip notes out of note-range
        if (note < 0 || note > 127) continue;

        // Add event to this pattern. It will overwrite existing notes in the same position.
        StepEvent pasted_ev = *ev;
        pasted_ev.m_nPosition = pos;
        pasted_ev.m_fOffset = offset;
        pasted_ev.m_nValue1start = note;
        addEvent(&pasted_ev);
    }
}

// Returns a new pattern copying events from this in a time & note range
Pattern* Pattern::copyPattern(uint32_t pos1, uint32_t pos2, uint8_t note1, uint8_t note2) {
    uint32_t nsteps = getSteps();

    // Check range of offset parameters
    if (pos1 >= nsteps) pos1 = nsteps - 1;
    if (pos2 >= nsteps) pos2 = nsteps - 1;
    if (note1 > 127) note1 = 127;
    if (note2 > 127) note2 = 127;

    // Create an empty pattern for the result. The caller must delete when not needed anymore.
    Pattern* res = new Pattern(m_nBeats, m_nStepsPerBeat);

    // Copy note events from argument pattern into this pattern. Ignore other events.
    uint32_t i = 0;
    while (StepEvent* ev = getEventAt(i++)) {
        if (ev->m_nCommand != MIDI_NOTE_ON) continue;
        if (ev->m_nPosition < pos1 || ev->m_nPosition > pos2) continue;
        if (ev->m_nValue1start < note1 || ev->m_nValue1start > note2) continue;
        res->addEvent(ev);
    }
    return res;
}

StepEvent* Pattern::addEvent(uint32_t position, uint8_t command, uint8_t value1, uint8_t value2, float duration, float offset) {
    uint8_t nStutterSpeed = 0;
    uint8_t nStutterVelfx = 0;
    uint8_t nStutterRamp = 0;
    float fPlayChance = 1.0;
    uint8_t nPlayFreq = 1;
    float fStutterChance = 1.0;
    uint8_t nStutterFreq = 1;
    // Delete overlapping events
    bool bFirstNote = false;
    for (auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it) {
        if ((*it)->getCommand() == command && (*it)->getValue1start() == value1) {
            float fEventEnd = position + duration;
            uint32_t nCheckStart = (*it)->getPosition();
            float fCheckEnd = nCheckStart + (*it)->getDuration();
            bool bOverlap = (nCheckStart >= position && nCheckStart < fEventEnd) || (fCheckEnd > position && fCheckEnd <= fEventEnd);
            if (bOverlap) {
                if (!bFirstNote) {
                    nStutterSpeed = (*it)->getStutterSpeed();
                    nStutterVelfx = (*it)->getStutterVelfx();
                    nStutterRamp = (*it)->getStutterRamp();
                    fPlayChance = (*it)->getPlayChance();
                    nPlayFreq = (*it)->getPlayFreq();
                    fStutterChance = (*it)->getStutterChance();
                    nStutterFreq = (*it)->getStutterFreq();
                    bFirstNote = true;
                }
                delete *it;
                it = m_vEvents.erase(it) - 1;
                if (it == m_vEvents.end())
                    break;
            }
        }
    }
    uint32_t nTime = position % (m_nBeats * m_nStepsPerBeat);
    auto it = m_vEvents.begin();
    for (; it != m_vEvents.end(); ++it) {
        if ((*it)->getPosition() > position)
            break;
    }
    auto itInserted = m_vEvents.insert(it, new StepEvent(position, command, value1, value2, duration, offset));
    (*itInserted)->setStutter(nStutterSpeed, nStutterVelfx, nStutterRamp);
    (*itInserted)->setPlayChance(fPlayChance);
    (*itInserted)->setPlayFreq(nPlayFreq);
    (*itInserted)->setStutterChance(fStutterChance);
    (*itInserted)->setStutterFreq(nStutterFreq);
    return *itInserted;
}

StepEvent* Pattern::addEvent(StepEvent* pEvent) {
    StepEvent* sev =
        addEvent(pEvent->getPosition(), pEvent->getCommand(), pEvent->getValue1start(), pEvent->getValue2start(), pEvent->getDuration(), pEvent->getOffset());
    sev->setValue1end(pEvent->getValue1end());
    sev->setValue2end(pEvent->getValue2end());
    sev->setStutter(pEvent->getStutterSpeed(), pEvent->getStutterVelfx(), pEvent->getStutterRamp());
    sev->setPlayChance(pEvent->getPlayChance());
    sev->setPlayFreq(pEvent->getPlayFreq());
    sev->setStutterChance(pEvent->getStutterChance());
    sev->setStutterFreq(pEvent->getStutterFreq());
    return sev;
}

void Pattern::deleteEvent(uint32_t position, uint8_t command, uint8_t value1) {
    for (auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it) {
        if ((*it)->getPosition() == position && (*it)->getCommand() == command && (*it)->getValue1start() == value1) {
            delete *it;
            m_vEvents.erase(it);
            return;
        }
    }
}

bool Pattern::addNote(uint32_t step, uint8_t note, uint8_t velocity, float duration, float offset) {
    //!@todo Should we limit note length to size of pattern?
    if (step >= (m_nBeats * m_nStepsPerBeat) || note > 127 || velocity > 127) // || duration > (m_nBeats * m_nStepsPerBeat))
        return false;
    addEvent(step, MIDI_NOTE_ON, note, velocity, duration, offset);
    return true;
}

void Pattern::removeNote(uint32_t step, uint8_t note) { deleteEvent(step, MIDI_NOTE_ON, note); }

void Pattern::clearNotes() {
	auto it = m_vEvents.begin();
    while (it != m_vEvents.end()) {
        if ((*it)->getCommand() == MIDI_NOTE_ON) {
            delete *it;
            it = m_vEvents.erase(it);
        } else {
        	++it;
        }
    }
}

int32_t Pattern::getNoteIndex(uint32_t step, uint8_t note) {
    int index;
    for (index = 0; index < m_vEvents.size(); ++index) {
        StepEvent* ev = m_vEvents[index];
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return index;
    }
    return -1;
}

int32_t Pattern::getNoteData(uint32_t step, uint8_t note, StepEvent* data) {
    int index;
    for (index = 0; index < m_vEvents.size(); ++index) {
        StepEvent* ev = m_vEvents[index];
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            memcpy(data, ev, sizeof(StepEvent));
            return index;
        }
    }
    return -1;
}

int32_t Pattern::setNoteData(uint32_t step, uint8_t note, StepEvent* data) {
    int index;
    for (index = 0; index < m_vEvents.size(); ++index) {
        StepEvent* ev = m_vEvents[index];
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            uint8_t pos = sizeof(uint32_t) + 2 * sizeof(float) + 2 * sizeof(uint8_t);
            memcpy((uint8_t *)ev + pos, (uint8_t *)data + pos, sizeof(StepEvent) - pos);
            return index;
        }
    }
    return -1;
}

int32_t Pattern::getNoteStart(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() <= step && int(std::ceil(ev->getPosition() + ev->getDuration())) > step && ev->getCommand() == MIDI_NOTE_ON &&
            ev->getValue1start() == note)
            return ev->getPosition();
    return -1;
}

uint8_t Pattern::getNoteVelocity(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getValue2start();
    return 0;
}

void Pattern::setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity) {
    if (velocity > 127)
        return;
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setValue2start(velocity);
            return;
        }
}

float Pattern::getNoteDuration(uint32_t step, uint8_t note) {
    if (step >= (m_nBeats * m_nStepsPerBeat))
        return 0.0;
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() != step || ev->getCommand() != MIDI_NOTE_ON || ev->getValue1start() != note)
            continue;
        return ev->getDuration();
    }
    return 0.0;
}

float Pattern::getNoteOffset(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getOffset();
    return 0;
}

void Pattern::setNoteOffset(uint32_t step, uint8_t note, float offset) {
    if (offset < 0.0)
        offset = 0.0;
    else if (offset > 0.99)
        offset = 0.99;
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setOffset(offset);
            return;
        }
    }
}

void Pattern::setStutter(uint32_t step, uint8_t note, uint8_t speed, uint8_t velfx, uint8_t ramp) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setStutter(speed, velfx, ramp);
            return;
        }
}

uint8_t Pattern::getStutterSpeed(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            return ev->getStutterSpeed();
        }
    }
    return 0;
}

void Pattern::setStutterSpeed(uint32_t step, uint8_t note, uint8_t speed) {
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setStutterSpeed(speed);
            return;
        }
    }
}

uint8_t Pattern::getStutterVelfx(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getStutterVelfx();
    return 1;
}

void Pattern::setStutterVelfx(uint32_t step, uint8_t note, uint8_t velfx) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setStutterVelfx(velfx);
            return;
        }
}

uint8_t Pattern::getStutterRamp(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getStutterRamp();
    return 1;
}

void Pattern::setStutterRamp(uint32_t step, uint8_t note, uint8_t ramp) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setStutterRamp(ramp);
            return;
        }
}

float Pattern::getPlayChance(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getPlayChance();
    return 1.0;
}

void Pattern::setPlayChance(uint32_t step, uint8_t note, float chance) {
    if (chance > 1.0f)
        chance = 1.0f;
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setPlayChance(chance);
            return;
        }
}

uint8_t Pattern::getPlayFreq(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getPlayFreq();
    return 1.0;
}

void Pattern::setPlayFreq(uint32_t step, uint8_t note, uint8_t freq) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setPlayFreq(freq);
            return;
        }
}

float Pattern::getStutterChance(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getStutterChance();
    return 1.0;
}

void Pattern::setStutterChance(uint32_t step, uint8_t note, float chance) {
    if (chance > 1.0f)
        chance = 1.0f;
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setStutterChance(chance);
            return;
        }
}

uint8_t Pattern::getStutterFreq(uint32_t step, uint8_t note) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note)
            return ev->getStutterFreq();
    return 1.0;
}

void Pattern::setStutterFreq(uint32_t step, uint8_t note, uint8_t freq) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_NOTE_ON && ev->getValue1start() == note) {
            ev->setStutterFreq(freq);
            return;
        }
}

bool Pattern::addProgramChange(uint32_t step, uint8_t program) {
    if (step >= (m_nBeats * m_nStepsPerBeat) || program > 127)
        return false;
    removeProgramChange(step); // Only one PC per step
    addEvent(step, MIDI_PROGRAM, program);
    return true;
}

bool Pattern::removeProgramChange(uint32_t step) {
    if (step >= (m_nBeats * m_nStepsPerBeat))
        return false;
    uint8_t program = getProgramChange(step);
    if (program == 0xFF)
        return false;
    deleteEvent(step, MIDI_PROGRAM, program);
    return true;
}

uint8_t Pattern::getProgramChange(uint32_t step) {
    if (step >= (m_nBeats * m_nStepsPerBeat))
        return 0xFF;
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() != step || ev->getCommand() != MIDI_PROGRAM)
            continue;
        return ev->getValue1start();
    }
    return 0xFF;
}

bool Pattern::addControl(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd, float duration, float offset) {
    if (step > (m_nBeats * m_nStepsPerBeat) || control > 127 || valueStart > 127 || valueEnd > 127 || duration > (m_nBeats * m_nStepsPerBeat))
        return false;

	if (m_bInterpolateCC[control]) stepControlEvents(control);
    StepEvent* pEvent = addEvent(step, MIDI_CONTROL, control, valueStart, duration, offset);
	pEvent->setValue2end(valueEnd);
	if (m_bInterpolateCC[control]) joinControlEvents(control);

    return true;
}

void Pattern::removeControl(uint32_t step, uint8_t control) {
	deleteEvent(step, MIDI_CONTROL, control);
	if (m_bInterpolateCC[control]) joinControlEvents(control);
}

void Pattern::removeControlInterval(uint32_t stepFrom, uint32_t stepTo, uint8_t control) {
    uint32_t step;
    if (stepTo >= stepFrom) {
        for (step = stepFrom; step <= stepTo; step++) {
            deleteEvent(step, MIDI_CONTROL, control);
        }
    } else {
        for (step = 0; step <= stepTo; step++) {
            deleteEvent(step, MIDI_CONTROL, control);
        }
        for (step = stepFrom; step < getSteps(); step++) {
            deleteEvent(step, MIDI_CONTROL, control);
        }
    }
}

void Pattern::clearControl(uint8_t control) {
	auto it = m_vEvents.begin();
    while (it != m_vEvents.end()) {
        if ((*it)->getCommand() == MIDI_CONTROL && (*it)->getValue1start() == control) {
            delete *it;
            it = m_vEvents.erase(it);
        } else {
        	++it;
        }
    }
}

int32_t Pattern::getControlStart(uint32_t step, uint8_t control) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() <= step && int(std::ceil(ev->getPosition() + ev->getDuration())) > step && ev->getCommand() == MIDI_CONTROL &&
            ev->getValue1start() == control)
            return ev->getPosition();
    return -1;
}

float Pattern::getControlDuration(uint32_t step, uint8_t control) {
    if (step >= (m_nBeats * m_nStepsPerBeat))
        return 0.0;
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() != step || ev->getCommand() != MIDI_CONTROL || ev->getValue1start() != control)
            continue;
        return ev->getDuration();
    }
    return 0.0;
}

float Pattern::getControlOffset(uint32_t step, uint8_t control) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_CONTROL && ev->getValue1start() == control)
            return ev->getOffset();
    return 0;
}

void Pattern::setControlOffset(uint32_t step, uint8_t control, float offset) {
    if (offset < 0.0)
        offset = 0.0;
    else if (offset > 0.99)
        offset = 0.99;
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() == step && ev->getCommand() == MIDI_CONTROL && ev->getValue1start() == control) {
            ev->setOffset(offset);
            return;
        }
    }
}

uint8_t Pattern::getControlValue(uint32_t step, uint8_t control) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_CONTROL && ev->getValue1start() == control)
            return ev->getValue2start();
    return -1;
}

uint8_t Pattern::getControlValueEnd(uint32_t step, uint8_t control) {
    for (StepEvent* ev : m_vEvents)
        if (ev->getPosition() == step && ev->getCommand() == MIDI_CONTROL && ev->getValue1start() == control)
            return ev->getValue2end();
    return 0xff;
}

void Pattern::setControlValue(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd) {
    if (valueStart > 127 || valueEnd > 127)
        return;
    auto it = m_vEvents.begin();
    for (; it != m_vEvents.end(); ++it) {
        if ((*it)->getCommand() == MIDI_CONTROL && (*it)->getValue1start() == control) {
        	if ((*it)->getPosition() == step) {
        		(*it)->setValue2start(valueStart);
        		(*it)->setValue2end(valueEnd);
        		if (m_bInterpolateCC[control]) joinControlEvents(control);
        		break;
        	}
        }
    }
}

void Pattern::joinControlEvents(uint8_t control) {
	if (m_vEvents.size() < 2)
		return;
    int32_t pos0 = -1;
    uint8_t valueStart0;
    uint8_t duration;
    uint8_t valueEnd;
    auto it = m_vEvents.begin();
    auto it_prev = m_vEvents.begin();
	for (; it != m_vEvents.end(); ++it) {
	    if ((*it)->getCommand() == MIDI_CONTROL && (*it)->getValue1start() == control) {
	    	if (pos0 >= 0) {
				duration = (*it)->getPosition() - (*it_prev)->getPosition();
				valueEnd = (*it)->getValue2start();
				(*it_prev)->setValue2end(valueEnd);
				(*it_prev)->setDuration(duration);
				//fprintf(stderr, "Join CC%u values => Pos=%u, Duration=%u, Start=%u, End=%u\n", control, (*it_prev)->getPosition(), duration, (*it_prev)->getValue2start(), valueEnd);
			} else {
				pos0 = (*it)->getPosition();
				valueStart0 = (*it)->getValue2start();
			}
			it_prev = it;
		}
	}
	duration = getSteps() - (*it_prev)->getPosition() + pos0;
	(*it_prev)->setValue2end(valueStart0);
	(*it_prev)->setDuration(duration);
	//fprintf(stderr, "Join CC%u values => Pos=%u, Duration=%u, Start=%u, End=%u\n", control, (*it_prev)->getPosition(), duration, (*it_prev)->getValue2start(), valueEnd);
}

void Pattern::stepControlEvents(uint8_t control) {
    auto it = m_vEvents.begin();
	for (; it != m_vEvents.end(); ++it) {
	    if ((*it)->getCommand() == MIDI_CONTROL && (*it)->getValue1start() == control) {
			(*it)->setValue2end((*it)->getValue2start());
			(*it)->setDuration(1);
			//fprintf(stderr, "Step CC%u values => Pos=%u, Duration=%u, Start=%u, End=%u\n", control, (*it)->getPosition(), 1, (*it)->getValue2start(), (*it)->getValue2end());
		}
	}
}

uint32_t Pattern::getSteps() { return (m_nBeats * m_nStepsPerBeat); }

uint32_t Pattern::getLength() { return m_nBeats * PPQN_INTERNAL; }

uint32_t Pattern::getClocksPerStep() {
    if (m_nStepsPerBeat > PPQN_INTERNAL || m_nStepsPerBeat == 0)
        return 1;
    return PPQN_INTERNAL / m_nStepsPerBeat;
}

bool Pattern::setStepsPerBeat(uint32_t value) {
    float fScale = 1.0;
    if (m_nStepsPerBeat == 0 || m_nStepsPerBeat > PPQN_INTERNAL)
        m_nStepsPerBeat = 4;
    else
        float fScale = float(value) / m_nStepsPerBeat;

    switch (value) {
    case 1:
    case 2:
    case 3:
    case 4:
    case 6:
    case 8:
    case 12:
    case 24:
        m_nStepsPerBeat = value;
        break;
    default:
        return false;
    }
    // Move events
    for (StepEvent* ev : m_vEvents) {
        ev->setPosition(ev->getPosition() * fScale);
        ev->setDuration(ev->getDuration() * fScale);
    }
    return true;
}

uint32_t Pattern::getStepsPerBeat() { return m_nStepsPerBeat; }

void Pattern::setBeatsInPattern(uint32_t beats) {
    if (beats > 0)
        m_nBeats = beats;

    // Remove steps if shrinking
    size_t nIndex = 0;
    for (; nIndex < m_vEvents.size(); ++nIndex)
        if (m_vEvents[nIndex]->getPosition() >= (m_nBeats * m_nStepsPerBeat))
            break;
    m_vEvents.resize(nIndex);
}

uint32_t Pattern::getBeatsInPattern() { return m_nBeats; }

void Pattern::setScale(uint8_t scale) { m_nScale = scale; }

uint8_t Pattern::getScale() { return m_nScale; }

void Pattern::setTonic(uint8_t tonic) { m_nTonic = tonic; }

uint8_t Pattern::getTonic() { return m_nTonic; }

void Pattern::setSwingDiv(uint32_t div) { m_nSwingDiv = div; }

uint32_t Pattern::getSwingDiv() { return m_nSwingDiv; }

void Pattern::setSwingAmount(float amount) { m_fSwingAmount = amount; }

float Pattern::getSwingAmount() { return m_fSwingAmount; }

void Pattern::setHumanTime(float amount) { m_fHumanTime = amount; }

float Pattern::getHumanTime() { return m_fHumanTime; }

void Pattern::setHumanVelo(float amount) { m_fHumanVelo = amount; }

float Pattern::getHumanVelo() { return m_fHumanVelo; }

void Pattern::setPlayChance(float chance) { m_fPlayChance = chance; }

float Pattern::getPlayChance() { return m_fPlayChance; }

void Pattern::transpose(int value) {
    // Check if any notes will be transposed out of MIDI note range (0..127)
    for (StepEvent* ev : m_vEvents) {
        if (ev->getCommand() != MIDI_NOTE_ON)
            continue;
        int note = ev->getValue1start() + value;
        if (note > 127 || note < 0)
            return;
    }

    for (auto it = m_vEvents.begin(); it != m_vEvents.end(); ++it) {
        if ((*it)->getCommand() != MIDI_NOTE_ON)
            continue;
        int note = (*it)->getValue1start() + value;
        if (note > 127 || note < 0) {
            // Delete notes that have been pushed out of range
            //!@todo Should we squash notes that are out of range back in at ends? I don't think so.
            delete (*it);
            m_vEvents.erase(it);
        } else {
            (*it)->setValue1start(note);
            (*it)->setValue1end(note);
        }
    }
}

void Pattern::changeVelocityAll(int value) {
    for (StepEvent* ev : m_vEvents) {
        if (ev->getCommand() != MIDI_NOTE_ON)
            continue;
        int vel = ev->getValue2start() + value;
        if (vel > 127)
            vel = 127;
        if (vel < 1)
            vel = 1;
        ev->setValue2start(vel);
    }
}

void Pattern::changeDurationAll(float value) {
    for (StepEvent* ev : m_vEvents) {
        if (ev->getCommand() != MIDI_NOTE_ON)
            continue;
        float duration = ev->getDuration() + value;
        if (duration <= 0)
            return;         // Don't allow jump larger than current value
        if (duration < 0.1) //!@todo How short should we allow duration change?
            duration = 0.1;
        ev->setDuration(duration);
    }
}

void Pattern::clear() { clearStepEventVector(&m_vEvents); }

StepEvent* Pattern::getEventAt(uint32_t index) {
    if (index < 0 || index >= m_vEvents.size())
        return NULL;
    return m_vEvents[index];
}

int Pattern::getFirstEventAtStep(uint32_t step) {
    int index;
    for (index = 0; index < m_vEvents.size(); ++index) {
        if (m_vEvents[index]->getPosition() == step)
            return index;
    }
    return -1;
}

size_t Pattern::getEvents() { return m_vEvents.size(); }

uint8_t Pattern::getRefNote() { return m_nRefNote; }

void Pattern::setRefNote(uint8_t note) {
    if (note < 128)
        m_nRefNote = note;
}

uint8_t Pattern::getQuantizeNotes() { return m_nQuantizeNotes; }

void Pattern::setQuantizeNotes(uint8_t qn) { m_nQuantizeNotes = qn; }

bool Pattern::getInterpolateCC(uint8_t ccnum) { return m_bInterpolateCC[ccnum]; }

void Pattern::setInterpolateCC(uint8_t ccnum, bool flag) {
	m_bInterpolateCC[ccnum] = flag;
	if (flag) joinControlEvents(ccnum);
	else stepControlEvents(ccnum);
}

void Pattern::setInterpolateCCDefaults() {
	int ccnum;
    for (ccnum=0; ccnum<128; ccnum++) m_bInterpolateCC[ccnum] = true;
    m_bInterpolateCC[64] = false;
    m_bInterpolateCC[66] = false;
    m_bInterpolateCC[67] = false;
    m_bInterpolateCC[69] = false;
    for (ccnum=0; ccnum<128; ccnum++) {
    	if (m_bInterpolateCC[ccnum]) joinControlEvents(ccnum);
    	else stepControlEvents(ccnum);
    }
}

int32_t Pattern::getLastStep() {
    if (m_vEvents.size() == 0)
        return -1;
    int32_t nStep = 0;
    for (StepEvent* ev : m_vEvents) {
        if (ev->getPosition() > nStep)
            nStep = ev->getPosition();
    }
    return nStep;
}

// Pattern Snapshots => Undo/Redo

void Pattern::clearStepEventVector(StepEventVector* sev) {
    if (sev && sev->size() > 0) {
        for (StepEvent* ev : *sev)
            delete ev;
        sev->clear();
    }
}

bool Pattern::restoreSnapshot(StepEventVector* sev) {
    if (sev) {
        clear();
        for (StepEvent* ev : *sev) {
            m_vEvents.push_back(new StepEvent(ev));
        }
        return true;
    }
    return false;
}

void Pattern::resetSnapshots() {
    // Destroy events
    for (StepEventVector* sev : m_vSnapshots) {
        clearStepEventVector(sev);
        delete (sev);
    }
    m_vSnapshots.clear();
    // m_vSnapshotPos = m_vSnapshots.end();
    saveSnapshot();
}

void Pattern::saveSnapshot() {
    // Delete snapshots from the current position, truncating the history
    if (m_vSnapshotPos < m_vSnapshots.end()) {
        for (auto it = m_vSnapshotPos + 1; it < m_vSnapshots.end(); it++) {
            clearStepEventVector(*it);
            delete (*it);
        }
        m_vSnapshots.erase(m_vSnapshotPos + 1, m_vSnapshots.end());
    }
    // Push snapshot at the end of the truncated history
    StepEventVector* ss = new StepEventVector();
    for (StepEvent* ev : m_vEvents) {
        ss->push_back(new StepEvent(ev));
    }
    m_vSnapshots.push_back(ss);
    m_vSnapshotPos = m_vSnapshots.end() - 1;
}

bool Pattern::undo() {
    if (m_vSnapshotPos > m_vSnapshots.begin()) {
        // Undo one position
        m_vSnapshotPos--;
        return restoreSnapshot(*m_vSnapshotPos);
    }
    return false;
}

bool Pattern::redo() {
    if (m_vSnapshots.size() > 1 && m_vSnapshotPos < m_vSnapshots.end() - 1) {
        // Redo one position
        m_vSnapshotPos++;
        return restoreSnapshot(*m_vSnapshotPos);
    }
    return false;
}

bool Pattern::undoAll() {
    if (m_vSnapshotPos > m_vSnapshots.begin()) {
        // Undo one position
        m_vSnapshotPos = m_vSnapshots.begin();
        return restoreSnapshot(*m_vSnapshotPos);
    }
    return false;
}

bool Pattern::redoAll() {
    if (m_vSnapshots.size() > 1 && m_vSnapshotPos < m_vSnapshots.end() - 1) {
        // Undo one position
        m_vSnapshotPos = m_vSnapshots.end() - 1;
        return restoreSnapshot(*m_vSnapshotPos);
    }
    return false;
}
