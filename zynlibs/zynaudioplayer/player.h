/*  Audio file player library for Zynthian
    Copyright (C) 2021-2026 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include "audio_player.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    NOTIFY_ALL              = 0,
    NOTIFY_TRANSPORT        = 1,
    NOTIFY_POSITION         = 2,
    NOTIFY_GAIN             = 3,
    NOTIFY_LOOP             = 4,
    NOTIFY_TRACK_A          = 5,
    NOTIFY_TRACK_B          = 6,
    NOTIFY_QUALITY          = 7,
    NOTIFY_BUFFER_SIZE      = 8,
    NOTIFY_BUFFER_COUNT     = 9,
    NOTIFY_DEBUG            = 10,
    NOTIFY_CROP_START       = 13,
    NOTIFY_CROP_END         = 14,
    NOTIFY_VARISPEED        = 23
};

/** @brief  Library constructor (initalisation) */
static void __attribute__((constructor)) lib_init(void);

/** @brief  Library destructor (initalisation) */
static void __attribute__((destructor)) lib_exit(void);

/** @brief  Init jack client and ports
*   @param  cb_fn Pointer to a callback function handling notifications
*   @retval bool True if success
*/
bool init(cb_fn_t* cb_fn);

/** @brief  Stop jack client */
void stop();

/** @brief  Check if a codec is supported
*   @param  codec name of codec (file extension, e.g. wav)
*   @retval int 1 if supported
*/
int is_codec_supported(const char* codec);

/** @brief  Get a comma separated list of supported codecs
*   @retval char* Comma separated list of supported codecs (file extensions)
*/
char* get_supported_codecs();

/** @brief  Get name of CODEC of loaded file
*   @param  id Index of player
*   @retval const char* Name of CODEC
*/
const char* get_codec(uint8_t id);

/** @brief  Add a player instance
*   @retval uint8_t Player id on success or 255 on failure
*/
uint8_t add_player();

/** @brief  Remove player from library
*   @param  id Player id
*/
void remove_player(uint8_t id);

/** @brief Get jack client name
*   @retval const char* Jack client name
*/
const char* get_jack_client_name();

/** @brief  Open audio file
*   @param  id Player id
*   @param  filename Full path and name of file to load
*   @retval uint8_t True on success
*/
uint8_t load(uint8_t id, const char* filename);

/** @brief  Save audio file
*   @param  id Player id
*   @param  filename Full path and name of file to create or overwrite
*   @retval uint8_t True on success
*   @note   Crops file by crop markers and saves cue points as metadata
*/
uint8_t save(uint8_t id, const char* filename);

/** @brief  Close audio file clearing all data
*   @param  id Player id
*/
void unload(uint8_t id);

/** @brief  Get filename of currently loaded file
*   @param  id Player id
*   @retval const char* Filename or emtpy string if no file loaded
*/
const char* get_filename(uint8_t id);

/** @brief  Get duration of audio
*   @param  id Player id
*   @retval float Duration in seconds
*/
float get_duration(uint8_t id);

/** @brief  Set playhead position
*   @param  id Player id
*   @param  time Time in seconds since start of audio
*/
void set_position(uint8_t id, float time);

/** @brief  Get playhead position
*   @param  id Playernid
*   @retval float Time in seconds since start of audio
*/
float get_position(uint8_t id);

/** @brief  Set loop mode
*   @param  id Player id
*   @param  nLoop 1 to loop at end of audio, 2 to play to end (ignore MIDI note-off)
*/
void enable_loop(uint8_t id, uint8_t nLoop);

/*  @brief  Get loop mode
*   @param  uint8_t id
*   @retval uint8_t 1 if looping, 0 if one-shot
*/
uint8_t is_loop(uint8_t id);

/** @brief  Set start of audio (crop)
*   @param  id Player id
*   @param  time Start of crop in seconds since start of file
*/
void set_crop_start_time(uint8_t id, float time);

/** @brief  Get start of audio (crop)
*   @param  id Player id
*   @retval float Start of crop in seconds since start of file
*/
float get_crop_start_time(uint8_t id);

