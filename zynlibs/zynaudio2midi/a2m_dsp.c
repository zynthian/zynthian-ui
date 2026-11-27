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
 * Each output has a mode (mono / poly). A detector runs for each mode used by an active output, so outputs share
 * the analysis: an inactive output costs nothing, two monophonic outputs cost one detector plus two (cheap) note
 * trackers. Two polyphonic outputs receive the same notes (the polyphonic note tracking is part of its detection).
 *
 * Both detectors low-pass filter and decimate the input, remove DC and analyse it once per hop. While the input is
 * below the thresholds (no note can start or is held) only its level is measured, so silence costs almost nothing.
 *
 * Monophonic: YIN (as zyntuner) at ~8 kHz, 32 ms window, 8 ms hop, 30..1600 Hz. The difference function is
 * computed lazily, only up to the first dip, so high notes are cheaper than low ones. Note on after the same note is
 * seen on 1..4 hops (noise filter) above the onset threshold, note off below the release threshold, legato note
 * change when the pitch moves more than 70 cents for as many hops, re-trigger on a sudden level rise (new pluck).
 * Optional pitch bend (per output): while a note is held, gradual pitch movement within the bend range (e.g. a
 * string bend, vibrato, slide) is sent as pitch bend instead of a new note; a jump of more than half a semitone
 * between two hops (hammer-on, new fret) still starts a new note. Pitch bend is reset to centre before each note on.
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
#define MONO_JUMP_ST 0.5f    // Pitch bend: pitch change within one hop that is a new note, not a bend
#define MONO_BEND_MARGIN_ST 0.5f // Pitch bend: deviation beyond the bend range before a new note
#define BEND_CENTRE 8192
#define BEND_MIN_CENTS 2.0f  // Pitch bend: smallest change sent (limits MIDI traffic)

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

#define MODE_OFF -1
#define MODE_MONO 0
#define MODE_POLY 1

// Anti-alias filter (2 biquads), decimation and DC blocker feeding a ring buffer of decimated samples
typedef struct {
    int decim, phase;
    float drate;
    float fb[2], fa1[2], fa2[2], fz[2][2];
    float hp_coef, hp_x, hp_y;
    float ring[RING_SIZE];
    uint32_t wr, fill;
    int hop, since_hop;
} front_t;

// Events and held notes of a note tracker
typedef struct {
    a2m_event_t ev[A2M_MAX_EVENTS];
    uint32_t count;
    uint32_t frame; // Frame of the events being produced
    uint8_t on[128];
    int held;
    int bend_sent; // Last pitch bend value sent
} stream_t;

// Monophonic pitch detector, shared by the monophonic outputs
typedef struct {
    front_t f;
    int win, max_lag, min_lag, done;
    float frame[MONO_MAX_WIN + MONO_MAX_LAG];
    float diff[MONO_MAX_LAG + 2];
    const float* a;
    float hist[2];    // Levels of the newest 2 hops, 1 and 2 hops ago
    float prev_pitch; // Pitch on the previous analysed hop (0: none)
} mono_t;

// Monophonic note tracker, one per output
typedef struct {
    stream_t s;
    int note, cand, cand_cnt, off_cnt, invalid, age;
    float peak;
    int jump; // Pitch jumped away from the held note: new note, not a bend
    int need; // Needs the pitch of this hop
} mono_trk_t;

// Polyphonic detector and note tracker (the detection depends on the held notes), shared by the polyphonic outputs
typedef struct {
    front_t f;
    stream_t s;
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
} poly_t;

// What has been sent on an output: notes released when the output changes mode or is deactivated
typedef struct {
    int mode; // MODE_OFF / MODE_MONO / MODE_POLY
    uint8_t on[128];
    int bend_sent;
} output_t;

struct a2m_dsp {
    uint32_t rate;
    a2m_params_t params;
    output_t out[A2M_OUTPUTS];
    int mono_on, poly_on; // Detectors running
    mono_t mono;
    mono_trk_t mt[A2M_OUTPUTS];
    poly_t poly;
};

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

static void push(stream_t* s, uint8_t status, uint8_t note, uint8_t vel) {
    if (s->count >= A2M_MAX_EVENTS)
        return;
    a2m_event_t* e = &s->ev[s->count++];
    e->frame = s->frame;
    e->data[0] = status;
    e->data[1] = note;
    e->data[2] = vel;
}

static void send_bend(stream_t* s, int value) {
    if (value == s->bend_sent)
        return;
    push(s, 0xE0, value & 0x7f, (value >> 7) & 0x7f);
    s->bend_sent = value;
}

