/*
 * ******************************************************************
 * ZYNTHIAN PROJECT: Audio to MIDI converter - DSP core
 *
 * Copyright (C) 2026 Brian Walton <riban@zynthian.org>
 *
 * ******************************************************************
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * For a full copy of the GNU General Public License see the LICENSE.txt file.
 *
 * ******************************************************************
 *
 * Both modes low-pass filter and decimate the input, remove DC and analyse it once per hop. While the input is
 * below the thresholds (no note can start or is held) only its level is measured, so silence costs almost nothing.
 *
 * Monophonic: YIN (as zyntuner) at ~8 kHz, 32 ms window, 8 ms hop, 30..1600 Hz. The difference function is
 * computed lazily, only up to the first dip, so high notes are cheaper than low ones. Note on after the same note is
 * seen on 1..4 hops (noise filter) above the onset threshold, note off below the release threshold, legato note
 * change when the pitch moves more than 70 cents for as many hops, re-trigger on a sudden level rise (new pluck).
 *
 * Polyphonic: 2048 point FFT at ~12 kHz (170 ms Hann window, 21 ms hop), MIDI notes 36..96. Spectral peaks above an
 * adaptive noise floor (noise filter sets the margin) are matched to the harmonics of each candidate note. The note
 * with the highest weighted harmonic sum is accepted and its harmonics are subtracted (spectrally smoothed, so a
 * partial shared with another note is not lost), up to 6 notes (iterative estimation as Klapuri 2006). Each note has
 * its own onset / release hysteresis.
 */

#include "a2m_dsp.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#define RING_SIZE 4096 // Decimated samples (power of 2)
#define RING_MASK (RING_SIZE - 1)

// Monophonic
#define MONO_RATE 8000.0f     // Target decimated samplerate
#define MONO_LPF 2000.0f      // Anti-alias low-pass cutoff
#define MONO_MIN_FREQ 30.0f   // Below B0 (30.9 Hz)
#define MONO_MAX_FREQ 1600.0f // Above G6 (1568 Hz)
#define MONO_MAX_LAG 400
#define MONO_MAX_WIN 384
#define MONO_WIN_S 0.032f
#define MONO_HOP_S 0.008f
#define MONO_OFF_HOPS 2      // Hops below release threshold before note off
#define MONO_INVALID_HOPS 20 // Hops without pitch (above release threshold) before note off
#define MONO_RETRIG_HOPS 6   // Minimum hops after note on before a re-trigger
#define MONO_CHANGE_ST 0.7f  // Pitch deviation (semitones) from the held note that may start a new note

// Polyphonic
#define POLY_RATE 12000.0f // Target decimated samplerate
#define FFT_N 2048
#define FFT_M (FFT_N / 2)
#define POLY_HOP 256
#define POLY_LO 36 // C2
#define POLY_HI 96 // C7
#define POLY_NOTES (POLY_HI - POLY_LO + 1)
#define POLY_HARM 10
#define POLY_MAX_PEAKS 256
#define POLY_MAX_NOTES 6 // Maximum held notes
#define POLY_ITERATIONS 8 // Maximum notes detected per hop (more than held, so ghosts don't hide real notes)
#define POLY_HELD_BIAS 1.5f
#define POLY_OFF_HOPS 3
#define POLY_RETRIG_HOPS 3       // Hops a note must be held before an attack to be re-triggered by it
#define POLY_ATTACK_DB 6.0f      // Rise of the newest hop's level that is an attack
#define POLY_ATTACK_HOPS 6       // Hops after an attack in which held notes may be re-triggered
#define POLY_RETRIG_RISE_DB 4.0f // Rise of a held note's level over its minimum since the attack to re-trigger it
#define POLY_RETRIG_PRE_DB 2.0f  // ... and over its level before the attack
#define POLY_FLOOR_RADIUS 12 // Bins each side for the noise floor estimate
#define POLY_TOLERANCE 0.025f
#define POLY_RISING_DB 1.0f // Total level rise per hop that indicates an attack
#define POLY_WEAK_DB 9.0f   // Notes this much below the strongest wait for the end of an attack

#define RETRIG_DB 9.0f       // Monophonic: level rise (16 ms windows) that re-triggers a held note
#define NOTE_ON_RESERVE 192  // Note on only if fewer events than this are queued: room is left for note offs
#define SILENCE_DB -200.0f

struct a2m_dsp {
    uint32_t rate;
    a2m_params_t params; // Requested
    int poly;            // Active mode

    // Anti-alias filter (2 biquads), decimation, DC blocker
    int decim, phase;
    float drate;
    float fb[2], fa1[2], fa2[2], fz[2][2];
    float hp_coef, hp_x, hp_y;

    // Decimated signal
    float ring[RING_SIZE];
    uint32_t wr, fill;
    int hop, since_hop;

