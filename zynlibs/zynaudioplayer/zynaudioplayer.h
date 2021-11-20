/*  Audio file player library for Zynthian
*
*/
//!@todo Add license

#include <cstdint>

#ifdef __cplusplus
extern "C"
{
#endif

/** @brief  Initialise library
*/
void init();

/** @brief  Enable debug output
*   @param  bEnable True to enable, false to disable
*/
void enableDebug(bool bEnable);

/** @brief  Open audio file
*   @param  filename Full path and name of file to load
*   @retval bool True on success
*/
bool open(const char* filename);

/** @brief  Get duration of a file without loading it
*   @param  filename Full path and name of file to load
*   @retval double Duration is seconds. Zero if cannot open file.
*/
double getFileDuration(const char* filename);

/** @brief  Save audio file
*   @param  filename Full path and name of file to create or overwrite
*   @retval bool True on success
*/
bool save(const char* filename);

/** @brief  Close audio file clearing all data
*/
void close_file();

/** @brief  Get duration of audio
*   @retval double Duration in seconds
*/
double getDuration();

/** @brief  Set position to time
*   @param  time Time in microseconds since start of audio
*/
void setPosition(uint32_t time);

/** @brief  Set loop mode
*   @param  bLoop True to loop at end of audio
*/
void setLoop(bool bLoop);

/** @brief  Start playback
*/
void startPlayback();

/** @brief  Stop playback
*/
void stopPlayback();

/** @brief  Get play state
*   @retval uint8_t Play state [STOPPED|STARTING|PLAYING|STOPPING]
*/
uint8_t getPlayState();

/** @brief  Get samplerate of currently loaded file
*   @retval int Samplerate in samples per seconds
*/
int getSamplerate();

/** @brief  Get quantity of channels in currently loaded file
*   @retval int Quantity of channels, e.g. 2 for stereo
*/
int getChannels();

/** @brief  Get quantity of frames (samples) in currently loaded file
*   @retval int Quantity of frames
*/
int getFrames();

/** @brief  Get format of currently loaded file
*   @retval int Bitwise OR of major and minor format type and optional endianness value
*   @see    sndfile.h for supported formats
*/
int getFormat();


#ifdef __cplusplus
}
#endif

// Private functions not exposed to C library API

void *fileThread(void*);
