#include <stdint.h> // Provides fixed width integer defininitions

#define PRELOAD_FRAMES 2048 // Size of preload buffers in frames
#define RINGBUFFER PRELOAD_FRAMES * 2 // Size of ring buffers in frames
#define MAX_CLIPS 127 // Maximum quantity of clips per player/channel
#define MIN_FRAMES 1024 // Minimum quantity of frames to allow in audio files

enum STATE {
    STATE_IDLE,     // Not ready for use
    STATE_LOAD,     // Load new file into preload cache
    STATE_READY,    // Cached, ready for use
    STATE_STARTING, // Switch sndfile
    STATE_PLAYING,  // Buffer in use for playback (may be from preload or ring buffer)
    STATE_STOPPING,  // Fade to avoid stop clitch
    STATE_SYNCYNG
};

enum ERROR {
    ERROR_SUCCESS,      // No error
    ERROR_EXISTS,       // Already exists
    ERROR_RANGE,        // Parameter out of range
    ERROR_CREATE,       // Cannot create object
    ERROR_PORT,         // Cannot create port
    ERROR_OPEN,         // Error opening file
    ERROR_SAMPLERATE,   // Wrong samplerate
    ERROR_ACTIVATE,     // Cannot activate jack
    ERROR_SRC,          // Error during samplerate conversion
    ERROR_STRETCH       // Error during time stretch
};

enum MIDI_COMMANDS {
    MIDI_NOTE_OFF   = 0x80,
    MIDI_NOTE_ON    = 0x90,
    MIDI_CC         = 0xb0,
    MIDI_POLYTOUCH  = 0xa0,
    MIDI_PROGRAM    = 0xc0,
    MIDI_AFTERTOUCH = 0xd0,
    MIDI_PITCHBEND  = 0xe0
};

// ***Function declarations***

/** @brief  Get the next available clip
    @param  channel MIDI channel
    @retval uint8_t Clip ID (MIDI note) or 0 on error
*/
uint8_t getFreeClip(uint8_t channel);

/** @brief  Load a file into a player
    @param  channel MIDI channel
    @param  note MIDI note to trigger clip or 0 for next available
    @param  path Full (or relative) path and filename
    @param  nbeats Total number of beats in sample file
    @param  start Start frame
    @param  end End frame
    @param  quality Re-sample quality
    @param  ratio Time stretch ratio (1.0 for no stretch)
    @retval uint8_t Clip ID (MIDI note) or 0 on error
*/
uint8_t loadClip(uint8_t channel, uint8_t note, const char* path, uint16_t nbeats,
                 uint32_t start, uint32_t end, uint8_t quality, float ratio);

/** @brief  Unload a file from a player
    @param  channel MIDI channel
    @param  note MIDI note to trigger clip
    @retval uint8_t Error code
*/
uint8_t unloadClip(uint8_t channel, uint8_t note);

/** @brief  Create a new clip player
    @brief  channel MIDI channel for new player or 255 for next available channel
    @retval uint8_t Channel number or 255 on error
*/
uint8_t addPlayer(uint8_t channel);

/** @brief  Remove a clip player
    @param  channel MIDI channel
    @retval uint8_t Error code
*/
uint8_t removePlayer(uint8_t channel);

/** @brief  Idle Player
    @param  channel MIDI channel
    @param  clip Index of clip to insert
    @retval uint8_t Error code
*/
uint8_t idlePlayerClip(uint8_t channel, uint8_t clip);

//!@todo Remove clip manipulation (insert, remove, swap).

/** @brief  Insert clip
    @param  channel MIDI channel
    @param  clip Index of clip to insert
    @retval uint8_t Error code
    @note   Moves existing clips up. Fails if no room.
*/
uint8_t insertClip(uint8_t channel, uint8_t clip);

/** @brief  Remove clip
    @param  channel MIDI channel
    @param  clip Index of clip to remove
    @retval uint8_t Error code
    @note   Moves existing clips down.
*/
uint8_t removeClip(uint8_t channel, uint8_t clip);

/** @brief  Nudge (move) a clip one position
    @param  channel MIDI channel
    @param  clip Index of clip
    @param  forward True to move the clip forward
    @retval uint8_t Error code
*/
uint8_t nudgeClip(uint8_t channel, uint8_t clip, uint8_t forward);

/** @brief  Set clip gain
    @param  channel MIDI channel
    @param  id Clip index
    @param  gain Gain factor (dB)
    @retval uint8_t Error code
*/
uint8_t setGain(uint8_t channel, uint8_t id, float gain);

/** @brief  Get clip gain
    @param  channel MIDI channel
    @param  id Clip index
    @retval float Gain factor (dB)
*/
float getGain(uint8_t channel, uint8_t id);

//!@todo Remove cropping.

/** @brief  Set clip start offset
    @param  channel MIDI channel
    @param  id Clip index
    @param  start Start offset in frames
    @retval uint8_t Error code
*/
uint8_t setStart(uint8_t channel, uint8_t id, uint32_t start);

/** @brief  Get clip start offset
    @param  channel MIDI channel
    @param  id Clip index
    @retval uint32_t Start offset in frames
*/
uint32_t getStart(uint8_t channel, uint8_t id);

/** @brief  Set clip end offset
    @param  channel MIDI channel
    @param  id Clip index
    @param  end End offset in frames
    @retval uint8_t Error code
*/
uint8_t setEnd(uint8_t channel, uint8_t id, uint32_t end);

/** @brief  Get clip end offset
    @param  channel MIDI channel
    @param  id Clip index
    @retval uint32_t End offset in frames
*/
uint32_t getEnd(uint8_t channel, uint8_t id);

/** @brief  Get the samplerate of a file
    @param  path Full path and filename
    @retval uint32_t Samplerate in frames per second or 0z0ero on error
*/
uint32_t getFileSamplerate(const char* path);

/** @brief  Get the quantity of frames in a file
    @param  path Full path and filename
    @retval uint32_t Duration in frames or 0 on error
*/
uint32_t getFileFrames(const char* path);

/** @brief  Write sample data to file
    @param  dst_path Full path and filename of file to create
    @param  *data[] Array of deinterleaved (per-channel) sample data
    @param samplerate Sample rate
    @param channels Number of channels in data array
    @param frames Number of frames in data array
    @retval int Error code
*/
int saveFile(const char* dst_path, float *data[], int samplerate, int channels, uint32_t frames);
