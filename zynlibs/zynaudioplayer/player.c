/*  Audio file player library for Zynthian
    Copyright (C) 2021-2022 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

/**
    @todo   Add 'slate' markers- general purpose markers that can be jumpped to
*/

#include "player.h"

#include <stdio.h> //provides printf
#include <string.h> //provides strcmp, memset
#include <jack/jack.h> //provides interface to JACK
#include <jack/midiport.h> //provides JACK MIDI interface
#include <jack/ringbuffer.h> //provides jack ring buffer
#include <sndfile.h> //provides sound file manipulation
#include <samplerate.h> //provides samplerate conversion
#include <pthread.h> //provides multithreading
#include <unistd.h> //provides usleep
#include <stdlib.h> //provides exit
#include <arpa/inet.h> // provides inet_pton
#include <fcntl.h> //provides fcntl
#include <math.h> // provides pow

#define MAX_PLAYERS 17 // Maximum quanity of audio players the library can host

enum playState {
    STOPPED		= 0,
    STARTING	= 1,
    PLAYING		= 2,
    STOPPING	= 3
};

enum seekState {
    IDLE        = 0, // Not seeking
    SEEKING     = 1, // Seeking within file
    LOADING     = 2, // Seek complete, loading data from file
    LOOPING     = 3, // Reached loop end point, need to load from loop start point
};

enum fileState {
    FILE_CLOSED  = 0,
    FILE_OPENING = 1,
    FILE_OPEN    = 2
};

enum envState {
    ENV_IDLE = 0,
    ENV_ATTACK,
    ENV_DECAY,
    ENV_SUSTAIN,
    ENV_RELEASE,
    ENV_END
};

struct AUDIO_PLAYER {
    unsigned int handle;

    jack_port_t* jack_out_a;
    jack_port_t* jack_out_b;

    uint8_t file_open; // 0=file closed, 1=file opening, 2=file open - used to flag thread to close file or thread to flag file failed to open
    uint8_t file_read_status; // File reading status (IDLE|SEEKING|LOADING)

    uint8_t play_state; // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    sf_count_t file_read_pos; // Current file read position (frames)
    uint8_t loop; // 1 to loop at end of song
    sf_count_t loop_start; // Start of loop in frames from start of file
    sf_count_t loop_start_src; // Start of loop in frames from start after SRC
    sf_count_t loop_end; // End of loop in frames from start of file
    sf_count_t loop_end_src; // End of loop in frames from start after SRC
    sf_count_t crop_start; // Start of audio (crop) in frames from start of file
    sf_count_t crop_start_src; // Start of audio (crop) in frames from start after SRC
    sf_count_t crop_end; // End of audio (crop) in frames from start of file
    sf_count_t crop_end_src; // End of audio (crop) in frames from start after SRC
    float gain; // Audio level (volume) 0..1
    int track_a; // Which track to playback to left output (-1 to mix all stereo pairs)
    int track_b; // Which track to playback to right output (-1 to mix all stereo pairs)
    unsigned int input_buffer_size; // Quantity of frames that may be read from file
    unsigned int output_buffer_size; // Quantity of frames that may be SRC
    unsigned int buffer_count; // Factor by which ring buffer is larger than input / SRC buffer
    unsigned int src_quality; // SRC quality [0..4]

    // Value of data at last notification
    uint8_t last_play_state;
    uint8_t last_loop;
    sf_count_t last_loop_start;
    sf_count_t last_loop_end;
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

    // ADSR envelope
    int env_state;
    uint8_t env_gate;
    float env_level;
    float env_attack_rate;
    float last_env_attack_rate;
    float env_attack_base;
    float env_attack_coef;
    float env_decay_rate;
    float last_env_decay_rate;
    float env_decay_base;
    float env_decay_coef;
    float env_sustain_level;
    float last_env_sustain_level;
    float env_release_rate;
    float last_env_release_rate;
    float env_release_base;
    float env_release_coef;
    float env_target_ratio_a;
    float last_env_target_ratio_a;
    float env_target_ratio_dr;
    float last_env_target_ratio_dr;

    struct SF_INFO  sf_info; // Structure containing currently loaded file info
    pthread_t file_thread; // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats
    jack_ringbuffer_t * ringbuffer_a; // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t * ringbuffer_b; // Used to pass B samples from file reader to jack process
    jack_nframes_t play_pos_frames; // Current playback position in frames since start of audio at play samplerate
    size_t frames; // Quanity of frames after samplerate conversion
    char filename[128];
    uint8_t midi_chan; // MIDI channel to listen
    uint8_t last_note_played; // MIDI note number of last note that triggered playback
    uint8_t held_notes[128]; // MIDI notes numbers that have been pressed but not released
    uint8_t held_note; // 1 if any MIDI notes held
    uint8_t sustain; // True when sustain pedal held
    uint8_t last_sustain;
    float src_ratio; // Samplerate ratio of file
    float pitch_shift; // Factor of pitch shift
    float pitch_bend; // Amount of MIDI pitch bend applied +/-range
    uint8_t pitch_bend_range; // Pitchbend range in semitones
    void * cb_object; // Pointer to the object hosting the callback function
    cb_fn_t * cb_fn; // Pointer to function to receive notification of chage
    float pos_notify_delta; // Position time difference to trigger notification
};

// **** Global variables ****
struct AUDIO_PLAYER * g_players[MAX_PLAYERS];
jack_client_t* g_jack_client;
jack_port_t* g_jack_midi_in;
jack_nframes_t g_samplerate = 44100; // Playback samplerate set by jackd
uint8_t g_debug = 0;
uint8_t g_last_debug = 0;
char g_supported_codecs[1024];
uint8_t g_mutex = 0;

// Declare local functions
void set_env_gate(struct AUDIO_PLAYER * pPlayer, uint8_t gate);
void reset_env(struct AUDIO_PLAYER * pPlayer);
float process_env(struct AUDIO_PLAYER * pPlayer);

#define DPRINTF(fmt, args...) if(g_debug) fprintf(stderr, fmt, ## args)
    
// **** Internal (non-public) functions ****

void getMutex() {
    while(g_mutex)
        usleep(10);
    g_mutex = 1;
}

void releaseMutex() {
    g_mutex = 0;
}

static inline struct AUDIO_PLAYER * get_player(int player_handle) {
    if(player_handle > MAX_PLAYERS || player_handle < 0)
        return NULL;
    return g_players[player_handle];
}

int is_codec_supported(const char* codec) {
    SF_FORMAT_INFO  format_info ;
    int k, count ;
    sf_command (NULL, SFC_GET_SIMPLE_FORMAT_COUNT, &count, sizeof (int));
    for (k = 0 ; k < count ; k++) {
        format_info.format = k;
        sf_command (NULL, SFC_GET_SIMPLE_FORMAT, &format_info, sizeof (format_info));
        if(strcmp(codec, format_info.extension) == 0)
            return 1;
    }
    return 0;
}

