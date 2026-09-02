#pragma once

#include <jack/jack.h>                      //provides interface to JACK
#include <jack/ringbuffer.h>                //provides jack ring buffer
#include <rubberband/RubberBandStretcher.h> //provides rubberband time/freq warp
#include <samplerate.h>                     //provides samplerate conversion
#include <sndfile.h>                        //provides sound file manipulation
#include <string>

class AUDIO_PLAYER; // Have to declare audio player class to allow typdef to work that uses the class...

typedef void cb_fn_t(AUDIO_PLAYER*, int, float);

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
    char name[256] = {'\0'};
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
    uint32_t index; // A number to identify each player (jack ports)

    uint8_t file_open = FILE_CLOSED;
    ;                                 // 0=file closed, 1=file opening, 2=file open - used to flag thread to close file or thread to flag file failed to open
    uint8_t file_read_status  = IDLE; // File reading status (IDLE|SEEKING|LOADING)

    uint8_t play_state        = STOPPED;          // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    sf_count_t file_read_pos  = 0;                // Current file read position (frames)
    uint8_t loop              = 0;                // 1 to loop at end of song
    sf_count_t crop_start     = 0;                // Start of audio (crop) in frames from start of file
    sf_count_t crop_start_src = -1;               // Start of audio (crop) in frames from start after SRC
    sf_count_t crop_end;                          // End of audio (crop) in frames from start of file
    sf_count_t crop_end_src;                      // End of audio (crop) in frames from start after SRC
    float gain                     = 1.0;         // Audio level (volume) 0.00001..10000 (-100db..+100dB)
    int track_a                    = -1;          // Which track to playback to left output (-1 to mix all stereo pairs)
    int track_b                    = -1;          // Which track to playback to right output (-1 to mix all stereo pairs)
    unsigned int input_buffer_size = 48000;       // Quantity of frames that may be read from file
    unsigned int output_buffer_size;              // Quantity of frames that may be SRC
    unsigned int buffer_count = 5;                // Factor by which ring buffer is larger than input / SRC buffer
    unsigned int src_quality  = SRC_SINC_FASTEST; // SRC quality [0..4]
    std::vector<cue_point> cue_points;            // List of cue point markers

    // Value of data at last notification
    uint8_t last_play_state              = -1;
    uint8_t last_loop                    = -1;
    sf_count_t last_crop_start           = -1;
    sf_count_t last_crop_end             = -1;
    float last_position                  = -1;
    float last_gain                      = 0;
    int last_track_a                     = -1;
    int last_track_b                     = -1;
    unsigned int last_input_buffer_size  = -1;
    unsigned int last_output_buffer_size = -1;
    unsigned int last_buffer_count       = -1;
    unsigned int last_src_quality        = -1;

    struct SF_INFO sf_info; // Structure containing currently loaded file info
    pthread_t file_thread;  // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats

    jack_ringbuffer_t* ringbuffer_a = nullptr; // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t* ringbuffer_b = nullptr; // Used to pass B samples from file reader to jack process
    jack_nframes_t play_pos_frames  = 0;       // Current playback position in frames since start of audio at play samplerate
    size_t frames                   = 0;       // Quanity of frames after samplerate conversion
    std::string filename;
    bool time_ratio_dirty    = false;                 // True if time stretch ratio changed
    double time_ratio        = 1.0;                   // Time stretch ratio
    float src_ratio          = 1.0;                   // Samplerate ratio of file
    cb_fn_t* cb_fn           = nullptr;               // Pointer to function to receive notification of change
    float pos_notify_delta;                           // Position time difference to trigger notification
    float varispeed                            = 1.0; // Ratio to adjust speed and pitch - goes to zero when stopped to allow scrubbing
    float last_varispeed                       = 1.0;
    float play_varispeed                       = 1.0; // Used to restore varispeed when starting playback
    float pitchshift                           = 1.0; // Ratio of MIDI pitch shift (note, bend, etc.)
    float speed                                = 1.0; // Base speed factor
    float pitch                                = 1.0; // Base pitch factor
    int8_t semitones                           = 0; // Base pitch factor semitones
    int8_t cents                               = 0; // Base pitch factor cents

    RubberBand::RubberBandStretcher* stretcher = nullptr; // Time/pitch warp
};
