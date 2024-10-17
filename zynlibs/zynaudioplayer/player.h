/*  Audio file player library for Zynthian
    Copyright (C) 2021-2024 Brian Walton <brian@riban.co.uk>
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
    NOTIFY_LOOP_START       = 11,
    NOTIFY_LOOP_END         = 12,
    NOTIFY_CROP_START       = 13,
    NOTIFY_CROP_END         = 14,
    NOTIFY_SUSTAIN          = 15,
    NOTIFY_ENV_ATTACK       = 16,
    NOTIFY_ENV_HOLD         = 17,
    NOTIFY_ENV_DECAY        = 18,
    NOTIFY_ENV_SUSTAIN      = 19,
    NOTIFY_ENV_RELEASE      = 20,
    NOTIFY_ENV_ATTACK_CURVE = 21,
    NOTIFY_ENV_DECAY_CURVE  = 22,
    NOTIFY_VARISPEED        = 23
};

/** @brief  Library constructor (initalisation) */
static void __attribute__((constructor)) lib_init(void);

/** @brief  Library destructor (initalisation) */
static void __attribute__((destructor)) lib_exit(void);

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
 *   @param  player_handle Index of player to initialise
 *   @retval const char* Name of CODEC
 */
const char* get_codec(AUDIO_PLAYER* pPlayer);

/** @brief  Add a player instance
 *   @param  player_handle Index of player to initialise
 *   @retval AUDIO_PLAYER* Player handle (pointer to player object) on success or 0 on failure
 */
AUDIO_PLAYER* add_player();

/** @brief  Remove player from library
 *   @param  player_handle Handle of player provided by init_player()
 */
void remove_player(AUDIO_PLAYER* pPlayer);

/** @brief  Set the MIDI base note
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  base_note MIDI note that will trigger playback at normal speed
 */
void set_base_note(AUDIO_PLAYER* pPlayer, uint8_t base_note);

/** @brief  Get the MIDI base note
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval uint8_t MIDI note that will trigger playback at normal speed
 */
uint8_t get_base_note(AUDIO_PLAYER* pPlayer);

/** @brief  Set player MIDI channel
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  midi_chan MIDI channel (0..15 or other value to disable MIDI listen)
 */
void set_midi_chan(AUDIO_PLAYER* pPlayer, uint8_t midi_chan);

/** @brief  Get player index
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  index ID of the player
 */
int get_index(AUDIO_PLAYER* pPlayer);

/** @brief Get jack client name
 *   @retval const char* Jack client name
 */
const char* get_jack_client_name();

/** @brief  Open audio file
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  filename Full path and name of file to load
 *   @param  cb_fn Pointer to callback function with template void(float)
 *   @retval uint8_t True on success
 */
uint8_t load(AUDIO_PLAYER* pPlayer, const char* filename, cb_fn_t cb_fn);

/** @brief  Save audio file
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  filename Full path and name of file to create or overwrite
 *   @retval uint8_t True on success
 *   @note   Crops file by crop markers and saves cue points as metadata
 */
uint8_t save(AUDIO_PLAYER* pPlayer, const char* filename);

/** @brief  Close audio file clearing all data
 *   @param  player_handle Handle of player provided by init_player()
 */
void unload(AUDIO_PLAYER* pPlayer);

/** @brief  Get filename of currently loaded file
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval const char* Filename or emtpy string if no file loaded
 */
const char* get_filename(AUDIO_PLAYER* pPlayer);

/** @brief  Get duration of audio
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Duration in seconds
 */
float get_duration(AUDIO_PLAYER* pPlayer);

/** @brief  Set playhead position
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  time Time in seconds since start of audio
 */
void set_position(AUDIO_PLAYER* pPlayer, float time);

/** @brief  Get playhead position
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Time in seconds since start of audio
 */
float get_position(AUDIO_PLAYER* pPlayer);

/** @brief  Set loop mode
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  nLoop 1 to loop at end of audio, 2 to play to end (ignore MIDI note-off)
 */
