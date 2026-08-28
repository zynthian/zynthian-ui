/*  Audio file player library for Zynthian
    Copyright (C) 2021-2026 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include "player.h"

#include <algorithm>       // provides find
#include <arpa/inet.h>     // provides inet_pton
#include <cstring>         // provides strcmp, memset
#include <fcntl.h>         // provides fcntl
#include <jack/jack.h>     // provides interface to JACK
#include <jack/midiport.h> // provides JACK MIDI interface
#include <math.h>          // provides pow, log, fabs, isinf
#include <pthread.h>       // provides multithreading
#include <stdio.h>         // provides printf
#include <stdlib.h>        // provides exit
#include <string>          // provides std:string
#include <unistd.h>        // provides usleep
#include <vector>

using namespace RubberBand;
using namespace std;

// **** Global variables ****
jack_client_t* g_jack_client;
jack_port_t* g_jack_midi_in;
jack_nframes_t g_samplerate = 48000; // Playback samplerate set by jackd
uint8_t g_debug             = 0;
uint8_t g_last_debug        = 0;
char g_supported_codecs[1024];
uint8_t g_mutex      = 0;
uint32_t g_nextIndex = 1;

struct PlayerVector {
    vector<AUDIO_PLAYER*> players;
    ~PlayerVector() {
        while (!players.empty()) {
            remove_player(players.front());
        }
    };
};

static PlayerVector playerVector;

// Declare local functions

#define DPRINTF(fmt, args...)                                                                                                                                  \
    if (g_debug)                                                                                                                                               \
    fprintf(stderr, fmt, ##args)

// **** Internal (non-public) functions ****

void getMutex() {
    while (g_mutex)
        usleep(10);
    g_mutex = 1;
}

void releaseMutex() { g_mutex = 0; }

int is_codec_supported(const char* codec) {
    SF_FORMAT_INFO format_info;
    int k, count;
    sf_command(NULL, SFC_GET_SIMPLE_FORMAT_COUNT, &count, sizeof(int));
    for (k = 0; k < count; k++) {
        format_info.format = k;
        sf_command(NULL, SFC_GET_SIMPLE_FORMAT, &format_info, sizeof(format_info));
        if (strcmp(codec, format_info.extension) == 0)
            return 1;
    }
    return 0;
}

char* get_supported_codecs() {
    g_supported_codecs[0] = '\0';
    SF_FORMAT_INFO format_info;
    int k, count;
    sf_command(NULL, SFC_GET_SIMPLE_FORMAT_COUNT, &count, sizeof(int));
    for (k = 0; k < count; k++) {
        format_info.format = k;
        sf_command(NULL, SFC_GET_SIMPLE_FORMAT, &format_info, sizeof(format_info));
        if (strstr(g_supported_codecs, format_info.extension))
            continue;
        if (g_supported_codecs[0])
            strcat(g_supported_codecs, ",");
        strcat(g_supported_codecs, format_info.extension);
    }
    return g_supported_codecs;
}

void send_notifications(AUDIO_PLAYER* pPlayer, int param) {
    // Send dynamic notifications within this thread, not jack process
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if ((param == NOTIFY_ALL || param == NOTIFY_TRANSPORT) && pPlayer->last_play_state != pPlayer->play_state) {
        pPlayer->last_play_state = pPlayer->play_state;
        if (pPlayer->cb_fn && pPlayer->play_state <= PLAYING)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_TRANSPORT, (float)(pPlayer->play_state));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_POSITION) && fabs(get_position(pPlayer) - pPlayer->last_position) >= pPlayer->pos_notify_delta) {
        pPlayer->last_position = get_position(pPlayer);
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_POSITION, pPlayer->last_position);
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_GAIN) && fabs(pPlayer->gain - pPlayer->last_gain) >= 0.01) {
        pPlayer->last_gain = pPlayer->gain;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_GAIN, (float)(pPlayer->gain));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_LOOP) && pPlayer->loop != pPlayer->last_loop) {
        pPlayer->last_loop = pPlayer->loop;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_LOOP, (float)(pPlayer->loop));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_CROP_START) && pPlayer->crop_start != pPlayer->last_crop_start) {
        pPlayer->last_crop_start = pPlayer->crop_start;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_CROP_START, get_crop_start_time(pPlayer));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_CROP_END) && pPlayer->crop_end != pPlayer->last_crop_end) {
        pPlayer->last_crop_end = pPlayer->crop_end;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_CROP_END, get_crop_end_time(pPlayer));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_TRACK_A) && pPlayer->track_a != pPlayer->last_track_a) {
        pPlayer->last_track_a = pPlayer->track_a;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_TRACK_A, (float)(pPlayer->track_a));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_TRACK_B) && pPlayer->track_b != pPlayer->last_track_b) {
        pPlayer->last_track_b = pPlayer->track_b;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_TRACK_B, (float)(pPlayer->track_b));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_QUALITY) && pPlayer->src_quality != pPlayer->last_src_quality) {
        pPlayer->last_src_quality = pPlayer->src_quality;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_QUALITY, (float)(pPlayer->src_quality));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_VARISPEED) && pPlayer->varispeed != pPlayer->last_varispeed) {
        pPlayer->last_varispeed = pPlayer->varispeed;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_VARISPEED, (float)(pPlayer->varispeed));
    }
    if ((param == NOTIFY_ALL || param == NOTIFY_DEBUG) && g_debug != g_last_debug) {
        g_last_debug = g_debug;
        if (pPlayer->cb_fn)
            ((cb_fn_t*)pPlayer->cb_fn)(pPlayer, NOTIFY_DEBUG, (float)(g_debug));
    }
}

void* file_thread_fn(void* param) {
    AUDIO_PLAYER* pPlayer   = (AUDIO_PLAYER*)(param);
    pPlayer->sf_info.format = 0; // This triggers sf_open to populate info structure
    SRC_STATE* pSrcState    = NULL;
    SRC_DATA srcData;
    size_t nMaxFrames;        // Maximum quantity of frames that may be read from file
    size_t nUnusedFrames = 0; // Quantity of frames in input buffer not used by SRC
    SNDFILE* pFile       = sf_open(pPlayer->filename.c_str(), SFM_READ, &pPlayer->sf_info);
    if (!pFile || pPlayer->sf_info.channels < 1) {
        pPlayer->file_open = FILE_CLOSED;
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename.c_str(), sf_strerror(pFile));
    }
    if (pPlayer->sf_info.channels < 0) {
        pPlayer->file_open = FILE_CLOSED;
        fprintf(stderr, "libaudioplayer error: file %s has no tracks\n", pPlayer->filename.c_str());
        int nError = sf_close(pFile);
        if (nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
    }
    if (pPlayer->file_open) {
        pPlayer->stretcher = new RubberBandStretcher(g_samplerate, 2,
                                                     RubberBandStretcher::OptionProcessRealTime | RubberBandStretcher::OptionWindowShort |
                                                         RubberBandStretcher::OptionPitchHighConsistency | RubberBandStretcher::OptionFormantPreserved);
        pPlayer->stretcher->setMaxProcessSize(256);

        pPlayer->crop_start       = 0;
        pPlayer->crop_end         = pPlayer->sf_info.frames;
        pPlayer->file_read_status = SEEKING;
        pPlayer->src_ratio        = (float)g_samplerate / pPlayer->sf_info.samplerate;
        if (pPlayer->src_ratio < 0.1)
            pPlayer->src_ratio = 1;
        srcData.src_ratio           = pPlayer->src_ratio;
        pPlayer->pos_notify_delta   = float(pPlayer->sf_info.frames) / g_samplerate / 400;
        pPlayer->output_buffer_size = pPlayer->src_ratio * pPlayer->input_buffer_size;
        pPlayer->ringbuffer_a       = jack_ringbuffer_create(pPlayer->output_buffer_size * pPlayer->buffer_count * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_a);
        pPlayer->ringbuffer_b = jack_ringbuffer_create(pPlayer->output_buffer_size * pPlayer->buffer_count * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_b);
        pPlayer->file_open = FILE_OPEN;
        
        {
            // Scope to avoid extra memory usage
            const char* loopModes[] = {"None", "Forward", "Backward", "Alternating"};
            SF_CUES cues;
            uint32_t count = 0;
            sf_command(pFile, SFC_GET_CUE_COUNT, &count, sizeof(count));
            if (count > 100)
                count = 100;
            sf_command(pFile, SFC_GET_CUE, &cues, sizeof(cues));
            for (uint32_t i = 0; i < count; ++i)
                add_cue_point(pPlayer, float(cues.cue_points[i].sample_offset) / pPlayer->sf_info.samplerate, cues.cue_points[i].name);

            pPlayer->gain      = 1.0;
        }

        // Initialise samplerate converter
        float pBufferIn[pPlayer->input_buffer_size * pPlayer->sf_info.channels];   // Buffer used to read sample data from file
        float pBufferOut[pPlayer->output_buffer_size * pPlayer->sf_info.channels]; // Buffer used to write converted sample data to
        float pBufferRev[pPlayer->output_buffer_size * pPlayer->sf_info.channels]; // Buffer used to write reverse playback sample data to
        srcData.data_in         = pBufferIn;
        srcData.data_out        = pBufferOut;
        srcData.output_frames   = pPlayer->output_buffer_size;
        pPlayer->frames         = pPlayer->sf_info.frames * pPlayer->src_ratio;
        pPlayer->crop_end_src   = pPlayer->crop_end * pPlayer->src_ratio;
        pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
        int nError;
        pSrcState = src_new(pPlayer->src_quality, pPlayer->sf_info.channels, &nError);
        if (!pSrcState) {
            fprintf(stderr, "Failed to create a samplerate converter: %d\n", nError);
            pPlayer->file_open = FILE_CLOSED;
        }

        DPRINTF("Opened file '%s' with samplerate %u, duration: %f\n", pPlayer->filename.c_str(), pPlayer->sf_info.samplerate, get_duration(pPlayer));

        while (pPlayer->file_open == FILE_OPEN) {
            if (pPlayer->file_read_status == SEEKING) {
                // Main thread has signalled seek within file
                getMutex();
                jack_ringbuffer_reset(pPlayer->ringbuffer_a);
                jack_ringbuffer_reset(pPlayer->ringbuffer_b);
                sf_count_t pos = sf_seek(pFile, pPlayer->play_pos_frames / pPlayer->src_ratio, SEEK_SET);
                if (pos >= 0)
                    pPlayer->file_read_pos = pos;
                // DPRINTF("Seeking to %u frames (%fs) src ratio=%f\n", nNewPos, get_position(pPlayer), srcData.src_ratio);
                pPlayer->file_read_status = LOADING;
                releaseMutex();
                src_reset(pSrcState);
                nUnusedFrames        = 0;
                srcData.end_of_input = 0;
                pPlayer->stretcher->reset();
            } else if (pPlayer->file_read_status == LOOPING) {
                // Reached loop end point and need to read from loop marker
                sf_count_t pos;
                if (pPlayer->varispeed < 0.0)
                    pos = sf_seek(pFile, pPlayer->crop_end, SEEK_SET);
                else
                    pos = sf_seek(pFile, pPlayer->crop_start, SEEK_SET);
                getMutex();
                if (pos >= 0)
                    pPlayer->file_read_pos = pos;
                pPlayer->file_read_status = LOADING;
                releaseMutex();
                src_reset(pSrcState);
                srcData.end_of_input = 0;
                nUnusedFrames        = 0;
            }

            if (pPlayer->file_read_status == WAITING)
                pPlayer->file_read_status = LOADING;

            while (pPlayer->file_read_status == LOADING) {
                int nFramesRead = 0;
                // Load block of data from file to SRC or output buffer
                nMaxFrames      = pPlayer->input_buffer_size - nUnusedFrames;

                if (jack_ringbuffer_write_space(pPlayer->ringbuffer_a) >= nMaxFrames * sizeof(float) * pPlayer->src_ratio &&
                    jack_ringbuffer_write_space(pPlayer->ringbuffer_b) >= nMaxFrames * sizeof(float) * pPlayer->src_ratio) {

                    bool bReverse = (pPlayer->varispeed < 0.0);
                    if (bReverse) {
                        if (pPlayer->loop == 1) {
                            // Limit read to crop range
                            if (pPlayer->file_read_pos <= pPlayer->crop_start)
                                nMaxFrames = 0;
                            else if (pPlayer->file_read_pos - nMaxFrames < pPlayer->crop_start)
                                nMaxFrames = pPlayer->file_read_pos - pPlayer->crop_start;
                        } else if (pPlayer->file_read_pos - nMaxFrames < pPlayer->crop_start) {
                            // Limit read to crop range
                            nMaxFrames = pPlayer->file_read_pos - pPlayer->crop_start;
                        }
                    } else {
                        if (pPlayer->loop == 1) {
                            // Limit read to crop range
                            if (pPlayer->file_read_pos >= pPlayer->crop_end)
                                nMaxFrames = 0;
                            else if (pPlayer->file_read_pos + nMaxFrames > pPlayer->crop_end)
                                nMaxFrames = pPlayer->crop_end - pPlayer->file_read_pos;
                        } else if (pPlayer->file_read_pos + nMaxFrames > pPlayer->crop_end) {
                            // Limit read to crop range
                            nMaxFrames = pPlayer->crop_end - pPlayer->file_read_pos;
                        }
                    }

                    if (srcData.src_ratio == 1.0) {
                        // No SRC required so populate SRC output buffer directly
                        if (bReverse) {
                            if (pPlayer->file_read_pos > nMaxFrames)
                                pPlayer->file_read_pos -= nMaxFrames;
                            else {
                                nMaxFrames             = pPlayer->file_read_pos;
                                pPlayer->file_read_pos = 0;
                            }
                            // Move to start of audio chunk
                            sf_count_t pos = sf_seek(pFile, pPlayer->file_read_pos, SEEK_SET);
                            if (pos >= 0) {
                                // Read audio chunk
                                nFramesRead    = sf_readf_float(pFile, pBufferRev, nMaxFrames);
                                size_t wOffset = 0;
                                // Reverse audio chunk
                                for (int i = nFramesRead; i > 0; --i) {
                                    for (size_t j = 0; j < pPlayer->sf_info.channels; ++j) {
                                        pBufferOut[wOffset] = pBufferRev[(i - 1) * pPlayer->sf_info.channels + j];
                                        ++wOffset;
                                    }
                                }
                                // Move to start of audio chunk again for next cycle (we have processed this chunk)
                                sf_seek(pFile, pos, SEEK_SET);
                            }
                        } else
                            pPlayer->file_read_pos += (nFramesRead = sf_readf_float(pFile, pBufferOut, nMaxFrames));
                    } else {
                        // Populate SRC input buffer before SRC process
                        if (bReverse) {
                            if (pPlayer->file_read_pos > nMaxFrames)
                                pPlayer->file_read_pos -= nMaxFrames;
                            else
                                pPlayer->file_read_pos = 0;
                            sf_count_t pos = sf_seek(pFile, pPlayer->file_read_pos, SEEK_SET);
                            if (pos >= 0) {
                                nFramesRead = sf_readf_float(pFile, pBufferRev, nMaxFrames);
                                size_t wPos = nUnusedFrames;
                                for (size_t i = nFramesRead; i == 0; --i) {
                                    for (size_t j = 0; j < pPlayer->sf_info.channels; ++j) {
                                        pBufferIn[wPos] = pBufferRev[(i - 1) * pPlayer->sf_info.channels + j];
                                        ++wPos;
                                    }
                                }
                                sf_seek(pFile, pos, SEEK_SET);
                            }
                        } else
                            pPlayer->file_read_pos += (nFramesRead = sf_readf_float(pFile, pBufferIn + nUnusedFrames * pPlayer->sf_info.channels, nMaxFrames));
                    }

                    if (nFramesRead) {
                        // Got some audio data to process...
                        // Remain in LOADING state to trigger next file read when FIFO has sufficient space
                        DPRINTF("libzynaudioplayer read %u frames into input buffer\n", nFramesRead);

                        if (srcData.src_ratio != 1.0) {
                            // We need to perform SRC on this block of code
                            srcData.input_frames = nFramesRead;
                            int rc               = src_process(pSrcState, &srcData);
                            if (rc) {
                                DPRINTF("SRC failed with error %d, %lu frames generated\n", nFramesRead, srcData.output_frames_gen);
                            } else {
                                DPRINTF("SRC suceeded - %lu frames generated, %lu frames used, %lu frames unused\n", srcData.output_frames_gen,
                                        srcData.input_frames_used, nUnusedFrames);
                                nUnusedFrames = nFramesRead - srcData.input_frames_used;
                                nFramesRead   = srcData.output_frames_gen;
                                // Shift unused samples to start of buffer
                                memcpy(pBufferIn, pBufferIn + srcData.input_frames_used * sizeof(float) * pPlayer->sf_info.channels,
                                       nUnusedFrames * sizeof(float) * pPlayer->sf_info.channels);
                            }
                        } else {
                            // DPRINTF("No SRC, read %u frames\n", nFramesRead);
                        }
                        // Demux samples and populate playback ring buffers
                        for (size_t frame = 0; frame < nFramesRead; ++frame) {
                            float fA = 0.0, fB = 0.0;
                            size_t sample = frame * pPlayer->sf_info.channels;
                            if (pPlayer->sf_info.channels > 1) {
                                if (pPlayer->track_a < 0) {
                                    // Send sum of odd channels to A
                                    for (int track = 0; track < pPlayer->sf_info.channels; track += 2)
                                        fA += pBufferOut[sample + track] / (pPlayer->sf_info.channels / 2);
                                } else {
                                    // Send pPlayer->track to A
                                    fA = pBufferOut[sample + pPlayer->track_a];
                                }
                                if (pPlayer->track_b < 0) {
                                    // Send sum of odd channels to B
                                    for (int track = 0; track + 1 < pPlayer->sf_info.channels; track += 2)
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
                            if (sizeof(float) < jack_ringbuffer_write(pPlayer->ringbuffer_a, (const char*)(&fA), nWrote)) {
                                // Shouldn't underun due to previous wait for space but just in case...
                                fprintf(stderr, "libZynAudioPlayer Underrun during writing to ringbuffer - this should never happen!!!\n");
                                break;
                            }
                        }
                    } else if (pPlayer->loop == 1) {
                        // Short read - looping so fill from loop start point in file
                        getMutex();
                        pPlayer->file_read_status = LOOPING;
                        // srcData.end_of_input = 1;
                        releaseMutex();
                        DPRINTF("libzynaudioplayer read to loop point in input file - setting loading status to looping\n");
                    } else {
                        // End of file
                        getMutex();
                        pPlayer->file_read_status = IDLE;
                        srcData.end_of_input      = 1;
                        releaseMutex();
                        DPRINTF("libzynaudioplayer read to end of input file - setting loading status to IDLE\n");
                    }
                } else {
                    pPlayer->file_read_status = WAITING;
                }
            }
            // if(pPlayer->file_read_status != LOOPING) {
            send_notifications(pPlayer, NOTIFY_ALL);
            usleep(10000); // Reduce CPU load by waiting until next file read operation
            //}
        }
    }
    if (pFile) {
        int nError = sf_close(pFile);
        if (nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        else
            pPlayer->filename = "";
    }
    pPlayer->play_pos_frames = 0;
    pPlayer->cb_fn           = NULL;
    if (pSrcState)
        pSrcState = src_delete(pSrcState);

    DPRINTF("File reader thread ended\n");
    pthread_exit(NULL);
}

/**** player instance functions take 'handle' param to identify player instance****/