char* get_supported_codecs() {
    g_supported_codecs[0] = '\0';
    SF_FORMAT_INFO  format_info ;
    int k, count ;
    sf_command (NULL, SFC_GET_SIMPLE_FORMAT_COUNT, &count, sizeof (int));
    for (k = 0 ; k < count ; k++) {
        format_info.format = k;
        sf_command (NULL, SFC_GET_SIMPLE_FORMAT, &format_info, sizeof (format_info));
        if(strstr(g_supported_codecs, format_info.extension))
            continue;
        if(g_supported_codecs[0])
            strcat(g_supported_codecs, ",");
        strcat(g_supported_codecs, format_info.extension);
    }
    return g_supported_codecs;
}

void send_notifications(struct AUDIO_PLAYER * pPlayer, int param) {
    // Send dynamic notifications within this thread, not jack process
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if((param == NOTIFY_ALL || param == NOTIFY_TRANSPORT) && pPlayer->last_play_state != pPlayer->play_state) {
        pPlayer->last_play_state = pPlayer->play_state;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_TRANSPORT, (float)(pPlayer->play_state));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_POSITION) && fabs(get_position(pPlayer->handle) - pPlayer->last_position) >= pPlayer->pos_notify_delta) {
        pPlayer->last_position = get_position(pPlayer->handle);
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_POSITION, pPlayer->last_position);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_GAIN) && fabs(pPlayer->gain - pPlayer->last_gain) >= 0.01) {
        pPlayer->last_gain = pPlayer->gain;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_GAIN, (float)(pPlayer->gain));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_LOOP) && pPlayer->loop != pPlayer->last_loop) {
        pPlayer->last_loop = pPlayer->loop;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_LOOP, (float)(pPlayer->loop));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_LOOP_START) && pPlayer->loop_start != pPlayer->last_loop_start) {
        pPlayer->last_loop_start = pPlayer->loop_start;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_LOOP_START, get_loop_start_time(pPlayer->handle));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_LOOP_END) && pPlayer->loop_end != pPlayer->last_loop_end) {
        pPlayer->last_loop_end = pPlayer->loop_end;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_LOOP_END, get_loop_end_time(pPlayer->handle));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_CROP_START) && pPlayer->crop_start != pPlayer->last_crop_start) {
        pPlayer->last_crop_start = pPlayer->crop_start;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_CROP_START, get_crop_start_time(pPlayer->handle));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_CROP_END) && pPlayer->crop_end != pPlayer->last_crop_end) {
        pPlayer->last_crop_end = pPlayer->crop_end;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_CROP_END, get_crop_end_time(pPlayer->handle));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_SUSTAIN) && pPlayer->sustain != pPlayer->last_sustain) {
        pPlayer->last_sustain = pPlayer->sustain;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_SUSTAIN, pPlayer->sustain);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_ENV_ATTACK) && pPlayer->env_attack_rate != pPlayer->last_env_attack_rate) {
        pPlayer->last_env_attack_rate = pPlayer->env_attack_rate;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_ENV_ATTACK, pPlayer->env_attack_rate);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_ENV_DECAY) && pPlayer->env_decay_rate != pPlayer->last_env_decay_rate) {
        pPlayer->last_env_decay_rate = pPlayer->env_decay_rate;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_ENV_DECAY, pPlayer->env_decay_rate);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_ENV_SUSTAIN) && pPlayer->env_sustain_level != pPlayer->last_env_sustain_level) {
        pPlayer->last_env_sustain_level = pPlayer->env_sustain_level;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_ENV_SUSTAIN, pPlayer->env_sustain_level);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_ENV_RELEASE) && pPlayer->env_release_rate != pPlayer->last_env_release_rate) {
        pPlayer->last_env_release_rate = pPlayer->env_release_rate;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_ENV_RELEASE, pPlayer->env_release_rate);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_ENV_ATTACK_CURVE) && pPlayer->env_target_ratio_a != pPlayer->last_env_target_ratio_a) {
        pPlayer->last_env_target_ratio_a = pPlayer->env_target_ratio_a;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_ENV_ATTACK_CURVE, pPlayer->env_target_ratio_a);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_ENV_DECAY_CURVE) && pPlayer->env_target_ratio_dr != pPlayer->last_env_target_ratio_dr) {
        pPlayer->last_env_target_ratio_dr = pPlayer->env_target_ratio_dr;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_ENV_DECAY_CURVE, pPlayer->env_target_ratio_dr);
    }
    if((param == NOTIFY_ALL || param == NOTIFY_TRACK_A) && pPlayer->track_a != pPlayer->last_track_a) {
        pPlayer->last_track_a = pPlayer->track_a;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_TRACK_A, (float)(pPlayer->track_a));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_TRACK_B) && pPlayer->track_b != pPlayer->last_track_b) {
        pPlayer->last_track_b = pPlayer->track_b;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_TRACK_B, (float)(pPlayer->track_b));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_QUALITY) && pPlayer->src_quality != pPlayer->last_src_quality) {
        pPlayer->last_src_quality = pPlayer->src_quality;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_QUALITY, (float)(pPlayer->src_quality));
    }
    if((param == NOTIFY_ALL || param == NOTIFY_DEBUG) && g_debug != g_last_debug) {
        g_last_debug = g_debug;
        if(pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer->cb_object, pPlayer->handle, NOTIFY_DEBUG, (float)(g_debug));
    }
}