void enable_loop(AUDIO_PLAYER* pPlayer, uint8_t nLoop);

/*  @brief  Get loop mode
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval uint8_t 1 if looping, 0 if one-shot
 */
uint8_t is_loop(AUDIO_PLAYER* pPlayer);

/** @brief  Set start of loop
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  time Start of loop in seconds since start of file
 */
void set_loop_start_time(AUDIO_PLAYER* pPlayer, float time);

/** @brief  Get start of loop
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Start of loop in seconds since start of file
 */
float get_loop_start_time(AUDIO_PLAYER* pPlayer);

/** @brief  Set end of loop
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  time End of loop in seconds since end of file
 */
void set_loop_end_time(AUDIO_PLAYER* pPlayer, float time);

/** @brief  Get end of loop
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float End of loop in seconds since end of file
 */
float get_loop_end_time(AUDIO_PLAYER* pPlayer);

/** @brief  Set start of audio (crop)
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  time Start of crop in seconds since start of file
 */
void set_crop_start_time(AUDIO_PLAYER* pPlayer, float time);

/** @brief  Get start of audio (crop)
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Start of crop in seconds since start of file
 */
float get_crop_start_time(AUDIO_PLAYER* pPlayer);

/** @brief  Set end audio (crop)
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  time End of crop in seconds since end of file
 */
void set_crop_end_time(AUDIO_PLAYER* pPlayer, float time);

/** @brief  Get end of audio (crop)
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float End of crop in seconds since end of file
 */
float get_crop_end_time(AUDIO_PLAYER* pPlayer);

/** @brief  Add a cue marker
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  position Position within file (in seconds) to add marker
 *   @param  name Cue point name
 *   @retval int32_t Index of marker or -1 on failure
 */
int32_t add_cue_point(AUDIO_PLAYER* pPlayer, float position, const char* name = nullptr);

/** @brief  Remove a cue marker
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  position Position within file (in secondes) of marker to remove
 *   @retval int32_t Index of removed maker or -1 on failure
 *   @note   The closest marker within +/-0.5s will be removed
 */
int32_t remove_cue_point(AUDIO_PLAYER* pPlayer, float position);

/** @brief  Get quantity of cue points
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval uint32_t Quantity of cue points
 */
uint32_t get_cue_point_count(AUDIO_PLAYER* pPlayer);

/** @brief  Get a cue point's position
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  index Index of cue point
 *   @retval float Position (in seconds) of cue point or -1.0 if not found
 */
float get_cue_point_position(AUDIO_PLAYER* pPlayer, uint32_t index);

/** @brief  Set a cue point's position
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  index Index of cue point
 *   @param  position Position (in seconds) of cue point
 *   @retval bool True on success
 */
bool set_cue_point_position(AUDIO_PLAYER* pPlayer, uint32_t index, float position);

/** @brief  Get a cue point's name
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  index Index of cue point
 *   @retval char* Name of cue point or "" if not found
 */
const char* get_cue_point_name(AUDIO_PLAYER* pPlayer, uint32_t index);

/** @brief  Set a cue point's name
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  index Index of cue point
 *   @param  name Name of cue point (as c-string) - max 255 characters
 *   @retval bool True on success
 */
bool set_cue_point_name(AUDIO_PLAYER* pPlayer, uint32_t index, const char* name);

/** @brief  Clear all cue points
 *   @param  player_handle Handle of player provided by init_player()
 */
void clear_cue_points(AUDIO_PLAYER* pPlayer);

/** @brief  Start playback
 *   @param  player_handle Handle of player provided by init_player()
 */
void start_playback(AUDIO_PLAYER* pPlayer);

/** @brief  Stop playback
 *   @param  player_handle Handle of player provided by init_player()
 */
void stop_playback(AUDIO_PLAYER* pPlayer);

/** @brief  Get play state
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval uint8_t Play state [STOPPED|STARTING|PLAYING|STOPPING]
 */
uint8_t get_playback_state(AUDIO_PLAYER* pPlayer);

/** @brief  Get samplerate of currently loaded file
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval int Samplerate in samples per seconds
 */