uint8_t load(AUDIO_PLAYER* pPlayer, const char* filename, cb_fn_t cb_fn) {
    unload(pPlayer);
    pPlayer->cb_fn;
    pPlayer->track_a   = 0;
    pPlayer->track_b   = 0;
    pPlayer->filename  = filename;

    pPlayer->file_open = FILE_OPENING;
    if (pthread_create(&(pPlayer->file_thread), 0, file_thread_fn, pPlayer)) {
        fprintf(stderr, "libzynaudioplayer error: failed to create file reading thread\n");
        unload(pPlayer);
        return 0;
    }
    while (pPlayer->file_open == FILE_OPENING) {
        usleep(10000); //!@todo Optimise wait for file open
    }

    if (pPlayer->file_open) {
        pPlayer->cb_fn = cb_fn;
    }
    return (pPlayer->file_open == FILE_OPEN);
}

void unload(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return;
    stop_playback(pPlayer);
    if (pPlayer->file_open == FILE_CLOSED)
        return;
    getMutex();
    pPlayer->file_open = FILE_CLOSED;
    releaseMutex();
    pPlayer->cue_points.clear();
    pthread_join(pPlayer->file_thread, NULL);
}

uint8_t save(AUDIO_PLAYER* pPlayer, const char* filename) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;

    AUDIO_PLAYER* overwrite = NULL;
    for (const auto player: playerVector.players) {
        if (strcmp(player->filename.c_str(), filename) == 0) {
            // Trying to overwrite an open file
            unload(player);
            overwrite = player;
            break;
        }
    }

    SF_INFO sfinfo;
    sfinfo.format   = 0; // This triggers sf_open to populate info structure

    SNDFILE* infile = sf_open(pPlayer->filename.c_str(), SFM_READ, &sfinfo);
    if (!infile || sfinfo.channels < 1) {
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename.c_str(), sf_strerror(infile));
        return 0;
    }

    sfinfo.format = SF_FORMAT_WAV | SF_FORMAT_FLOAT;

    if (!sf_format_check(&sfinfo)) {
        sf_close(infile);
        fprintf(stderr, "Invalid encoding\n");
        return 0;
    };

    SNDFILE* outfile = sf_open(filename, SFM_WRITE, &sfinfo);
    if (!outfile) {
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", filename, sf_strerror(outfile));
        sf_close(infile);
        return 0;
    }

    // sndfile cue points are a structure of {quantity of points (uint32) + n x SF_CUE_POINT structs}
    int32_t count = 0;
    SF_CUES cues;
    for (size_t i = 0; i < pPlayer->cue_points.size(); ++i) {
        int64_t offset = pPlayer->cue_points[i].offset - pPlayer->crop_start;
        if (offset < 0)
            continue;
        cues.cue_points[i].indx          = count;
        cues.cue_points[i].position      = 0;
        cues.cue_points[i].fcc_chunk     = 0;
        cues.cue_points[i].chunk_start   = 0;
        cues.cue_points[i].block_start   = 0;
        cues.cue_points[i].sample_offset = offset;
        memcpy(cues.cue_points[i].name, pPlayer->cue_points[i].name, 256);
        if (++count > 99)
            break;
    }
    cues.cue_count  = count;
    size_t cue_size = sizeof(uint32_t) + count * sizeof(SF_CUE_POINT);

    if (SF_TRUE != sf_command(outfile, SFC_SET_CUE, &cues, cue_size))
        fprintf(stderr, "Failed to set cue points: %s\n", sf_strerror(outfile));

    float buffer[1024 * sfinfo.channels];
    sf_count_t pos    = sf_seek(infile, pPlayer->crop_start, SEEK_SET);
    uint32_t duration = pPlayer->crop_end - pPlayer->crop_start;
    while (duration) {
        uint32_t frames = sf_readf_float(infile, buffer, 1024);
        if (duration > frames) {
            sf_writef_float(outfile, buffer, frames);
            duration -= frames;
        } else {
            sf_writef_float(outfile, buffer, duration);
            duration = 0;
        }
    }
    sf_close(infile);
    sf_close(outfile);
    if (overwrite)
        load(overwrite, overwrite->filename.c_str(), overwrite->cb_fn);
    return 1;
}