void* file_thread_fn(void * param) {
    struct AUDIO_PLAYER * pPlayer = (struct AUDIO_PLAYER *) (param);
    pPlayer->sf_info.format = 0; // This triggers sf_open to populate info structure
    pPlayer->ringbuffer_a = NULL;
    pPlayer->ringbuffer_b = NULL;
    SRC_STATE* pSrcState = NULL;
    SRC_DATA srcData;
    size_t nMaxFrames; // Maximum quantity of frames that may be read from file
    size_t nUnusedFrames = 0; // Quantity of frames in input buffer not used by SRC

    SNDFILE* pFile = sf_open(pPlayer->filename, SFM_READ, &pPlayer->sf_info);
    if(!pFile || pPlayer->sf_info.channels < 1) {
        pPlayer->file_open = FILE_CLOSED;
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename, sf_strerror(pFile));
    }
    if(pPlayer->sf_info.channels < 0) {
        pPlayer->file_open = FILE_CLOSED;
        fprintf(stderr, "libaudioplayer error: file %s has no tracks\n", pPlayer->filename);
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
    }

    if(pPlayer->file_open) {
        pPlayer->cb_fn = NULL;
        pPlayer->cb_object = NULL;
        pPlayer->last_play_state = -1;
        pPlayer->last_position = -1;
        pPlayer->play_pos_frames = 0;
        pPlayer->loop_start = 0;
        pPlayer->last_loop_start = -1;
        pPlayer->loop_end  = pPlayer->sf_info.frames;
        pPlayer->last_loop_end = -1;
        pPlayer->crop_start = 0;
        pPlayer->last_crop_start = -1;
        pPlayer->crop_end  = pPlayer->sf_info.frames;
        pPlayer->last_crop_end = -1;
        pPlayer->file_read_pos = 0;
        pPlayer->file_read_status = SEEKING;
        pPlayer->src_ratio = (float)g_samplerate / pPlayer->sf_info.samplerate;
        if(pPlayer->src_ratio < 0.1)
            pPlayer->src_ratio = 1;
        srcData.src_ratio = pPlayer->src_ratio;
        pPlayer->pos_notify_delta = pPlayer->sf_info.frames / g_samplerate / 400;
        pPlayer->output_buffer_size = pPlayer->src_ratio * pPlayer->input_buffer_size;
        pPlayer->ringbuffer_a = jack_ringbuffer_create(pPlayer->output_buffer_size * pPlayer->buffer_count * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_a);
        pPlayer->ringbuffer_b = jack_ringbuffer_create(pPlayer->output_buffer_size * pPlayer->buffer_count * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_b);

        pPlayer->file_open = FILE_OPEN;

        // Initialise samplerate converter
        float pBufferIn[pPlayer->input_buffer_size * pPlayer->sf_info.channels]; // Buffer used to read sample data from file
        float pBufferOut[pPlayer->output_buffer_size * pPlayer->sf_info.channels]; // Buffer used to write converted sample data to
        srcData.data_in = pBufferIn;
        srcData.data_out = pBufferOut;
        pPlayer->pitch_shift = 1.0;
        pPlayer->pitch_bend = 0.0;
        pPlayer->pitch_bend_range = 2;
        srcData.output_frames = pPlayer->output_buffer_size;
        pPlayer->frames = pPlayer->sf_info.frames * pPlayer->src_ratio;
        pPlayer->loop_end_src = pPlayer->loop_end * pPlayer->src_ratio;
        pPlayer->loop_start_src = pPlayer->loop_start * pPlayer->src_ratio;
        pPlayer->crop_end_src = pPlayer->crop_end * pPlayer->src_ratio;
        pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
        int nError;
        pSrcState = src_new(pPlayer->src_quality, pPlayer->sf_info.channels, &nError);
        if(!pSrcState) {
            fprintf(stderr, "Failed to create a samplerate converter: %d\n", nError);
            pPlayer->file_open = FILE_CLOSED;
        }
 
        DPRINTF("Opened file '%s' with samplerate %u, duration: %f\n", pPlayer->filename, pPlayer->sf_info.samplerate, get_duration(pPlayer->handle));

        while(pPlayer->file_open == FILE_OPEN) {
            if(pPlayer->file_read_status == SEEKING) {
                // Main thread has signalled seek within file
                jack_ringbuffer_reset(pPlayer->ringbuffer_a);
                jack_ringbuffer_reset(pPlayer->ringbuffer_b);
                size_t nNewPos = pPlayer->play_pos_frames / pPlayer->src_ratio;
                sf_count_t pos = sf_seek(pFile, nNewPos, SEEK_SET);
                getMutex();
                if(pos >= 0)
                    pPlayer->file_read_pos = pos;
                //DPRINTF("Seeking to %u frames (%fs) src ratio=%f\n", nNewPos, get_position(pPlayer->handle), srcData.src_ratio);
                pPlayer->file_read_status = LOADING;
                releaseMutex();
                src_reset(pSrcState);
                nUnusedFrames = 0;
                srcData.end_of_input = 0;
            } else if(pPlayer->file_read_status == LOOPING) {
                // Reached loop end point and need to read from loop start point
                // Only load one loop to avoid playback of loops after looping disabled
                sf_count_t pos = sf_seek(pFile, pPlayer->loop_start, SEEK_SET);
                getMutex();
                if(pos >= 0)
                    pPlayer->file_read_pos = pos;
                pPlayer->file_read_status = LOADING;
                releaseMutex();
                src_reset(pSrcState);
                srcData.end_of_input = 0;
                nUnusedFrames = 0;
            }

            if(pPlayer->file_read_status == LOADING)
            {
                int nFramesRead;
                // Load block of data from file to SRC or output buffer

                nMaxFrames = pPlayer->input_buffer_size - nUnusedFrames;

                if(jack_ringbuffer_write_space(pPlayer->ringbuffer_a) >= nMaxFrames * sizeof(float) * pPlayer->src_ratio
                    && jack_ringbuffer_write_space(pPlayer->ringbuffer_b) >= nMaxFrames * sizeof(float)  * pPlayer->src_ratio) {

                    if(pPlayer->loop) {
                        // Limit read to loop range
                        if(pPlayer->file_read_pos > pPlayer->loop_end)
                            nMaxFrames = 0;
                        else if(pPlayer->file_read_pos + nMaxFrames > pPlayer->loop_end)
                            nMaxFrames = pPlayer->loop_end - pPlayer->file_read_pos;
                    } else if(pPlayer->file_read_pos > pPlayer->crop_end) {
                        nMaxFrames = 0;
                    } else if(pPlayer->file_read_pos + nMaxFrames > pPlayer->crop_end) {
                        // Limit read to crop range
                        nMaxFrames = pPlayer->crop_end - pPlayer->file_read_pos;
                    }

                    if(srcData.src_ratio == 1.0) {
                        // No SRC required so populate SRC output buffer directly
                        nFramesRead = sf_readf_float(pFile, pBufferOut, nMaxFrames);
                    } else {
                        // Populate SRC input buffer before SRC process
                        nFramesRead = sf_readf_float(pFile, pBufferIn + nUnusedFrames * pPlayer->sf_info.channels, nMaxFrames);
                    }
                    getMutex();
                    pPlayer->file_read_pos += nFramesRead;

                    if(nFramesRead) {
                        // Got some audio data to process...
                        // Remain in LOADING state to trigger next file read when FIFO is sufficient space
                        releaseMutex();
                        DPRINTF("libzynaudioplayer read %u frames into input buffer\n", nFramesRead);

                        if(srcData.src_ratio != 1.0) {
                            // We need to perform SRC on this block of code
                            srcData.input_frames = nFramesRead;
                            int rc = src_process(pSrcState, &srcData);
                            nUnusedFrames = nFramesRead - srcData.input_frames_used;
                            nFramesRead = srcData.output_frames_gen;
                            if(rc) {
                                DPRINTF("SRC failed with error %d, %u frames generated\n", nFramesRead, srcData.output_frames_gen);
                            } else {
                                DPRINTF("SRC suceeded - %u frames generated, %u frames used, %u frames unused\n", srcData.output_frames_gen, srcData.input_frames_used, nUnusedFrames);
                            }
                            // Shift unused samples to start of buffer
                            memcpy(pBufferIn, pBufferIn + srcData.input_frames_used * sizeof(float) * pPlayer->sf_info.channels, nUnusedFrames * sizeof(float) * pPlayer->sf_info.channels);
                        } else {
                            //DPRINTF("No SRC, read %u frames\n", nFramesRead);
                        }
                        // Demux samples and populate playback ring buffers
                        for(size_t frame = 0; frame < nFramesRead; ++frame) {
                            float fA = 0.0, fB = 0.0;
                            size_t sample = frame * pPlayer->sf_info.channels;
                            if(pPlayer->sf_info.channels > 1) {
                                if(pPlayer->track_a < 0) {
                                    // Send sum of odd channels to A
                                    for(int track = 0; track < pPlayer->sf_info.channels; track += 2)
                                        fA += pBufferOut[sample + track] / (pPlayer->sf_info.channels / 2);
                                } else {
                                    // Send pPlayer->track to A
                                    fA = pBufferOut[sample + pPlayer->track_a];
                                }
                                if(pPlayer->track_b < 0) {
                                    // Send sum of odd channels to B
                                    for(int track = 0; track + 1 < pPlayer->sf_info.channels; track += 2)
                                        fB += pBufferOut[sample + track + 1] / (pPlayer->sf_info.channels / 2);
                                } else {
                                    // Send pPlayer->track to B
                                    fB = pBufferOut[sample + pPlayer->track_b];
                                }
                            } else {
                                // Mono source so send to both outputs
                                fA = pBufferOut[sample] / 2;
                                fB = pBufferOut[sample] / 2;
                            }
                            int nWrote = jack_ringbuffer_write(pPlayer->ringbuffer_b, (const char*)(&fB), sizeof(float));
                            if(sizeof(float) < jack_ringbuffer_write(pPlayer->ringbuffer_a, (const char*)(&fA), nWrote)) {
                                // Shouldn't underun due to previous wait for space but just in case...
                                fprintf(stderr, "libZynAudioPlayer Underrun during writing to ringbuffer - this should never happen!!!\n");
                                break;
                            }
                        }
                    } else if(pPlayer->loop) {
                        // Short read - looping so fill from loop start point in file
                        pPlayer->file_read_status = LOOPING;
                        srcData.end_of_input = 1;
                        releaseMutex();
                        DPRINTF("libzynaudioplayer read to loop point in input file - setting loading status to looping\n");
                    } else {
                        // End of file
                        pPlayer->file_read_status = IDLE;
                        srcData.end_of_input = 1;
                        releaseMutex();
                        DPRINTF("libzynaudioplayer read to end of input file - setting loading status to IDLE\n");
                    }
                }
            }
            usleep(10000);
            send_notifications(pPlayer, NOTIFY_ALL);
        }
    }

    getMutex();
    pPlayer->play_state = STOPPED; // Already stopped when clearing file_open but let's be sure!
    releaseMutex();
    if(pFile) {
        int nError = sf_close(pFile);
        if(nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        else
            pPlayer->filename[0] = '\0';
    }
    pPlayer->play_pos_frames = 0;
    pPlayer->cb_fn = NULL;
    pPlayer->cb_object = NULL;
    if(pPlayer->ringbuffer_a)
        jack_ringbuffer_free(pPlayer->ringbuffer_a);
    if(pPlayer->ringbuffer_b)
        jack_ringbuffer_free(pPlayer->ringbuffer_b);
    if(pSrcState)
        pSrcState = src_delete(pSrcState);

    DPRINTF("File reader thread ended\n");
    pthread_exit(NULL);
}

