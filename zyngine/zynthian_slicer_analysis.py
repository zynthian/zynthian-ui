# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Slicer analysis helpers
#
# Pure functions that build and validate slice lists for the slicer engine.
# A slice is a dict: {"start", "end", "note", "gain", "mode"}, with start
# and end in frames of the source file and mode one of PLAY_MODES.
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import logging

MAX_SLICES = 127  # One slice per MIDI note 1..127 (zynclippy has no note 0 slot)
MAX_NOTE = 127

# How a slice plays: to its end, while the key is held, or repeating while held
PLAY_MODES = ("one-shot", "gate", "loop")
# Mode of newly created slices. Saved slices without a mode keep the older
# one-shot default (see get_play_mode).
DEFAULT_PLAY_MODE = "gate"


def get_play_mode(sl):
    """Return a slice's play mode, converting the older one_shot flag."""
    mode = sl.get("mode")
    if mode in PLAY_MODES:
        return mode
    return "one-shot" if sl.get("one_shot", True) else "gate"


def max_slices(base_note):
    """Return how many slices fit between base_note and the top MIDI note."""
    return max(0, min(MAX_SLICES, MAX_NOTE - int(base_note) + 1))


def make_even_slices(frames, count):
    """Split frames into count equal, contiguous slices."""
    count = max(1, min(MAX_SLICES, int(count)))
    frames = int(frames)
    if frames <= 0:
        return []
    step = frames / count
    slices = []
    for i in range(count):
        start = int(round(i * step))
        end = int(round((i + 1) * step)) if i < count - 1 else frames
        if end > start:
            slices.append({"start": start, "end": end, "gain": 1.0, "mode": DEFAULT_PLAY_MODE})
    return slices


def detect_transients(fpath, source_frames, threshold=50, min_gap_ms=50):
    """Detect transients using a simple energy-flux onset detector.

    This intentionally uses only numpy/soundfile, which are already present
    in Zynthian. It is not as sophisticated as aubio/librosa but works well
    for drum loops and percussive material.

    fpath: Audio file to analyse
    source_frames: Length of the file in frames, used to scale positions
    threshold: Sensitivity 0..100 (higher detects fewer onsets)
    min_gap_ms: Minimum distance between detected onsets
    Returns: List of contiguous slices, or [] if nothing was detected
    """
    try:
        import numpy as np
        import soundfile as sf
        data, sr = sf.read(fpath, dtype="float32", always_2d=True)
    except Exception as e:
        logging.warning(f"Can't read audio for transient detection: {e}")
        return []
    if data.size == 0 or sr <= 0:
        return []
    mono = data.mean(axis=1)
    frame = max(64, int(sr * 0.01))
    if len(mono) <= frame:
        return []
    energy = np.square(mono)
    cum = np.concatenate(([0.0], np.cumsum(energy, dtype=np.float64)))
    n_frames = (len(mono) - frame) // frame + 1
    starts = np.arange(n_frames) * frame
    env = np.sqrt((cum[starts + frame] - cum[starts]) / frame + 1e-12)
    flux = np.maximum(np.diff(env, prepend=env[:1]), 0.0)
    if len(flux) > 2:
        flux = np.convolve(flux, np.ones(3) / 3.0, mode="same")
    max_flux = float(np.max(flux))
    if max_flux <= 0:
        return []
    median_flux = float(np.median(flux))
    threshold = max(0.0, min(100.0, float(threshold)))
    onset_threshold = median_flux + (threshold / 100.0) * (max_flux - median_flux)
    candidates = []
    for i in range(1, len(flux) - 1):
        if flux[i] >= onset_threshold and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]:
            candidates.append((float(flux[i]), int(i * frame)))
    # Keep the strongest onsets that respect the minimum gap
    candidates.sort(key=lambda x: x[0], reverse=True)
    min_gap = max(1, int(sr * max(1.0, float(min_gap_ms)) / 1000.0))
    selected = []
    for _, pos in candidates:
        if all(abs(pos - p) >= min_gap for p in selected):
            selected.append(pos)
            if len(selected) >= MAX_SLICES - 1:
                break
    positions = [0] + sorted(selected) + [len(mono)]
    slices = []
    for start, end in zip(positions, positions[1:]):
        start = int(start * source_frames / len(mono))
        end = int(end * source_frames / len(mono))
        if end > start:
            slices.append({"start": start, "end": end, "gain": 1.0, "mode": DEFAULT_PLAY_MODE})
    return slices


def normalize_slices(slices, frames, base_note):
    """Return slices as a strict contiguous partition with notes assigned.

    Slice starts are authoritative: invalid slices are skipped, starts are
    made strictly increasing, and every internal end is set to the following
    slice's start. The first start and the last end stay within the sample.
    Slice i always plays on MIDI note base_note + i; slices that would go
    above the top MIDI note are dropped.

    slices: List of slice dicts (only start/end are required)
    frames: Sample length in source frames
    base_note: MIDI note of the first slice (1..127)
    """
    normalized = []
    if frames <= 0:
        return normalized
    last_start = -1
    for sl in slices:
        try:
            start = int(sl["start"])
            end = int(sl["end"])
            gain = max(0.0, float(sl.get("gain", 1.0)))
            mode = get_play_mode(sl)
        except Exception:
            continue
        if start >= end:
            continue
        start = max(last_start + 1, min(max(0, start), frames - 1))
        if start >= frames:
            break
        normalized.append({"start": start, "end": end, "gain": gain, "mode": mode})
        last_start = start

    limit = max_slices(base_note)
    if len(normalized) > limit:
        logging.warning(f"Only {limit} slices fit above base note {base_note}; "
                        f"dropping {len(normalized) - limit}")
        del normalized[limit:]
    if not normalized:
        return normalized

    for i, sl in enumerate(normalized):
        sl["note"] = int(base_note) + i
    for left, right in zip(normalized, normalized[1:]):
        left["end"] = right["start"]
    last = normalized[-1]
    last["end"] = max(last["start"] + 1, min(last["end"], frames))
    return normalized
