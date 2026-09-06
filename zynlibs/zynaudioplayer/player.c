/*  Audio file player library for Zynthian
    Copyright (C) 2021-2026 Brian Walton <brian@riban.co.uk>
    License: LGPL V3
*/

#include "player.h"

#include <string.h>        // provides strcmp, memset
#include <fcntl.h>         // provides fcntl
#include <jack/jack.h>     // provides interface to JACK
#include <jack/midiport.h> // provides JACK MIDI interface
#include <math.h>          // provides pow, log, fabs, isinf
#include <pthread.h>       // provides multithreading
#include <stdio.h>         // provides printf
//#include <stdlib.h>        // provides exit
#include <unistd.h>        // provides usleep

// **** Global variables ****
jack_client_t* g_jack_client;
jack_port_t* g_jack_midi_in;
jack_nframes_t g_samplerate = 48000; // Playback samplerate set by jackd
uint8_t g_debug             = 0;
uint8_t g_removePlayerId    = 255;
char g_supported_codecs[1024];
uint32_t g_nextIndex        = 1;
cb_fn_t* g_cb_fn            = NULL;

struct AUDIO_PLAYER* g_players[MAX_PLAYERS];

// Declare local functions

#define DPRINTF(fmt, args...)                                                                                                                                  \
    if (g_debug)                                                                                                                                               \
    fprintf(stderr, fmt, ##args)

#define MIN(a, b) ((a) < (b) ? (a) : (b))

#define STRETCH_LOOKAHEAD_FRAMES 4096
#define STRETCH_POLL_USLEEP 1000

// *** Internal private (non-public) functions not exposed as external C functions (not declared in header) ***

inline struct AUDIO_PLAYER* get_player(uint8_t id) {
    if (id < MAX_PLAYERS)
        return g_players[id];
    return NULL;
}

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

void send_notifications(uint8_t id) {
    // Send dynamic notifications within non-realtime thread of changes to play_state, play_pos, loop & varispeed
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!g_cb_fn || !pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    uint8_t bSend = 0;
    if (pPlayer->play_state <= PLAYING && pPlayer->last_play_state != pPlayer->play_state) {
        pPlayer->last_play_state = pPlayer->play_state;
        bSend = 1;
    }
    if (pPlayer->last_position != pPlayer->play_pos_frames) {
        pPlayer->last_position = pPlayer->play_pos_frames;
        bSend = 1;
    }
    if (pPlayer->loop != pPlayer->last_loop) {
        pPlayer->last_loop = pPlayer->loop;
        bSend = 1;
    }
    if (pPlayer->varispeed != pPlayer->last_varispeed) {
        pPlayer->last_varispeed = pPlayer->varispeed;
        bSend = 1;
    }
    if (bSend)
        g_cb_fn(id, pPlayer->play_state != STOPPED, pPlayer->loop, (float)(pPlayer->play_pos_frames) / g_samplerate, pPlayer->varispeed);
}

// Detects whether the effective playback direction has changed since we last read or
// stretched audio and, if so, flushes the raw/stretch pipeline so newly-read audio
// reflects the new direction.
static void handle_direction_change(struct AUDIO_PLAYER* pPlayer, uint8_t* pLastBReverse, SNDFILE* pFile, SRC_STATE* pSrcState, size_t* pNUnusedFrames,
                                     uint8_t* pFinalSignalled) {
    uint8_t bReverse = (pPlayer->varispeed < 0.0);
    if (bReverse == *pLastBReverse)
        return;
    jack_ringbuffer_reset(pPlayer->ringbuffer_a);
    jack_ringbuffer_reset(pPlayer->ringbuffer_b);
    src_reset(pSrcState);
    rubberband_reset(pPlayer->rb_state);
    *pNUnusedFrames  = 0;
    *pFinalSignalled = 0;
    sf_count_t pos = sf_seek(pFile, pPlayer->play_pos_frames / pPlayer->src_ratio, SEEK_SET);
    if (pos >= 0)
        pPlayer->file_read_pos = pos;
    *pLastBReverse = bReverse;
}

// Thread function to open file, stream content to ring buffers AND time-stretch it.
void* file_thread_fn(void* param) {
    uint8_t id = *(uint8_t*)param;
    struct AUDIO_PLAYER* pPlayer = get_player(id);

    pPlayer->sf_info.format = 0; // This triggers sf_open to populate info structure
    SRC_DATA srcData;
    size_t nMaxFrames;        // Maximum quantity of frames that may be read from file
    size_t nUnusedFrames = 0; // Quantity of frames in input buffer not used by SRC
    // Open the sound file (libsoundfile handles CODEC conversion)
    SNDFILE* pFile = sf_open(pPlayer->filename, SFM_READ, &pPlayer->sf_info);
    if (!pFile || pPlayer->sf_info.channels < 1) {
        atomic_store_explicit(&pPlayer->file_open, FILE_CLOSED, memory_order_relaxed);
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename, sf_strerror(pFile));
    }
    if (pPlayer->sf_info.channels < 0) {
        atomic_store_explicit(&pPlayer->file_open, FILE_CLOSED, memory_order_relaxed);
        fprintf(stderr, "libaudioplayer error: file %s has no tracks\n", pPlayer->filename);
        int nError = sf_close(pFile);
        if (nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
    }
    if (pPlayer->file_open) {
        // Create rubberband stretcher
        RubberBandOptions options =
            RubberBandOptionProcessRealTime |
            RubberBandOptionEngineFaster |
            RubberBandOptionChannelsTogether |
            RubberBandOptionThreadingNever;
        pPlayer->rb_state = rubberband_new(
            g_samplerate,
            2,
            options,
            1.0,
            1.0
        );
        rubberband_set_max_process_size(pPlayer->rb_state, STRETCH_BUF_SIZE);

        // Reset player parameters
        pPlayer->gain = 1.0;
        pPlayer->crop_start = 0;
        pPlayer->crop_end = pPlayer->sf_info.frames;
        atomic_store_explicit(&pPlayer->file_read_status, SEEKING, memory_order_relaxed);
        pPlayer->src_ratio = (float)g_samplerate / pPlayer->sf_info.samplerate;
        if (pPlayer->src_ratio < 0.1)
            pPlayer->src_ratio = 1.0;
        srcData.src_ratio = pPlayer->src_ratio;
        pPlayer->output_buffer_size = pPlayer->src_ratio * pPlayer->input_buffer_size;

        pPlayer->ringbuffer_a = jack_ringbuffer_create(MAX_VARISPEED * pPlayer->output_buffer_size * pPlayer->buffer_count * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_a);
        pPlayer->ringbuffer_b = jack_ringbuffer_create(MAX_VARISPEED * pPlayer->output_buffer_size * pPlayer->buffer_count * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_b);

        pPlayer->ringbuffer_out_a = jack_ringbuffer_create(STRETCH_LOOKAHEAD_FRAMES * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_out_a);
        pPlayer->ringbuffer_out_b = jack_ringbuffer_create(STRETCH_LOOKAHEAD_FRAMES * sizeof(float));
        jack_ringbuffer_mlock(pPlayer->ringbuffer_out_b);

        atomic_store_explicit(&pPlayer->file_open, FILE_OPEN, memory_order_relaxed);

        // Initialise samplerate converter
        float pBufferIn[pPlayer->input_buffer_size * pPlayer->sf_info.channels];   // Buffer used to read sample data from file
        float pBufferOut[pPlayer->output_buffer_size * pPlayer->sf_info.channels]; // Buffer used to write converted sample data to
        float pBufferRev[pPlayer->input_buffer_size * pPlayer->sf_info.channels]; // Buffer used to write reverse playback sample data to

        // Local buffers for the time-stretch stage (formerly declared in on_jack_process).
        float pInA[STRETCH_BUF_SIZE];
        float pInB[STRETCH_BUF_SIZE];
        float pStretchOutA[STRETCH_BUF_SIZE];
        float pStretchOutB[STRETCH_BUF_SIZE];
        float* stretch_input_buffers[]  = {pInA, pInB};
        float* stretch_output_buffers[] = {pStretchOutA, pStretchOutB};

        srcData.data_in         = pBufferIn;
        srcData.data_out        = pBufferOut;
        srcData.output_frames   = pPlayer->output_buffer_size;
        pPlayer->crop_end_src   = pPlayer->crop_end * pPlayer->src_ratio;
        pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
        int nError;
        SRC_STATE* pSrcState = src_new(pPlayer->src_quality, pPlayer->sf_info.channels, &nError);
        if (!pSrcState) {
            fprintf(stderr, "Failed to create a samplerate converter: %d\n", nError);
            atomic_store_explicit(&pPlayer->file_open, FILE_CLOSED, memory_order_relaxed);
        }

        DPRINTF("Opened file '%s' with samplerate %u, frames: %f\n", pPlayer->filename, pPlayer->sf_info.samplerate, pPlayer->sf_info.frames);

        int64_t pipelinePos = (int64_t)pPlayer->play_pos_frames;
        uint8_t lastBReverse = (pPlayer->varispeed < 0.0);
        uint8_t finalSignalled = 0;

        atomic_store_explicit(&pPlayer->stream_ended, 0, memory_order_relaxed);

        while (pPlayer->file_open == FILE_OPEN) {
            if (pPlayer->file_read_status == SEEKING) {
                // Main thread has signalled seek within file
                jack_ringbuffer_reset(pPlayer->ringbuffer_a);
                jack_ringbuffer_reset(pPlayer->ringbuffer_b);
                jack_ringbuffer_reset(pPlayer->ringbuffer_out_a);
                jack_ringbuffer_reset(pPlayer->ringbuffer_out_b);
                atomic_store_explicit(&pPlayer->stream_ended, 0, memory_order_relaxed);
                // Fresh, disjoint stream of position markers starts now
                atomic_store_explicit(&pPlayer->pos_marker_wr, 0, memory_order_relaxed);
                atomic_store_explicit(&pPlayer->pos_marker_rd, 0, memory_order_relaxed);
                pipelinePos  = (int64_t)pPlayer->play_pos_frames; // play_pos_frames here is the caller's seek target
                lastBReverse = (pPlayer->varispeed < 0.0);        // re-sync - this reset already accounts for the current direction
                sf_count_t pos = sf_seek(pFile, pPlayer->play_pos_frames / pPlayer->src_ratio, SEEK_SET);
                if (pos >= 0)
                    pPlayer->file_read_pos = pos;
                // DPRINTF("Seeking to %u frames (%fs) src ratio=%f\n", nNewPos, get_position(pPlayer), srcData.src_ratio);
                atomic_store_explicit(&pPlayer->file_read_status, LOADING, memory_order_relaxed);
                src_reset(pSrcState);
                rubberband_reset(pPlayer->rb_state); // Was signalled to the RT thread via g_reset_rb; now done directly, same thread
                nUnusedFrames        = 0;
                srcData.end_of_input = 0;
                finalSignalled       = 0;
            } else if (pPlayer->file_read_status == LOOPING) {
                // Reached loop end point and need to read from loop marker
                sf_count_t pos;
                if (pPlayer->varispeed < 0.0)
                    pos = sf_seek(pFile, pPlayer->crop_end, SEEK_SET);
                else
                    pos = sf_seek(pFile, pPlayer->crop_start, SEEK_SET);
                if (pos >= 0)
                    pPlayer->file_read_pos = pos;
                atomic_store_explicit(&pPlayer->file_read_status, LOADING, memory_order_relaxed);
                src_reset(pSrcState);
                srcData.end_of_input = 0;
                nUnusedFrames        = 0;
            }

            if (pPlayer->file_read_status == WAITING)
                atomic_store_explicit(&pPlayer->file_read_status, LOADING, memory_order_relaxed);

            while (pPlayer->file_read_status == LOADING) {
                handle_direction_change(pPlayer, &lastBReverse, pFile, pSrcState, &nUnusedFrames, &finalSignalled);

                int nFramesRead = 0;
                // Load block of data from file to SRC or output buffer
                nMaxFrames = pPlayer->input_buffer_size - nUnusedFrames;

                if (jack_ringbuffer_write_space(pPlayer->ringbuffer_a) >= nMaxFrames * sizeof(float) * pPlayer->src_ratio &&
                    jack_ringbuffer_write_space(pPlayer->ringbuffer_b) >= nMaxFrames * sizeof(float) * pPlayer->src_ratio) {

                    uint8_t bReverse = (pPlayer->varispeed < 0.0);
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
                        size_t nTotalValid = nUnusedFrames + nFramesRead;
                        // No SRC required so populate SRC output buffer directly
                        if (bReverse) {
                            if (pPlayer->file_read_pos > nMaxFrames)
                                pPlayer->file_read_pos -= nMaxFrames;
                            else {
                                nMaxFrames = pPlayer->file_read_pos;
                                pPlayer->file_read_pos = 0;
                            }
                            // Move to start of audio chunk
                            sf_count_t pos = sf_seek(pFile, pPlayer->file_read_pos, SEEK_SET);
                            if (pos >= 0) {
                                // Read audio chunk
                                nFramesRead = sf_readf_float(pFile, pBufferRev, nMaxFrames);
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
                                size_t wPos = nUnusedFrames * pPlayer->sf_info.channels;
                                for (size_t i = nFramesRead; i > 0; --i) {
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
                            size_t nTotalValid = nUnusedFrames + nFramesRead;
                            srcData.input_frames = nTotalValid;
                            int rc = src_process(pSrcState, &srcData);
                            if (rc) {
                                DPRINTF("SRC failed with error %d, %lu frames generated\n", nFramesRead, srcData.output_frames_gen);
                            } else {
                                DPRINTF("SRC suceeded - %lu frames generated, %lu frames used, %lu frames unused\n", srcData.output_frames_gen,
                                        srcData.input_frames_used, nUnusedFrames);
                                nUnusedFrames = nTotalValid - srcData.input_frames_used;
                                nFramesRead   = srcData.output_frames_gen;
                                // Shift unused samples to start of buffer
                                memcpy(pBufferIn, pBufferIn + srcData.input_frames_used * pPlayer->sf_info.channels,
                                       nUnusedFrames * sizeof(float) * pPlayer->sf_info.channels);
                            }
                        } else {
                            // DPRINTF("No SRC, read %u frames\n", nFramesRead);
                        }
                        // Demux samples and populate raw (pre-stretch) ring buffers
                        for (size_t frame = 0; frame < nFramesRead; ++frame) {
                            float fA = 0.0f, fB = 0.0f;
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
                        atomic_store_explicit(&pPlayer->file_read_status, LOOPING, memory_order_relaxed);
                        // srcData.end_of_input = 1;
                        DPRINTF("libzynaudioplayer read to loop point in input file - setting loading status to looping\n");
                    } else {
                        // End of file
                        atomic_store_explicit(&pPlayer->file_read_status, IDLE, memory_order_relaxed);
                        srcData.end_of_input = 1;
                        DPRINTF("libzynaudioplayer read to end of input file - setting loading status to IDLE\n");
                    }
                } else {
                    atomic_store_explicit(&pPlayer->file_read_status, WAITING, memory_order_relaxed);
                }
            }

            uint8_t bReverseStretch = (pPlayer->varispeed < 0.0);
            for (;;) {
                if (pPlayer->file_read_status == SEEKING)
                    break;

                // While genuinely paused, don't commit any more stretched audio into
                // ringbuffer_out. varispeed reads as 0.0 (i.e. "forward") the whole time
                // we're stopped, so without this the pipeline would quietly keep
                // pre-generating and queuing up forward-direction audio in that buffer -
                // and since handle_direction_change() deliberately leaves ringbuffer_out
                // alone (to keep live reversals during active playback gapless), that
                // stale forward content would just play first, as a burst, before
                // whatever direction is actually requested on resume. Reading/feeding can
                // continue harmlessly (handle_direction_change() flushes it if direction
                // changes anyway); only the retrieve-and-commit step needs to pause.
                if (pPlayer->play_state == STOPPED)
                    break;

                handle_direction_change(pPlayer, &lastBReverse, pFile, pSrcState, &nUnusedFrames, &finalSignalled);

                if (pPlayer->time_ratio_dirty) {
                    float abs_varispeed = fabs(pPlayer->varispeed);
                    float speed = pPlayer->speed;
                    float pitch = pPlayer ->pitch;
                    if (abs_varispeed > MIN_VARISPEED) {
                        speed *= abs_varispeed;
                        pitch *= abs_varispeed;
                    }
                    rubberband_set_pitch_scale(pPlayer->rb_state, pitch);
                    rubberband_set_time_ratio(pPlayer->rb_state, 1.0 / speed);
                    atomic_store_explicit(&pPlayer->time_ratio_dirty, 0, memory_order_relaxed);
                    bReverseStretch = (pPlayer->varispeed < 0.0);
                }

                int available = rubberband_available(pPlayer->rb_state);
                if (available < 0)
                    available = 0;
                size_t outSpace = MIN(jack_ringbuffer_write_space(pPlayer->ringbuffer_out_a), jack_ringbuffer_write_space(pPlayer->ringbuffer_out_b)) /
                                  sizeof(float);
                uint32_t markerWr = atomic_load_explicit(&pPlayer->pos_marker_wr, memory_order_relaxed);
                uint32_t markerRd = atomic_load_explicit(&pPlayer->pos_marker_rd, memory_order_acquire);
                uint8_t markerQueueFull = (markerWr - markerRd) >= POS_MARKER_QUEUE_SIZE;

                if ((size_t)available > 0 && outSpace > 0 && !markerQueueFull) {
                    size_t nRetrieve = MIN((size_t)available, MIN(outSpace, (size_t)STRETCH_BUF_SIZE));
                    size_t got = rubberband_retrieve(pPlayer->rb_state, stretch_output_buffers, nRetrieve);
                    if (got > 0) {
                        jack_ringbuffer_write(pPlayer->ringbuffer_out_a, (const char*)pStretchOutA, got * sizeof(float));
                        jack_ringbuffer_write(pPlayer->ringbuffer_out_b, (const char*)pStretchOutB, got * sizeof(float));
                        // Tag this batch with the pipeline's current source-domain position.
                        pos_marker_t* m = &pPlayer->pos_markers[markerWr % POS_MARKER_QUEUE_SIZE];
                        m->frames   = (uint32_t)got;
                        m->position = (uint32_t)pipelinePos;
                        atomic_store_explicit(&pPlayer->pos_marker_wr, markerWr + 1, memory_order_release);
                    }
                    continue; // there may be more ready - check again before trying to feed
                }
                if (outSpace == 0 || markerQueueFull)
                    break;

                size_t framesReq = MIN(rubberband_get_samples_required(pPlayer->rb_state), (size_t)STRETCH_BUF_SIZE);
                size_t nInBytes = MIN(jack_ringbuffer_read_space(pPlayer->ringbuffer_a), jack_ringbuffer_read_space(pPlayer->ringbuffer_b));
                nInBytes -= nInBytes % sizeof(float);
                nInBytes = MIN(nInBytes, framesReq * sizeof(float));
                if (nInBytes == 0) {
                    if (!pPlayer->loop && pPlayer->file_read_status == IDLE && !finalSignalled) {
                        rubberband_process(pPlayer->rb_state, (const float* const*)stretch_input_buffers, 0, 1);
                        finalSignalled = 1;
                        continue;
                    }
                    break;
                }

                size_t nRead = jack_ringbuffer_read(pPlayer->ringbuffer_a, (char*)pInA, nInBytes) / sizeof(float);
                jack_ringbuffer_read(pPlayer->ringbuffer_b, (char*)pInB, nRead * sizeof(float));
                rubberband_process(pPlayer->rb_state, (const float* const*)stretch_input_buffers, nRead, 0);

                pipelinePos += bReverseStretch ? -(int64_t)nRead : (int64_t)nRead;
                if (pPlayer->loop == 1) {
                    int64_t cropStart = (int64_t)pPlayer->crop_start_src;
                    int64_t cropEnd   = (int64_t)pPlayer->crop_end_src;
                    if (bReverseStretch) {
                        if (pipelinePos <= cropStart) {
                            int64_t i = cropStart - pipelinePos;
                            int64_t span = cropEnd - cropStart;
                            if (span > 0)
                                i %= span;
                            pipelinePos = cropEnd - i;
                        }
                    } else if (pipelinePos >= cropEnd) {
                        if (cropEnd > 0)
                            pipelinePos %= cropEnd;
                        pipelinePos += cropStart;
                    }
                }
            }

            {
                uint32_t markerWr = atomic_load_explicit(&pPlayer->pos_marker_wr, memory_order_relaxed);
                uint32_t markerRd = atomic_load_explicit(&pPlayer->pos_marker_rd, memory_order_relaxed);
                uint8_t markerQueueNearlyFull = (markerWr - markerRd) >= POS_MARKER_QUEUE_SIZE - 1;
                size_t lowWaterBytes = (STRETCH_LOOKAHEAD_FRAMES / 4) * sizeof(float);
                if ((jack_ringbuffer_write_space(pPlayer->ringbuffer_out_a) < lowWaterBytes ||
                     jack_ringbuffer_write_space(pPlayer->ringbuffer_out_b) < lowWaterBytes || markerQueueNearlyFull) &&
                    pPlayer->file_read_status == LOADING)
                    atomic_store_explicit(&pPlayer->file_read_status, WAITING, memory_order_relaxed);
            }

            uint8_t ended = !pPlayer->loop && pPlayer->file_read_status == IDLE &&
                            jack_ringbuffer_read_space(pPlayer->ringbuffer_a) == 0 &&
                            jack_ringbuffer_read_space(pPlayer->ringbuffer_b) == 0 &&
                            rubberband_available(pPlayer->rb_state) <= 0;
            atomic_store_explicit(&pPlayer->stream_ended, ended, memory_order_relaxed);
            send_notifications(id);
            usleep(STRETCH_POLL_USLEEP);
        }

        rubberband_delete(pPlayer->rb_state);
        jack_ringbuffer_free(pPlayer->ringbuffer_a);
        jack_ringbuffer_free(pPlayer->ringbuffer_b);
        jack_ringbuffer_free(pPlayer->ringbuffer_out_a);
        jack_ringbuffer_free(pPlayer->ringbuffer_out_b);
        pPlayer->rb_state = NULL;
        src_delete(pSrcState);
    }
    if (pFile) {
        int nError = sf_close(pFile);
        if (nError != 0)
            fprintf(stderr, "libaudioplayer error: failed to close file with error code %d\n", nError);
        else
            pPlayer->filename[0] = '\0';
    }
    atomic_store_explicit(&pPlayer->play_pos_frames, 0, memory_order_relaxed);

    DPRINTF("File reader thread ended\n");
    pthread_exit(NULL);
}

// Handle JACK process callback
int on_jack_process(jack_nframes_t nFrames, void* arg) {

    for (uint8_t id = 0; id < MAX_PLAYERS; ++id) {
        struct AUDIO_PLAYER* pPlayer = g_players[id];
        if (!pPlayer || pPlayer->file_open != FILE_OPEN)
            continue;

        size_t a_count = 0; // Quantity of frames delivered to JACK this cycle
        jack_default_audio_sample_t* pOutA = jack_port_get_buffer(pPlayer->jack_out_a, nFrames);
        jack_default_audio_sample_t* pOutB = jack_port_get_buffer(pPlayer->jack_out_b, nFrames);
        memset(pOutA, 0, nFrames * sizeof(float));
        memset(pOutB, 0, nFrames * sizeof(float));

        if (pPlayer->play_state == STARTING && pPlayer->file_read_status != SEEKING) {
            atomic_store_explicit(&pPlayer->play_state, PLAYING, memory_order_relaxed);
            pPlayer->pos_marker_remaining      = 0;
            pPlayer->pos_marker_total          = 0;
            pPlayer->pos_marker_start_position = pPlayer->play_pos_frames;
            pPlayer->pos_marker_cached_position = pPlayer->play_pos_frames;
        }

        if ((pPlayer->play_state == PLAYING || pPlayer->play_state == STOPPING) && pPlayer->file_read_status != SEEKING) {
            size_t nBytes = MIN(jack_ringbuffer_read_space(pPlayer->ringbuffer_out_a), jack_ringbuffer_read_space(pPlayer->ringbuffer_out_b));
            nBytes -= nBytes % sizeof(float);
            nBytes = MIN(nBytes, (size_t)nFrames * sizeof(float));
            a_count = jack_ringbuffer_read(pPlayer->ringbuffer_out_a, (char*)pOutA, nBytes) / sizeof(float);
            jack_ringbuffer_read(pPlayer->ringbuffer_out_b, (char*)pOutB, a_count * sizeof(float));

            for (size_t offset = 0; offset < a_count; ++offset) {
                // Set gain
                pOutA[offset] *= pPlayer->gain;
                pOutB[offset] *= pPlayer->gain;
            }

            // Advance the PUBLIC play position using position markers
            size_t toAccount = a_count;
            while (toAccount > 0) {
                if (pPlayer->pos_marker_remaining == 0) {
                    uint32_t rd = atomic_load_explicit(&pPlayer->pos_marker_rd, memory_order_relaxed);
                    uint32_t wr = atomic_load_explicit(&pPlayer->pos_marker_wr, memory_order_acquire);
                    if (rd == wr)
                        break;
                    pos_marker_t* m = &pPlayer->pos_markers[rd % POS_MARKER_QUEUE_SIZE];
                    pPlayer->pos_marker_start_position   = pPlayer->pos_marker_cached_position;
                    pPlayer->pos_marker_remaining        = m->frames;
                    pPlayer->pos_marker_total            = m->frames;
                    pPlayer->pos_marker_cached_position  = m->position;
                }
                size_t take = MIN(toAccount, (size_t)pPlayer->pos_marker_remaining);
                pPlayer->pos_marker_remaining -= (uint32_t)take;
                toAccount -= take;

                if (pPlayer->pos_marker_total > 0) {
                    uint32_t consumed    = pPlayer->pos_marker_total - pPlayer->pos_marker_remaining;
                    int64_t  startPos    = (int64_t)pPlayer->pos_marker_start_position;
                    int64_t  endPos      = (int64_t)pPlayer->pos_marker_cached_position;
                    int64_t  interpolated = startPos + (endPos - startPos) * (int64_t)consumed / (int64_t)pPlayer->pos_marker_total;
                    atomic_store_explicit(&pPlayer->play_pos_frames, (uint32_t)interpolated, memory_order_relaxed);
                }

                if (pPlayer->pos_marker_remaining == 0) {
                    uint32_t rd = atomic_load_explicit(&pPlayer->pos_marker_rd, memory_order_relaxed);
                    atomic_store_explicit(&pPlayer->pos_marker_rd, rd + 1, memory_order_release);
                }
            }

            if (pPlayer->play_state == PLAYING && a_count < nFrames && pPlayer->stream_ended && !pPlayer->loop)
                atomic_store_explicit(&pPlayer->play_state, STOPPING, memory_order_relaxed);
        }

        if (pPlayer->play_state == STOPPING) {
            // Soft mute (not perfect for short last period of file but better than nowt). Adds a few ms of delay.
            for (size_t offset = 0; offset < a_count; ++offset) {
                pOutA[offset] *= 1.0 - ((jack_default_audio_sample_t)offset / a_count);
                pOutB[offset] *= 1.0 - ((jack_default_audio_sample_t)offset / a_count);
            }
            atomic_store_explicit(&pPlayer->varispeed, 0.0, memory_order_relaxed);
            atomic_store_explicit(&pPlayer->play_state, STOPPED, memory_order_relaxed);
            atomic_store_explicit(&pPlayer->file_read_status, SEEKING, memory_order_relaxed);
            DPRINTF("libzynaudioplayer: Stopped. Used %u frames from %u in buffer to soft mute (fade). Silencing remaining %u frames (%u bytes)\n", a_count,
                    nFrames, nFrames - a_count, (nFrames - a_count) * sizeof(jack_default_audio_sample_t));
        }
    }

    // Remove player
    if (g_removePlayerId != 255) {
        g_players[g_removePlayerId] = NULL;
        g_removePlayerId = 255;
    }

    return 0;
}

// Handle JACK samplerate callback
int on_jack_samplerate(jack_nframes_t nFrames, void* pArgs) {
    DPRINTF("libzynaudioplayer: Jack sample rate: %u\n", nFrames);
    if (nFrames)
        g_samplerate = nFrames;
    return 0;
}

static void lib_init() {
    for (uint8_t id = 0; id < MAX_PLAYERS; ++id)
        g_players[id] = NULL;
    fprintf(stderr, "Loaded libzynaudioplayer using %s\n", sf_version_string());
}

// Public functions declared in header and exported as C lib

uint8_t init(cb_fn_t* cb_fn) {
    if (g_jack_client)
        return 1;
    jack_status_t nStatus;
    jack_options_t nOptions = JackNoStartServer;

    if ((g_jack_client = jack_client_open("audioplayer", nOptions, &nStatus)) == 0) {
        fprintf(stderr, "libaudioplayer error: failed to start jack client: %d\n", nStatus);
        return 0;
    }

    // Register the callback to process audio and MIDI
    jack_set_process_callback(g_jack_client, on_jack_process, 0);
    jack_set_sample_rate_callback(g_jack_client, on_jack_samplerate, 0);

    if (jack_activate(g_jack_client)) {
        fprintf(stderr, "libaudioplayer error: cannot activate client\n");
        return 0;
    }

    g_samplerate = jack_get_sample_rate(g_jack_client);
    if (g_samplerate < 8000)
        g_samplerate = 8000;
    g_cb_fn = cb_fn;
    return 1;
}

// Player instance functions take 'id' param to identify player instance 

uint8_t load(uint8_t id, const char* filename) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return 0;
    unload(id);
    strncpy(pPlayer->filename, filename, MAX_FILENAME - 1);

    atomic_store_explicit(&pPlayer->file_open, FILE_OPENING, memory_order_relaxed);
    if (pthread_create(&pPlayer->file_thread, NULL, file_thread_fn, &id)) {
        fprintf(stderr, "libzynaudioplayer error: failed to create file reading thread\n");
        unload(id);
        return 0;
    }
    while (pPlayer->file_open == FILE_OPENING)
        usleep(1000); //!@todo Optimise wait for file open

    return (pPlayer->file_open == FILE_OPEN);
}

void unload(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open == FILE_CLOSED)
        return;
    stop_playback(id);
    while (pPlayer->play_state != STOPPED)
        usleep(1000);
    atomic_store_explicit(&pPlayer->file_open, FILE_CLOSED, memory_order_relaxed);
    pthread_join(pPlayer->file_thread, NULL);
}

uint8_t save(uint8_t id, const char* filename) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;

    // Reload any players that have the new filename loaded
    uint8_t overwrite[MAX_PLAYERS];
    for (size_t i = 0; i < MAX_PLAYERS; ++i) {
        struct AUDIO_PLAYER* player = g_players[i];
        if (player && strcmp(player->filename, filename) == 0) {
            unload(id);
            overwrite[i] = 1;
        } else
            overwrite[i] = 0;
    }
    overwrite[id] = 1;

    SF_INFO sfinfo;
    sfinfo.format   = 0; // This triggers sf_open to populate info structure

    SNDFILE* infile = sf_open(pPlayer->filename, SFM_READ, &sfinfo);
    if (!infile || sfinfo.channels < 1) {
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", pPlayer->filename, sf_strerror(infile));
        return 0;
    }

    sfinfo.format = SF_FORMAT_WAV | SF_FORMAT_FLOAT;

    if (!sf_format_check(&sfinfo)) {
        sf_close(infile);
        fprintf(stderr, "Invalid encoding\n");
        return 0;
    }

    SNDFILE* outfile = sf_open(filename, SFM_WRITE, &sfinfo);
    if (!outfile) {
        fprintf(stderr, "libaudioplayer error: failed to open file %s: %s\n", filename, sf_strerror(outfile));
        sf_close(infile);
        return 0;
    }

    int32_t count = 0;

    float buffer[1024 * sfinfo.channels];
    sf_count_t pos = sf_seek(infile, pPlayer->crop_start, SEEK_SET);
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

    for (uint8_t i = 0; i < MAX_PLAYERS; ++i) {
        if (overwrite[i])
            load(i, filename);
    }
    return 1;
}