/**** player instance functions take 'handle' param to identify player instance****/

uint8_t load(int player_handle, const char* filename, void* cb_object, cb_fn_t cb_fn) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0;
    unload(player_handle);
    pPlayer->cb_fn;
    pPlayer->cb_object = NULL;
    pPlayer->track_a = 0;
    pPlayer->track_b = 0;
    strcpy(pPlayer->filename, filename);
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

    pPlayer->file_open = FILE_OPENING;
    if(pthread_create(&pPlayer->file_thread, &attr, file_thread_fn, pPlayer)) {
        fprintf(stderr, "libzynaudioplayer error: failed to create file reading thread\n");
        unload(player_handle);
        return 0;
    }
    while(pPlayer->file_open == FILE_OPENING) {
        usleep(10000); //!@todo Optimise wait for file open
    }

    if(pPlayer->file_open) {
        pPlayer->cb_object = cb_object;
        pPlayer->cb_fn = cb_fn;
    }
    return (pPlayer->file_open == FILE_OPEN);
}

void unload(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open == FILE_CLOSED)
        return;
    stop_playback(player_handle);
    pPlayer->file_open = FILE_CLOSED;
    pPlayer->cb_fn = NULL;
    void* status;
    pthread_join(pPlayer->file_thread, &status);
    pPlayer->filename[0] = '\0';
}

uint8_t save(int player_handle, const char* filename) {
    //!@todo Implement save
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return 0;
}

const char* get_filename(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return "";
    return pPlayer->filename;
}

float get_duration(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->file_open == FILE_OPEN && pPlayer->sf_info.samplerate)
        return (float)pPlayer->sf_info.frames / pPlayer->sf_info.samplerate;
    return 0.0f;
}

void set_position(int player_handle, float time) {

    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    sf_count_t frames = time * g_samplerate;
    if(frames > pPlayer->crop_end_src)
        frames = pPlayer->crop_end_src;
    else if(frames < pPlayer->crop_start_src)
        frames = pPlayer->crop_start_src;
    getMutex();
    pPlayer->play_pos_frames = frames;
    pPlayer->file_read_status = SEEKING;
    releaseMutex();
    DPRINTF("New position requested, setting loading status to SEEKING\n");
    send_notifications(pPlayer, NOTIFY_POSITION);
}

float get_position(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->file_open == FILE_OPEN)
        return (float)(pPlayer->play_pos_frames) / g_samplerate;
    return 0.0;
}

void enable_loop(int player_handle, uint8_t bLoop) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    getMutex();
    pPlayer->loop = bLoop;
    if(bLoop && pPlayer->play_pos_frames > pPlayer->loop_end_src)
        pPlayer->play_pos_frames = pPlayer->loop_start_src;
    pPlayer->file_read_status = SEEKING;
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_LOOP);
}

void set_loop_start_time(int player_handle, float time) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if(frames >= pPlayer->loop_end)
        frames = pPlayer->loop_end - 1;
    if(frames < pPlayer->crop_start)
        frames = pPlayer->crop_start;
    getMutex();
    pPlayer->loop_start = frames;
    pPlayer->loop_start_src = pPlayer->loop_start * pPlayer->src_ratio;
    if(pPlayer->loop) {
        if(pPlayer->play_pos_frames < frames) {
            releaseMutex();
            set_position(player_handle, time);
            return;
        }
        else
            pPlayer->file_read_status = SEEKING;
    }
    releaseMutex();
}

float get_loop_start_time(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->loop_start) / pPlayer->sf_info.samplerate;
}

void set_loop_end_time(int player_handle, float time) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if(frames <= pPlayer->loop_start)
        frames = pPlayer->loop_start + 1;
    if(frames > pPlayer->crop_end)
        frames = pPlayer->crop_end;
    getMutex();
    pPlayer->loop_end = frames;
    pPlayer->loop_end_src = pPlayer->loop_end * pPlayer->src_ratio;
    if(pPlayer->loop) {
        if(pPlayer->play_pos_frames > pPlayer->loop_end_src)
            pPlayer->play_pos_frames = pPlayer->loop_end_src;
        pPlayer->file_read_status = SEEKING;
    }
    releaseMutex();
}