const char* get_filename(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return "";
    return pPlayer->filename.c_str();
}

float get_duration(AUDIO_PLAYER* pPlayer) {
    if (pPlayer && pPlayer->file_open == FILE_OPEN && pPlayer->sf_info.samplerate)
        return (float)pPlayer->sf_info.frames / pPlayer->sf_info.samplerate / pPlayer->speed;
    return 0.0f;
}

void set_position(AUDIO_PLAYER* pPlayer, float time) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    sf_count_t frames = time * g_samplerate * pPlayer->speed;
    if (frames > pPlayer->crop_end_src)
        frames = pPlayer->crop_end_src;
    else if (frames < pPlayer->crop_start_src)
        frames = pPlayer->crop_start_src;
    getMutex();
    pPlayer->play_pos_frames  = frames;
    pPlayer->file_read_status = SEEKING;
    releaseMutex();
    DPRINTF("New position requested, setting loading status to SEEKING\n");
    send_notifications(pPlayer, NOTIFY_POSITION);
}

float get_position(AUDIO_PLAYER* pPlayer) {
    if (pPlayer && pPlayer->file_open == FILE_OPEN)
        return (float)(pPlayer->play_pos_frames) / g_samplerate / pPlayer->speed;
    return 0.0;
}

void enable_loop(AUDIO_PLAYER* pPlayer, uint8_t nLoop) {
    if (!pPlayer)
        return;
    getMutex();
    pPlayer->loop = nLoop;
    pPlayer->file_read_status = SEEKING;
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_LOOP);
}