const char* get_filename(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return "";
    return pPlayer->filename;
}

float get_duration(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer && pPlayer->file_open == FILE_OPEN && pPlayer->sf_info.samplerate)
        return (float)pPlayer->sf_info.frames / pPlayer->sf_info.samplerate;
    return 0.0f;
}

void set_position(uint8_t id, float time) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    sf_count_t frames = time * g_samplerate;
    if (frames > pPlayer->crop_end_src)
        frames = pPlayer->crop_end_src;
    else if (frames < pPlayer->crop_start_src)
        frames = pPlayer->crop_start_src;
    atomic_store_explicit(&pPlayer->play_pos_frames, frames, memory_order_relaxed);
    atomic_store_explicit(&pPlayer->file_read_status, SEEKING, memory_order_relaxed);
    DPRINTF("New position requested, setting loading status to SEEKING\n");
}

float get_position(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer && pPlayer->file_open == FILE_OPEN)
        return (float)(pPlayer->play_pos_frames) / g_samplerate;
    return 0.0;
}

void enable_loop(uint8_t id, uint8_t nLoop) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || nLoop == pPlayer->loop)
        return;
    pPlayer->loop = nLoop;
    if (nLoop && pPlayer->file_read_status == IDLE) {
        // Reader may have already reached true end-of-file and given up before loop was
        // enabled - kick it back into action.
        atomic_store_explicit(&pPlayer->file_read_status, LOOPING, memory_order_relaxed);
    } else if (!nLoop && pPlayer->file_open == FILE_OPEN) {
        // Disabling loop mid-playback: while looping, the reader keeps re-reading the same
        // crop_start..crop_end region over and over as far ahead as the deep raw buffer
        // allows, so that buffer can already hold several EXTRA loop iterations' worth of
        // audio queued up. Flipping the flag only changes what happens on FUTURE reads - it
        // doesn't discard any of that already-buffered backlog, so playback would keep
        // looping through whatever was already queued for potentially a long time before
        // the reader's own next encounter with crop_end (now correctly non-looping) takes
        // effect on fresh material - which is what made this look ignored. Force a reseek
        // from the current position instead, discarding the stale backlog and resuming
        // immediately under the new, non-looping bound.
        atomic_store_explicit(&pPlayer->file_read_status, SEEKING, memory_order_relaxed);
    }
}