float get_loop_end_time(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->loop_end) / pPlayer->sf_info.samplerate;
}

uint8_t is_loop(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return(pPlayer->loop);
}

void set_crop_start_time(int player_handle, float time) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    if(time < 0.0)
        time = 0.0;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if(frames >= pPlayer->crop_end)
        frames = pPlayer->crop_end - 1;
    if(frames > pPlayer->loop_start)
        set_loop_start_time(player_handle, time);
    getMutex();
    pPlayer->crop_start = frames;
    pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
    if(pPlayer->play_pos_frames < frames) {
        releaseMutex();
        set_position(player_handle, time);
        return;
    }
    releaseMutex();
}

float get_crop_start_time(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->crop_start) / pPlayer->sf_info.samplerate;
}

void set_crop_end_time(int player_handle, float time) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if(frames < pPlayer->crop_start)
        frames = pPlayer->crop_start + 1;
    if(frames < pPlayer->loop_end)
        set_loop_end_time(player_handle, time);
    getMutex();
    pPlayer->crop_end = frames;
    pPlayer->crop_end_src = frames * pPlayer->src_ratio;
    if(pPlayer->crop_end_src >= pPlayer->frames) {
        pPlayer->crop_end_src = pPlayer->frames - 1;
        pPlayer->crop_end = pPlayer->frames / pPlayer->src_ratio;
    }
    if(pPlayer->play_pos_frames > pPlayer->crop_end_src)
            pPlayer->play_pos_frames = pPlayer->crop_end_src;
        pPlayer->file_read_status = SEEKING;
    releaseMutex();
}

float get_crop_end_time(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->crop_end) / pPlayer->sf_info.samplerate;
}

void start_playback(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && g_jack_client && pPlayer->file_open == FILE_OPEN && pPlayer->play_state != PLAYING)
        pPlayer->play_state = STARTING;
    send_notifications(pPlayer, NOTIFY_TRANSPORT);
}

void stop_playback(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->play_state != STOPPED)
        pPlayer->play_state = STOPPING;
    send_notifications(pPlayer, NOTIFY_TRANSPORT);
}

uint8_t get_playback_state(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return STOPPED;
    return pPlayer->play_state;
}

int get_samplerate(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return g_samplerate;
    return pPlayer->sf_info.samplerate;
}

int get_channels(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.channels;
}

int get_frames(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.frames;
}

int get_format(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.format;
}


float calc_env_coef(float rate, float ratio) {
    return (rate <= 0) ? 0.0 : exp(-log((1.0 + ratio) / ratio) / rate);
}

void set_env_attack(int player_handle, float rate) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    getMutex();
    pPlayer->env_attack_rate = rate;
    pPlayer->env_attack_coef = calc_env_coef(rate * g_samplerate, pPlayer->env_target_ratio_a);
    pPlayer->env_attack_base = (1.0 + pPlayer->env_target_ratio_a) * (1.0 - pPlayer->env_attack_coef);
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_ENV_ATTACK);
}

float get_env_attack(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0.0;
    return pPlayer->env_attack_rate;
}

void set_env_decay(int player_handle, float rate) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    getMutex();
    pPlayer->env_decay_rate = rate;
    pPlayer->env_decay_coef = calc_env_coef(rate * g_samplerate, pPlayer->env_target_ratio_dr);
    pPlayer->env_decay_base = (pPlayer->env_sustain_level - pPlayer->env_target_ratio_dr) * (1.0 - pPlayer->env_decay_coef);
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_ENV_DECAY);
}

float get_env_decay(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0.0;
    return pPlayer->env_decay_rate;
}

void set_env_release(int player_handle, float rate) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    getMutex();
    pPlayer->env_release_rate = rate;
    pPlayer->env_release_coef = calc_env_coef(rate * g_samplerate, pPlayer->env_target_ratio_dr);
    pPlayer->env_release_base = -pPlayer->env_target_ratio_dr * (1.0 - pPlayer->env_release_coef);
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_ENV_RELEASE);
}

float get_env_release(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0.0;
    return pPlayer->env_release_rate;
}

void set_env_sustain(int player_handle, float level) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    getMutex();
    pPlayer->env_sustain_level = level;
    pPlayer->env_decay_base = (pPlayer->env_sustain_level - pPlayer->env_target_ratio_dr) * (1.0 - pPlayer->env_decay_coef);
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_ENV_SUSTAIN);
}

float get_env_sustain(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0.0;
    return pPlayer->env_sustain_level;
}

void set_env_target_ratio_a(int player_handle, float ratio) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    if (ratio < 0.000000001)
        ratio = 0.000000001;  // -180 dB
    getMutex();
    pPlayer->env_target_ratio_a = ratio;
    pPlayer->env_attack_coef = calc_env_coef(pPlayer->env_attack_rate * g_samplerate, pPlayer->env_target_ratio_a);
    pPlayer->env_attack_base = (1.0 + pPlayer->env_target_ratio_a) * (1.0 - pPlayer->env_attack_coef);
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_ENV_ATTACK_CURVE);
}

float get_env_target_ratio_a(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0.0;
    return pPlayer->env_target_ratio_a;
}

void set_env_target_ratio_dr(int player_handle, float ratio) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    if (ratio < 0.000000001)
        ratio = 0.000000001;  // -180 dB
    getMutex();
    pPlayer->env_target_ratio_dr = ratio;
    pPlayer->env_decay_coef = calc_env_coef(pPlayer->env_decay_rate * g_samplerate, pPlayer->env_target_ratio_dr);
    pPlayer->env_release_coef = calc_env_coef(pPlayer->env_release_rate * g_samplerate, pPlayer->env_target_ratio_dr);
    pPlayer->env_decay_base = (pPlayer->env_sustain_level - pPlayer->env_target_ratio_dr) * (1.0 - pPlayer->env_decay_coef);
    pPlayer->env_release_base = -pPlayer->env_target_ratio_dr * (1.0 - pPlayer->env_release_coef);
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_ENV_DECAY_CURVE);
}

float get_env_target_ratio_dr(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0.0;
    return pPlayer->env_target_ratio_dr;
}

/*** Private functions not exposed as external C functions (not declared in header) ***/