uint8_t is_loop(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return (pPlayer->loop);
}

void set_crop_start_time(AUDIO_PLAYER* pPlayer, float time) {
    if (!pPlayer)
        return;
    if (time < 0.0)
        time = 0.0;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if (frames >= pPlayer->crop_end)
        frames = pPlayer->crop_end - 1;
    getMutex();
    pPlayer->crop_start     = frames;
    pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
    releaseMutex();
    if (pPlayer->play_pos_frames < frames)
        set_position(pPlayer, time);
    pPlayer->last_crop_start = -1;
    send_notifications(pPlayer, NOTIFY_CROP_START);
}

float get_crop_start_time(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->crop_start) / pPlayer->sf_info.samplerate;
}

void set_crop_end_time(AUDIO_PLAYER* pPlayer, float time) {
    if (!pPlayer)
        return;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if (frames < pPlayer->crop_start)
        frames = pPlayer->crop_start + 1;
    if (frames > pPlayer->sf_info.frames)
        frames = pPlayer->sf_info.frames;
    getMutex();
    pPlayer->crop_end     = frames;
    pPlayer->crop_end_src = frames * pPlayer->src_ratio;
    if (pPlayer->crop_end_src > pPlayer->frames) {
        pPlayer->crop_end_src = pPlayer->frames;
        pPlayer->crop_end     = pPlayer->frames / pPlayer->src_ratio;
    }
    if (pPlayer->play_pos_frames > pPlayer->crop_end_src) {
        pPlayer->play_pos_frames  = pPlayer->crop_end_src;
        pPlayer->file_read_status = SEEKING;
    } else
        pPlayer->file_read_status = WAITING;
    releaseMutex();
    pPlayer->last_crop_end = -1;
    send_notifications(pPlayer, NOTIFY_CROP_END);
}