    // Held notes (both modes)
    uint8_t on[128];
    int held;

    // Monophonic
    int m_win, m_max_lag, m_min_lag, m_done;
    float m_frame[MONO_MAX_WIN + MONO_MAX_LAG];
    float m_diff[MONO_MAX_LAG + 2];
    const float* m_a;
    int m_note, m_cand, m_cand_cnt, m_off_cnt, m_invalid, m_age;
    float m_peak, m_hist[2]; // m_hist: levels of the newest 2 hops, 1 and 2 hops ago

    // Polyphonic
    float bin_hz;
    float window[FFT_N];
    float re[FFT_M], im[FFT_M];
    float tw_re[FFT_M / 2], tw_im[FFT_M / 2]; // Complex FFT twiddles
    float rtw_re[FFT_M], rtw_im[FFT_M];       // Real FFT post-processing twiddles
    uint16_t bitrev[FFT_M];
    float amp[FFT_M + 1], floor[FFT_M + 1], clip[FFT_M + 1], sum[FFT_M + 2];
    int16_t bin2peak[FFT_M + 1];
    int npeaks, k_min, k_max;
    float pk_freq[POLY_MAX_PEAKS], pk_amp[POLY_MAX_PEAKS];
    float f0[POLY_NOTES];
    int nharm[POLY_NOTES];
    uint16_t h_lo[POLY_NOTES][POLY_HARM], h_hi[POLY_NOTES][POLY_HARM];
    float h_tol[POLY_NOTES][POLY_HARM], h_w[POLY_NOTES][POLY_HARM];
    uint8_t p_cnt[POLY_NOTES], p_off[POLY_NOTES], p_age[POLY_NOTES];
    float p_peak[POLY_NOTES], p_last[POLY_NOTES];
    float p_total;              // Total level on the previous hop
    float p_short;              // Level of the previous hop's samples
    int p_attack_age;           // Hops since the last attack
    float p_attack_pre[POLY_NOTES]; // Note levels before the last attack
    float p_attack_min[POLY_NOTES]; // Minimum note levels since the last attack
    uint8_t p_retrig[POLY_NOTES];   // Note re-triggered since the last attack
};

typedef struct {
    a2m_event_t* ev;
    uint32_t count;
    uint32_t frame;
} out_t;

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

static void push(out_t* o, uint8_t status, uint8_t note, uint8_t vel) {
    if (o->count >= A2M_MAX_EVENTS)
        return;
    a2m_event_t* e = &o->ev[o->count++];
    e->frame = o->frame;
    e->data[0] = status;
    e->data[1] = note;
    e->data[2] = vel;
}

static int note_on(a2m_dsp_t* d, out_t* o, int note, uint8_t vel) {
    if (note < 0 || note > 127 || d->on[note] || o->count >= NOTE_ON_RESERVE)
        return 0;
    push(o, 0x90, note, vel);
    d->on[note] = 1;
    ++d->held;
    return 1;
}

static void note_off(a2m_dsp_t* d, out_t* o, int note) {
    if (note < 0 || note > 127 || !d->on[note])
        return;
    push(o, 0x80, note, 0);
    d->on[note] = 0;
    --d->held;
}

static void release_all(a2m_dsp_t* d, out_t* o) {
    for (int note = 0; note < 128 && d->held; ++note)
        note_off(d, o, note);
    d->held = 0;
    d->m_note = -1;
}

// Level (dBFS RMS) to velocity: onset - 12 dB => 1, max(-6 dBFS, onset + 6 dB) => 127
static uint8_t velocity(float lvl, float onset) {
    float lo = onset - 12.0f;
    float hi = fmaxf(-6.0f, onset + 6.0f);
    float v = 1.0f + 126.0f * (lvl - lo) / (hi - lo);
    if (v < 1.0f)
        return 1;
    if (v > 127.0f)
        return 127;
    return (uint8_t)lrintf(v);
}

static float thresholds(const a2m_dsp_t* d, float* release) {
    *release = fminf(d->params.release_db, d->params.onset_db);
    return d->params.onset_db;
}