/** @brief  Set end audio (crop)
*   @param  id Player id
*   @param  time End of crop in seconds since end of file
*/
void set_crop_end_time(uint8_t id, float time);

/** @brief  Get end of audio (crop)
*   @param  id Player id
*   @retval float End of crop in seconds since end of file
*/
float get_crop_end_time(uint8_t id);

/** @brief  Add a cue marker
*   @param  id Player id
*   @param  position Position within file (in seconds) to add marker
*   @param  name Cue point name
*   @retval int32_t Index of marker or -1 on failure
*/
int32_t add_cue_point(uint8_t id, float position, const char* name = nullptr);

/** @brief  Remove a cue marker
*   @param  id Player id
*   @param  position Position within file (in secondes) of marker to remove
*   @retval int32_t Index of removed maker or -1 on failure
*   @note   The closest marker within +/-0.5s will be removed
*/
int32_t remove_cue_point(uint8_t id, float position);

/** @brief  Get quantity of cue points
*   @param  id Player id
*   @retval uint32_t Quantity of cue points
*/
uint32_t get_cue_point_count(uint8_t id);

/** @brief  Get a cue point's position
*   @param  id Player id
*   @param  index Index of cue point
*   @retval float Position (in seconds) of cue point or -1.0 if not found
*/
float get_cue_point_position(uint8_t id, uint32_t index);

/** @brief  Set a cue point's position
*   @param  id Player id
*   @param  index Index of cue point
*   @param  position Position (in seconds) of cue point
*   @retval bool True on success
*/
bool set_cue_point_position(uint8_t id, uint32_t index, float position);

/** @brief  Get a cue point's name
*   @param  id Player id
*   @param  index Index of cue point
*   @retval char* Name of cue point or "" if not found
*/
const char* get_cue_point_name(uint8_t id, uint32_t index);

/** @brief  Set a cue point's name
*   @param  id Player id
*   @param  index Index of cue point
*   @param  name Name of cue point (as c-string) - max 255 characters
*   @retval bool True on success
*/
bool set_cue_point_name(uint8_t id, uint32_t index, const char* name);

/** @brief  Clear all cue points
*   @param  id Player id
*/
void clear_cue_points(uint8_t id);

/** @brief  Start playback
*   @param  id Player id
*/
void start_playback(uint8_t id);

/** @brief  Stop playback
*   @param  id Player id
*/
void stop_playback(uint8_t id);

/** @brief  Get play state
*   @param  id Player id
*   @retval uint8_t Play state [STOPPED|STARTING|PLAYING|STOPPING]
 */
uint8_t get_playback_state(uint8_t id);

/** @brief  Get samplerate of currently loaded file
*   @param  id Player id
*   @retval int Samplerate in samples per seconds
*/
int get_samplerate(uint8_t id);

/** @brief  Get quantity of channels in currently loaded file
*   @param  id Player id
*   @retval int Quantity of channels, e.g. 2 for stereo
*/
int get_channels(uint8_t id);

/** @brief  Get quantity of frames (samples) in currently loaded file
*   @param  id Player id
*   @retval int Quantity of frames
*/
int get_frames(uint8_t id);

/** @brief  Get format of currently loaded file
*   @param  id Player id
*   @retval int Bitwise OR of major and minor format type and optional endianness value
*   @see    sndfile.h for supported formats
*/
int get_format(uint8_t id);

/** @brief  Set samplerate converter quality
*   @param  id Player id
*   @param  quality Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
*   @retval uint8_t True on success, i.e. the quality parameter is valid
*   @note   Quality will apply to subsequently opened files, not currently open file
*/
uint8_t set_src_quality(uint8_t id, unsigned int quality);

/** @brief  Get samplerate converter quality
*   @param  id Player id
*   @retval unsigned int Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
*   @note   Quality applied to subsequently opened files, not necessarily currently open file
*/
unsigned int get_src_quality(uint8_t id);

/** @brief  Set gain
*   @param  id Player id
*   @param  gain Gain factor (0.01..2.0)
*/
void set_gain(uint8_t id, float gain);

/** @brief  Get gain (volume)
*   @param  id Player id
*   @retval float Gain
*/
float get_gain(uint8_t id);

