#pragma once
#include "constants.h"
#include <cstdio>
#include <vector>
#include <memory>

#define MAX_STUTTER_COUNT 32
#define MAX_STUTTER_DUR 96

const static uint32_t PPQN = 24;

/** StepEvent class provides an individual step event .
*   The event may be part of a song, pattern or sequence. Events do not have MIDI channel which is applied by the function to play the event, e.g. pattern player assigned to specific channel. Events have the concept of position which is an offset from some epoch measured in steps. The epoch depends on the function using the event, e.g. pattern player may use start of pattern as epoch (position = 0). There is a starting and end value to allow interpolation of MIDI events between the start and end positions.
*/
class StepEvent
{

    public:
        /** Default constructor of StepEvent object
        */
        StepEvent()
        {
            m_nPosition = 0;
            m_fDuration = 1.0;
            m_nCommand = MIDI_NOTE_ON;
            m_nValue1start = 60;
            m_nValue2start = 100;
            m_nValue1end = 60;
            m_nValue2end = 0;
            m_nStutterCount = 0;
            m_nStutterDur = 1;
        };

        /** Constructor - create an instance of StepEvent object
        */
        StepEvent(uint32_t position, uint8_t command, uint8_t value1 = 0, uint8_t value2 = 0, float duration = 1.0)
        {
            m_nPosition = position;
            m_fDuration = duration;
            m_nCommand = command;
            m_nValue1start = value1;
            m_nValue2start = value2;
            m_nValue1end = value1;
            if(command == MIDI_NOTE_ON)
                m_nValue2end = 0;
            else
                m_nValue2end = value2;
            m_nStutterCount = 0;
            m_nStutterDur = 1;
        };

        /** Copy constructor - create an copy of StepEvent object from an existing object
        */
        StepEvent(StepEvent* pEvent)
        {
            m_nPosition = pEvent->getPosition();
            m_fDuration = pEvent->getDuration();
            m_nCommand = pEvent->getCommand();
            m_nValue1start = pEvent->getValue1start();
            m_nValue2start = pEvent->getValue2start();
            m_nValue1end = pEvent->getValue1end();
            m_nValue2end = pEvent->getValue2end();
            m_nStutterCount = pEvent->getStutterCount();
            m_nStutterDur = pEvent->getStutterDur();
        };

        uint32_t getPosition() { return m_nPosition; };
        float getDuration() { return m_fDuration; };
        uint8_t getCommand() { return m_nCommand; };
        uint8_t getValue1start() { return m_nValue1start; };
        uint8_t getValue2start() { return m_nValue2start; };
        uint8_t getValue1end() { return m_nValue1end; };
        uint8_t getValue2end() { return m_nValue2end; };
        uint8_t getStutterCount() { return m_nStutterCount; };
        uint8_t getStutterDur() { return m_nStutterDur; };
        void setPosition(uint32_t position) { m_nPosition = position; };
        void setDuration(float duration) { m_fDuration = duration; };
        void setValue1start(uint8_t value) { m_nValue1start = value; };
        void setValue2start(uint8_t value) { m_nValue2start = value; };
        void setValue1end(uint8_t value) { m_nValue1end = value; };
        void setValue2end(uint8_t value) { m_nValue2end = value; };
        void setStutterCount(uint8_t value) { m_nStutterCount = value; };
        void setStutterDur(uint8_t value) { if (value) m_nStutterDur = value; };

    private:
        uint32_t m_nPosition; // Start position of event in steps
        float m_fDuration; // Duration of event in steps
        uint8_t m_nCommand; // MIDI command without channel
        uint8_t m_nValue1start; // MIDI value 1 at start of event
        uint8_t m_nValue2start; // MIDI value 2 at start of event
        uint8_t m_nValue1end; // MIDI value 1 at end of event
        uint8_t m_nValue2end; // MIDI value 2 at end of event
        uint32_t m_nProgress; // Progress through event (start value to end value)
        uint8_t m_nStutterCount; // Quantity of stutters (fast repeats) at start of event
        uint8_t m_nStutterDur; // Duration of each stutter in clock cycles
};

/**    Pattern class provides a group of MIDI events within period of time
*/
class Pattern
{
    public:
        /** @brief  Construct pattern object
        *   @param  beats Quantity of beats in pattern [Optional - default:4]
        *   @param  stepsPerBeat Quantity of steps per beat [Optional - default: 4]
        */
        Pattern(uint32_t beats = 4, uint32_t stepsPerBeat = 4);

