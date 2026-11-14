"""Tiny Standard MIDI File writer/reader used to build test inputs independently of libzynsmf."""

import struct


def vlq(n):
    """Variable-length quantity."""
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def track(events, running_status=False):
    """MTrk chunk from [(absolute tick, bytes)], adding an end-of-track meta event at the last tick."""
    body, last, prev_status = b"", 0, None
    for tick, data in events:
        body += vlq(tick - last)
        if running_status and data[0] == prev_status and 0x80 <= data[0] < 0xF0:
            data = data[1:]                       # omit the repeated status byte
        else:
            prev_status = data[0] if 0x80 <= data[0] < 0xF0 else None
        body += data
        last = tick
    body += vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def smf(tracks, ppqn=480, fmt=1):
    return b"MThd" + struct.pack(">IHHH", 6, fmt, len(tracks), ppqn) + b"".join(tracks)


def tempo(bpm):
    return b"\xff\x51\x03" + int(60_000_000 / bpm).to_bytes(3, "big")


def note_on(ch, note, vel):
    return bytes([0x90 | ch, note, vel])


def note_off(ch, note):
    return bytes([0x80 | ch, note, 0])


def header(data):
    """(format, number of tracks, division) of an SMF byte string."""
    assert data[:4] == b"MThd"
    _, fmt, ntrks, division = struct.unpack(">IHHH", data[4:14])
    return fmt, ntrks, division


# Two beats of music at 120 BPM / 480 ppqn: C4 for one beat, then D4 for one beat. 1.0 s long.
SONG = smf([track([(0, tempo(120)), (0, note_on(0, 60, 100)), (480, note_off(0, 60)),
                   (480, note_on(0, 62, 90)), (960, note_off(0, 62))])])
