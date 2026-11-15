# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Slicer SFZ export
#
# Writes a self-contained SFZ instrument (one region per slice) plus a WAV
# copy of the sample, laid out as a sfizz bank: <output_dir>/<name>/<name>.sfz
# A <name>.yml next to it gives the Zynthian sfizz chain a "tune" control.
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

import os
import re
import math
import shutil

from zyngine.zynthian_slicer_analysis import get_play_mode

# Records which sample an export folder was made from, so re-exporting the
# same sample overwrites it while a different sample with the same name
# gets a new folder.
SOURCE_MARKER = ".zynthian_slicer_source"

MIN_VOLUME_DB = -144.0
MAX_VOLUME_DB = 6.0  # SFZ volume opcode range
SFZ_LOOP_MODES = {"one-shot": "one_shot", "gate": "no_loop", "loop": "loop_continuous"}

# Tune is exported as a MIDI CC, so it stays adjustable (and MIDI-learnable)
# in sfizz. Each CC step is exactly one semitone and CC 64 is no change, so
# the range is -64..+63 semitones. Zynthian maps a -64..63 controller to CC
# values 0..127 exactly (value + 64), so its knob reads in semitones.
TUNE_CC = 20         # General purpose CC, undefined in the MIDI spec
TUNE_CC_CENTER = 64  # CC value for no tuning
MIN_TUNE = -TUNE_CC_CENTER
MAX_TUNE = 127 - TUNE_CC_CENTER


def build_sfz(slices, sample_name, gain_db=0.0, polyphony=16, fade_seconds=0.0, tune=0):
    """Return SFZ text with one region per slice.

    slices: Normalized slices (start/end in sample frames, end exclusive)
    sample_name: Sample filename, relative to the .sfz file
    gain_db: Master gain applied to every region
    polyphony: Maximum simultaneous voices, as in the slicer
    fade_seconds: Attack/release time matching the slicer's voice fades
    tune: Initial tuning in semitones, adjustable in sfizz with CC TUNE_CC
    """
    if not slices:
        raise ValueError("No slices to export")
    # No <control> default_path: sfizz prepends it verbatim to each sample
    # name (no separator added), and samples already resolve relative to the
    # .sfz file.
    tune_cc_value = TUNE_CC_CENTER + max(MIN_TUNE, min(int(tune), MAX_TUNE))
    lines = [
        "// Zynthian slicer export",
        "<control>",
        f"label_cc{TUNE_CC}=Tune",
        f"set_cc{TUNE_CC}={tune_cc_value}",
        "",
        "<global>",
        f"polyphony={max(1, int(polyphony))}",
        f"ampeg_attack={fade_seconds:.4f}",
        f"ampeg_release={fade_seconds:.4f}",
        # Tune CC: 100 cents per CC step, centered on TUNE_CC_CENTER.
        # Transposing pitch resamples like the slicer: pitch and speed together.
        f"transpose={-TUNE_CC_CENTER}",
        f"pitch_oncc{TUNE_CC}={127 * 100}",
        "",
    ]
    for i, sl in enumerate(slices):
        gain = max(0.0, float(sl.get("gain", 1.0)))
        volume_db = gain_db + 20.0 * math.log10(gain) if gain > 0.0 else MIN_VOLUME_DB
        volume_db = max(MIN_VOLUME_DB, min(MAX_VOLUME_DB, volume_db))
        note = int(sl["note"])
        mode = get_play_mode(sl)
        lines += [
            f"// slice {i}",
            "<region>",
            f"sample={sample_name}",
            f"offset={int(sl['start'])}",
            f"end={int(sl['end']) - 1}",  # SFZ end is inclusive
            f"lokey={note}",
            f"hikey={note}",
            f"pitch_keycenter={note}",
            f"loop_mode={SFZ_LOOP_MODES[mode]}",
        ]
        if mode == "loop":
            # Loop the whole slice (positions are absolute, end inclusive)
            lines += [f"loop_start={int(sl['start'])}", f"loop_end={int(sl['end']) - 1}"]
        lines += [f"volume={volume_db:.2f}", ""]
    return "\n".join(lines)


def build_controller_yaml(tune=0):
    """Return the Zynthian controller config for an exported SFZ.

    The sfizz engine reads <name>.yml instead of parsing the SFZ's label_cc
    opcodes, which lets the tune control show semitones instead of CC values.
    """
    tune = max(MIN_TUNE, min(int(tune), MAX_TUNE))
    return "\n".join([
        "# Zynthian controls for this slicer export (read by the sfizz engine)",
        "controllers:",
        "  slicer:",
        "    tune:",
        f"      midi_cc: {TUNE_CC}",
        f"      value_min: {MIN_TUNE}",
        f"      value_max: {MAX_TUNE}",
        f"      value: {tune}",
        "      is_integer: true",
        "",
    ])


def export_sfz(sample_path, slices, output_dir, **sfz_options):
    """Write <output_dir>/<name>/<name>.sfz and a WAV copy of the sample.

    Also writes <name>.yml with the Zynthian controller config.

    sample_path: Source sample (any format libsndfile can read)
    slices: Normalized slices
    output_dir: Parent folder, e.g. the user's sfizz bank folder
    sfz_options: Passed to build_sfz()
    Returns: Path of the written .sfz file
    Raises: Exception on failure
    """
    if not slices:
        raise ValueError("No slices to export")
    base = os.path.splitext(os.path.basename(sample_path))[0]
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" ._") or "slicer"
    name = _get_export_name(output_dir, base, sample_path)
    export_dir = os.path.join(output_dir, name)
    os.makedirs(export_dir, exist_ok=True)

    wav_path = os.path.join(export_dir, name + ".wav")
    _write_wav(sample_path, wav_path)
    sfz_path = os.path.join(export_dir, name + ".sfz")
    with open(sfz_path, "w", encoding="utf-8") as fh:
        fh.write(build_sfz(slices, os.path.basename(wav_path), **sfz_options))
    with open(os.path.join(export_dir, name + ".yml"), "w", encoding="utf-8") as fh:
        fh.write(build_controller_yaml(sfz_options.get("tune", 0)))
    with open(os.path.join(export_dir, SOURCE_MARKER), "w", encoding="utf-8") as fh:
        fh.write(os.path.abspath(sample_path))
    return sfz_path


def _get_export_name(output_dir, base, sample_path):
    """Return a folder name: reuse this sample's folder, else find a free one."""
    src = os.path.abspath(sample_path)
    name = base
    n = 1
    while os.path.exists(os.path.join(output_dir, name)):
        try:
            with open(os.path.join(output_dir, name, SOURCE_MARKER), "r", encoding="utf-8") as fh:
                if fh.read().strip() == src:
                    return name
        except OSError:
            pass
        n += 1
        name = f"{base}_{n}"
    return name


def _write_wav(src, dest):
    """Copy a WAV sample, or decode any other format to 24-bit WAV.

    Only libsndfile is used: it is the decoder the slicer loads samples with,
    so slice frame positions stay valid. Other decoders (e.g. ffmpeg) may add
    or trim encoder padding.
    """
    if os.path.splitext(src)[1].lower() == ".wav":
        if os.path.abspath(src) != os.path.abspath(dest):
            shutil.copy2(src, dest)
        return
    import soundfile as sf
    data, samplerate = sf.read(src, dtype="float32", always_2d=True)
    sf.write(dest, data, samplerate, subtype="PCM_24")