int get_samplerate(AUDIO_PLAYER* pPlayer);

/** @brief  Get quantity of channels in currently loaded file
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval int Quantity of channels, e.g. 2 for stereo
 */
int get_channels(AUDIO_PLAYER* pPlayer);

/** @brief  Get quantity of frames (samples) in currently loaded file
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval int Quantity of frames
 */
int get_frames(AUDIO_PLAYER* pPlayer);

/** @brief  Get format of currently loaded file
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval int Bitwise OR of major and minor format type and optional endianness value
 *   @see    sndfile.h for supported formats
 */
int get_format(AUDIO_PLAYER* pPlayer);

/** @brief  Set samplerate converter quality
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  quality Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
 *   @retval uint8_t True on success, i.e. the quality parameter is valid
 *   @note   Quality will apply to subsequently opened files, not currently open file
 */
uint8_t set_src_quality(AUDIO_PLAYER* pPlayer, unsigned int quality);

/** @brief  Get samplerate converter quality
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval unsigned int Samplerate conversion quality [SRC_SINC_BEST_QUALITY | SRC_SINC_MEDIUM_QUALITY | SRC_SINC_FASTEST | SRC_ZERO_ORDER_HOLD | SRC_LINEAR]
 *   @note   Quality applied to subsequently opened files, not necessarily currently open file
 */
unsigned int get_src_quality(AUDIO_PLAYER* pPlayer);

/** @brief  Set gain
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  gain Gain factor (0.01..2.0)
 */
void set_gain(AUDIO_PLAYER* pPlayer, float gain);

/** @brief  Get gain (volume)
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Gain
 */
float get_gain(AUDIO_PLAYER* pPlayer);

/** @brief  Set track to playback to left output
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  track Index of track to play to left output or -1 for mix of all odd tracks
 */
void set_track_a(AUDIO_PLAYER* pPlayer, int track);

/** @brief  Set track to playback to right output
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  track Index of track to play to right output or -1 for mix of all even tracks
 */
void set_track_b(AUDIO_PLAYER* pPlayer, int track);

/** @brief  Get track to playback to left output
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval int Index of track to play or -1 for mix of all tracks
 */
int get_track_a(AUDIO_PLAYER* pPlayer);

/** @brief  Get track to playback to right output
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval int Index of track to play or -1 for mix of all tracks
 */
int get_track_b(AUDIO_PLAYER* pPlayer);

/** @brief  Set pitchbend range
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  range Range in semitones
 */
void set_pitchbend_range(AUDIO_PLAYER* pPlayer, uint8_t range);

/** @brief  Get pitchbend range
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval uint8_t Range in semitones
 */
uint8_t get_pitchbend_range(AUDIO_PLAYER* pPlayer);

/** @brief  Set base speed
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  factor Speed factor (0.25..4.0)
 */
void set_speed(AUDIO_PLAYER* pPlayer, float factor);

/** @brief  Get base speed
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Speed factor
 */
float get_speed(AUDIO_PLAYER* pPlayer);

/** @brief  Set base pitch
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  factor Pitch factor (0.25..4.0)
 */
void set_pitch(AUDIO_PLAYER* pPlayer, float factor);

/** @brief  Get base pitch
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Pitch factor
 */
float get_pitch(AUDIO_PLAYER* pPlayer);

/** @brief  Set varispeed
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  ratio Ratio of speed:pitch (1.0 for no varispeed, -1.0 for reverse, 0.0 for stopped)
 */
void set_varispeed(AUDIO_PLAYER* pPlayer, float ratio);

/** @brief  Get varispeed
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval float Ratio of speed:pitch (1.0 for no varispeed)
 */
float get_varispeed(AUDIO_PLAYER* pPlayer);

/** @brief  Set size of file read buffers
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  size Size of buffers in frames
 *   @note   Cannot change size whilsts file is open
 */
void set_buffer_size(AUDIO_PLAYER* pPlayer, unsigned int size);