// Noise filter 0..1
static float noise(const a2m_dsp_t* d) {
    float n = d->params.noise * 0.01f;
    return n < 0.0f ? 0.0f : (n > 1.0f ? 1.0f : n);
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

static void fft_init(a2m_dsp_t* d) {
    int bits = 0;
    while ((1 << bits) < FFT_M)
        ++bits;
    for (int i = 0; i < FFT_M; ++i) {
        int r = 0;
        for (int b = 0; b < bits; ++b)
            if (i & (1 << b))
                r |= 1 << (bits - 1 - b);
        d->bitrev[i] = r;
    }
    for (int k = 0; k < FFT_M / 2; ++k) {
        d->tw_re[k] = cos(-2.0 * M_PI * k / FFT_M);
        d->tw_im[k] = sin(-2.0 * M_PI * k / FFT_M);
    }
    for (int k = 0; k < FFT_M; ++k) {
        d->rtw_re[k] = cos(-2.0 * M_PI * k / FFT_N);
        d->rtw_im[k] = sin(-2.0 * M_PI * k / FFT_N);
    }
    for (int i = 0; i < FFT_N; ++i)
        d->window[i] = 0.5 - 0.5 * cos(2.0 * M_PI * i / FFT_N);
}

static void poly_tables(a2m_dsp_t* d) {
    float fmax = 0.33f * d->drate; // Below the anti-alias filter cutoff
    d->bin_hz = d->drate / FFT_N;
    d->k_min = 1;
    d->k_max = 1;
    for (int c = 0; c < POLY_NOTES; ++c) {
        float f0 = 440.0f * powf(2.0f, (POLY_LO + c - 69) / 12.0f);
        d->f0[c] = f0;
        int nh = 0;
        for (int h = 0; h < POLY_HARM; ++h) {
            float fh = f0 * (h + 1);
            if (fh > fmax)
                break;
            // Unresolved low partials: allow half a bin
            float tol = fmaxf(POLY_TOLERANCE, 0.5f * d->bin_hz / fh);
            int lo = (int)floorf(fh * (1.0f - tol) / d->bin_hz);
            int hi = (int)ceilf(fh * (1.0f + tol) / d->bin_hz);
            if (lo < 2)
                lo = 2;
            if (hi > FFT_M - 2)
                hi = FFT_M - 2;
            d->h_lo[c][h] = lo;
            d->h_hi[c][h] = hi;
            d->h_tol[c][h] = tol;
            d->h_w[c][h] = (f0 + 52.0f) / (fh + 320.0f); // Klapuri's partial weighting
            if (c == 0 && h == 0)
                d->k_min = lo;
            if (hi > d->k_max)
                d->k_max = hi;
            ++nh;
        }
        d->nharm[c] = nh;
    }
}

static void configure(a2m_dsp_t* d) {
    d->poly = d->params.poly ? 1 : 0;
    float target = d->poly ? POLY_RATE : MONO_RATE;
    d->decim = (int)(d->rate / target + 0.5f);
    if (d->decim < 1)
        d->decim = 1;
    d->drate = (float)d->rate / d->decim;
    float fc = d->poly ? 0.33f * d->drate : fminf(MONO_LPF, 0.3f * d->drate);

    // 4th order Butterworth low-pass (two biquads, bilinear transform)
    const double w = 2.0 * M_PI * fc / d->rate, c = cos(w);
    const double q[2] = {0.54119610, 1.30656296};
    for (int s = 0; s < 2; ++s) {
        const double alpha = sin(w) / (2.0 * q[s]), a0 = 1.0 + alpha;
        d->fb[s] = (1.0 - c) * 0.5 / a0;
        d->fa1[s] = -2.0 * c / a0;
        d->fa2[s] = (1.0 - alpha) / a0;
    }
    d->hp_coef = expf(-2.0f * (float)M_PI * 20.0f / d->drate);
    memset(d->fz, 0, sizeof(d->fz));
    d->hp_x = d->hp_y = 0.0f;
    d->phase = 0;

    memset(d->ring, 0, sizeof(d->ring));
    d->wr = d->fill = 0;
    d->since_hop = 0;

    if (d->poly) {
        d->hop = POLY_HOP;
        poly_tables(d);
        memset(d->p_cnt, 0, sizeof(d->p_cnt));
        memset(d->p_off, 0, sizeof(d->p_off));
        memset(d->p_age, 0, sizeof(d->p_age));
        for (int i = 0; i < POLY_NOTES; ++i)
            d->p_last[i] = SILENCE_DB;
        d->p_total = d->p_short = SILENCE_DB;
        d->p_attack_age = 255;
    } else {
        d->hop = (int)(d->drate * MONO_HOP_S + 0.5f);
        if (d->hop < 1)
            d->hop = 1;
        d->m_win = (int)(d->drate * MONO_WIN_S);
        if (d->m_win > MONO_MAX_WIN)
            d->m_win = MONO_MAX_WIN;
        d->m_max_lag = (int)(d->drate / MONO_MIN_FREQ) + 2;
        if (d->m_max_lag > MONO_MAX_LAG - 2)
            d->m_max_lag = MONO_MAX_LAG - 2;
        d->m_min_lag = (int)(d->drate / MONO_MAX_FREQ);
        if (d->m_min_lag < 2)
            d->m_min_lag = 2;
        d->m_note = -1;
        d->m_cand = -1;
        d->m_cand_cnt = d->m_off_cnt = d->m_invalid = d->m_age = 0;
        d->m_hist[0] = d->m_hist[1] = SILENCE_DB;
    }
}

// ---------------------------------------------------------------------------
// Monophonic
// ---------------------------------------------------------------------------

// Compute the difference function up to lag t (YIN step 2), on demand
static void mono_ensure(a2m_dsp_t* d, int t) {
    const int W = d->m_win;
    while (d->m_done < t) {
        int lag = ++d->m_done;
        const float* a = d->m_a;
        const float* b = d->m_a - lag;
        float sum = 0.0f;
        for (int i = 0; i < W; ++i) {
            const float x = a[i] - b[i];
            sum += x * x;
        }
        d->m_diff[lag] = sum;
    }
}

// Vertex of the parabola through diff[t-1..t+1]
static float mono_vertex(a2m_dsp_t* d, int t) {
    mono_ensure(d, t + 1);
    const float a = d->m_diff[t - 1], b = d->m_diff[t], c = d->m_diff[t + 1];
    const float den = a - 2.0f * b + c;
    if (den <= 0.0f)
        return (float)t;
    return t + fmaxf(-1.0f, fminf(1.0f, 0.5f * (a - c) / den));
}

static int mono_local_min(a2m_dsp_t* d, int centre, int radius) {
    int best = centre - radius < 1 ? 1 : centre - radius;
    int hi = centre + radius > d->m_max_lag - 1 ? d->m_max_lag - 1 : centre + radius;
    mono_ensure(d, hi);
    for (int t = best + 1; t <= hi; ++t)
        if (d->m_diff[t] < d->m_diff[best])
            best = t;
    return best;
}

// YIN on the most recent window, compared with earlier samples. Returns frequency in Hz or 0 if no pitch.
static float mono_yin(a2m_dsp_t* d, float threshold) {
    const int max_lag = d->m_max_lag;
    d->m_done = 0;
    d->m_diff[0] = 0.0f;
    mono_ensure(d, 2);
    float cum = d->m_diff[1];
    int tau = 0;
    for (int t = 2; t < max_lag; ++t) {
        mono_ensure(d, t + 1);
        const float l = d->m_diff[t - 1], m = d->m_diff[t], r = d->m_diff[t + 1];
        cum += m;
        if (t < d->m_min_lag || m > l || m >= r || cum <= 0.0f)
            continue;
        // Interpolated depth of the dip (high notes: the dip falls between two lags)
        const float depth = m - (l - r) * (l - r) / (8.0f * (l - 2.0f * m + r));
        if (depth * t < threshold * cum) {
            tau = t;
            break;
        }
    }
    if (tau <= 0 || tau >= max_lag - 1)
        return 0.0f;

    // Refine short periods on their multiples: the interpolation error is divided by the multiple
    float period = mono_vertex(d, tau);
    int mult = 1;
    while (period * mult * 2 < fminf(max_lag - 2, 64.0f)) {
        mult *= 2;
        const int t = mono_local_min(d, (int)(period * mult + 0.5f), 2);
        if (t < 2 || t >= max_lag - 1)
            break;
        period = mono_vertex(d, t) / mult;
    }
    const float freq = d->drate / period;
    return (freq >= MONO_MIN_FREQ && freq <= MONO_MAX_FREQ) ? freq : 0.0f;
}

// Count consecutive hops on the same candidate note. Returns 1 when confirmed.
static int mono_candidate(a2m_dsp_t* d, int note, float lvl, int confirm) {
    if (note == d->m_cand && d->m_cand_cnt > 0) {
        ++d->m_cand_cnt;
        d->m_peak = fmaxf(d->m_peak, lvl);
    } else {
        d->m_cand = note;
        d->m_cand_cnt = 1;
        d->m_peak = lvl;
    }
    if (d->m_cand_cnt < confirm)
        return 0;
    d->m_cand_cnt = 0;
    return 1;
}

static void mono_hop(a2m_dsp_t* d, out_t* o) {
    const int W = d->m_win;
    const int n = W + d->m_max_lag;
    if (d->fill < (uint32_t)n)
        return;
    float release, onset = thresholds(d, &release);
    const float nf = noise(d);
    const int confirm = 1 + (int)lrintf(3.0f * nf);

    // Level of the most recent window
    uint32_t r = (d->wr - W) & RING_MASK;
    float e = 0.0f;
    for (int i = 0; i < W; ++i) {
        const float x = d->ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float lvl = 10.0f * log10f(e / W + 1e-20f);
    // Attack: level of the newest 2 hops compared with the 2 hops before them (the window smears a fast rise)
    const int ns = 2 * d->hop < W ? 2 * d->hop : W;
    e = 0.0f;
    for (int i = W - ns; i < W; ++i) {
        const float x = d->ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float short_lvl = 10.0f * log10f(e / ns + 1e-20f);
    const int attack = short_lvl > d->m_hist[1] + RETRIG_DB;
    d->m_hist[1] = d->m_hist[0];
    d->m_hist[0] = short_lvl;

    if (d->m_note < 0) {
        if (lvl < onset) {
            d->m_cand_cnt = 0;
            return; // Nothing to analyse
        }
    } else if (lvl < release) {
        if (++d->m_off_cnt >= MONO_OFF_HOPS) {
            note_off(d, o, d->m_note);
            d->m_note = -1;
            d->m_cand_cnt = 0;
        }
        return;
    } else {
        d->m_off_cnt = 0;
        if (++d->m_age > MONO_RETRIG_HOPS && attack) {
            // New attack (same note plucked again or another note): release, then detect as from silence
            note_off(d, o, d->m_note);
            d->m_note = -1;
            d->m_cand_cnt = 0;
        }
    }

    r = (d->wr - n) & RING_MASK;
    for (int i = 0; i < n; ++i)
        d->m_frame[i] = d->ring[(r + i) & RING_MASK];
    d->m_a = d->m_frame + n - W;
    const float freq = mono_yin(d, 0.3f - 0.2f * nf);
    if (freq <= 0.0f) {
        d->m_cand_cnt = 0;
        if (d->m_note >= 0 && ++d->m_invalid > MONO_INVALID_HOPS) {
            note_off(d, o, d->m_note);
            d->m_note = -1;
        }
        return;
    }
    d->m_invalid = 0;
    const float pitch = 69.0f + 12.0f * log2f(freq / 440.0f);
    int note = (int)lrintf(pitch);
    if (note < 0 || note > 127)
        return;

    if (d->m_note < 0) {
        if (mono_candidate(d, note, lvl, confirm) && note_on(d, o, note, velocity(d->m_peak, onset))) {
            d->m_note = note;
            d->m_age = 0;
        }
        return;
    }

    if (fabsf(pitch - d->m_note) > MONO_CHANGE_ST) {
        // Legato note change
        if (mono_candidate(d, note, lvl, confirm)) {
            note_off(d, o, d->m_note);
            d->m_note = -1;
            if (note_on(d, o, note, velocity(d->m_peak, onset))) {
                d->m_note = note;
                d->m_age = 0;
            }
        }
    } else {
        d->m_cand_cnt = 0;
    }
}

// ---------------------------------------------------------------------------
// Polyphonic
// ---------------------------------------------------------------------------

// In-place radix-2 complex FFT of d->re / d->im (FFT_M points)
static void cfft(a2m_dsp_t* d) {
    float* re = d->re;
    float* im = d->im;
    for (int i = 0; i < FFT_M; ++i) {
        const int j = d->bitrev[i];
        if (j > i) {
            float t = re[i];
            re[i] = re[j];
            re[j] = t;
            t = im[i];
            im[i] = im[j];
            im[j] = t;
        }
    }
    for (int len = 2; len <= FFT_M; len <<= 1) {
        const int half = len >> 1;
        const int step = FFT_M / len;
        for (int i = 0; i < FFT_M; i += len) {
            for (int j = 0; j < half; ++j) {
                const float wr = d->tw_re[j * step], wi = d->tw_im[j * step];
                const int a = i + j, b = a + half;
                const float tr = re[b] * wr - im[b] * wi;
                const float ti = re[b] * wi + im[b] * wr;
                re[b] = re[a] - tr;
                im[b] = im[a] - ti;
                re[a] += tr;
                im[a] += ti;
            }
        }
    }
}

// Amplitude spectrum of the most recent FFT_N samples: a sinusoid of amplitude A gives a peak of ~A
static void poly_spectrum(a2m_dsp_t* d) {
    const uint32_t r = (d->wr - FFT_N) & RING_MASK;
    for (int m = 0; m < FFT_M; ++m) {
        d->re[m] = d->ring[(r + 2 * m) & RING_MASK] * d->window[2 * m];
        d->im[m] = d->ring[(r + 2 * m + 1) & RING_MASK] * d->window[2 * m + 1];
    }
    cfft(d);
    // Real FFT of N points from the complex FFT of N/2 points (even samples real, odd samples imaginary)
    const float scale = 4.0f / FFT_N;
    d->amp[0] = fabsf(d->re[0] + d->im[0]) * scale;
    d->amp[FFT_M] = fabsf(d->re[0] - d->im[0]) * scale;
    for (int k = 1; k < FFT_M; ++k) {
        const float zr = d->re[k], zi = d->im[k];
        const float cr = d->re[FFT_M - k], ci = -d->im[FFT_M - k];
        const float er = 0.5f * (zr + cr), ei = 0.5f * (zi + ci);
        const float or_ = 0.5f * (zi - ci), oi = -0.5f * (zr - cr);
        const float xr = er + d->rtw_re[k] * or_ - d->rtw_im[k] * oi;
        const float xi = ei + d->rtw_re[k] * oi + d->rtw_im[k] * or_;
        d->amp[k] = sqrtf(xr * xr + xi * xi) * scale;
    }
}

// Moving average of src over +/-POLY_FLOOR_RADIUS bins into dst
static void moving_average(a2m_dsp_t* d, const float* src, float* dst) {
    d->sum[0] = 0.0f;
    for (int k = 0; k <= FFT_M; ++k)
        d->sum[k + 1] = d->sum[k] + src[k];
    for (int k = 0; k <= FFT_M; ++k) {
        const int lo = k - POLY_FLOOR_RADIUS < 0 ? 0 : k - POLY_FLOOR_RADIUS;
        const int hi = k + POLY_FLOOR_RADIUS > FFT_M ? FFT_M : k + POLY_FLOOR_RADIUS;
        dst[k] = (d->sum[hi + 1] - d->sum[lo]) / (hi - lo + 1);
    }
}

// Find spectral peaks clearly above the noise floor
static void poly_peaks(a2m_dsp_t* d, float margin_db, float abs_min) {
    // Noise floor: moving average, then again with the peaks clipped so they don't raise it
    moving_average(d, d->amp, d->floor);
    for (int k = 0; k <= FFT_M; ++k)
        d->clip[k] = fminf(d->amp[k], d->floor[k]);
    moving_average(d, d->clip, d->floor);

    const float gain = powf(10.0f, margin_db / 20.0f);
    float max_amp = 0.0f;
    for (int k = d->k_min; k <= d->k_max; ++k)
        max_amp = fmaxf(max_amp, d->amp[k]);
    const float min_amp = fmaxf(abs_min, max_amp * 0.003f); // Ignore window side lobes (-50 dB)

    memset(d->bin2peak, 0xff, sizeof(d->bin2peak));
    d->npeaks = 0;
    for (int k = d->k_min; k <= d->k_max && d->npeaks < POLY_MAX_PEAKS; ++k) {
        const float a = d->amp[k];
        if (a <= d->amp[k - 1] || a < d->amp[k + 1])
            continue;
        // Parabolic interpolation on log amplitude (a partial between two bins is attenuated by the window)
        const float l = logf(d->amp[k - 1] + 1e-20f), c = logf(a), r = logf(d->amp[k + 1] + 1e-20f);
        const float den = l - 2.0f * c + r;
        float p = den < 0.0f ? 0.5f * (l - r) / den : 0.0f;
        p = fmaxf(-0.5f, fminf(0.5f, p));
        const float pa = expf(c - 0.25f * (l - r) * p);
        if (pa < min_amp || pa < gain * d->floor[k])
            continue;
        d->pk_freq[d->npeaks] = (k + p) * d->bin_hz;
        d->pk_amp[d->npeaks] = pa;
        d->bin2peak[k] = d->npeaks++;
    }
}

// Weighted sum of the harmonic amplitudes of a candidate note. A[h] / P[h]: amplitude / peak index of each harmonic.
static float poly_salience(a2m_dsp_t* d, int c, float* A, int* P) {
    const int nh = d->nharm[c];
    const float f0 = d->f0[c];
    float s = 0.0f;
    for (int h = 0; h < nh; ++h) {
        const float fh = f0 * (h + 1);
        const float tol = d->h_tol[c][h] * fh;
        float best = 0.0f;
        int bp = -1;
        for (int k = d->h_lo[c][h]; k <= d->h_hi[c][h]; ++k) {
            const int p = d->bin2peak[k];
            if (p < 0 || d->pk_amp[p] <= best || fabsf(d->pk_freq[p] - fh) > tol)
                continue;
            best = d->pk_amp[p];
            bp = p;
        }
        A[h] = best;
        P[h] = bp;
        s += d->h_w[c][h] * best;
    }
    // Need the fundamental, or the 2nd and 3rd harmonics (missing fundamental). Rejects sub-octave ghosts.
    if (nh < 1 || !(A[0] > 0.0f || (nh > 2 && A[1] > 0.0f && A[2] > 0.0f)))
        return 0.0f;
    return s;
}

// Iterative multiple pitch estimation. det[c]: level (dBFS RMS) of each detected note, SILENCE_DB if not detected.
static void poly_detect(a2m_dsp_t* d, float* det, float release, float nf) {
    for (int c = 0; c < POLY_NOTES; ++c)
        det[c] = SILENCE_DB;
    poly_spectrum(d);
    poly_peaks(d, 4.0f + 10.0f * nf, 1.41f * powf(10.0f, (release - 24.0f) / 20.0f));
    if (!d->npeaks)
        return;

    uint8_t excluded[POLY_NOTES] = {0};
    float A[POLY_HARM], env[POLY_HARM];
    int P[POLY_HARM];
    int found[POLY_ITERATIONS], nfound = 0;
    const float ratio = 0.1f + 0.15f * nf;
    float first = 0.0f;
    for (int iter = 0; iter < POLY_ITERATIONS; ++iter) {
        // Held notes are favoured (hysteresis): less flicker while they decay
        int best = -1;
        float bs = 0.0f, bs_raw = 0.0f;
        for (int c = 0; c < POLY_NOTES; ++c) {
            if (excluded[c])
                continue;
            const float s = poly_salience(d, c, A, P);
            const float se = d->on[POLY_LO + c] ? s * POLY_HELD_BIAS : s;
            if (se > bs) {
                bs = se;
                bs_raw = s;
                best = c;
            }
        }
        if (best < 0)
            break;
        if (iter == 0)
            first = bs_raw;
        else if (bs < ratio * first)
            break;

        poly_salience(d, best, A, P);
        // Spectrally smoothed partial amplitudes of this note: the excess over them belongs to other notes
        const int nh = d->nharm[best];
        float e2 = 0.0f;
        for (int h = 0; h < nh; ++h) {
            if (h == 0)
                env[h] = A[0];
            else
                env[h] = fminf(A[h], (A[h - 1] + A[h] + (h + 1 < nh ? A[h + 1] : 0.0f)) / 3.0f);
            e2 += env[h] * env[h];
        }
        const float lvl = 10.0f * log10f(0.5f * e2 + 1e-20f);
        if (lvl < release)
            break;
        det[best] = lvl;
        found[nfound++] = best;
        excluded[best] = 1;
        if (best > 0)
            excluded[best - 1] = 1;
        if (best < POLY_NOTES - 1)
            excluded[best + 1] = 1;
        for (int h = 0; h < nh; ++h) {
            if (P[h] < 0)
                continue;
            d->pk_amp[P[h]] = fmaxf(0.0f, d->pk_amp[P[h]] - env[h]);
        }
    }

    // Harmonic ghosts: a note on a low harmonic of a louder note is mostly that note's residue (e.g. at onsets,
    // or with octave doubled chords: a quieter doubled octave is lost too). Not applied to held notes.
    static const int harm_st[] = {12, 19, 24, 28, 31};
    const float ghost_db = 12.0f - 8.0f * nf;
    for (int i = 0; i < nfound; ++i) {
        const int c = found[i];
        if (d->on[POLY_LO + c])
            continue;
        for (int j = 0; j < nfound; ++j) {
            const int b = found[j];
            const float base_lvl = det[b] > SILENCE_DB ? det[b] : d->p_last[b];
            int related = 0;
            for (unsigned k = 0; k < sizeof(harm_st) / sizeof(harm_st[0]); ++k)
                related |= c - b == harm_st[k];
            if (related && det[c] < base_lvl - ghost_db) {
                det[c] = SILENCE_DB;
                break;
            }
        }
    }
}

static void poly_hop(a2m_dsp_t* d, out_t* o) {
    if (d->fill < FFT_N)
        return;
    float release, onset = thresholds(d, &release);
    const float nf = noise(d);
    const int confirm = 1 + (int)lrintf(2.0f * nf);
    float det[POLY_NOTES];

    // Total level of the most recent half window: no note can be above it
    const uint32_t r = (d->wr - FFT_N / 2) & RING_MASK;
    float e = 0.0f;
    for (int i = 0; i < FFT_N / 2; ++i) {
        const float x = d->ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float lvl = 10.0f * log10f(e / (FFT_N / 2) + 1e-20f);
    // Attack: sudden rise of the level of the newest hop. Held notes that get louder soon after are re-triggered.
    e = 0.0f;
    for (int i = FFT_N / 2 - POLY_HOP; i < FFT_N / 2; ++i) {
        const float x = d->ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float short_lvl = 10.0f * log10f(e / POLY_HOP + 1e-20f);
    if (short_lvl > d->p_short + POLY_ATTACK_DB) {
        d->p_attack_age = 0;
        memcpy(d->p_attack_pre, d->p_last, sizeof(d->p_attack_pre));
        memcpy(d->p_attack_min, d->p_last, sizeof(d->p_attack_min));
        memset(d->p_retrig, 0, sizeof(d->p_retrig));
    } else if (d->p_attack_age < 255) {
        ++d->p_attack_age;
    }
    d->p_short = short_lvl;
    // During an attack the window is partly filled: weak partials of a louder note may resolve before its
    // fundamental and look like notes. Weak new notes wait until the level stops rising.
    const int rising = lvl > d->p_total + POLY_RISING_DB;
    d->p_total = lvl;
    if (lvl < (d->held ? release : onset)) {
        if (!d->held)
            return; // Nothing to analyse
        for (int c = 0; c < POLY_NOTES; ++c)
            det[c] = SILENCE_DB;
    } else {
        poly_detect(d, det, release, nf);
    }
    float strongest = SILENCE_DB;
    for (int c = 0; c < POLY_NOTES; ++c)
        strongest = fmaxf(strongest, det[c]);

    for (int c = 0; c < POLY_NOTES; ++c) {
        const int note = POLY_LO + c;
        const float l = det[c];
        if (!d->on[note]) {
            if (l >= onset && d->held < POLY_MAX_NOTES) {
                // A weak note keeps its count during an attack and is decided when the attack is over
                if (!rising || l >= strongest - POLY_WEAK_DB) {
                    if (d->p_cnt[c] == 0 || l > d->p_peak[c])
                        d->p_peak[c] = l;
                    if (++d->p_cnt[c] >= confirm) {
                        d->p_cnt[c] = d->p_off[c] = d->p_age[c] = 0;
                        note_on(d, o, note, velocity(d->p_peak[c], onset));
                    }
                }
            } else {
                d->p_cnt[c] = 0;
            }
        } else {
            if (d->p_age[c] < 255)
                ++d->p_age[c];
            if (l < release) {
                if (++d->p_off[c] >= POLY_OFF_HOPS)
                    note_off(d, o, note);
            } else {
                d->p_off[c] = 0;
                // After an attack the old and new vibrations may first cancel: compare with the lowest level since
                d->p_attack_min[c] = fminf(d->p_attack_min[c], l);
                if (d->p_age[c] > d->p_attack_age + POLY_RETRIG_HOPS && d->p_attack_age <= POLY_ATTACK_HOPS && !d->p_retrig[c] &&
                    l > d->p_attack_min[c] + POLY_RETRIG_RISE_DB && l > d->p_attack_pre[c] + POLY_RETRIG_PRE_DB) {
                    note_off(d, o, note);
                    note_on(d, o, note, velocity(l, onset));
                    d->p_age[c] = 0;
                    d->p_retrig[c] = 1;
                }
            }
        }
        d->p_last[c] = l;
    }
}

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

a2m_dsp_t* a2m_dsp_new(uint32_t rate) {
    if (rate == 0)
        return NULL;
    a2m_dsp_t* d = calloc(1, sizeof(a2m_dsp_t));
    if (!d)
        return NULL;
    d->rate = rate;
    d->params.onset_db = -40.0f;
    d->params.release_db = -50.0f;
    d->params.noise = 50.0f;
    d->params.poly = 0;
    fft_init(d);
    configure(d);
    return d;
}

void a2m_dsp_free(a2m_dsp_t* d) {
    free(d);
}

uint32_t a2m_dsp_set_samplerate(a2m_dsp_t* d, uint32_t rate, a2m_event_t* ev) {
    out_t o = {ev, 0, 0};
    release_all(d, &o);
    if (rate) {
        d->rate = rate;
        configure(d);
    }
    return o.count;
}

void a2m_dsp_set_params(a2m_dsp_t* d, const a2m_params_t* params) {
    d->params = *params;
}

uint32_t a2m_dsp_release_all(a2m_dsp_t* d, a2m_event_t* ev, uint32_t frame) {
    out_t o = {ev, 0, frame};
    release_all(d, &o);
    return o.count;
}

uint32_t a2m_dsp_process(a2m_dsp_t* d, const float* in, uint32_t frames, a2m_event_t* ev) {
    out_t o = {ev, 0, 0};
    if ((d->params.poly ? 1 : 0) != d->poly) {
        release_all(d, &o);
        configure(d);
    }
    for (uint32_t i = 0; i < frames; ++i) {
        float v = in[i] + 1e-18f; // Keeps the filters out of denormals
        for (int s = 0; s < 2; ++s) {
            const float y = d->fb[s] * v + d->fz[s][0];
            d->fz[s][0] = 2.0f * d->fb[s] * v - d->fa1[s] * y + d->fz[s][1];
            d->fz[s][1] = d->fb[s] * v - d->fa2[s] * y;
            v = y;
        }
        if (++d->phase < d->decim)
            continue;
        d->phase = 0;
        d->hp_y = v - d->hp_x + d->hp_coef * d->hp_y; // DC blocker
        d->hp_x = v;
        d->ring[d->wr] = d->hp_y;
        d->wr = (d->wr + 1) & RING_MASK;
        if (d->fill < RING_SIZE)
            ++d->fill;
        if (++d->since_hop < d->hop)
            continue;
        d->since_hop = 0;
        o.frame = i;
        if (d->poly)
            poly_hop(d, &o);
        else
            mono_hop(d, &o);
    }
    return o.count;
}