float get_crop_end_time(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->crop_end) / pPlayer->sf_info.samplerate;
}

int32_t add_cue_point(AUDIO_PLAYER* pPlayer, float position, const char* name) {
    if (!pPlayer || position < 0.0)
        return -1;

    uint32_t frames = position * pPlayer->sf_info.samplerate;
    if (frames >= pPlayer->sf_info.frames)
        return -1;
    for (size_t i = 0; i < pPlayer->cue_points.size(); ++i) {
        if (pPlayer->cue_points[i].offset == frames)
            return -1;
        if (pPlayer->cue_points[i].offset > frames) {
            pPlayer->cue_points.insert(pPlayer->cue_points.begin() + i, cue_point(frames, name));
            return i;
        }
    }
    pPlayer->cue_points.push_back(cue_point(frames, name));
    return pPlayer->cue_points.size() - 1;
}

int32_t remove_cue_point(AUDIO_PLAYER* pPlayer, float position) {
    if (!pPlayer || position < 0.0)
        return -1;
    int32_t minOffset    = 0.5 * pPlayer->sf_info.samplerate;
    int32_t markerOffset = minOffset;
    int32_t frames       = position * pPlayer->sf_info.samplerate;
    int32_t result       = -1;
    for (int32_t i = 0; i < pPlayer->cue_points.size(); ++i) {
        int32_t dT = abs(int32_t(pPlayer->cue_points[i].offset) - frames);
        if (dT < markerOffset) {
            result       = i;
            markerOffset = dT;
        }
    }
    if (markerOffset < minOffset) {
        pPlayer->cue_points.erase(pPlayer->cue_points.begin() + result);
        return result;
    }
    return -1;
}

uint32_t get_cue_point_count(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return 0;
    return pPlayer->cue_points.size();
}

float get_cue_point_position(AUDIO_PLAYER* pPlayer, uint32_t index) {
    if (!pPlayer || index >= pPlayer->cue_points.size() || pPlayer->sf_info.samplerate < 1000)
        return -1.0;
    return float(pPlayer->cue_points[index].offset) / pPlayer->sf_info.samplerate;
}

bool set_cue_point_position(AUDIO_PLAYER* pPlayer, uint32_t index, float position) {
    if (!pPlayer || index >= pPlayer->cue_points.size() || position < 0.0)
        return false;
    uint32_t frames = position * pPlayer->sf_info.samplerate;
    if (frames >= pPlayer->sf_info.frames)
        return false;
    pPlayer->cue_points[index].offset = frames;
    return true;
}