        /** @brief  Copy constructor
        *   @param  Pointer to pattern to copy
        */
        Pattern(Pattern* pattern);

        /** @brief  Destruct pattern object
        */
        ~Pattern();

        /** @brief  Add step event to pattern
        *   @param  position Quantity of steps from start of pattern
        *   @param  command MIDI command
        *   @param  value1 MIDI value 1
        *   @param  value2 MIDI value 2
        *   @param  duration Event duration in steps cycles
        */
        StepEvent* addEvent(uint32_t position, uint8_t command, uint8_t value1 = 0, uint8_t value2 = 0, float duration = 1.0);

        /** @brief  Add event from existing event
        *   @param  pEvent Pointer to event to copy
        *   @retval StepEvent* Pointer to new event
        */
        StepEvent* addEvent(StepEvent* pEvent);

        /** @brief  Add note to pattern
        *   @param  step Quantity of steps from start of pattern at which to add note
        *   @param  note MIDI note number
        *   @param  velocity MIDI velocity
        *   @param  duration Duration of note in steps
        *   @retval bool True on success
        */
        bool addNote(uint32_t step, uint8_t note, uint8_t velocity, float duration = 1.0);

        /** @brief  Remove note from pattern
        *   @param  position Quantity of steps from start of pattern at which to remove note
        *   @param  note MIDI note number
        */
        void removeNote(uint32_t step, uint8_t note);

        /** @brief  Get step that note starts
        *   @param  position Quantity of steps from start of pattern at which to check for note
        *   @param  note MIDI note number
        *   @retval int32_t Quantity of steps from start of pattern that note starts or -1 if note not found
        */
        int32_t getNoteStart(uint32_t step, uint8_t note);

        /** @brief  Get velocity of note
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @retval uint8_t MIDI velocity of note
        */
        uint8_t getNoteVelocity(uint32_t step, uint8_t note);

        /** @brief  Set velocity of note
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @param  velocity MIDI velocity
        */
        void setNoteVelocity(uint32_t step, uint8_t note, uint8_t velocity);

        /** @brief  Get duration of note
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @retval float Duration of note or 0 if note does not exist
        */
        float getNoteDuration(uint32_t step, uint8_t note);

        /** @brief  Set note stutter
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @param  count Quantity of stutters
        *   @param  dur Length of each stutter in clock cycles (min=1)
        */
        void setStutter(uint32_t step, uint8_t note, uint8_t count, uint8_t dur);

        /** @brief  Set note stutter count
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @param  count Quantity of stutters
        */
        void setStutterCount(uint32_t step, uint8_t note, uint8_t count);

        /** @brief  Set note stutter duration
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @param  dur Length of each stutter in clock cycles (min=1)
        */
        void setStutterDur(uint32_t step, uint8_t note, uint8_t dur);

        /** @brief  Get note stutter duration
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @retval uint8_t Duration of stutter each stutter in clock cycles
        */
        uint8_t getStutterCount(uint32_t step, uint8_t note);

        /** @brief  Get note stutter count
        *   @param  position Quantity of steps from start of pattern at which note starts
        *   @param  note MIDI note number
        *   @retval uint8_t Quantity of stutter repeats at start of note
        */
        uint8_t getStutterDur(uint32_t step, uint8_t note);

        /** @brief  Add program change to pattern
        *   @param  position Quantity of steps from start of pattern at which to add program change
        *   @param  program MIDI program change number
        *   @retval bool True on success
        */
        bool addProgramChange(uint32_t step, uint8_t program);

        /** @brief  Remove program change from pattern
        *   @param  position Quantity of steps from start of pattern at which to remove program change
        *   @retval bool True on success
        */
        bool removeProgramChange(uint32_t step);

        /** @brief  Get program change at a step
        *   @param  position Quantity of steps from start of pattern at which program change resides
        *   @retval uint8_t Program change (0..127, 0xFF if no program change at this step)
        */
        uint8_t getProgramChange(uint32_t step);

        /** @brief  Add continuous controller to pattern
        *   @param  position Quantity of steps from start of pattern at which control starts
        *   @param  control MIDI controller number
        *   @param  valueStart Controller value at start of event
        *   @param  valueEnd Controller value at end of event
        *   @param  duration Duration of event in steps
        */
        void addControl(uint32_t step, uint8_t control, uint8_t valueStart, uint8_t valueEnd, float duration = 1.0);

