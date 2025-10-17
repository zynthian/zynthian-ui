import time

from zyncoder.zyncore import lib_zyncore

from zyngine.ctrldev.zynthian_ctrldev_akai_apc_key25 import \
    zynthian_ctrldev_akai_apc_key25, COLORS, BTN_PAD_END

from zyngine.ctrldev.zynthian_ctrldev_akai_apc_key25_mk2_sooperlooper import \
    zynthian_ctrldev_akai_apc_key25_mk2_sooperlooper, looper_handler, split_every, generator_difference, TRACK_LEVELS, KNOBS_PER_ROW, getGlob, getLoopoffset, getDeviceSetting

from zyngine.zynthian_engine_sooperlooper import (
    SL_STATE_UNKNOWN,
    SL_STATE_OFF,
    SL_STATE_REC_STARTING,
    SL_STATE_RECORDING,
    SL_STATE_REC_STOPPING,
    SL_STATE_PLAYING,
    SL_STATE_OVERDUBBING,
    SL_STATE_MULTIPLYING,
    SL_STATE_INSERTING,
    SL_STATE_REPLACING,
    SL_STATE_DELAYING,
    SL_STATE_MUTED,
    SL_STATE_SCRATCHING,
    SL_STATE_PLAYING_ONCE,
    SL_STATE_SUBSTITUTING,
    SL_STATE_PAUSED,
    SL_STATE_UNDO_ALL,
    SL_STATE_TRIGGER_PLAY,
    SL_STATE_UNDO,
    SL_STATE_REDO,
    SL_STATE_REDO_ALL,
    SL_STATE_OFF_MUTED,
)


LEVEL_COLORS = [
    COLORS.COLOR_RED,           # peak meter
    COLORS.COLOR_RED,           # rec thresh
    COLORS.COLOR_GREEN,         # gain
    COLORS.COLOR_GREEN,         # wet
    COLORS.COLOR_YELLOW,        # dry
    COLORS.COLOR_GREEN,         # feedback
    COLORS.COLOR_RED,           # pitch
    COLORS.COLOR_RED,           # none
]

SETTINGCOLORS = [
    COLORS.COLOR_GREEN,
    COLORS.COLOR_GREEN,
    COLORS.COLOR_GREEN,
    COLORS.COLOR_GREEN,
    COLORS.COLOR_RED,
    COLORS.COLOR_RED,
    # -3 = internal,  -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed)
    [
        COLORS.COLOR_GREEN,
        COLORS.COLOR_YELLOW,
        COLORS.COLOR_RED,
        COLORS.COLOR_BLACK,
        COLORS.COLOR_YELLOW,
        COLORS.COLOR_GREEN,
    ],
    [
        COLORS.COLOR_YELLOW, # 
        COLORS.COLOR_RED,    # jack? 
        COLORS.COLOR_YELLOW, # 8th
        COLORS.COLOR_GREEN,  # mups
    ],
]

class BRIGHTS:
    LED_OFF = 0x80
    LED_BRIGHT_10 = 0x90
    LED_BRIGHT_25 = 0x91
    LED_BRIGHT_50 = 0x92
    LED_BRIGHT_65 = 0x93
    LED_BRIGHT_75 = 0x94
    LED_BRIGHT_90 = 0x95
    LED_BRIGHT_100 = 0x96
    LED_PULSING_16 = 0x97
    LED_PULSING_8 = 0x97
    LED_PULSING_4 = 0x97
    LED_PULSING_2 = 0x97
    LED_BLINKING_24 = 0x97
    LED_BLINKING_16 = 0x97
    LED_BLINKING_8 = 0x97
    LED_BLINKING_4 = 0x97
    LED_BLINKING_2 = 0x97