const char* get_cue_point_name(AUDIO_PLAYER* pPlayer, uint32_t index) {
    if (!pPlayer || index >= pPlayer->cue_points.size())
        return "";
    return pPlayer->cue_points[index].name;
}

bool set_cue_point_name(AUDIO_PLAYER* pPlayer, uint32_t index, const char* name) {
    if (!pPlayer || index >= pPlayer->cue_points.size())
        return false;
    if (strlen(name) > 255)
        return false;
    strcpy(pPlayer->cue_points[index].name, name);
    return true;
}

void clear_cue_points(AUDIO_PLAYER* pPlayer) {
    if (pPlayer)
        pPlayer->cue_points.clear();
}

void start_playback(AUDIO_PLAYER* pPlayer) {
    if (pPlayer && g_jack_client && pPlayer->file_open == FILE_OPEN && pPlayer->play_state != PLAYING) {
        pPlayer->varispeed        = pPlayer->play_varispeed;
        pPlayer->play_state       = STARTING;
        pPlayer->time_ratio_dirty = true;
    }
    // send_notifications(pPlayer, NOTIFY_TRANSPORT);
}

void stop_playback(AUDIO_PLAYER* pPlayer) {
    if (pPlayer && pPlayer->play_state != STOPPED) {
        pPlayer->play_state     = STOPPING;
        pPlayer->play_varispeed = pPlayer->varispeed;
    }
    // send_notifications(pPlayer, NOTIFY_TRANSPORT);
}

uint8_t get_playback_state(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return STOPPED;
    return pPlayer->play_state;
}

int get_samplerate(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return g_samplerate;
    return pPlayer->sf_info.samplerate;
}

const char* get_codec(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return "NONE";
    // Define some constants that are not included in my version of sndfile header
    static char buffer[20];
    const char* sType    = NULL;
    const char* sSubtype = NULL;

    SF_FORMAT_INFO format_info;
    format_info.format = pPlayer->sf_info.format;
    if (sf_command(NULL, SFC_GET_FORMAT_INFO, &format_info, sizeof(format_info)))
        return "UNKNOWN";
    return format_info.name;
}

int get_channels(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.channels;
}

int get_frames(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.frames;
}

int get_format(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.format;
}

/*** Private functions not exposed as external C functions (not declared in header) ***/