// Process ADSR envelope
inline float process_env(struct AUDIO_PLAYER * pPlayer) {
    switch (pPlayer->env_state) {
        case ENV_IDLE:
            break;
        case ENV_ATTACK:
            pPlayer->env_level = pPlayer->env_attack_base + pPlayer->env_level * pPlayer->env_attack_coef;
            if (pPlayer->env_level >= 1.0) {
                pPlayer->env_level = 1.0;
                pPlayer->env_state = ENV_DECAY;
                //fprintf(stderr, "Envelope: DECAY\n");
            }
            break;
        case ENV_DECAY:
            pPlayer->env_level = pPlayer->env_decay_base + pPlayer->env_level * pPlayer->env_decay_coef;
            if (pPlayer->env_level <= pPlayer->env_sustain_level) {
                pPlayer->env_level = pPlayer->env_sustain_level;
                pPlayer->env_state = ENV_SUSTAIN;
                //fprintf(stderr, "Envelope: SUSTAIN\n");
            }
            break;
        case ENV_SUSTAIN:
            break;
        case ENV_RELEASE:
            pPlayer->env_level = pPlayer->env_release_base + pPlayer->env_level * pPlayer->env_release_coef;
            if (pPlayer->env_level < 0.0000000001) {
                // Below -200dBfs so let's end this thing
                pPlayer->env_level = 0.0;
                pPlayer->env_state = ENV_END;
                // fprintf(stderr, "Envelope: END\n");
            }
    }
    return pPlayer->env_level;
}

inline void set_env_gate(struct AUDIO_PLAYER * pPlayer, uint8_t gate) {
    if (gate) {
        pPlayer->env_state = ENV_ATTACK;
        // fprintf(stderr, "Envelope: ATTACK\n");
    } else if (pPlayer->env_state != ENV_IDLE) {
        pPlayer->env_state = ENV_RELEASE;
        // fprintf(stderr, "Envelope: RELEASE\n");
    }
    pPlayer->env_gate = gate;
}

inline void reset_env(struct AUDIO_PLAYER * pPlayer) {
    pPlayer->env_state = ENV_IDLE;
    pPlayer->env_level = 0.0;
}