/** @brief  Set track to playback to left output
*   @param  id Player id
*   @param  track Index of track to play to left output or -1 for mix of all odd tracks
*/
void set_track_a(uint8_t id, int track);

/** @brief  Set track to playback to right output
*   @param  id Player id
*   @param  track Index of track to play to right output or -1 for mix of all even tracks
*/
void set_track_b(uint8_t id, int track);

/** @brief  Get track to playback to left output
*   @param  id Player id
*   @retval int Index of track to play or -1 for mix of all tracks
*/
int get_track_a(uint8_t id);

/** @brief  Get track to playback to right output
*   @param  id Player id
*   @retval int Index of track to play or -1 for mix of all tracks
*/
int get_track_b(uint8_t id);

/** @brief  Set base speed
*   @param  id Player id
*   @param  factor Speed factor (0.25..4.0)
*/
void set_speed(uint8_t id, float factor);

/** @brief  Get base speed
*   @param  id Player id
*   @retval float Speed factor
*/
float get_speed(uint8_t id);

/** @brief  Set base pitch
*   @param  id Player id
*   @param  factor Pitch factor (0.25..4.0)
*/
void set_pitch(uint8_t id, float factor);

/** @brief  Get base pitch
*   @param  id Player id
*   @retval float Pitch factor
*/
float get_pitch(uint8_t id);

/** @brief  Set varispeed
*   @param  id Player id
*   @param  ratio Ratio of speed:pitch (1.0 for no varispeed, -1.0 for reverse, 0.0 for stopped)
*/
void set_varispeed(uint8_t id, float ratio);

/** @brief  Get varispeed
*   @param  id Player id
*   @retval float Ratio of speed:pitch (1.0 for no varispeed)
*/
float get_varispeed(uint8_t id);

/** @brief  Set size of file read buffers
*   @param  id Player id
*   @param  size Size of buffers in frames
*   @note   Cannot change size whilsts file is open
*/
void set_buffer_size(uint8_t id, unsigned int size);

/** @brief  Get size of file read buffers
*   @param  id Player id
*   @retval unsigned int Size of buffers in frames
*/
unsigned int get_buffer_size(uint8_t id);

/** @brief  Set factor by which ring buffer is larger than file read buffers
*   @param  id Player id
*   @param  count Quantity of buffers
*   @note   Cannot change count whilst file is open
*/
void set_buffer_count(uint8_t id, unsigned int count);

/** @brief  Get factor by which ring buffer is larger than file read buffers
*   @param  id Player id
*   @retval unsigned int Quantity of buffers
*/
unsigned int get_buffer_count(uint8_t id);

/** @brief Set difference in postion that will trigger notificaton
*   @param  id Player id
*   @param time Time difference in seconds
*/
void set_pos_notify_delta(uint8_t id, float time);

/**** Global functions ****/

/** @brief  Enable debug output
*   @param  bEnable True to enable, false to disable
*/
void enable_debug(int enable);

/** @brief  Get debug state
*   @retval int 1 if debug enabled
*/
int is_debug();

/** @brief  Get duration of a file without loading it
*   @param  filename Full path and name of file to load
*   @retval float Duration is seconds. Zero if cannot open file.
*/
float get_file_duration(const char* filename);

/** @brief  Get num of channels of a file without loading it
*   @param  filename Full path and name of file to load
*   @retval int Num of channels in the file. Zero if cannot open file.
*/
int get_file_channels(const char* filename);

/** @brief  Get info from file meta data
*   @param  filename Full path and filename of audio file
*   @param  type Info type to retrieve [SF_STR_TITLE | SF_STR_COPYRIGHT | SF_STR_SOFTWARE | SF_STR_ARTIST | SF_STR_COMMENT | SF_STR_DATE| SF_STR_ALBUM |
* SF_STR_LICENSE | SF_STR_TRACKNUMBER | SF_STR_GENRE]
*   @retval const char Info value as c-string
*/
const char* get_file_info(const char* filename, int type);

/** @brief  Get quantity of instantiated players
 *   @retval unsigned int Quantity of players
 */
uint8_t get_player_count();

#ifdef __cplusplus
}
#endif