// Handle JACK process callback
int on_jack_process(jack_nframes_t nFrames, void* arg) {
    getMutex();

    for (const auto& pPlayer: playerVector.players) {
        if (pPlayer->file_open != FILE_OPEN)
            continue;

        size_t r_count          = 0; // Quantity of frames removed from queue, i.e. how far advanced through the audio
        size_t a_count          = 0; // Quantity of frames added to playback (non silent audio)
        auto pOutA              = (jack_default_audio_sample_t*)jack_port_get_buffer(pPlayer->jack_out_a, nFrames);
        auto pOutB              = (jack_default_audio_sample_t*)jack_port_get_buffer(pPlayer->jack_out_b, nFrames);
        float pInA[256];
        float pInB[256];
        float* stretch_input_buffers[] = {pInA, pInB};
        float* output_buffers[]        = {pOutA, pOutB};
        bool bReverse                  = pPlayer->varispeed < 0.0;

        if (pPlayer->play_state == STARTING && pPlayer->file_read_status != SEEKING) {
            pPlayer->play_state = PLAYING;
        }

        if (pPlayer->play_state == PLAYING || pPlayer->play_state == STOPPING) {
            if (pPlayer->time_ratio_dirty) {
                if (fabs(pPlayer->varispeed) < 0.1) {
                    // Much lower than this and the stretcher starts auto-resizing its buffers
                    //!@todo Pause playback
                    // pPlayer->stretcher->setTimeRatio(0.0);
                } else {
                    pPlayer->stretcher->setTimeRatio(pPlayer->time_ratio / fabs(pPlayer->varispeed) / pPlayer->speed);
                    pPlayer->stretcher->setPitchScale(pPlayer->pitch * pPlayer->pitchshift * fabs(pPlayer->varispeed));
                }
                pPlayer->time_ratio_dirty = false;
            }
            while (pPlayer->stretcher->available() < nFrames) {
                // Process data from fifo until sufficient to populate this frame (first attempt may give -1 but that's okay as we will repeat)
                size_t sampsReq = min((size_t)256, pPlayer->stretcher->getSamplesRequired());
                size_t nBytes   = min(jack_ringbuffer_read_space(pPlayer->ringbuffer_a), jack_ringbuffer_read_space(pPlayer->ringbuffer_b));
                nBytes          = min(nBytes, sampsReq * sizeof(float));
                nBytes -= nBytes % sizeof(float);
                size_t nRead  = jack_ringbuffer_read(pPlayer->ringbuffer_a, (char*)pInA, nBytes);
                size_t nReadB = jack_ringbuffer_read(pPlayer->ringbuffer_b, (char*)pInB, nRead);
                r_count += nRead / sizeof(float);
                // stretch
                pPlayer->stretcher->process(stretch_input_buffers, nRead / sizeof(float), nRead != nBytes);
                if (nRead == 0)
                    break; // fifo buffers run dry
            }
            a_count = min(pPlayer->stretcher->available(), (int)nFrames);
            if (a_count < 0)
                a_count = 0; // If stretcher gives fault it will respond with -1
            a_count = pPlayer->stretcher->retrieve(output_buffers, a_count);
            for (size_t offset = 0; offset < a_count; ++offset) {
                // Set volume / gain / level / envelope
                pOutA[offset] *= pPlayer->gain;
                pOutB[offset] *= pPlayer->gain;
            }
            // Advance play position based on the raw (SRC'd) frames
            if (bReverse)
                pPlayer->play_pos_frames -= r_count;
            else
                pPlayer->play_pos_frames += r_count;

            if (pPlayer->loop == 1) {
                if (bReverse) {
                    if (pPlayer->play_pos_frames <= pPlayer->crop_start_src) {
                        size_t i = pPlayer->crop_start_src - pPlayer->play_pos_frames;
                        i %= pPlayer->crop_end_src - pPlayer->crop_start_src;
                        pPlayer->play_pos_frames = pPlayer->crop_end_src - i;
                    }
                } else {
                    if (pPlayer->play_pos_frames >= pPlayer->crop_end_src) {
                        pPlayer->play_pos_frames %= pPlayer->crop_end_src;
                        pPlayer->play_pos_frames += pPlayer->crop_start_src;
                    }
                }
            } else if (a_count < nFrames && pPlayer->file_read_status == IDLE) {
                // No more data from file reader, e.g. reached end of file
                if (bReverse)
                    pPlayer->play_pos_frames = pPlayer->crop_end_src;
                else
                    pPlayer->play_pos_frames = pPlayer->crop_start_src;
                pPlayer->play_state = STOPPING;
                DPRINTF("libzynaudioplayer: Short read (%lu) and IDLE so STOPPING\n", a_count);
            } else {
                if (bReverse && pPlayer->play_pos_frames <= pPlayer->crop_start_src || !bReverse && pPlayer->play_pos_frames >= pPlayer->crop_end_src)
                    pPlayer->play_state = STOPPING;
            }
        }

        if (pPlayer->play_state == STOPPING) {
            // Soft mute (not perfect for short last period of file but better than nowt). Adds a few ms of delay.
            for (size_t offset = 0; offset < a_count; ++offset) {
                pOutA[offset] *= 1.0 - ((jack_default_audio_sample_t)offset / a_count);
                pOutB[offset] *= 1.0 - ((jack_default_audio_sample_t)offset / a_count);
            }
            pPlayer->play_state       = STOPPED;
            pPlayer->varispeed        = 0.0;
            pPlayer->file_read_status = SEEKING;
            DPRINTF("libzynaudioplayer: Stopped. Used %u frames from %u in buffer to soft mute (fade). Silencing remaining %u frames (%u bytes)\n", a_count,
                    nFrames, nFrames - a_count, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
        }

        // Silence remainder of frame
        memset(pOutA + a_count, 0, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
        memset(pOutB + a_count, 0, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
    }

    releaseMutex();
    return 0;
}

// Handle JACK process callback
int on_jack_samplerate(jack_nframes_t nFrames, void* pArgs) {
    DPRINTF("libzynaudioplayer: Jack sample rate: %u\n", nFrames);
    if (nFrames)
        g_samplerate = nFrames;
    return 0;
}

bool init_jack() {
    if (g_jack_client)
        return true;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;

    if ((g_jack_client = jack_client_open("audioplayer", nOptions, &nStatus)) == 0) {
        fprintf(stderr, "libaudioplayer error: failed to start jack client: %d\n", nStatus);
        return false;
    }

    // Register the callback to process audio and MIDI
    jack_set_process_callback(g_jack_client, on_jack_process, 0);
    jack_set_sample_rate_callback(g_jack_client, on_jack_samplerate, 0);

    if (jack_activate(g_jack_client)) {
        fprintf(stderr, "libaudioplayer error: cannot activate client\n");
        return false;
    }

    g_samplerate = jack_get_sample_rate(g_jack_client);
    if (g_samplerate < 8000)
        g_samplerate = 8000;
    return true;
}

static void lib_init(void) {
    fprintf(stderr, "Loaded libzynaudioplayer using %s\n", sf_version_string());
}

void stop_jack() {
    if (g_jack_client)
        jack_deactivate(g_jack_client);
    jack_client_close(g_jack_client);
    g_jack_client = NULL;
}

static void lib_exit(void) {
    fprintf(stderr, "libzynaudioplayer exiting\n");
}

AUDIO_PLAYER* add_player() {
    if (!init_jack())
        return nullptr;
    AUDIO_PLAYER* pPlayer = new AUDIO_PLAYER();
    if (!pPlayer)
        return nullptr;
    pPlayer->index = g_nextIndex++;
    pPlayer->crop_start     = 0;
    pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
    pPlayer->crop_end       = pPlayer->input_buffer_size;
    pPlayer->crop_end_src   = pPlayer->crop_end * pPlayer->src_ratio;
    playerVector.players.push_back(pPlayer);

    // Create audio output ports
    char port_name[8];

    sprintf(port_name, "out_%02da", pPlayer->index);
    if (!(pPlayer->jack_out_a = jack_port_register(g_jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port %s\n", port_name);
        return 0;
    }
    sprintf(port_name, "out_%02db", pPlayer->index);
    if (!(pPlayer->jack_out_b = jack_port_register(g_jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port %s\n", port_name);
        jack_port_unregister(g_jack_client, pPlayer->jack_out_a);
        return 0;
    }
    DPRINTF("libaudioplayer player %u registered JACK audio output ports %u & %u\n", pPlayer, pPlayer->jack_out_a, pPlayer->jack_out_b);
    return pPlayer;
}

void remove_player(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return;
    unload(pPlayer);
    if (jack_port_unregister(g_jack_client, pPlayer->jack_out_a)) {
        fprintf(stderr, "libaudioplayer error: player %u (%u) cannot unregister audio output port A %02d\n", pPlayer->index, pPlayer, pPlayer->jack_out_a);
    }
    if (jack_port_unregister(g_jack_client, pPlayer->jack_out_b)) {
        fprintf(stderr, "libaudioplayer error: player %u (%u) cannot unregister audio output port B %02d\n", pPlayer->index, pPlayer, pPlayer->jack_out_b);
    }
    auto it = find(playerVector.players.begin(), playerVector.players.end(), pPlayer);
    if (it != playerVector.players.end())
        playerVector.players.erase(it);
    if (playerVector.players.size() == 0)
        stop_jack();
}

int get_index(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return -1;
    return pPlayer->index;
}

const char* get_jack_client_name() {
    if (g_jack_client)
        return jack_get_client_name(g_jack_client);
    return "";
}

uint8_t set_src_quality(AUDIO_PLAYER* pPlayer, unsigned int quality) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    if (quality > SRC_LINEAR)
        return 0;
    getMutex();
    pPlayer->src_quality = quality;
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_QUALITY);
    return 1;
}

unsigned int get_src_quality(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 2;
    return pPlayer->src_quality;
}

void set_gain(AUDIO_PLAYER* pPlayer, float gain) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if (gain <= 0.00001)
        gain = 0.00001;
    if (gain > 100000)
        gain = 100000;
    getMutex();
    pPlayer->gain = gain;
    releaseMutex();
    send_notifications(pPlayer, NOTIFY_GAIN);
}

float get_gain(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 1.0;
    return pPlayer->gain;
}

void set_track_a(AUDIO_PLAYER* pPlayer, int track) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if (track < pPlayer->sf_info.channels) {
        getMutex();
        if (pPlayer->sf_info.channels == 1)
            pPlayer->track_a = 0;
        else
            pPlayer->track_a = track;
        releaseMutex();
    }
    set_position(pPlayer, get_position(pPlayer));
    send_notifications(pPlayer, NOTIFY_TRACK_A);
}

void set_track_b(AUDIO_PLAYER* pPlayer, int track) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if (track < pPlayer->sf_info.channels) {
        getMutex();
        if (pPlayer->sf_info.channels == 1)
            pPlayer->track_b = 0;
        else
            pPlayer->track_b = track;
        releaseMutex();
    }
    set_position(pPlayer, get_position(pPlayer));
    send_notifications(pPlayer, NOTIFY_TRACK_B);
}

int get_track_a(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->track_a;
}

int get_track_b(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->track_b;
}

void set_speed(AUDIO_PLAYER* pPlayer, float factor) {
    if (!pPlayer || factor < 0.25 || factor > 4.0)
        return;
    pPlayer->speed            = factor;
    pPlayer->time_ratio_dirty = true;
}

float get_speed(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return 0.0;
    return pPlayer->speed;
}

void set_pitch(AUDIO_PLAYER* pPlayer, float factor) {
    if (!pPlayer || factor < 0.25 || factor > 4.0)
        return;
    pPlayer->pitch            = factor;
    pPlayer->time_ratio_dirty = true;
}

float get_pitch(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return 0.0;
    return pPlayer->pitch;
}

void set_varispeed(AUDIO_PLAYER* pPlayer, float ratio) {
    if (!pPlayer || ratio < -32.0 || ratio > 32.0)
        return;

    // Check if moving into or through zone too small to reliably varispeed
    bool stop  = ((pPlayer->varispeed >= 0.1 && ratio < 0.1) || pPlayer->varispeed <= -0.1 && ratio > -0.1);
    // Check for scrubbing
    bool start = (pPlayer->play_state != PLAYING && fabs(pPlayer->varispeed) < 0.1 && fabs(ratio) >= 0.1);

    getMutex();
    pPlayer->varispeed        = ratio;
    pPlayer->time_ratio_dirty = true;
    pPlayer->file_read_status = SEEKING;
    releaseMutex();

    if (stop && pPlayer->play_state != STOPPED) {
        pPlayer->play_state = STOPPING;
        // send_notifications(pPlayer, NOTIFY_TRANSPORT);
    }
    if (start && g_jack_client && pPlayer->file_open == FILE_OPEN && pPlayer->play_state != PLAYING) {
        pPlayer->play_state = STARTING;
        // send_notifications(pPlayer, NOTIFY_TRANSPORT);
    }

    send_notifications(pPlayer, NOTIFY_VARISPEED);
}

float get_varispeed(AUDIO_PLAYER* pPlayer) {
    if (!pPlayer)
        return 1.0;
    return pPlayer->varispeed;
}

void set_buffer_size(AUDIO_PLAYER* pPlayer, unsigned int size) {
    if (pPlayer && pPlayer->file_open == FILE_CLOSED) {
        getMutex();
        pPlayer->input_buffer_size = size;
        releaseMutex();
    }
}

unsigned int get_buffer_size(AUDIO_PLAYER* pPlayer) {
    if (pPlayer)
        return pPlayer->input_buffer_size;
    return 0;
}

void set_buffer_count(AUDIO_PLAYER* pPlayer, unsigned int count) {
    if (pPlayer && pPlayer->file_open == FILE_CLOSED && count > 1) {
        getMutex();
        pPlayer->buffer_count = count;
        releaseMutex();
    }
}

unsigned int get_buffer_count(AUDIO_PLAYER* pPlayer) {
    if (pPlayer)
        return pPlayer->buffer_count;
    return 0;
}

void set_pos_notify_delta(AUDIO_PLAYER* pPlayer, float time) {
    if (pPlayer) {
        getMutex();
        pPlayer->pos_notify_delta = time;
        releaseMutex();
    }
}

/**** Global functions ***/

float get_file_duration(const char* filename) {
    SF_INFO info;
    info.format     = 0;
    info.samplerate = 0;
    SNDFILE* pFile  = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if (info.samplerate)
        return (float)info.frames / info.samplerate;
    return 0.0f;
}

int get_file_channels(const char* filename) {
    SF_INFO info;
    info.format     = 0;
    info.samplerate = 0;
    SNDFILE* pFile  = sf_open(filename, SFM_READ, &info);
    sf_close(pFile);
    if (info.samplerate)
        return info.channels;
    return 0;
}

const char* get_file_info(const char* filename, int type) {
    SF_INFO info;
    info.format        = 0;
    info.samplerate    = 0;
    SNDFILE* pFile     = sf_open(filename, SFM_READ, &info);
    const char* pValue = sf_get_string(pFile, type);
    if (pValue) {
        sf_close(pFile);
        return pValue;
    }
    sf_close(pFile);
    return "";
}

void enable_debug(int enable) {
    fprintf(stderr, "libaudioplayer setting debug mode %s\n", enable ? "on" : "off");
    g_debug = enable;
}

int is_debug() { return g_debug; }

unsigned int get_player_count() {
    return playerVector.players.size();
}