// Handle JACK process callback
int on_jack_process(jack_nframes_t nFrames, void * arg) {
    getMutex();
    for(int i = 0; i < MAX_PLAYERS; ++i) {
        struct AUDIO_PLAYER * pPlayer = (struct AUDIO_PLAYER *) (g_players[i]);
        if(!pPlayer || pPlayer->file_open != FILE_OPEN)
            continue;

        size_t r_count = 0; // Quantity of frames removed from queue, i.e. how far advanced through the audio
        size_t a_count = 0; // Quantity of frames added to jack buffer
        float f_count = 0.0; // Amount moved through buffer when pitch shifting
        jack_default_audio_sample_t *pOutA = (jack_default_audio_sample_t*)jack_port_get_buffer(pPlayer->jack_out_a, nFrames);
        jack_default_audio_sample_t *pOutB = (jack_default_audio_sample_t*)jack_port_get_buffer(pPlayer->jack_out_b, nFrames);

        if(pPlayer->play_state == STARTING && pPlayer->file_read_status != SEEKING)
            pPlayer->play_state = PLAYING;

        if(pPlayer->play_state == PLAYING || pPlayer->play_state == STOPPING || pPlayer->play_state == STOPPING) {
            if(pPlayer->pitch_shift != 1.0) {
                while(a_count < nFrames) {
                    if(
                        (jack_ringbuffer_peek(pPlayer->ringbuffer_a, (char*)(&pOutA[a_count]), sizeof(jack_default_audio_sample_t)) < sizeof(jack_default_audio_sample_t)) ||
                        (jack_ringbuffer_peek(pPlayer->ringbuffer_b, (char*)(&pOutB[a_count]), sizeof(jack_default_audio_sample_t)) < sizeof(jack_default_audio_sample_t))
                    )
                        break;
                    while(f_count < a_count) {
                        f_count += pPlayer->pitch_shift;
                        jack_ringbuffer_read_advance(pPlayer->ringbuffer_a, sizeof(jack_default_audio_sample_t));
                        jack_ringbuffer_read_advance(pPlayer->ringbuffer_b, sizeof(jack_default_audio_sample_t));
                        ++r_count;
                        if(jack_ringbuffer_read_space(pPlayer->ringbuffer_a) == 0 || jack_ringbuffer_read_space(pPlayer->ringbuffer_a) == 0)
                            break; // Run out of data to read 
                            //!@todo Should break out of outer loop
                    }
                    ++a_count;
                }
            } else {
                r_count = jack_ringbuffer_read(pPlayer->ringbuffer_a, (char*)pOutA, nFrames * sizeof(jack_default_audio_sample_t));
                jack_ringbuffer_read(pPlayer->ringbuffer_b, (char*)pOutB, r_count);
                r_count /= sizeof(jack_default_audio_sample_t);
                a_count = r_count;
            }

            if(a_count > nFrames)
                a_count = nFrames;
            if(pPlayer->held_note != pPlayer->env_gate)
                set_env_gate(pPlayer, pPlayer->held_note);
            for(size_t offset = 0; offset < a_count; ++offset) {
                // Set volume / gain / level / envelope
                if(pPlayer->env_state != ENV_IDLE) {
                    process_env(pPlayer);
                    pOutA[offset] *= pPlayer->gain * pPlayer->env_level;
                    pOutB[offset] *= pPlayer->gain * pPlayer->env_level;
                } else if(pPlayer->env_state == ENV_END) {
                    pOutA[offset] = 0.0;
                    pOutB[offset] = 0.0;
                } else {
                    pOutA[offset] *= pPlayer->gain;
                    pOutB[offset] *= pPlayer->gain;
                }
            }
            pPlayer->play_pos_frames += r_count;
            if(pPlayer->loop) {
                if(pPlayer->play_pos_frames >= pPlayer->loop_end_src) {
                    pPlayer->play_pos_frames %= pPlayer->loop_end_src;
                    pPlayer->play_pos_frames += pPlayer->loop_start_src;
                }
            } else {
                if(a_count < nFrames && pPlayer->file_read_status == IDLE) {
                    // Reached end of file
                    pPlayer->play_pos_frames = 0;
                    pPlayer->play_state = STOPPING;
                }
            }
        }

        if(pPlayer->env_state == ENV_END)
            pPlayer->env_state = ENV_IDLE;
        if(pPlayer->play_state == STOPPING && pPlayer->env_state == ENV_IDLE) {
            // Soft mute (not perfect for short last period of file but better than nowt)
            for(size_t offset = 0; offset < a_count; ++offset) {
                pOutA[offset] *= 1.0 - ((jack_default_audio_sample_t)offset / a_count);
                pOutB[offset] *= 1.0 - ((jack_default_audio_sample_t)offset / a_count);
            }
            pPlayer->play_state = STOPPED;
            pPlayer->file_read_status = SEEKING;

            DPRINTF("libzynaudioplayer: Stopped. Used %u frames from %u in buffer to soft mute (fade). Silencing remaining %u frames (%u bytes)\n", a_count, nFrames, nFrames - a_count, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
        }

        // Silence remainder of frame
        memset(pOutA + a_count, 0, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
        memset(pOutB + a_count, 0, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
    }

    // Process MIDI input
    void* pMidiBuffer = jack_port_get_buffer(g_jack_midi_in, nFrames);
    jack_midi_event_t midiEvent;
    jack_nframes_t nCount = jack_midi_get_event_count(pMidiBuffer);
    for(jack_nframes_t i = 0; i < nCount; i++)
    {
        jack_midi_event_get(&midiEvent, pMidiBuffer, i);
        uint8_t chan = midiEvent.buffer[0] & 0x0F;
        for(int i = 0; i < MAX_PLAYERS; ++i) {
            if(g_players[i]) {
                struct AUDIO_PLAYER * pPlayer = g_players[i];
                if(pPlayer->midi_chan != chan)
                    continue;
                uint8_t cmd = midiEvent.buffer[0] & 0xF0;
                if(cmd == 0x80 || cmd == 0x90 && midiEvent.buffer[2] == 0) {
                    // Note off
                    pPlayer->held_notes[midiEvent.buffer[1]] = 0;
                    if(pPlayer->last_note_played == midiEvent.buffer[1]) {
                        pPlayer->held_note = 0;
                        for (uint8_t i = 0; i < 128; ++i) {
                            if(pPlayer->held_notes[i]) {
                                pPlayer->last_note_played = i;
                                pPlayer->pitch_shift  = pow(1.059463094359, 60 - pPlayer->last_note_played + pPlayer->pitch_bend);
                                pPlayer->held_note = 1;
                                break;
                            }
                        }
                        if(pPlayer->held_note)
                            continue;
                        if(pPlayer->sustain == 0) {
                            stop_playback(pPlayer->handle);
                        }
                    }
                } else if(cmd == 0x90) {
                    // Note on
                    if(pPlayer->play_state == STOPPED) {
                        pPlayer->play_pos_frames = pPlayer->crop_start_src;
                        pPlayer->play_state = STARTING;
                    }
                    pPlayer->last_note_played = midiEvent.buffer[1];
                    pPlayer->held_notes[pPlayer->last_note_played] = 1;
                    pPlayer->held_note = 1;
                    pPlayer->pitch_shift  = pow(1.059463094359, 60 - pPlayer->last_note_played + pPlayer->pitch_bend);
                    pPlayer->file_read_status = SEEKING;
                    jack_ringbuffer_reset(pPlayer->ringbuffer_a);
                    jack_ringbuffer_reset(pPlayer->ringbuffer_b);
                } else if(cmd == 0xE0) {
                    // Pitchbend
                    pPlayer->pitch_bend =  pPlayer->pitch_bend_range * (1.0 - (midiEvent.buffer[1] + 128 * midiEvent.buffer[2]) / 8192.0);
                    if(pPlayer->play_state != STOPPED)
                        pPlayer->pitch_shift  = pow(1.059463094359, 60 - pPlayer->last_note_played + pPlayer->pitch_bend);
                } else if(cmd == 0xB0) {
                    if(midiEvent.buffer[1] == 64) {
                        // Sustain pedal
                        pPlayer->sustain = midiEvent.buffer[2];
                        if(!pPlayer->sustain) {
                            pPlayer->held_note = 0;
                            for(uint8_t i = 0; i < 128; ++i) {
                                if(pPlayer->held_notes[i]) {
                                    pPlayer->held_note = 1;
                                    break;
                                }
                            }
                            if(!pPlayer->held_note) {
                                stop_playback(pPlayer->handle);
                                pPlayer->pitch_shift = 1.0;
                            }
                        }
                    } else if (midiEvent.buffer[1] == 120 || midiEvent.buffer[1] == 123) {
                        // All off
                        for(uint8_t i = 0; i < 128; ++i)
                            pPlayer->held_notes[i] = 0;
                        pPlayer->held_note = 0;
                        stop_playback(pPlayer->handle);
                        pPlayer->pitch_shift = 1.0;
                    }
                }
                #ifdef ENABLE_MIDI
                else if(cmd == 0xB0) {
                    // CC
                    switch(midiEvent.buffer[1])
                    {
                        case 1:
                            set_position(pPlayer->handle, midiEvent.buffer[2] * get_duration(pPlayer->handle) / 127);
                            break;
                        case 2:
                            set_loop_start(pPlayer->handle, midiEvent.buffer[2] * get_duration(pPlayer->handle) / 127);
                            break;
                        case 3:
                            set_loop_end(pPlayer->handle, midiEvent.buffer[2] * get_duration(pPlayer->handle) / 127);
                            break;
                        case 7:
                            pPlayer->gain = (float)midiEvent.buffer[2] / 100.0;
                            break;
                        case 68:
                            if(midiEvent.buffer[2] > 63)
                                start_playback(pPlayer->handle);
                            else
                                stop_playback(pPlayer->handle);
                            break;
                        case 69:
                            enable_loop(pPlayer->handle, midiEvent.buffer[2] > 63);
                            break;
                    }
                }
                #endif //ENABLE_MIDI
            }
        }
     }
    releaseMutex();
    return 0;
}

// Handle JACK process callback
int on_jack_samplerate(jack_nframes_t nFrames, void *pArgs) {
    DPRINTF("libzynaudioplayer: Jack sample rate: %u\n", nFrames);
    if(nFrames)
        g_samplerate = nFrames;
    return 0;
}
 
static void lib_init(void) { 
    fprintf(stderr, "libzynaudioplayer initialised\n");
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;

    for(int i = 0; i < MAX_PLAYERS; ++i)
        g_players[i] = NULL;

    if((g_jack_client = jack_client_open("audioplayer", nOptions, &nStatus)) == 0)
        fprintf(stderr, "libaudioplayer error: failed to start jack client: %d\n", nStatus);

    // Create MIDI input port
    if(!(g_jack_midi_in = jack_port_register(g_jack_client, "in", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0)))
        fprintf(stderr, "libzynaudioplayer error: cannot register MIDI input port\n");

    // Register the callback to process audio and MIDI
    jack_set_process_callback(g_jack_client, on_jack_process, 0);
    jack_set_sample_rate_callback(g_jack_client, on_jack_samplerate, 0);

    if(jack_activate(g_jack_client))
        fprintf(stderr, "libaudioplayer error: cannot activate client\n");

    g_samplerate = jack_get_sample_rate(g_jack_client);
    if(g_samplerate < 10)
        g_samplerate = 44100;
}

static void lib_exit(void) {
    fprintf(stderr, "libzynaudioplayer exiting...  ");
    if(g_jack_client)
        lib_stop();
    fprintf(stderr, "done!\n");
}

void lib_stop() {
    for(int i = 0; i < MAX_PLAYERS; ++i)
        remove_player(i);
    jack_client_close(g_jack_client);
    g_jack_client = NULL;
}

int add_player() {
    struct AUDIO_PLAYER * pPlayer = NULL;
    int player_handle;
    for(player_handle = 0; player_handle < MAX_PLAYERS; ++player_handle) {
        if(!g_players[player_handle])
            break;
    }
    if(player_handle >= MAX_PLAYERS) {
        fprintf(stderr, "Failed to create instance of audio player %d\n", player_handle);
        return -1;
    }

    pPlayer = malloc(sizeof(struct AUDIO_PLAYER));
    pPlayer->file_open = FILE_CLOSED;
    pPlayer->file_read_status = IDLE;
    pPlayer->play_state = STOPPED;
    pPlayer->loop = 0;
    pPlayer->play_pos_frames = 0;
    pPlayer->src_quality = SRC_SINC_FASTEST;
    pPlayer->filename[0] = '\0';
    pPlayer->gain = 1.0;
    pPlayer->track_a = 0;
    pPlayer->last_track_a = 0;
    pPlayer->last_track_b = 0;
    pPlayer->track_b = 0;
    pPlayer->handle = player_handle;
    pPlayer->input_buffer_size = 48000; // Quantity of frames
    pPlayer->buffer_count = 5;
    pPlayer->frames = 0;
    pPlayer->loop_start = 0;
    pPlayer->loop_start_src = pPlayer->loop_start * pPlayer->src_ratio;
    pPlayer->loop_end = pPlayer->input_buffer_size;
    pPlayer->loop_end_src = pPlayer->loop_end * pPlayer->src_ratio;
    pPlayer->crop_start = 0;
    pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
    pPlayer->crop_end = pPlayer->input_buffer_size;
    pPlayer->crop_end_src = pPlayer->crop_end * pPlayer->src_ratio;
    pPlayer->midi_chan = -1;
    pPlayer->last_note_played = 60;
    for (uint8_t i = 0; i < 128; ++i)
        pPlayer->held_notes[i] = 0;
    pPlayer->held_note = 0;
    pPlayer->sustain = 0;
    pPlayer->last_sustain = 0;
    g_players[player_handle] = pPlayer;

    set_env_target_ratio_a(player_handle, 0.3);
    set_env_target_ratio_dr(player_handle, 0.0001);
    set_env_attack(player_handle, 0.0);
    set_env_decay(player_handle, 0.0);
    set_env_release(player_handle, 0.0);
    set_env_sustain(player_handle, 1.0);
    set_env_gate(pPlayer, 0);
    reset_env(pPlayer);

    // Create audio output ports
    char port_name[8];
    sprintf(port_name, "out_%02da", player_handle + 1);
    if (!(pPlayer->jack_out_a = jack_port_register(g_jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port %s\n", port_name);
        return 0;
    }
    sprintf(port_name, "out_%02db", player_handle + 1);
    if (!(pPlayer->jack_out_b = jack_port_register(g_jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port %s\n", port_name);
        jack_port_unregister(g_jack_client, pPlayer->jack_out_a);
        return 0;
    }

    //fprintf(stderr, "libzynaudioplayer: Created new audio player\n");
    return player_handle;
}

void remove_player(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    unload(player_handle);
    if (jack_port_unregister(g_jack_client, pPlayer->jack_out_a)) {
        fprintf(stderr, "libaudioplayer error: cannot unregister audio output port %02dA\n", player_handle + 1);
    }
    if (jack_port_unregister(g_jack_client, pPlayer->jack_out_b)) {
        fprintf(stderr, "libaudioplayer error: cannot unregister audio output port %02dB\n", player_handle + 1);
    }
    g_players[player_handle] = NULL;
    free(pPlayer);
}

void set_midi_chan(int player_handle, uint8_t midi_chan) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return;
    if(midi_chan < 16)
        pPlayer->midi_chan = midi_chan;
    else
        pPlayer->midi_chan = -1;        
}


const char* get_jack_client_name() {
    return jack_get_client_name(g_jack_client);
}

uint8_t set_src_quality(int player_handle, unsigned int quality) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    if(quality > SRC_LINEAR)
        return 0;
    getMutex();
    pPlayer->src_quality = quality;
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_QUALITY);
    return 1;
}

unsigned int get_src_quality(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 2;
    return pPlayer->src_quality;
}

void set_gain(int player_handle, float gain) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if(gain < 0 || gain > 2)
        return;
    getMutex();
    pPlayer->gain = gain;
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_GAIN);
}

float get_gain(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0.0;
    return pPlayer->gain;
}

void set_track_a(int player_handle, int track) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if(track < pPlayer->sf_info.channels) {
        getMutex();
        if(pPlayer->sf_info.channels == 1)
            pPlayer->track_a = 0;
        else
            pPlayer->track_a = track;
        releaseMutex();
    }
    set_position(player_handle, get_position(player_handle));
    send_notifications(pPlayer, NOTIFY_TRACK_A);
}

void set_track_b(int player_handle, int track) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if(track < pPlayer->sf_info.channels) {
        getMutex();
        if(pPlayer->sf_info.channels == 1)
            pPlayer->track_b = 0;
        else
            pPlayer->track_b = track;
        releaseMutex();
    }
    set_position(player_handle, get_position(player_handle));
    send_notifications(pPlayer, NOTIFY_TRACK_B);
}

