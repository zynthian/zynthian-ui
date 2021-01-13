/*  Standard MIDI File library for Zynthian
*   Loads a SMF and parses events
*   Provides time information, e.g. duration of song
*/

#include <cstdint>

#ifdef __cplusplus
extern "C"
{
#endif

/** @brief  Enable debug output
*   @param  bEnable True to enable, false to disable
*/
void enableDebug(bool bEnable);

/** @brief  Load a SMF file
*   @param  filename Full path and name of file to load
*   @retval bool True on success
*/
bool load(char* filename);

/** @brief  Get duration of longest track
*   @retval uint32_t Duration in seconds
*/
int getDuration();

/** @brief  Clear all song data
*/
void unload();

#ifdef __cplusplus
}
#endif