uint8_t is_loop(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return (pPlayer->loop);
}

void set_crop_start_time(uint8_t id, float time) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return;
    if (time < 0.0)
        time = 0.0;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if (frames >= pPlayer->crop_end)
        frames = pPlayer->crop_end - 1;
    pPlayer->crop_start = frames;
    pPlayer->crop_start_src = pPlayer->crop_start * pPlayer->src_ratio;
    if (pPlayer->play_pos_frames < pPlayer->crop_start_src)
        atomic_store_explicit(&pPlayer->play_pos_frames, pPlayer->crop_start_src, memory_order_relaxed);
    atomic_store_explicit(&pPlayer->file_read_status, SEEKING, memory_order_relaxed);
}

float get_crop_start_time(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->crop_start) / pPlayer->sf_info.samplerate;
}

void set_crop_end_time(uint8_t id, float time) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return;
    jack_nframes_t frames = pPlayer->sf_info.samplerate * time;
    if (frames < pPlayer->crop_start)
        frames = pPlayer->crop_start + 1;
    if (frames > pPlayer->sf_info.frames)
        frames = pPlayer->sf_info.frames;
    pPlayer->crop_end = frames;
    pPlayer->crop_end_src = frames * pPlayer->src_ratio;
    if (pPlayer->play_pos_frames >= pPlayer->crop_end_src)
        atomic_store_explicit(&pPlayer->play_pos_frames, pPlayer->crop_end_src, memory_order_relaxed);
    atomic_store_explicit(&pPlayer->file_read_status, SEEKING, memory_order_relaxed);
}

