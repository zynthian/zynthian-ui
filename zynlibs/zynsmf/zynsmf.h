/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include <cstdint>

#ifdef __cplusplus
extern "C"
{
#endif

#define NO_EVENT 0xFFFFFFFF

/** @brief  Enable debug output
*   @param  bEnable True to enable, false to disable
*/
void enableDebug(bool bEnable);

/** @brief  Load a SMF file
*   @param  filename Full path and name of file to load
*   @retval bool True on success
*/
bool load(char* filename);

/** @brief  Opens SMF file and parses data but does not load into memory
 *  @retval bool True on success
 */
bool open(char* filename);

/** @brief  Get duration of longest track
*   @retval float Duration in seconds
*/
double getDuration();

/** @brief  Set position to time
*   @param  time Time in milliseconds
*/
void setPosition(uint32_t time);

/** @brief  Get quantity of tracks in SMF
*   @retval uint32_t Quantity of tracks
*/
uint32_t getTracks();

/** @brief  Get SMF format
*   @retval uint8_t File format [0|1|2]
*/
uint8_t getFormat();

/** @brief  Get the next event in SMF
*   @retval bool False if there are no more events
*/
bool getNextEvent();

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

/** @brief  Adds a JACK player
*   @retval bool True on success
*/
bool addPlayer();

/** @brief  Removes a JACK player
*/
void removePlayer();

/** @brief  Start JACK player playback
*   @param  loop True to loop song else stop at end (Default: false)
*/
void startPlayback(bool loop = false);

/** @brief  Stop JACK player playback
*/
void stopPlayback();


#ifdef __cplusplus
}
#endif

