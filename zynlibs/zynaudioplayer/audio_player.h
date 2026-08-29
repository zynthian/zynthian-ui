#pragma once

#include <jack/jack.h>                      //provides interface to JACK
#include <jack/ringbuffer.h>                //provides jack ring buffer
#include <rubberband/RubberBandStretcher.h> //provides rubberband time/freq warp
#include <samplerate.h>                     //provides samplerate conversion
#include <sndfile.h>                        //provides sound file manipulation
#include <atomic>                           // provides atomic variable access

#define MAX_PLAYERS  100
#define MAX_CUES     100
#define MAX_FILENAME 256
#define MAX_CUENAME  256

// Callback function definition (id, play_state, loop, pos)
typedef void cb_fn_t(uint8_t, uint8_t, uint8_t, float);

enum playState {
    STOPPED  = 0,
    PLAYING  = 1,
    STARTING = 2,
    STOPPING = 3
};

enum seekState {
    IDLE,    // Not seeking
    SEEKING, // Seeking within file
    LOADING, // Seek complete, loading data from file
    LOOPING, // Reached loop end point, need to load from loop start point
    WAITING  // File buffer is full so wait a cycle then try again
};

enum fileState {
    FILE_CLOSED,
    FILE_OPENING,
    FILE_OPEN
};

struct cue_point {
    uint32_t offset;
    char name[MAX_CUENAME] = {'\0'};
    cue_point(uint32_t pos, const char* nm) {
        offset = pos;
        if (nm)
            sprintf(name, nm);
    };
};

class AUDIO_PLAYER {

  public:
    jack_port_t* jack_out_a;
    jack_port_t* jack_out_b;
    
    std::atomic<uint8_t> file_open = FILE_CLOSED; // Used to flag thread to close file or thread to flag file failed to open
    std::atomic<uint8_t> file_read_status  = IDLE; // File reading status (IDLE|SEEKING|LOADING)

    std::atomic<uint8_t> play_state        = STOPPED;          // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    std::atomic<sf_count_t> file_read_pos  = 0;                // Current file read position (frames)
    std::atomic<uint8_t> loop              = 0;                // 1 to loop at end of song
    std::atomic<sf_count_t> crop_start     = 0;                // Start of audio (crop) in frames from start of file
    std::atomic<sf_count_t> crop_start_src = -1;               // Start of audio (crop) in frames from start after SRC
    std::atomic<sf_count_t> crop_end;                          // End of audio (crop) in frames from start of file
    std::atomic<sf_count_t> crop_end_src;                      // End of audio (crop) in frames from start after SRC
    std::atomic<float> gain                     = 1.0;         // Audio level (volume) 0.00001..10000 (-100db..+100dB)
    std::atomic<int> track_a                    = -1;          // Which track to playback to left output (-1 to mix all stereo pairs)
    std::atomic<int> track_b                    = -1;          // Which track to playback to right output (-1 to mix all stereo pairs)
    std::atomic<unsigned int> input_buffer_size = 48000;       // Quantity of frames that may be read from file
    unsigned int output_buffer_size;              // Quantity of frames that may be SRC
    std::atomic<unsigned int> buffer_count = 5;                // Factor by which ring buffer is larger than input / SRC buffer
    std::atomic<unsigned int> src_quality  = SRC_SINC_FASTEST; // SRC quality [0..4]
    std::vector<cue_point> cue_points;            // List of cue point markers

    // Value of data at last notification
    uint8_t last_play_state              = 0;
    uint8_t last_loop                    = 0;
    sf_count_t last_crop_start           = 0;
    sf_count_t last_crop_end             = 0;
    float last_position                  = 0;
    float last_gain                      = 0;
    int last_track_a                     = 0;
    int last_track_b                     = 0;
    unsigned int last_input_buffer_size  = 0;
    unsigned int last_output_buffer_size = 0;
    unsigned int last_buffer_count       = 0;
    unsigned int last_src_quality        = 0;

    struct SF_INFO sf_info; // Structure containing currently loaded file info
    pthread_t file_thread;  // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats

    jack_ringbuffer_t* ringbuffer_a = nullptr; // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t* ringbuffer_b = nullptr; // Used to pass B samples from file reader to jack process
    std::atomic<jack_nframes_t> play_pos_frames  = 0;       // Current playback position in frames since start of audio at play samplerate
    size_t frames                   = 0;       // Quanity of frames after samplerate conversion
    char filename[MAX_FILENAME];
    std::atomic<bool> time_ratio_dirty    = false;                 // True if time stretch ratio changed
    double time_ratio        = 1.0;                   // Time stretch ratio
    float src_ratio          = 1.0;                   // Samplerate ratio of file
    std::atomic<float> pos_notify_delta;                           // Position time difference to trigger notification
    std::atomic<float> varispeed                            = 1.0; // Ratio to adjust speed and pitch - goes to zero when stopped to allow scrubbing
    float last_varispeed                       = 1.0;
    float play_varispeed                       = 1.0; // Used to restore varispeed when starting playback
    float pitchshift                           = 1.0; // Ratio of MIDI pitch shift (note, bend, etc.)
    float speed                                = 1.0; // Base speed factor
    float pitch                                = 1.0; // Base pitch factor

    RubberBand::RubberBandStretcher* stretcher = nullptr; // Time/pitch warp
};