float get_crop_end_time(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->sf_info.samplerate == 0)
        return 0.0;
    return (float)(pPlayer->crop_end) / pPlayer->sf_info.samplerate;
}

void start_playback(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer && g_jack_client && pPlayer->file_open == FILE_OPEN && pPlayer->play_state != PLAYING) {
        if (pPlayer->play_varispeed < 0.0 && pPlayer->play_pos_frames <= pPlayer->crop_start_src)
            pPlayer->play_varispeed = 1.0;
        atomic_store_explicit(&pPlayer->varispeed, pPlayer->play_varispeed, memory_order_relaxed);
        atomic_store_explicit(&pPlayer->play_state, STARTING, memory_order_relaxed);
        atomic_store_explicit(&pPlayer->time_ratio_dirty, 1, memory_order_relaxed);
    }
}

void stop_playback(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer && pPlayer->play_state != STOPPED)
        atomic_store_explicit(&pPlayer->play_state, STOPPING, memory_order_relaxed);
}

uint8_t get_playback_state(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return STOPPED;
    return pPlayer->play_state;
}

int get_samplerate(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return g_samplerate;
    return pPlayer->sf_info.samplerate;
}

const char* get_codec(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return "NONE";
    static char buffer[20];
    const char* sType    = NULL;
    const char* sSubtype = NULL;

    SF_FORMAT_INFO format_info;
    format_info.format = pPlayer->sf_info.format;
    if (sf_command(NULL, SFC_GET_FORMAT_INFO, &format_info, sizeof(format_info)))
        return "UNKNOWN";
    return format_info.name;
}