static int note_on(stream_t* s, int note, uint8_t vel) {
    if (note < 0 || note > 127 || s->on[note] || s->count >= NOTE_ON_RESERVE)
        return 0;
    send_bend(s, BEND_CENTRE); // Each note starts unbent
    push(s, 0x90, note, vel);
    s->on[note] = 1;
    ++s->held;
    return 1;
}

static void note_off(stream_t* s, int note) {
    if (note < 0 || note > 127 || !s->on[note])
        return;
    push(s, 0x80, note, 0);
    s->on[note] = 0;
    --s->held;
}

// Forget held notes without sending note off (they are released on the outputs)
static void stream_reset(stream_t* s) {
    memset(s->on, 0, sizeof(s->on));
    s->held = 0;
    s->count = 0;
    s->bend_sent = BEND_CENTRE;
}

// Pitch bend for a deviation (semitones) from the held note. Small changes are not sent.
static void mono_bend(stream_t* s, float dev, float range) {
    if (range < 1.0f)
        range = 1.0f;
    int value = BEND_CENTRE + (int)lrintf(dev / range * BEND_CENTRE);
    if (value < 0)
        value = 0;
    if (value > 16383)
        value = 16383;
    const int min_step = (int)(BEND_CENTRE * BEND_MIN_CENTS * 0.01f / range) + 1;
    if (abs(value - s->bend_sent) >= min_step)
        send_bend(s, value);
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
// Outputs
// ---------------------------------------------------------------------------

static void emit(a2m_dsp_t* d, a2m_out_t* out, int i, const a2m_event_t* e) {
    output_t* o = &d->out[i];
    const uint8_t status = e->data[0] & 0xF0, note = e->data[1] & 0x7F;
    if (status == 0x90) {
        o->on[note] = 1;
    } else if (status == 0x80) {
        if (!o->on[note])
            return; // Started before this output joined the detector
        o->on[note] = 0;
    } else if (status == 0xE0) {
        const int value = e->data[1] | (e->data[2] << 7);
        if (value == o->bend_sent)
            return;
        o->bend_sent = value;
    }
    if (out->count[i] < A2M_MAX_EVENTS)
        out->ev[i][out->count[i]++] = *e;
}

static void emit_msg(a2m_dsp_t* d, a2m_out_t* out, int i, uint32_t frame, uint8_t status, uint8_t d1, uint8_t d2) {
    const a2m_event_t e = {frame, {status, d1, d2}};
    emit(d, out, i, &e);
}

// Note off for all notes sent on an output, then reset pitch bend
static void release_output(a2m_dsp_t* d, a2m_out_t* out, int i, uint32_t frame) {
    for (int note = 0; note < 128; ++note)
        if (d->out[i].on[note])
            emit_msg(d, out, i, frame, 0x80, note, 0);
    emit_msg(d, out, i, frame, 0xE0, BEND_CENTRE & 0x7f, (BEND_CENTRE >> 7) & 0x7f);
}

static void emit_stream(a2m_dsp_t* d, a2m_out_t* out, int i, stream_t* s) {
    for (uint32_t k = 0; k < s->count; ++k)
        emit(d, out, i, &s->ev[k]);
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

static void front_configure(front_t* f, uint32_t rate, float target, int poly) {
    f->decim = (int)(rate / target + 0.5f);
    if (f->decim < 1)
        f->decim = 1;
    f->drate = (float)rate / f->decim;
    float fc = poly ? 0.33f * f->drate : fminf(MONO_LPF, 0.3f * f->drate);

    // 4th order Butterworth low-pass (two biquads, bilinear transform)
    const double w = 2.0 * M_PI * fc / rate, c = cos(w);
    const double q[2] = {0.54119610, 1.30656296};
    for (int s = 0; s < 2; ++s) {
        const double alpha = sin(w) / (2.0 * q[s]), a0 = 1.0 + alpha;
        f->fb[s] = (1.0 - c) * 0.5 / a0;
        f->fa1[s] = -2.0 * c / a0;
        f->fa2[s] = (1.0 - alpha) / a0;
    }
    f->hp_coef = expf(-2.0f * (float)M_PI * 20.0f / f->drate);
    memset(f->fz, 0, sizeof(f->fz));
    f->hp_x = f->hp_y = 0.0f;
    f->phase = 0;
    memset(f->ring, 0, sizeof(f->ring));
    f->wr = f->fill = 0;
    f->since_hop = 0;
}

// Filter and decimate one input sample. Returns 1 when a hop is due.
static inline int front_push(front_t* f, float x) {
    float v = x + 1e-18f; // Keeps the filters out of denormals
    for (int s = 0; s < 2; ++s) {
        const float y = f->fb[s] * v + f->fz[s][0];
        f->fz[s][0] = 2.0f * f->fb[s] * v - f->fa1[s] * y + f->fz[s][1];
        f->fz[s][1] = f->fb[s] * v - f->fa2[s] * y;
        v = y;
    }
    if (++f->phase < f->decim)
        return 0;
    f->phase = 0;
    f->hp_y = v - f->hp_x + f->hp_coef * f->hp_y; // DC blocker
    f->hp_x = v;
    f->ring[f->wr] = f->hp_y;
    f->wr = (f->wr + 1) & RING_MASK;
    if (f->fill < RING_SIZE)
        ++f->fill;
    if (++f->since_hop < f->hop)
        return 0;
    f->since_hop = 0;
    return 1;
}

static void fft_init(poly_t* p) {
    int bits = 0;
    while ((1 << bits) < FFT_M)
        ++bits;
    for (int i = 0; i < FFT_M; ++i) {
        int r = 0;
        for (int b = 0; b < bits; ++b)
            if (i & (1 << b))
                r |= 1 << (bits - 1 - b);
        p->bitrev[i] = r;
    }
    for (int k = 0; k < FFT_M / 2; ++k) {
        p->tw_re[k] = cos(-2.0 * M_PI * k / FFT_M);
        p->tw_im[k] = sin(-2.0 * M_PI * k / FFT_M);
    }
    for (int k = 0; k < FFT_M; ++k) {
        p->rtw_re[k] = cos(-2.0 * M_PI * k / FFT_N);
        p->rtw_im[k] = sin(-2.0 * M_PI * k / FFT_N);
    }
    for (int i = 0; i < FFT_N; ++i)
        p->window[i] = 0.5 - 0.5 * cos(2.0 * M_PI * i / FFT_N);
}

static void poly_tables(poly_t* p) {
    float fmax = 0.33f * p->f.drate; // Below the anti-alias filter cutoff
    p->bin_hz = p->f.drate / FFT_N;
    p->k_min = 1;
    p->k_max = 1;
    for (int c = 0; c < POLY_NOTES; ++c) {
        float f0 = 440.0f * powf(2.0f, (POLY_LO + c - 69) / 12.0f);
        p->f0[c] = f0;
        int nh = 0;
        for (int h = 0; h < POLY_HARM; ++h) {
            float fh = f0 * (h + 1);
            if (fh > fmax)
                break;
            // Unresolved low partials: allow half a bin
            float tol = fmaxf(POLY_TOLERANCE, 0.5f * p->bin_hz / fh);
            int lo = (int)floorf(fh * (1.0f - tol) / p->bin_hz);
            int hi = (int)ceilf(fh * (1.0f + tol) / p->bin_hz);
            if (lo < 2)
                lo = 2;
            if (hi > FFT_M - 2)
                hi = FFT_M - 2;
            p->h_lo[c][h] = lo;
            p->h_hi[c][h] = hi;
            p->h_tol[c][h] = tol;
            p->h_w[c][h] = (f0 + 52.0f) / (fh + 320.0f); // Klapuri's partial weighting
            if (c == 0 && h == 0)
                p->k_min = lo;
            if (hi > p->k_max)
                p->k_max = hi;
            ++nh;
        }
        p->nharm[c] = nh;
    }
}

static void mono_configure(a2m_dsp_t* d) {
    mono_t* m = &d->mono;
    front_configure(&m->f, d->rate, MONO_RATE, 0);
    m->f.hop = (int)(m->f.drate * MONO_HOP_S + 0.5f);
    if (m->f.hop < 1)
        m->f.hop = 1;
    m->win = (int)(m->f.drate * MONO_WIN_S);
    if (m->win > MONO_MAX_WIN)
        m->win = MONO_MAX_WIN;
    m->max_lag = (int)(m->f.drate / MONO_MIN_FREQ) + 2;
    if (m->max_lag > MONO_MAX_LAG - 2)
        m->max_lag = MONO_MAX_LAG - 2;
    m->min_lag = (int)(m->f.drate / MONO_MAX_FREQ);
    if (m->min_lag < 2)
        m->min_lag = 2;
    m->hist[0] = m->hist[1] = SILENCE_DB;
    m->prev_pitch = 0.0f;
}

static void mono_trk_reset(mono_trk_t* t) {
    stream_reset(&t->s);
    t->note = -1;
    t->cand = -1;
    t->cand_cnt = t->off_cnt = t->invalid = t->age = 0;
    t->jump = 0;
    t->need = 0;
}

static void poly_configure(a2m_dsp_t* d) {
    poly_t* p = &d->poly;
    front_configure(&p->f, d->rate, POLY_RATE, 1);
    p->f.hop = POLY_HOP;
    poly_tables(p);
    stream_reset(&p->s);
    memset(p->p_cnt, 0, sizeof(p->p_cnt));
    memset(p->p_off, 0, sizeof(p->p_off));
    memset(p->p_age, 0, sizeof(p->p_age));
    for (int i = 0; i < POLY_NOTES; ++i)
        p->p_last[i] = SILENCE_DB;
    p->p_total = p->p_short = SILENCE_DB;
    p->p_attack_age = 255;
}

// Apply output modes: release outputs that change, start / stop the detectors
static void apply_modes(a2m_dsp_t* d, a2m_out_t* out) {
    int need_mono = 0, need_poly = 0;
    for (int i = 0; i < A2M_OUTPUTS; ++i) {
        const a2m_output_params_t* op = &d->params.out[i];
        const int mode = op->active ? (op->poly ? MODE_POLY : MODE_MONO) : MODE_OFF;
        if (mode != d->out[i].mode) {
            release_output(d, out, i, 0);
            d->out[i].mode = mode;
            mono_trk_reset(&d->mt[i]);
        }
        need_mono |= mode == MODE_MONO;
        need_poly |= mode == MODE_POLY;
    }
    if (need_mono && !d->mono_on)
        mono_configure(d);
    d->mono_on = need_mono;
    if (need_poly && !d->poly_on)
        poly_configure(d);
    d->poly_on = need_poly;
}

// ---------------------------------------------------------------------------
// Monophonic
// ---------------------------------------------------------------------------

// Compute the difference function up to lag t (YIN step 2), on demand
static void mono_ensure(mono_t* m, int t) {
    const int W = m->win;
    while (m->done < t) {
        int lag = ++m->done;
        const float* a = m->a;
        const float* b = m->a - lag;
        float sum = 0.0f;
        for (int i = 0; i < W; ++i) {
            const float x = a[i] - b[i];
            sum += x * x;
        }
        m->diff[lag] = sum;
    }
}

// Vertex of the parabola through diff[t-1..t+1]
static float mono_vertex(mono_t* m, int t) {
    mono_ensure(m, t + 1);
    const float a = m->diff[t - 1], b = m->diff[t], c = m->diff[t + 1];
    const float den = a - 2.0f * b + c;
    if (den <= 0.0f)
        return (float)t;
    return t + fmaxf(-1.0f, fminf(1.0f, 0.5f * (a - c) / den));
}

static int mono_local_min(mono_t* m, int centre, int radius) {
    int best = centre - radius < 1 ? 1 : centre - radius;
    int hi = centre + radius > m->max_lag - 1 ? m->max_lag - 1 : centre + radius;
    mono_ensure(m, hi);
    for (int t = best + 1; t <= hi; ++t)
        if (m->diff[t] < m->diff[best])
            best = t;
    return best;
}

// YIN on the most recent window, compared with earlier samples. Returns frequency in Hz or 0 if no pitch.
static float mono_yin(mono_t* m, float threshold) {
    const int max_lag = m->max_lag;
    m->done = 0;
    m->diff[0] = 0.0f;
    mono_ensure(m, 2);
    float cum = m->diff[1];
    int tau = 0;
    for (int t = 2; t < max_lag; ++t) {
        mono_ensure(m, t + 1);
        const float l = m->diff[t - 1], c = m->diff[t], r = m->diff[t + 1];
        cum += c;
        if (t < m->min_lag || c > l || c >= r || cum <= 0.0f)
            continue;
        // Interpolated depth of the dip (high notes: the dip falls between two lags)
        const float depth = c - (l - r) * (l - r) / (8.0f * (l - 2.0f * c + r));
        if (depth * t < threshold * cum) {
            tau = t;
            break;
        }
    }
    if (tau <= 0 || tau >= max_lag - 1)
        return 0.0f;

    // Refine short periods on their multiples: the interpolation error is divided by the multiple
    float period = mono_vertex(m, tau);
    int mult = 1;
    while (period * mult * 2 < fminf(max_lag - 2, 64.0f)) {
        mult *= 2;
        const int t = mono_local_min(m, (int)(period * mult + 0.5f), 2);
        if (t < 2 || t >= max_lag - 1)
            break;
        period = mono_vertex(m, t) / mult;
    }
    const float freq = m->f.drate / period;
    return (freq >= MONO_MIN_FREQ && freq <= MONO_MAX_FREQ) ? freq : 0.0f;
}

// Count consecutive hops on the same candidate note. Returns 1 when confirmed.
static int mono_candidate(mono_trk_t* t, int note, float lvl, int confirm) {
    if (note == t->cand && t->cand_cnt > 0) {
        ++t->cand_cnt;
        t->peak = fmaxf(t->peak, lvl);
    } else {
        t->cand = note;
        t->cand_cnt = 1;
        t->peak = lvl;
    }
    if (t->cand_cnt < confirm)
        return 0;
    t->cand_cnt = 0;
    return 1;
}

// Tracker, before pitch detection: level thresholds and re-trigger. Returns 1 if the pitch of this hop is needed.
static int mono_pre(mono_trk_t* t, float lvl, float onset, float release, int attack) {
    if (t->note < 0) {
        if (lvl < onset) {
            t->cand_cnt = 0;
            return 0; // Nothing to analyse
        }
    } else if (lvl < release) {
        if (++t->off_cnt >= MONO_OFF_HOPS) {
            note_off(&t->s, t->note);
            t->note = -1;
            t->cand_cnt = 0;
        }
        return 0;
    } else {
        t->off_cnt = 0;
        if (++t->age > MONO_RETRIG_HOPS && attack) {
            // New attack (same note plucked again or another note): release, then detect as from silence
            note_off(&t->s, t->note);
            t->note = -1;
            t->cand_cnt = 0;
        }
    }
    return 1;
}

// Tracker, after pitch detection (pitch 0: no pitch)
static void mono_post(mono_trk_t* t, const a2m_output_params_t* op, float pitch, float prev_pitch, float lvl, float onset,
                      int confirm) {
    stream_t* s = &t->s;
    if (pitch <= 0.0f) {
        t->cand_cnt = 0;
        if (t->note >= 0 && ++t->invalid > MONO_INVALID_HOPS) {
            note_off(s, t->note);
            t->note = -1;
        }
        return;
    }
    t->invalid = 0;
    int note = (int)lrintf(pitch);
    if (note < 0 || note > 127)
        return;

    if (t->note < 0) {
        if (mono_candidate(t, note, lvl, confirm) && note_on(s, note, velocity(t->peak, onset))) {
            t->note = note;
            t->age = 0;
            t->jump = 0;
        }
        return;
    }

    const float dev = pitch - t->note;
    if (op->bend) {
        // Gradual movement within the bend range is pitch bend, a sudden jump is a new note
        if (prev_pitch > 0.0f && fabsf(pitch - prev_pitch) > MONO_JUMP_ST)
            t->jump = 1;
        else if (fabsf(dev) <= MONO_CHANGE_ST)
            t->jump = 0;
        // Bends slightly beyond the range (overshoot) are clamped, further is a new note
        if (!t->jump && fabsf(dev) <= op->bend_range + MONO_BEND_MARGIN_ST) {
            t->cand_cnt = 0;
            mono_bend(s, dev, op->bend_range);
            return;
        }
    } else if (s->bend_sent != BEND_CENTRE) {
        send_bend(s, BEND_CENTRE); // Pitch bend disabled while bent
    }

    if (fabsf(dev) > MONO_CHANGE_ST) {
        // Legato note change
        if (mono_candidate(t, note, lvl, confirm)) {
            note_off(s, t->note);
            t->note = -1;
            if (note_on(s, note, velocity(t->peak, onset))) {
                t->note = note;
                t->age = 0;
                t->jump = 0;
            }
        }
    } else {
        t->cand_cnt = 0;
    }
}

static void mono_hop(a2m_dsp_t* d, uint32_t frame) {
    mono_t* m = &d->mono;
    const int W = m->win;
    const int n = W + m->max_lag;
    if (m->f.fill < (uint32_t)n)
        return;
    float release, onset = thresholds(d, &release);
    const float nf = noise(d);
    const int confirm = 1 + (int)lrintf(3.0f * nf);
    const float* ring = m->f.ring;

    // Level of the most recent window
    uint32_t r = (m->f.wr - W) & RING_MASK;
    float e = 0.0f;
    for (int i = 0; i < W; ++i) {
        const float x = ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float lvl = 10.0f * log10f(e / W + 1e-20f);
    // Attack: level of the newest 2 hops compared with the 2 hops before them (the window smears a fast rise)
    const int ns = 2 * m->f.hop < W ? 2 * m->f.hop : W;
    e = 0.0f;
    for (int i = W - ns; i < W; ++i) {
        const float x = ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float short_lvl = 10.0f * log10f(e / ns + 1e-20f);
    const int attack = short_lvl > m->hist[1] + RETRIG_DB;
    m->hist[1] = m->hist[0];
    m->hist[0] = short_lvl;

    int need = 0;
    for (int i = 0; i < A2M_OUTPUTS; ++i) {
        mono_trk_t* t = &d->mt[i];
        if (d->out[i].mode != MODE_MONO)
            continue;
        t->s.frame = frame;
        t->need = mono_pre(t, lvl, onset, release, attack);
        need |= t->need;
    }
    if (!need)
        return;

    r = (m->f.wr - n) & RING_MASK;
    for (int i = 0; i < n; ++i)
        m->frame[i] = ring[(r + i) & RING_MASK];
    m->a = m->frame + n - W;
    const float freq = mono_yin(m, 0.3f - 0.2f * nf);
    const float pitch = freq > 0.0f ? 69.0f + 12.0f * log2f(freq / 440.0f) : 0.0f;
    const float prev_pitch = m->prev_pitch;
    m->prev_pitch = pitch;

    for (int i = 0; i < A2M_OUTPUTS; ++i)
        if (d->out[i].mode == MODE_MONO && d->mt[i].need)
            mono_post(&d->mt[i], &d->params.out[i], pitch, prev_pitch, lvl, onset, confirm);
}

// ---------------------------------------------------------------------------
// Polyphonic
// ---------------------------------------------------------------------------

// In-place radix-2 complex FFT of p->re / p->im (FFT_M points)
static void cfft(poly_t* p) {
    float* re = p->re;
    float* im = p->im;
    for (int i = 0; i < FFT_M; ++i) {
        const int j = p->bitrev[i];
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
                const float wr = p->tw_re[j * step], wi = p->tw_im[j * step];
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
static void poly_spectrum(poly_t* p) {
    const uint32_t r = (p->f.wr - FFT_N) & RING_MASK;
    for (int m = 0; m < FFT_M; ++m) {
        p->re[m] = p->f.ring[(r + 2 * m) & RING_MASK] * p->window[2 * m];
        p->im[m] = p->f.ring[(r + 2 * m + 1) & RING_MASK] * p->window[2 * m + 1];
    }
    cfft(p);
    // Real FFT of N points from the complex FFT of N/2 points (even samples real, odd samples imaginary)
    const float scale = 4.0f / FFT_N;
    p->amp[0] = fabsf(p->re[0] + p->im[0]) * scale;
    p->amp[FFT_M] = fabsf(p->re[0] - p->im[0]) * scale;
    for (int k = 1; k < FFT_M; ++k) {
        const float zr = p->re[k], zi = p->im[k];
        const float cr = p->re[FFT_M - k], ci = -p->im[FFT_M - k];
        const float er = 0.5f * (zr + cr), ei = 0.5f * (zi + ci);
        const float or_ = 0.5f * (zi - ci), oi = -0.5f * (zr - cr);
        const float xr = er + p->rtw_re[k] * or_ - p->rtw_im[k] * oi;
        const float xi = ei + p->rtw_re[k] * oi + p->rtw_im[k] * or_;
        p->amp[k] = sqrtf(xr * xr + xi * xi) * scale;
    }
}

// Moving average of src over +/-POLY_FLOOR_RADIUS bins into dst
static void moving_average(poly_t* p, const float* src, float* dst) {
    p->sum[0] = 0.0f;
    for (int k = 0; k <= FFT_M; ++k)
        p->sum[k + 1] = p->sum[k] + src[k];
    for (int k = 0; k <= FFT_M; ++k) {
        const int lo = k - POLY_FLOOR_RADIUS < 0 ? 0 : k - POLY_FLOOR_RADIUS;
        const int hi = k + POLY_FLOOR_RADIUS > FFT_M ? FFT_M : k + POLY_FLOOR_RADIUS;
        dst[k] = (p->sum[hi + 1] - p->sum[lo]) / (hi - lo + 1);
    }
}

// Find spectral peaks clearly above the noise floor
static void poly_peaks(poly_t* p, float margin_db, float abs_min) {
    // Noise floor: moving average, then again with the peaks clipped so they don't raise it
    moving_average(p, p->amp, p->floor);
    for (int k = 0; k <= FFT_M; ++k)
        p->clip[k] = fminf(p->amp[k], p->floor[k]);
    moving_average(p, p->clip, p->floor);

    const float gain = powf(10.0f, margin_db / 20.0f);
    float max_amp = 0.0f;
    for (int k = p->k_min; k <= p->k_max; ++k)
        max_amp = fmaxf(max_amp, p->amp[k]);
    const float min_amp = fmaxf(abs_min, max_amp * 0.003f); // Ignore window side lobes (-50 dB)

    memset(p->bin2peak, 0xff, sizeof(p->bin2peak));
    p->npeaks = 0;
    for (int k = p->k_min; k <= p->k_max && p->npeaks < POLY_MAX_PEAKS; ++k) {
        const float a = p->amp[k];
        if (a <= p->amp[k - 1] || a < p->amp[k + 1])
            continue;
        // Parabolic interpolation on log amplitude (a partial between two bins is attenuated by the window)
        const float l = logf(p->amp[k - 1] + 1e-20f), c = logf(a), r = logf(p->amp[k + 1] + 1e-20f);
        const float den = l - 2.0f * c + r;
        float x = den < 0.0f ? 0.5f * (l - r) / den : 0.0f;
        x = fmaxf(-0.5f, fminf(0.5f, x));
        const float pa = expf(c - 0.25f * (l - r) * x);
        if (pa < min_amp || pa < gain * p->floor[k])
            continue;
        p->pk_freq[p->npeaks] = (k + x) * p->bin_hz;
        p->pk_amp[p->npeaks] = pa;
        p->bin2peak[k] = p->npeaks++;
    }
}

// Weighted sum of the harmonic amplitudes of a candidate note. A[h] / P[h]: amplitude / peak index of each harmonic.
static float poly_salience(poly_t* p, int c, float* A, int* P) {
    const int nh = p->nharm[c];
    const float f0 = p->f0[c];
    float s = 0.0f;
    for (int h = 0; h < nh; ++h) {
        const float fh = f0 * (h + 1);
        const float tol = p->h_tol[c][h] * fh;
        float best = 0.0f;
        int bp = -1;
        for (int k = p->h_lo[c][h]; k <= p->h_hi[c][h]; ++k) {
            const int pk = p->bin2peak[k];
            if (pk < 0 || p->pk_amp[pk] <= best || fabsf(p->pk_freq[pk] - fh) > tol)
                continue;
            best = p->pk_amp[pk];
            bp = pk;
        }
        A[h] = best;
        P[h] = bp;
        s += p->h_w[c][h] * best;
    }
    // Need the fundamental, or the 2nd and 3rd harmonics (missing fundamental). Rejects sub-octave ghosts.
    if (nh < 1 || !(A[0] > 0.0f || (nh > 2 && A[1] > 0.0f && A[2] > 0.0f)))
        return 0.0f;
    return s;
}

// Iterative multiple pitch estimation. det[c]: level (dBFS RMS) of each detected note, SILENCE_DB if not detected.
static void poly_detect(poly_t* p, float* det, float release, float nf) {
    for (int c = 0; c < POLY_NOTES; ++c)
        det[c] = SILENCE_DB;
    poly_spectrum(p);
    poly_peaks(p, 4.0f + 10.0f * nf, 1.41f * powf(10.0f, (release - 24.0f) / 20.0f));
    if (!p->npeaks)
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
            const float s = poly_salience(p, c, A, P);
            const float se = p->s.on[POLY_LO + c] ? s * POLY_HELD_BIAS : s;
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

        poly_salience(p, best, A, P);
        // Spectrally smoothed partial amplitudes of this note: the excess over them belongs to other notes
        const int nh = p->nharm[best];
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
            p->pk_amp[P[h]] = fmaxf(0.0f, p->pk_amp[P[h]] - env[h]);
        }
    }

    // Harmonic ghosts: a note on a low harmonic of a louder note is mostly that note's residue (e.g. at onsets,
    // or with octave doubled chords: a quieter doubled octave is lost too). Not applied to held notes.
    static const int harm_st[] = {12, 19, 24, 28, 31};
    const float ghost_db = 12.0f - 8.0f * nf;
    for (int i = 0; i < nfound; ++i) {
        const int c = found[i];
        if (p->s.on[POLY_LO + c])
            continue;
        for (int j = 0; j < nfound; ++j) {
            const int b = found[j];
            const float base_lvl = det[b] > SILENCE_DB ? det[b] : p->p_last[b];
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

static void poly_hop(a2m_dsp_t* d, uint32_t frame) {
    poly_t* p = &d->poly;
    stream_t* s = &p->s;
    if (p->f.fill < FFT_N)
        return;
    s->frame = frame;
    float release, onset = thresholds(d, &release);
    const float nf = noise(d);
    const int confirm = 1 + (int)lrintf(2.0f * nf);
    float det[POLY_NOTES];

    // Total level of the most recent half window: no note can be above it
    const uint32_t r = (p->f.wr - FFT_N / 2) & RING_MASK;
    float e = 0.0f;
    for (int i = 0; i < FFT_N / 2; ++i) {
        const float x = p->f.ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float lvl = 10.0f * log10f(e / (FFT_N / 2) + 1e-20f);
    // Attack: sudden rise of the level of the newest hop. Held notes that get louder soon after are re-triggered.
    e = 0.0f;
    for (int i = FFT_N / 2 - POLY_HOP; i < FFT_N / 2; ++i) {
        const float x = p->f.ring[(r + i) & RING_MASK];
        e += x * x;
    }
    const float short_lvl = 10.0f * log10f(e / POLY_HOP + 1e-20f);
    if (short_lvl > p->p_short + POLY_ATTACK_DB) {
        p->p_attack_age = 0;
        memcpy(p->p_attack_pre, p->p_last, sizeof(p->p_attack_pre));
        memcpy(p->p_attack_min, p->p_last, sizeof(p->p_attack_min));
        memset(p->p_retrig, 0, sizeof(p->p_retrig));
    } else if (p->p_attack_age < 255) {
        ++p->p_attack_age;
    }
    p->p_short = short_lvl;
    // During an attack the window is partly filled: weak partials of a louder note may resolve before its
    // fundamental and look like notes. Weak new notes wait until the level stops rising.
    const int rising = lvl > p->p_total + POLY_RISING_DB;
    p->p_total = lvl;
    if (lvl < (s->held ? release : onset)) {
        if (!s->held)
            return; // Nothing to analyse
        for (int c = 0; c < POLY_NOTES; ++c)
            det[c] = SILENCE_DB;
    } else {
        poly_detect(p, det, release, nf);
    }
    float strongest = SILENCE_DB;
    for (int c = 0; c < POLY_NOTES; ++c)
        strongest = fmaxf(strongest, det[c]);

    for (int c = 0; c < POLY_NOTES; ++c) {
        const int note = POLY_LO + c;
        const float l = det[c];
        if (!s->on[note]) {
            if (l >= onset && s->held < POLY_MAX_NOTES) {
                // A weak note keeps its count during an attack and is decided when the attack is over
                if (!rising || l >= strongest - POLY_WEAK_DB) {
                    if (p->p_cnt[c] == 0 || l > p->p_peak[c])
                        p->p_peak[c] = l;
                    if (++p->p_cnt[c] >= confirm) {
                        p->p_cnt[c] = p->p_off[c] = p->p_age[c] = 0;
                        note_on(s, note, velocity(p->p_peak[c], onset));
                    }
                }
            } else {
                p->p_cnt[c] = 0;
            }
        } else {
            if (p->p_age[c] < 255)
                ++p->p_age[c];
            if (l < release) {
                if (++p->p_off[c] >= POLY_OFF_HOPS)
                    note_off(s, note);
            } else {
                p->p_off[c] = 0;
                // After an attack the old and new vibrations may first cancel: compare with the lowest level since
                p->p_attack_min[c] = fminf(p->p_attack_min[c], l);
                if (p->p_age[c] > p->p_attack_age + POLY_RETRIG_HOPS && p->p_attack_age <= POLY_ATTACK_HOPS && !p->p_retrig[c] &&
                    l > p->p_attack_min[c] + POLY_RETRIG_RISE_DB && l > p->p_attack_pre[c] + POLY_RETRIG_PRE_DB) {
                    note_off(s, note);
                    note_on(s, note, velocity(l, onset));
                    p->p_age[c] = 0;
                    p->p_retrig[c] = 1;
                }
            }
        }
        p->p_last[c] = l;
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
    for (int i = 0; i < A2M_OUTPUTS; ++i) {
        d->params.out[i].bend_range = 2.0f;
        d->out[i].mode = MODE_OFF;
        d->out[i].bend_sent = BEND_CENTRE;
        mono_trk_reset(&d->mt[i]);
    }
    stream_reset(&d->poly.s);
    fft_init(&d->poly);
    return d;
}

void a2m_dsp_free(a2m_dsp_t* d) {
    free(d);
}

void a2m_dsp_release_all(a2m_dsp_t* d, a2m_out_t* out, uint32_t frame) {
    memset(out->count, 0, sizeof(out->count));
    for (int i = 0; i < A2M_OUTPUTS; ++i) {
        release_output(d, out, i, frame);
        mono_trk_reset(&d->mt[i]);
    }
    // Restart detection from silence
    if (d->mono_on)
        mono_configure(d);
    if (d->poly_on)
        poly_configure(d);
}

void a2m_dsp_set_samplerate(a2m_dsp_t* d, uint32_t rate, a2m_out_t* out) {
    if (rate)
        d->rate = rate;
    a2m_dsp_release_all(d, out, 0);
}

void a2m_dsp_set_params(a2m_dsp_t* d, const a2m_params_t* params) {
    d->params = *params;
}

void a2m_dsp_process(a2m_dsp_t* d, const float* in, uint32_t frames, a2m_out_t* out) {
    memset(out->count, 0, sizeof(out->count));
    apply_modes(d, out);
    if (d->mono_on) {
        for (uint32_t i = 0; i < frames; ++i)
            if (front_push(&d->mono.f, in[i]))
                mono_hop(d, i);
        for (int i = 0; i < A2M_OUTPUTS; ++i) {
            if (d->out[i].mode != MODE_MONO)
                continue;
            emit_stream(d, out, i, &d->mt[i].s);
            d->mt[i].s.count = 0;
        }
    }
    if (d->poly_on) {
        for (uint32_t i = 0; i < frames; ++i)
            if (front_push(&d->poly.f, in[i]))
                poly_hop(d, i);
        for (int i = 0; i < A2M_OUTPUTS; ++i)
            if (d->out[i].mode == MODE_POLY)
                emit_stream(d, out, i, &d->poly.s);
        d->poly.s.count = 0;
    }
}