        /** @brief  Remove continuous controller from pattern
        *   @param  position Quantity of steps from start of pattern at which control starts
        *   @param  control MIDI controller number
        */
        void removeControl(uint32_t step, uint8_t control);

        /** @brief  Get duration of controller event
        *   @param  position Quantity of steps from start of pattern at which control starts
        *   @param  control MIDI controller number
        *   @retval float Duration of control or 0 if control does not exist
        */
        float getControlDuration(uint32_t step, uint8_t control);

        /** @brief  Get quantity of steps in pattern
        *   @retval uint32_t Quantity of steps
        */
        uint32_t getSteps();

        /** @brief  Get length of pattern in clock cycles
        *   @retval uint32_t Length of pattern in clock cycles
        */
        uint32_t getLength();

        /** @brief  Get quantity of clocks per step
        *   @retval uint32_t Quantity of clocks per step
        */
        uint32_t getClocksPerStep();

        /** @brief  Set quantity of steps per beat (grid line separation)
        *   @param  value Quantity of steps per beat constrained to [1|2|3|4|6|8|12|24]
        *   @retval bool True on success
        */
        bool setStepsPerBeat(uint32_t value);

        /** @brief  Get quantity of steps per beat
        *   @retval uint32_t Quantity of steps per beat
        */
        uint32_t getStepsPerBeat();

        /** @brief  Set beats in pattern
        *   @param  beats Quantity of beats in pattern
        */
        void setBeatsInPattern(uint32_t beats);

        /** @brief  Get beats in pattern
        *   @retval uint32_t Quantity of beats in pattern
        */
        uint32_t getBeatsInPattern();

        /** @brief  Set map / scale used by pattern editor for this pattern
        *   @param  map Index of map / scale
        */
        void setScale(uint8_t scale);

        /** @brief  Get map / scale used by pattern editor for this pattern
        *   @retval uint8_t Index of map / scale
        */
        uint8_t getScale();

        /** @brief  Set scale tonic (root note) used by pattern editor for current pattern
        *   @param  tonic Scale tonic
        */
        void setTonic(uint8_t tonic);

        /** @brief  Get scale tonic (root note) used by pattern editor for current pattern
        *   @retval uint8_t Tonic
        */
        uint8_t getTonic();

        /** @brief  Transpose all notes within pattern
        *   @param  value Offset to transpose
        */
        void transpose(int value);

        /** @brief  Change velocity of all notes in patterm
        *   @param  value Offset to adjust +/-127
        */
        void changeVelocityAll(int value);

        /** @brief  Change duration of all notes in patterm
        *   @param  value Offset to adjust +/-100.0 or whatever
        */
        void changeDurationAll(float value);

        /** @brief  Change stutter count of all notes in patterm
        *   @param  value Offset to adjust +/-100 or whatever
        */
        void changeStutterCountAll(int value);

        /** @brief  Change stutter dur of all notes in patterm
        *   @param  value Offset to adjust +/-100 or whatever
        */
        void changeStutterDurAll(int value);

        /** @brief  Clear all events from pattern
        */
        void clear();

        /** @brief  Get event at given index
        *   @param  index Index of event
        *   @retval StepEvent* Pointer to event or null if event does not existing
        */
        StepEvent* getEventAt(uint32_t index);

        /** @brief  Get index of first event at given time (step)
        *   @param  step Index of step
        *   @retval uint32_t Index of event or -1 if not found
        */
        int getFirstEventAtStep(uint32_t step);

        /** @brief  Get quantity of events in pattern
        *   @retval size_t Quantity of events
        */
        size_t getEvents();

        /** @brief  Get the reference note
        *   @retval uint8_t MIDI note number
        *   @note   May be used for position within user interface
        */
        uint8_t getRefNote();

        /** @brief  Set the reference note
        *   @param  MIDI note number
         May be used for position within user interface
        */
        void setRefNote(uint8_t note);

        /** @brief  Get last populated step
        *   @retval uint32_t Index of last step that contains any events or -1 if pattern is empty
        */
        uint32_t getLastStep();

    private:
        void deleteEvent(uint32_t position, uint8_t command, uint8_t value1);

        std::vector<StepEvent*> m_vEvents; // Vector of pattern events
        uint32_t m_nBeats = 4; // Quantity of beats in pattern
        uint32_t m_nStepsPerBeat = 6; // Steps per beat
        uint8_t m_nScale = 0; // Index of scale
        uint8_t m_nTonic = 0; // Scale tonic (root note)
        uint8_t m_nRefNote = 60; // Note at which to position pattern editor
};