int get_channels(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.channels;
}

int get_frames(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.frames;
}

int get_format(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->sf_info.format;
}

void stop() {
    g_cb_fn = NULL;
    if (g_jack_client)
        jack_deactivate(g_jack_client);
    jack_client_close(g_jack_client);
    g_jack_client = NULL;
}

static void lib_exit(void) {
    fprintf(stderr, "libzynaudioplayer exiting\n");
}

uint8_t add_player() {
    uint8_t id = 0;
    while (g_players[id]) {
        if(++id >= MAX_PLAYERS)
            return 255;
    }
    struct AUDIO_PLAYER* pPlayer = malloc(sizeof(struct AUDIO_PLAYER));
    if (!pPlayer)
        return 255;
    memset(pPlayer, 0, sizeof(struct AUDIO_PLAYER));
    pPlayer->gain = 1.0;
    pPlayer->track_a = -1;
    pPlayer->track_b = -1;
    pPlayer->input_buffer_size = 48000;
    pPlayer->buffer_count = 5;
    pPlayer->src_quality = SRC_SINC_FASTEST;
    pPlayer->src_ratio = 1.0;
    pPlayer->varispeed = 1.0;
    pPlayer->play_varispeed = 1.0;
    pPlayer->speed = 1.0;
    pPlayer->pitch = 1.0;
    pPlayer->crop_end = pPlayer->input_buffer_size;
    pPlayer->crop_end_src = pPlayer->crop_end;
    g_players[id] = pPlayer;

    // Create audio output ports
    char port_name[8];

    sprintf(port_name, "out_%02da", id);
    if (!(pPlayer->jack_out_a = jack_port_register(g_jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port %s\n", port_name);
        return 255;
    }
    sprintf(port_name, "out_%02db", id);
    if (!(pPlayer->jack_out_b = jack_port_register(g_jack_client, port_name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0))) {
        fprintf(stderr, "libaudioplayer error: cannot register audio output port %s\n", port_name);
        jack_port_unregister(g_jack_client, pPlayer->jack_out_a);
        return 255;
    }
    DPRINTF("libaudioplayer player %u registered JACK audio output ports %u & %u\n", pPlayer, pPlayer->jack_out_a, pPlayer->jack_out_b);
    return id;
}

void remove_player(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return;
    unload(id);
    if (jack_port_unregister(g_jack_client, pPlayer->jack_out_a)) {
        fprintf(stderr, "libaudioplayer error: player %u (%u) cannot unregister audio output port A %02d\n", id, pPlayer, pPlayer->jack_out_a);
    }
    if (jack_port_unregister(g_jack_client, pPlayer->jack_out_b)) {
        fprintf(stderr, "libaudioplayer error: player %u (%u) cannot unregister audio output port B %02d\n", id, pPlayer, pPlayer->jack_out_b);
    }
    g_removePlayerId = id;
    while (g_removePlayerId != 255)
        usleep(1000); // Wait for process cycle to complete
    free(pPlayer);
}

const char* get_jack_client_name() {
    if (g_jack_client)
        return jack_get_client_name(g_jack_client);
    return "";
}

uint8_t set_src_quality(uint8_t id, unsigned int quality) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    if (quality > SRC_LINEAR)
        return 0;
    pPlayer->src_quality = quality;
    return 1;
}

unsigned int get_src_quality(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 2;
    return pPlayer->src_quality;
}

void set_gain(uint8_t id, float gain) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if (gain <= 0.00001)
        gain = 0.00001;
    if (gain > 100000)
        gain = 100000;
    pPlayer->gain = gain;
}