SL_STATES = {
    SL_STATE_UNKNOWN: {
        "name": "unknown",
        "idx": None,
        "color": COLORS.COLOR_BLACK,
        "ledmode": BRIGHTS.LED_OFF,
    },
    SL_STATE_OFF: {
        "name": "off",
        "idx": None,
        "color": COLORS.COLOR_WHITE,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_REC_STARTING: {
        "name": "waitstart",
        "idx": 0,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_PULSING_16,
    },
    SL_STATE_RECORDING: {
        "name": "record",
        "idx": 0,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_REC_STOPPING: {
        "name": "waitstop",
        "idx": 0,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_PULSING_8,
    },
    SL_STATE_PLAYING: {
        "name": "play",
        "idx": None,
        "color": COLORS.COLOR_GREEN,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_OVERDUBBING: {
        "name": "overdub",
        "idx": 0,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_MULTIPLYING: {
        "name": "multiply",
        "idx": 1,
        "color": COLORS.COLOR_YELLOW,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_INSERTING: {
        "name": "insert",
        "idx": 2,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_REPLACING: {
        "name": "replace",
        "idx": 3,
        "color": COLORS.COLOR_YELLOW,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_SUBSTITUTING: {
        "name": "substitute",
        "idx": 4,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_DELAYING: {
        "name": "delay",
        "idx": 3,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_10,
    },
    SL_STATE_MUTED: {
        "name": "mute",
        "idx": None,
        "color": COLORS.COLOR_YELLOW,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_SCRATCHING: {
        "name": "scratch",
        "idx": None,
        "color": COLORS.COLOR_BLUE,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_PLAYING_ONCE: {
        "name": "oneshot",
        "idx": 5,
        "color": COLORS.COLOR_GREEN,
        "ledmode": BRIGHTS.LED_PULSING_8,
    },
    SL_STATE_PAUSED: {
        "name": "pause",
        "idx": None,
        "color": COLORS.COLOR_YELLOW,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_UNDO_ALL: {
        "name": "undo_all",
        "idx": None,
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_UNDO: {
        "name": "undo_all",
        "idx": None,
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_50,
    },
    SL_STATE_REDO: {
        "name": "redo",
        "idx": None,
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_50,
    },
    SL_STATE_REDO_ALL: {
        "name": "redo_all",
        "idx": None,
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_OFF_MUTED: {
        "name": "offmute",
        "idx": None,
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },  # undocumented
    SL_STATE_TRIGGER_PLAY: {
        "name": "trigger_play",
        "idx": 6,
        "color": COLORS.COLOR_GREEN,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
}


class zynthian_ctrldev_akai_apc_key25_sooperlooper(zynthian_ctrldev_akai_apc_key25_mk2_sooperlooper, zynthian_ctrldev_akai_apc_key25):

    dev_ids = ["APC Key 25 MIDI 1", "APC Key 25 IN 1"]
    driver_name = 'AKAI APC Key25 + SL'
    unroute_from_chains = 0b1111111111111101

    @classmethod
    def get_autoload_flag(cls):
        return False

    class looper_handler(looper_handler):

        LEVEL_COLORS = LEVEL_COLORS
        SL_STATES = SL_STATES
        SETTINGCOLORS = SETTINGCOLORS
        COLOR_LOAD = COLORS.COLOR_GREEN
        COLOR_SAVE = COLORS.COLOR_YELLOW
        COLOR_YES = COLORS.COLOR_GREEN
        COLOR_NO = COLORS.COLOR_RED
        COLOR_EIGHTHS = COLORS.COLOR_YELLOW
        COLOR_EIGHTH_BTN = COLORS.COLOR_YELLOW
        matrixPadLedmode = {".": BRIGHTS.LED_BRIGHT_100, "_": BRIGHTS.LED_OFF}
        matrixPadColor = {".": COLORS.COLOR_YELLOW, "_": COLORS.COLOR_DARK_GREY}

        def init(self):
            super().init()
            self._knobmoves = {}

        def render(self):
            pads = self.createAllPads(self.state)
            notes = split_every(3, pads)
            these = generator_difference(notes, self.last_notes)
            self.last_notes = these;
            sendable = []
            for pad in these:
                if pad[0] < 0x92 and pad[1] <= BTN_PAD_END:
                    # For some reason simply sending a note off does not work.
                    # lib_zyncore.dev_send_midi_event(self.idev_out, bytes(pad), 3)
                    # The following does work, but something tells me to stay with they ctrldev_base way
                    # lib_zyncore.dev_send_note_on(self.idev, 0, pad[1], 0)
                    self._leds.led_off(pad[1], False)
                elif pad[0] > 0x96:
                    pad[0] = 0x90
                    pad[2] = pad[2] + 1
                    sendable.extend(pad)
                else:
                    pad[0] = 0x90
                    sendable.extend(pad)

            # logging.debug(pads, len(pads))
            if (len(sendable) > 0):
                msg = bytes(sendable)
                lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            # NOW RENDER


        def set(self, val, ctrl, track, loopnum):
            val = val/127
            curval = track.get(ctrl)
            if curval is None:
                return
            value_min = 0
            value_max = 1
            if ctrl == 'pitch_shift':
                value_min = -12
                value_max = 12
            value_range = abs(value_max - value_min)
            value = value_min + val * value_range
            ctrlid = f'{ctrl}{loopnum}'
            now = time.perf_counter()
            then = self._knobmoves.get(ctrlid)
            if ((then is not None) and ((now - then) < 0.2)) or (abs(value - curval) < (abs(value_max - value_min) * 0.01)):
                new_value = value_min + val * value_range
                self.just_send(f"/sl/{loopnum}/set", ("s", ctrl), ("f", new_value))
                self._knobmoves[ctrlid] = now
            else:
                pass

        def cc_change(self, ccnum, ccval):
            knobnum = ccnum - 48
            if self._current_handler == self._levels2_handler:
            # if doLevelsOfSelectedMode(self.state):
                if knobnum == 0:
                    return
                level = TRACK_LEVELS[knobnum]
                if not level:
                    return
                loopnum = getGlob("selected_loop_num", self.state)
                if loopnum == -1:
                    return
                self.set(ccval, level, self.state["tracks"][loopnum], loopnum)
                return
            loopoffset = getLoopoffset(self.state)
            loopnum = (knobnum % KNOBS_PER_ROW) - (loopoffset - 1)
            tracks = self.state["tracks"]
            track = tracks.get(loopnum)
            if track is None:  # Check if track is None
                return None  # Or handle as needed
            funnum = knobnum // KNOBS_PER_ROW
            # todo: this could be larger than 1?
            funs = ["wet", "pan"]
            fun = funs[funnum]
            if fun == "pan":
                channel_count = int(track.get("channel_count", 0))
                for c in range(
                    1, channel_count + 1
                ):  # Loop from 1 to channel_count inclusive
                    ctrl = f"pan_{c}"
                    if getDeviceSetting("shifted", self.state):
                        self.set(ccval, ctrl, track, loopnum)
                    else:
                        if channel_count == 2:
                            if c == 1:
                                if ccval >= 64:
                                    self.set(2*(ccval - 63.5), ctrl, track, loopnum)
                            if c == 2:
                                if ccval <= 64:
                                    self.set(ccval*2, ctrl, track, loopnum)
                        else:
                            self.set(ccval, ctrl, track, loopnum)
            else:
                self.set(ccval, fun, track, loopnum)



