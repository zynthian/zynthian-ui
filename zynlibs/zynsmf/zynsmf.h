/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include <cstdint>
#include "smf.h"

#ifdef __cplusplus
extern "C"
{
#endif

#define NO_EVENT 0xFFFFFFFF


/** @brief  Add a new SMF
*   @retval Smf* Pointer to the new SMF
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

/** @brief  Load a SMF file
*   @param  pSmf Pointer to the SMF
*   @param  filename Full path and name of file to load
*   @retval bool True on success
*/
bool load(Smf* pSmf, char* filename);

/** @brief  Unload SMF file clearing all data
*   @param  pSmf Pointer to the SMF
*/
void unload(Smf* pSmf);

/** @brief  Get duration of longest track
*   @param  pSmf Pointer to the SMF
*   @retval float Duration in milliseconds
*/
double getDuration(Smf* pSmf);

/** @brief  Set position to time
*   @param  pSmf Pointer to the SMF
*   @param  time Time in milliseconds
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

/** @brief  Get the next event in SMF
*   @param  pSmf Pointer to the SMF
*   @retval bool False if there are no more events
*/
bool getNextEvent(Smf* pSmf);

/** @brief  Get time of current event
*   @retval Time offset from start of track that the event occurs NO_EVENT if no event
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

/** @brief  Get event MIDI status byte (including channel)
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

/** @brief  Attach JACK player to a SMF
*   @param  pSmf Pointer to the SMF
*   @retval bool True on success
*/
bool attachPlayer(Smf* pSmf);

/** @brief  Removes a JACK player
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

#ifdef __cplusplus
}
#endif