float get_gain(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 1.0;
    return pPlayer->gain;
}

void set_track_a(uint8_t id, int track) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if (track < pPlayer->sf_info.channels) {
        if (pPlayer->sf_info.channels == 1)
            pPlayer->track_a = 0;
        else
            pPlayer->track_a = track;
    }
    set_position(id, get_position(id));
}

void set_track_b(uint8_t id, int track) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return;
    if (track < pPlayer->sf_info.channels) {
        if (pPlayer->sf_info.channels == 1)
            pPlayer->track_b = 0;
        else
            pPlayer->track_b = track;
    }
    set_position(id, get_position(id));
}

int get_track_a(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->track_a;
}

int get_track_b(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || pPlayer->file_open != FILE_OPEN)
        return 0;
    return pPlayer->track_b;
}

void set_speed(uint8_t id, float factor) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || factor < 0.1 || factor > 4.0)
        return;
    pPlayer->speed = factor;
    atomic_store_explicit(&pPlayer->time_ratio_dirty, 1, memory_order_relaxed);
}

float get_speed(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return 1.0;
    return pPlayer->speed;
}

void set_pitch_semitone(uint8_t id, int8_t semitones) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || semitones < -12 || semitones > 12)
        return;
    pPlayer->semitones = semitones;
    pPlayer->pitch = powf(2.0f, (pPlayer->cents / 100.0f + pPlayer->semitones) / 12.0f);
    atomic_store_explicit(&pPlayer->time_ratio_dirty, 1, memory_order_relaxed);
}

