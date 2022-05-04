/*  Audio file player library for Zynthian
    Copyright (C) 2021 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include <stdint.h>

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
void enableDebug(uint8_t bEnable);

/** @brief  Open audio file
*   @param  filename Full path and name of file to load
*   @retval uint8_t True on success
*/
uint8_t open(const char* filename);

/** @brief  Get duration of a file without loading it
*   @param  filename Full path and name of file to load
*   @retval float Duration is seconds. Zero if cannot open file.
*/
float getFileDuration(const char* filename);

/** @brief  Save audio file
*   @param  filename Full path and name of file to create or overwrite
*   @retval uint8_t True on success
*/
uint8_t save(const char* filename);

/** @brief  Close audio file clearing all data
*/
void closeFile();

/** @brief  Get filename of currently loaded file
*   @retval const char* Filename or emtpy string if no file loaded
*/
const char* getFilename();

/** @brief  Get duration of audio
*   @retval float Duration in seconds
*/
float getDuration();

/** @brief  Set playhead position
*   @param  time Time in seconds since start of audio
*/
void setPosition(float time);

/** @brief  Get playhead position
*   @retval float Time in seconds since start of audio
*/
float getPosition();

/** @brief  Set loop mode
*   @param  bLoop True to loop at end of audio
*/
void setLoop(uint8_t bLoop);

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

/** @brief  Get info from file meta data
*   @param  filename Full path and filename of audio file
*   @param  type Info type to retrieve [SF_STR_TITLE | SF_STR_COPYRIGHT | SF_STR_SOFTWARE | SF_STR_ARTIST | SF_STR_COMMENT | SF_STR_DATE| SF_STR_ALBUM | SF_STR_LICENSE | SF_STR_TRACKNUMBER | SF_STR_GENRE]
*   @retval const char Info value as c-string
*/
const char* getFileInfo(const char* filename, int type);

/** @brief  Set samplerate converter quality
*   @param  quality Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
*   @retval uint8_t True on success, i.e. the quality parameter is valid
*   @note   Quality will apply to subsequently opened files, not currently open file
*/
uint8_t setSrcQuality(unsigned int quality);

/** @brief  Set audio level (volume)
*   @param  level Audio level (0..2)
*/
void setVolume(float level);

/** @brief  Get audio level (volume)
*   @retval float Audio level
*/
float getVolume();

#ifdef __cplusplus
}
#endif

// Private functions not exposed to C library API

void *fileThread(void*);
int onJackXrun(void *pArgs);
