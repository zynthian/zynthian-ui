/*  Audio file player library for Zynthian
    Copyright (C) 2021-2026 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
    This file deescribes the structures used, including the definition of each player.
*/

#pragma once

#include <jack/jack.h>                  //provides interface to JACK
#include <jack/ringbuffer.h>            //provides jack ring buffer
#include <rubberband/rubberband-c.h>    //provides rubberband time/freq warp
#include <samplerate.h>                 //provides samplerate conversion
#include <sndfile.h>                    //provides sound file manipulation
#include <stdatomic.h>                  // provides atomic variable access

#define MAX_PLAYERS  100
#define MAX_CUES     100
#define MAX_FILENAME 256
#define MAX_CUENAME  256
#define MAX_VARISPEED 32.0
#define MIN_VARISPEED 0.1
#define STRETCH_BUF_SIZE 256

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
    char name[MAX_CUENAME];
    /*
    struct cue_point(uint32_t pos, const char* nm) {
        offset = pos;
        if (nm)
            sprintf(name, nm);
    };
    */
};

struct AUDIO_PLAYER {

    jack_port_t* jack_out_a;
    jack_port_t* jack_out_b;
    
    _Atomic uint8_t file_open; // Used to flag thread to close file or thread to flag file failed to open
    _Atomic uint8_t file_read_status; // File reading status (IDLE|SEEKING|LOADING)

    _Atomic uint8_t play_state;          // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    sf_count_t file_read_pos;                // Current file read position (frames)
    uint8_t loop;                // 1 to loop at end of song
    sf_count_t crop_start;                // Start of audio (crop) in frames from start of file
    sf_count_t crop_start_src;                // Start of audio (crop) in frames from start after SRC
    sf_count_t crop_end;                                       // End of audio (crop) in frames from start of file
    sf_count_t crop_end_src;                                   // End of audio (crop) in frames from start after SRC
    float gain;              // Audio level (volume) 0.00001..10000 (-100db..+100dB)
    int track_a;               // Which track to playback to left output (-1 to mix all stereo pairs)
    int track_b;               // Which track to playback to right output (-1 to mix all stereo pairs)
    unsigned int input_buffer_size;            // Quantity of frames that may be read from file
    unsigned int output_buffer_size;                           // Quantity of frames that may be SRC
    unsigned int buffer_count;                // Factor by which ring buffer is larger than input / SRC buffer
    unsigned int src_quality; // SRC quality [0..4]
    struct cue_point cue_points[MAX_CUES];                     // List of cue point markers

    // Value of data at last notification
    uint8_t last_play_state;
    uint8_t last_loop;
    sf_count_t last_crop_start;
    sf_count_t last_crop_end;
    float last_position;
    float last_gain;
    int last_track_a;
    int last_track_b;
    unsigned int last_input_buffer_size;
    unsigned int last_output_buffer_size;
    unsigned int last_buffer_count;
    unsigned int last_src_quality;

    struct SF_INFO sf_info; // Structure containing currently loaded file info
    pthread_t file_thread;  // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats

    jack_ringbuffer_t* ringbuffer_a;        // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t* ringbuffer_b;        // Used to pass B samples from file reader to jack process
    _Atomic jack_nframes_t play_pos_frames; // Current playback position in frames since start of audio at play samplerate
    size_t frames;                          // Quanity of frames after samplerate conversion
    char filename[MAX_FILENAME];
    _Atomic uint8_t time_ratio_dirty;       // True if time stretch ratio changed
    double time_ratio;                      // Time stretch ratio
    float src_ratio;                        // Samplerate ratio of file
    float pos_notify_delta;                 // Position time difference to trigger notification
    _Atomic float varispeed;                // Ratio to adjust speed and pitch - goes to zero when stopped to allow scrubbing
    float last_varispeed;
    float play_varispeed;                   // Used to restore varispeed when starting playback
    float speed;                            // Base speed factor
    float pitch;                            // Base pitch factor
    int8_t semitones;                       // Base pitch factor semitones
    int8_t cents;                           // Base pitch factor cents

    RubberBandState stretcher;              // Time/pitch warp engine
};