int8_t get_pitch_semitone(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return 0;
    return pPlayer->semitones;
}

void set_pitch_cent(uint8_t id, int8_t cents) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || cents < -100 || cents > 100)
        return;
    pPlayer->cents = cents;
    pPlayer->pitch = powf(2.0f, (pPlayer->cents / 100.0f + pPlayer->semitones) / 12.0f);
    atomic_store_explicit(&pPlayer->time_ratio_dirty, 1, memory_order_relaxed);
}

int8_t get_pitch_cent(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return 0;
    return pPlayer->cents;
}

void set_varispeed(uint8_t id, float ratio) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer || fabs(ratio) > MAX_VARISPEED)
        return;

    float abs_ratio = fabs(ratio);

    // Check if moving into or through zone too small to reliably varispeed
    uint8_t stop  = ((pPlayer->varispeed >= MIN_VARISPEED && ratio < MIN_VARISPEED) || pPlayer->varispeed <= -MIN_VARISPEED && ratio > -MIN_VARISPEED);
    // Check for scrubbing
    uint8_t start = (pPlayer->play_state != PLAYING && abs_ratio >= MIN_VARISPEED);

    if (abs_ratio >= MIN_VARISPEED)
        pPlayer->play_varispeed = ratio;
    else
        pPlayer->play_varispeed = 1.0;
    atomic_store_explicit(&pPlayer->varispeed, ratio, memory_order_relaxed);
    atomic_store_explicit(&pPlayer->time_ratio_dirty, 1, memory_order_relaxed);

    if (stop && pPlayer->play_state != STOPPED) {
        atomic_store_explicit(&pPlayer->play_state, STOPPING, memory_order_relaxed);
    }
    if (start && g_jack_client && pPlayer->file_open == FILE_OPEN && pPlayer->play_state != PLAYING) {
        atomic_store_explicit(&pPlayer->play_state, STARTING, memory_order_relaxed);
    }
}

float get_varispeed(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (!pPlayer)
        return 0.0;
    return pPlayer->varispeed;
}

void set_buffer_size(uint8_t id, unsigned int size) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer && pPlayer->file_open == FILE_CLOSED) {
        pPlayer->input_buffer_size = size;
    }
}

unsigned int get_buffer_size(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer)
        return pPlayer->input_buffer_size;
    return 0;
}

void set_buffer_count(uint8_t id, unsigned int count) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer && pPlayer->file_open == FILE_CLOSED && count > 1) {
        pPlayer->buffer_count = count;
    }
}

unsigned int get_buffer_count(uint8_t id) {
    struct AUDIO_PLAYER* pPlayer = get_player(id);
    if (pPlayer)
        return pPlayer->buffer_count;
    return 0;
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

uint8_t get_player_count() {
    uint8_t nCount = 0;
    for (uint8_t i = 0; i < MAX_PLAYERS; ++i)
        if (g_players[i])
            ++nCount;
    return nCount;
}