int get_track_a(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->track_a;
}

int get_track_b(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->track_b;
}

void set_pitchbend_range(int player_handle, uint8_t range) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer || range >= 64)
        return;
    getMutex();
    pPlayer->pitch_bend_range = range;
    releaseMutex();
}

uint8_t get_pitchbend_range(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(!pPlayer)
        return 0;
    return pPlayer->pitch_bend_range;
}



void set_buffer_size(int player_handle, unsigned int size) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->file_open == FILE_CLOSED) {
        getMutex();
        pPlayer->input_buffer_size = size;
        releaseMutex();
    }
}

unsigned int get_buffer_size(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer)
        return pPlayer->input_buffer_size;
    return 0;
}

void set_buffer_count(int player_handle, unsigned int count) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer && pPlayer->file_open == FILE_CLOSED && count > 1) {
        getMutex();
        pPlayer->buffer_count = count;
        releaseMutex();
    }
}

unsigned int get_buffer_count(int player_handle) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer)
        return pPlayer->buffer_count;
    return 0;
}

void set_pos_notify_delta(int player_handle, float time) {
    struct AUDIO_PLAYER * pPlayer = get_player(player_handle);
    if(pPlayer) {
        getMutex();
        pPlayer->pos_notify_delta = time;
        releaseMutex();
    }
}

/**** Global functions ***/

float get_file_duration(const char* filename) {
    SF_INFO info;
    info.format = 0;
    info.samplerate = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if(info.samplerate)
        return (float)info.frames / info.samplerate;
    return 0.0f;
}

const char* get_file_info(const char* filename, int type) {
    SF_INFO info;
    info.format = 0;
    info.samplerate = 0;
    SNDFILE* pFile = sf_open(filename, SFM_READ, &info);
    const char* pValue = sf_get_string(pFile, type);
    if(pValue) {
        sf_close(pFile);
        return pValue;
    }
    sf_close(pFile);
    return "";
}

void enable_debug(int enable) {
    fprintf(stderr, "libaudioplayer setting debug mode %s\n", enable?"on":"off");
    g_debug = enable;
}

int is_debug() {
    return g_debug;
}

unsigned int get_player_count() {
    int count = 0;
    for(int i = 0; i < MAX_PLAYERS; ++i)
        if(g_players[i])
            ++count;
    return count;
}
