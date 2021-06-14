/*  Standard MIDI File library for Zynthian
*   Manages multiple SMF
*   
*/
//!@todo Add license

#include <cstdint>
#include "smf.h"

#ifdef __cplusplus
extern "C"
{
#endif

#define NO_EVENT 0xFFFFFFFF


/** @brief  Add a new empty SMF
*   @retval Smf* Pointer to the new SMF
*   @note   Use the returned pointer for subsequent operations on this SMF
*/
Smf* addSmf();

/** @brief  Removes an existing SMF
*   @param  pSmf Pointer to the SMF to remove
*/
void removeSmf(Smf* pSmf);

/** @brief  Get quantity of SMF objects loaded
*   @retval size_t Quanity of SMF objects
*/
size_t getSmfCount();

/** @brief  Enable debug output
*   @param  bEnable True to enable, false to disable
*/
void enableDebug(bool bEnable);

/** @brief  Load and parse a file into a SMF object
*   @param  pSmf Pointer to the SMF object to populate
*   @param  filename Full path and name of file to load
*   @retval bool True on success
*/
bool load(Smf* pSmf, char* filename);

/** @brief  Save a SMF object to file
*   @param  pSmf Pointer to the SMF object to save
*   @param  filename Full path and name of file to create or overwrite
*   @retval bool True on success
*/
bool save(Smf* pSmf, char* filename);

/** @brief  Unload SMF file clearing all data
*   @param  pSmf Pointer to the SMF object to unload
*/
void unload(Smf* pSmf);

/** @brief  Get duration of longest track
*   @param  pSmf Pointer to the SMF
*   @retval double Duration in seconds
*/
double getDuration(Smf* pSmf);

/** @brief  Set position to time
*   @param  pSmf Pointer to the SMF
*   @param  time Time in ticks since start of song
*/
void setPosition(Smf* pSmf, uint32_t time);

/** @brief  Get quantity of tracks in SMF
*   @param  pSmf Pointer to the SMF
*   @retval uint32_t Quantity of tracks
*/
uint32_t getTracks(Smf* pSmf);

/** @brief  Get SMF format
*   @param  pSmf Pointer to the SMF
*   @retval uint8_t File format [0|1|2]
*/
uint8_t getFormat(Smf* pSmf);

/** @brief  Get quantity of events in a track
*   @param  pSmf Pointer to the SMF
*   @param  nTrack Track index (Optional: Default get all events in SMF)
*   @retval uint32_t Quantity of events in track
*/
uint32_t getEvents(Smf* pSmf, size_t nTrack = -1);

/** @brief  Get ticks per quarter note at event cursor
*   @param  pSmf Pointer to the SMF
*   @retval uint16_t Ticks per quarter note
*   @note   Quarter notes are often ambiguously refered to as beats
*/
uint16_t getTicksPerQuarterNote(Smf* pSmf);

/** @brief  Get the current event in SMF
*   @param  pSmf Pointer to the SMF
*   @param  bAdvance True to advance to next event after returning current event
*   @retval bool False if there are no more events
*/
bool getEvent(Smf* pSmf, bool bAdvance=false);

/** @brief  Add MIDI note event
*   @param  pSmf Pointer to the SMF
*   @param  nTrack Index of track to add event
*	@param	nTime Position of note in ticks since start of song
*   @param  nDuration Duration of note in ticks
*   @param  nChannel MIDI channel
*   @param  nNote MIDI note
*   @param  nVelocity MIDI velocity
*/
void addNote(Smf* pSmf, uint32_t nTrack, uint32_t nTime, uint32_t nDuration, uint8_t nChannel, uint8_t nNote, uint8_t nVelocity);

/** @brief  Add tempo event
*   @param  pSmf Pointer to the SMF
*	@param	nTime Position of tempo change in ticks since start of song
*   @param  dTempo Tempo in BPM
*/
void addTempo(Smf* pSmf, uint32_t nTime, double dTempo);

/** @brief  Set end of track time (required for loop playback)
*   @param  pSmf Pointer to the SMF
*   @param  nTrack Index of track to add event
*	@param	nTime Position of end of track in ticks since start of song
*/
void setEndOfTrack(Smf* pSmf, uint32_t nTrack, uint32_t nTime);

/** @brief  Get the track of the current event
*   @retval size_t Index of track
*/
size_t getEventTrack();

/** @brief  Get time of current event
*   @retval Time offset in ticks since start of song or NO_EVENT if no current event
*/
uint32_t getEventTime();

/** @brief  Get type of current event
*   @retval Event type or EVENT_TYPE_NONE if no event
*/
uint8_t getEventType();

/** @brief  Get event MIDI channel
*   @retval uint8_t MIDI channel (0..15 or 0xFF if not MIDI event)
*/
uint8_t getEventChannel();

/** @brief  Get event MIDI status byte (including channel) or meta-event type
*   @retval uint8_t MIDI status (0x80..0xFF or 0x00 if not MIDI event)
*/
uint8_t getEventStatus();

/** @brief  Get event MIDI value 1
*   @retval uint8_t MIDI value 1 (0..127 or 0xFF if not MIDI event or does not have value 1)
*/
uint8_t getEventValue1();

/** @brief  Get event MIDI value 2
*   @retval uint8_t MIDI value 2 (0..127 or 0xFF if not MIDI event or does not have value 2)
*/
uint8_t getEventValue2();

/** @brief  Create a JACK client if it does note exist and attach JACK player to a SMF
*   @param  pSmf Pointer to the SMF
*   @retval bool True on success
*/
bool attachPlayer(Smf* pSmf);

/** @brief  Disconnect JACK player from SMF and destroy JACK client if it exists (and recorder not attached)
*/
void removePlayer();

/** @brief  Set loop mode
*   @param  bLoop True to loop at end of song
*/
void setLoop(bool bLoop);

/** @brief  Start JACK player playback
*/
void startPlayback();

/** @brief  Stop JACK player playback
*/
void stopPlayback();

/** @brief  Get play state
*   @retval uint8_t Play state [STOPPED|STARTING|PLAYING|STOPPING]
*/
uint8_t getPlayState();

/** @brief  Create a JACK client if it does note exist and attach JACK recorder to a SMF
*   @param  pSmf Pointer to the SMF
*   @retval bool True on success
*/
bool attachRecorder(Smf* pSmf);

/** @brief  Disconnect JACK recorder from SMF and destroy JACK client if it exists (and player not attached)
*/
void removeRecorder();

/** @brief  Start JACK recording
*/
void startRecording();

/** @brief  Stop JACK recording
*/
void stopRecording();

/** @brief  Get record state
*   @retval bool True if recording
*/
bool isRecording();

/** @brief  Get tempo at current position
*   @param  pSmf Pointer to the SMF
*   @param  nTime Ticks from start of song
*   @retval double Tempo in BPM
*/
double getTempo(Smf* pSmf, uint32_t nTime);

/** @brief  Print events in human readable format
*   @param  pSmf Pointer to the SMF
*   @param  nTrack Index of track to show
*/
void printEvents(Smf* pSmf, size_t nTrack);

/** @brief  Mute a track
*   @param  pSmf Pointer to the SMF
*   @param  nTrack Index of track to mute
*   @param  bMute True to mute, false to unmute
*/
void muteTrack(Smf* pSmf, size_t nTrack, bool bMute);

/** @brief  Check if track is muted
*   @param  pSmf Pointer to the SMF
*   @param  nTrack Index of track to mute
*   @retval bool True if track is muted
*/
bool isTrackMuted(Smf* pSmf, size_t nTrack);

#ifdef __cplusplus
}
#endif