/** @brief  Get size of file read buffers
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval unsigned int Size of buffers in frames
 */
unsigned int get_buffer_size(AUDIO_PLAYER* pPlayer);

/** @brief  Set factor by which ring buffer is larger than file read buffers
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  count Quantity of buffers
 *   @note   Cannot change count whilst file is open
 */
void set_buffer_count(AUDIO_PLAYER* pPlayer, unsigned int count);

/** @brief  Get factor by which ring buffer is larger than file read buffers
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval unsigned int Quantity of buffers
 */
unsigned int get_buffer_count(AUDIO_PLAYER* pPlayer);

/** @brief Set difference in postion that will trigger notificaton
 *   @param  player_handle Handle of player provided by init_player()
 *   @param time Time difference in seconds
 */
void set_pos_notify_delta(AUDIO_PLAYER* pPlayer, float time);

/**** Envelope functions ****/

/** @brief  Set envelope attack rate
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  rate Attack rate
 */
void set_env_attack(AUDIO_PLAYER* pPlayer, float rate);

/** @brief  Get envelope attack rate
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Attack rate
 */
float get_env_attack(AUDIO_PLAYER* pPlayer);

/** @brief  Set envelope hold time
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  hold Time in seconds to hold between attack and decay phases
 */
void set_env_hold(AUDIO_PLAYER* pPlayer, float hold);

/** @brief  Get envelope hold time
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Time in seconds between attack and decay phases
 */
float get_env_hold(AUDIO_PLAYER* pPlayer);

/** @brief  Set envelope decay rate
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  rate Decay rate
 */
void set_env_decay(AUDIO_PLAYER* pPlayer, float rate);

/** @brief  Get envelope decay rate
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Decay rate
 */
float get_env_decay(AUDIO_PLAYER* pPlayer);

/** @brief  Set envelope release rate
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  rate Release rate
 */
void set_env_release(AUDIO_PLAYER* pPlayer, float rate);

/** @brief  Get envelope release rate
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Release rate
 */
float get_env_release(AUDIO_PLAYER* pPlayer);

/** @brief  Set envelope sustain level
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  level Sustain level
 */
void set_env_sustain(AUDIO_PLAYER* pPlayer, float level);

/** @brief  Get envelope sustain level
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Sustain level
 */
float get_env_sustain(AUDIO_PLAYER* pPlayer);

/** @brief  Set envelope attack target ratio (curve)
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  ratio Target ratio
 */
void set_env_target_ratio_a(AUDIO_PLAYER* pPlayer, float ratio);

/** @brief  Get envelope attack target ratio (curve)
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Target ratio
 */
float get_env_target_ratio_a(AUDIO_PLAYER* pPlayer);

/** @brief  Set envelope decay / release target ratio (curve)
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  ratio Target ratio
 */
void set_env_target_ratio_dr(AUDIO_PLAYER* pPlayer, float ratio);

/** @brief  Get envelope decay / release target ratio (curve)
 *   @param  player_handle Handle of player provided by init_player()
 *   @retval <float> Target ratio
 */
float get_env_target_ratio_dr(AUDIO_PLAYER* pPlayer);

/** @brief Set the quantity of beats in a loop
 *   @param player_handle Handle of player provided by init_player()
 *   @param beats Quantity of beats or 0 for no loop behaviour
 */
void set_beats(AUDIO_PLAYER* pPlayer, uint8_t beats);

/** @brief Get the quantity of beats in a loop
 *   @param player_handle Handle of player provided by init_player()
 *   @retval uint8_t Quantity of beats
 */
uint8_t get_beats(AUDIO_PLAYER* pPlayer);

/** @brief  Set tempo for loop play
 *   @param  tempo Tempo in beats per minute
 */
void set_tempo(float tempo);

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
 *   @param  player_handle Handle of player provided by init_player()
 *   @param  filename Full path and name of file to load
 *   @retval float Duration is seconds. Zero if cannot open file.
 */
float get_file_duration(const char* filename);

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
unsigned int get_player_count();

#ifdef __cplusplus
}
#endif
