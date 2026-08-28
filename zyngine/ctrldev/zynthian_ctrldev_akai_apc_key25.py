from time import monotonic
from zyngine.ctrldev.zynthian_ctrldev_akai_apc_key25_mk2 import zynthian_ctrldev_akai_apc_key25_mk2, NotePad, \
    MAX_STUTTER_VELFX, MAX_STUTTER_SPEED, \
    KNOB_1, KNOB_2, KNOB_3, KNOB_4, KNOB_5, KNOB_6, KNOB_7, KNOB_8, \
    KNOB_ZYN_1, KNOB_ZYN_2, KNOB_ZYN_3, KNOB_ZYN_4, \
    CCNUM_ZYNPOT, NOTE_ZYNSWITCH, ZYNSWITCH_NOTE, \
    LED_BRIGHT_10, LED_BRIGHT_100, LED_PULSING_8, \
    EV_NOTE_OFF, EV_NOTE_ON, EV_CC, \
    BTN_PAD_START, BTN_PAD_END, \
    BTN_OPT_ADMIN, BTN_MIX_LEVEL, BTN_CTRL_PRESET, BTN_ZS3_SHOT, BTN_ALT, BTN_PAD_STEP, BTN_METRONOME, BTN_F1, \
    BTN_PAD_RECORD,\
    BTN_PAD_STOP,\
    BTN_PAD_PLAY,\
    BTN_F2,\
    BTN_F3,\
    BTN_SEL_YES,\
    BTN_PAD_UP,\
    BTN_BACK_NO,\
    BTN_PAD_LEFT,\
    BTN_PAD_DOWN,\
    BTN_PAD_RIGHT,\
    BTN_F4

from zyncoder.zyncore import lib_zyncore

# APC Key25 (gen 1) LED colors and modes
class COLORS:
    COLOR_BLACK = 0x00
    COLOR_DARK_GREY = 0x01
    COLOR_GREEN = COLOR_INSERT_CHAIN = COLOR_STATE_1 = COLOR_PLAYING = COLOR_ALT_OFF = COLOR_FN = 0x01
    COLOR_BLUE = 0x25
    COLOR_AQUA = 0x21
    COLOR_BLUE_DARK = 0x2D
    COLOR_BLUE_LIGHT = 0x24
    COLOR_WHITE = 0x03
    COLOR_EGYPT = 0x6C
    COLOR_ORANGE = 0x09
    COLOR_ORANGE_LIGHT = 0x08
    COLOR_AMBER = 0x54
    COLOR_RUSSET = 0x3D
    COLOR_PURPLE = 0x51
    COLOR_PINK = 0x39
    COLOR_PINK_LIGHT = 0x52
    COLOR_PINK_WARM = 0x38
    COLOR_LIME = 0x4B
    COLOR_LIME_DARK = 0x11
    COLOR_DARK_GREEN = 0x41
    COLOR_GREEN_YELLOW = 0x4A
    COLOR_BROWNISH_RED = 0x0A
    COLOR_BROWN_LIGHT = 0x7E
    SOFT_OFF = 0x00
    SOFT_ON = 0x01
    SOFT_BLINK = 0x02
    COLOR_RED = COLOR_STATE_2 = COLOR_ALT_ON = 0x03 # 0x05
    COLOR_BLUE_DARK = 0x05 # 0x2D
    COLOR_WHITE = 0x05 # 0x08
    COLOR_EGYPT = 0x6C
    COLOR_ORANGE = 0x09
    COLOR_AMBER = 0x54
    COLOR_RUSSET = 0x3D
    COLOR_PURPLE = 0x03 # 0x51
    COLOR_PINK = 0x39
    COLOR_PINK_LIGHT = 0x52
    COLOR_PINK_WARM = 0x38
    COLOR_YELLOW = COLOR_STATE_0 = COLOR_LOCAL_ALT_ON = 0x05 # 0x0D
    COLOR_LIME = 0x4B
    COLOR_LIME_DARK = 0x11
    COLOR_GREEN_YELLOW = 0x4A


class zynthian_ctrldev_akai_apc_key25(zynthian_ctrldev_akai_apc_key25_mk2):

    dev_ids = ["APC Key 25 MIDI 1", "APC Key 25 IN 1"]
    driver_name = 'Full Zynthian Integration for AKAI APC Key25'
    apc_color_variant = 'apc_mk1'
    unroute_from_chains = 0b1111111111111101
    on_notes = {}

    COLOR_SET = COLORS

    def _on_midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        channel = ev[0] & 0x0F
            
        # Direct keybed to chains
        if (channel == 1):
            return

        return super()._on_midi_event(ev)

    class FeedbackLEDs(zynthian_ctrldev_akai_apc_key25_mk2.FeedbackLEDs):

        def led_on(self, led, color=1, brightness=0, overlay=False):
            self._timer.remove(led)
            mk1_brightness_100 = 0x00
            if brightness > 0x06:
                color += 1
            if led > BTN_PAD_END or brightness > 0x00:
                lib_zyncore.dev_send_note_on(self._idev, mk1_brightness_100, led, color)
            else:
                self.led_off(led, overlay)
                # lib_zyncore.dev_send_note_on(self._idev, mk1_brightness_100, led, color)
            if not overlay:
                self._state[led] = (color, brightness)
    
    class DeviceHandler(zynthian_ctrldev_akai_apc_key25_mk2.DeviceHandler):

        COLS = 8
        ROWS = 4
        WSCOLORS_DICT = {
            "0": COLORS.COLOR_BLACK,
            "B": COLORS.COLOR_GREEN,
            "G": COLORS.COLOR_YELLOW,
            "R": COLORS.COLOR_RED,
            "O": COLORS.COLOR_RED,
            "Y": COLORS.COLOR_YELLOW,
            "P": COLORS.COLOR_PURPLE,
            "T": COLORS.COLOR_BLUE_LIGHT
        }
        ZYNSWITCH_SCREEN_COLORS = WSCOLORS_DICT
        ZYNSWITCH_CONFIRM_COLORS = {
            "G": COLORS.COLOR_GREEN,
            "R": COLORS.COLOR_RED
        }

        ZYNSWITCH_FN_COLORS = {
            "0": COLORS.COLOR_BLACK,
            "B": COLORS.COLOR_YELLOW,
            "R": COLORS.COLOR_RED,
            "O": COLORS.COLOR_RED,
            "Y": COLORS.COLOR_YELLOW,
            "P": COLORS.COLOR_RED,
            "T": COLORS.COLOR_GREEN
        }

        ZYNSWITCH_TRANSPORT_COLORS = {
            "0": None,
            "B": None,
            "G": COLORS.COLOR_GREEN,
            "R": COLORS.COLOR_RED,
            "O": COLORS.COLOR_RED,
            "Y": COLORS.COLOR_YELLOW,
            "P": COLORS.COLOR_RED,
            "T": COLORS.COLOR_GREEN
        }

        ZYNSWITCH_ARROW_COLORS = {
            "0": COLORS.COLOR_BLACK,
            "B": COLORS.COLOR_YELLOW,
            "G": COLORS.COLOR_YELLOW,
            "R": COLORS.COLOR_RED,
            "O": COLORS.COLOR_RED,
            "Y": COLORS.COLOR_YELLOW,
            "P": COLORS.COLOR_RED,
            "T": COLORS.COLOR_GREEN
        }

        ZYNSWITCH_NOTES_AND_COLORS = {
            4:    [BTN_OPT_ADMIN, ZYNSWITCH_SCREEN_COLORS],
            5:    [BTN_MIX_LEVEL, ZYNSWITCH_SCREEN_COLORS],
            6:    [BTN_CTRL_PRESET, ZYNSWITCH_SCREEN_COLORS],
            7:    [BTN_ZS3_SHOT, ZYNSWITCH_SCREEN_COLORS],

            8:    [BTN_ALT, ZYNSWITCH_SCREEN_COLORS],
            9:    [BTN_PAD_STEP, ZYNSWITCH_SCREEN_COLORS],
            10:   [BTN_METRONOME, ZYNSWITCH_SCREEN_COLORS],
            11:   [BTN_F1, ZYNSWITCH_FN_COLORS],

            12:    [BTN_PAD_RECORD, ZYNSWITCH_TRANSPORT_COLORS],
            13:    [BTN_PAD_STOP,  ZYNSWITCH_TRANSPORT_COLORS],
            14:    [BTN_PAD_PLAY, ZYNSWITCH_TRANSPORT_COLORS],
            15:    [BTN_F2, ZYNSWITCH_FN_COLORS],

            16:    [BTN_F3, ZYNSWITCH_FN_COLORS],
            17:    [BTN_SEL_YES, ZYNSWITCH_CONFIRM_COLORS],
            18:    [BTN_PAD_UP, ZYNSWITCH_ARROW_COLORS],
            19:    [BTN_BACK_NO, ZYNSWITCH_CONFIRM_COLORS],

            20:    [BTN_PAD_LEFT, ZYNSWITCH_ARROW_COLORS],
            21:    [BTN_PAD_DOWN, ZYNSWITCH_ARROW_COLORS],
            22:    [BTN_PAD_RIGHT, ZYNSWITCH_ARROW_COLORS],
            23:    [BTN_F4, ZYNSWITCH_FN_COLORS]

        }

        def cc_change(self, ccnum, ccval):
            zynpot = CCNUM_ZYNPOT.get(ccnum, None)
            if zynpot is not None:
                self._state_manager.send_cuia("ZYNPOT_ABS", [zynpot, ccval / 127])
                return True
            return False

        def note_on(self, note, velocity, shifted_override=None):
            if note < 4:
                self._state_manager.send_cuia("ZYNPOT", [note, -10])
            elif self.COLS <= note < self.COLS*1+4:
                self._state_manager.send_cuia("ZYNPOT", [note - self.COLS, -1])
            elif self.COLS*2 <= note < self.COLS*2+4:
                self._state_manager.send_cuia("ZYNPOT", [note - self.COLS*2, +1])
            elif self.COLS*3 <= note < self.COLS*3+4:
                self._state_manager.send_cuia("ZYNPOT", [note - self.COLS*3, +10])
            else:
                super().note_on(note, velocity, shifted_override)

    class MixerHandler(zynthian_ctrldev_akai_apc_key25_mk2.MixerHandler):

        def __init__(self, state_manager, driver, leds: zynthian_ctrldev_akai_apc_key25_mk2.FeedbackLEDs):
            self._knobmoves = {}
            super().__init__(state_manager, driver, leds)

        def _update_volume(self, ccnum, ccval):
            if self._is_shifted:
                # Only main chain is handled with SHIFT, ignore the rest
                if ccnum == self.main_chain_knob:
                    index = -1
                else:
                    return True
            else:
                index = (ccnum - KNOB_1) + self.driver.scroll_h
            self.driver.set_mixer_param_cc("level", index, ccval)
            return True

        def _update_pan(self, ccnum, ccval):
            if self._is_shifted:
                # Only main chain is handled with SHIFT, ignore the rest
                if ccnum == self.main_chain_knob:
                    index = -1
                else:
                    return True
            else:
                index = (ccnum - KNOB_1) + self.driver.scroll_h
            self.driver.set_mixer_param_cc("balance", index, ccval)
            return True

        def _update_control(self, ccnum, ccval):
            if self._is_shifted:
                if ccnum == self.main_chain_knob:
                    index = -1
                else:
                    return True
            else:
                index = (ccnum - KNOB_1) + self.driver.scroll_h
            if index == -1:
                self.driver.set_mixer_param_cc("level", index, ccval)
                return True
            else:
                try:
                    zctrl = self._chain_manager.get_active_chain().zctrls[index]
                    zctrl.midi_control_change(ccval)
                    return True
                except:
                    return False
        
    class PadMatrixHandler(zynthian_ctrldev_akai_apc_key25_mk2.PadMatrixHandler):
            BRIGHT_OFF = LED_BRIGHT_10

    class StepSeqHandler(zynthian_ctrldev_akai_apc_key25_mk2.StepSeqHandler):

        NOTE_PAGE_COLORS = [
            COLORS.COLOR_YELLOW,
            COLORS.COLOR_GREEN,
            COLORS.COLOR_RED,
            COLORS.COLOR_YELLOW,
        ]

        BRIGHT_FIRSTBEAT = LED_BRIGHT_100
        COLOR_FIRSTBEAT = COLORS.COLOR_YELLOW
        COLOR_BEAT = COLORS.COLOR_GREEN
        COLOR_VELOCITY = COLOR_CLEAR = COLOR_SELECTED = COLORS.COLOR_RED
        COLOR_COPY = COLORS.COLOR_YELLOW

        def __init__(self, state_manager,  leds: zynthian_ctrldev_akai_apc_key25_mk2.FeedbackLEDs, dev_idx):
            self._knobmoves = {}
            super().__init__(state_manager, leds, dev_idx)

        # NOTE: Do NOT change argument names here (is called using keyword args)
        def _on_midi_note_on(self, izmip, chan, note, vel):
            # Skip own device events / not assigning mode
            if (chan == 0 and izmip == self._own_device_id) or len(self._pressed_pads) == 0:
                return

            # If MIDI is playing, we need to ensure this note_on does come
            # from a device (i.e the user pressed it!).
            if izmip >= self._state_manager.get_zmip_seq_index():
                return

            for pad in self._pressed_pads:
                self._note_pads[pad] = NotePad(note, vel, 1.0)
            self.refresh()

        def _update_step_duration(self, step, duration):
            if self._selected_note is None:
                return

            note = self._selected_note.note
            max_duration = self._libseq.getSteps()
            # duration = self._libseq.getNoteDuration(step, note) + delta * 0.1
            duration = round(min(max_duration, max(0.1, duration)), 1)
            self._set_note_duration(step, note, duration)
            self._play_step(step)
            self.refresh(only_steps=True)

        def _update_step_velocity(self, step, velocity):
            if self._selected_note is None:
                return

            note = self._selected_note.note
            # velocity = self._libseq.getNoteVelocity(step, note) + delta
            velocity = min(127, max(10, velocity))
            self._libseq.setNoteVelocity(step, note, velocity)
            self._leds.led_on(self._pads[step], self.COLOR_VELOCITY, int((velocity * 6) / 127))
            self._play_step(step)

        def _update_step_stutter_speed(self, step, speed):
            if self._selected_note is None:
                return

            note = self._selected_note.note
            speed = min(MAX_STUTTER_SPEED, max(0, speed))
            self._libseq.setNoteStutterSpeed(step, note, speed)
            self._play_step(step)

        def _update_step_stutter_velfx(self, step, duration):
            if self._selected_note is None:
                return

            note = self._selected_note.note
            velfx = min(MAX_STUTTER_VELFX, max(1, velfx))
            self._libseq.setNoteStutterVelfx(step, note, velfx)
            self._play_step(step)

        def _update_note_pad_duration(self, pad, note_spec, duration):
            max_duration = self._libseq.getSteps()
            note_spec.duration = \
                round(min(max_duration, max(0.1, duration)), 1)
            self._play_note_pad(pad)

        def _update_note_pad_velocity(self, pad, note_spec, velocity):
            is_selected = note_spec == self._selected_note
            note_spec.velocity = min(127, max(10, velocity))
            self._play_note_pad(pad)

            color = self.NOTE_PAGE_COLORS[self._note_page_number]
            self._leds.led_on(pad, color, int((note_spec.velocity * 6) / 127))

            if is_selected:
                self._leds.delayed("led_on", 1000, pad, color, LED_PULSING_8)

        def _update_note_pad_stutter_speed(self, pad, note_spec, stutter_speed):
            note_spec.stutter_speed = \
                min(MAX_STUTTER_SPEED, max(0, stutter_speed))
            self._play_note_pad(pad)

        def _update_note_pad_stutter_velfx(self, pad, note_spec, stutter_velfx):
            note_spec.stutter_velfx = \
                min(MAX_STUTTER_VELFX, max(0, stutter_velfx))
            self._play_note_pad(pad)


        def cc_change(self, ccnum, ccval):
            
            if self._pressed_pads:
                if self._note_config is not None:
                    return False

                adjust_pad_func = {
                    KNOB_1: self._update_note_pad_duration,
                    KNOB_2: self._update_note_pad_velocity,
                    KNOB_3: self._update_note_pad_stutter_speed,
                    KNOB_4: self._update_note_pad_stutter_velfx,
                }.get(ccnum)
                adjust_step_func = {
                    KNOB_1: self._update_step_duration,
                    KNOB_2: self._update_step_velocity,
                    KNOB_3: self._update_step_stutter_speed,
                    KNOB_4: self._update_step_stutter_velfx,
                }.get(ccnum)

                step_pads = self._pads[:self._used_pads]
                self._pressed_pads_action = "knobs"
                for pad in self._pressed_pads:
                    if adjust_pad_func:
                        note_spec = self._note_pads.get(pad)
                        if note_spec is not None:
                            adjust_pad_func(pad, note_spec, ccval)
                            continue
                    if adjust_step_func:
                        try:
                            step = step_pads.index(pad)
                            adjust_step_func(step, ccval)
                            continue
                        except ValueError:
                            pass
                return True

            # Adjust tempo
            if ccnum == KNOB_1:
                self._show_screen_briefly(
                    screen="tempo", cuia="TEMPO", timeout=1500)
                cval = ccval / 127
                curval = self._zynseq.get_tempo()
                min = 13.2
                max = 420
                val = min + (cval * (max - min))
                ctrlid = 'tempo'
                now = monotonic()
                then = self._knobmoves.get(ctrlid)
                within_time = ((then is not None) and ((now - then) < 0.2))

                if within_time or (abs(curval - val) < ((max - min) * 0.01)):
                    self._zynseq.set_tempo(val)
                    self._knobmoves[ctrlid] = now

            # Update sequence's chain volume
            elif ccnum == KNOB_2:
                self._show_screen_briefly(
                    screen="mixer", cuia="SCREEN_MIXER", timeout=1500)
                chain_id = self._get_chain_id_by_sequence(
                    self._zynseq.bank, self._selected_seq)
                chain = self._chain_manager.chains.get(chain_id)
                if chain is not None:
                    mixer_chan = chain.mixer_chan
                    cval = ccval / 127
                    curval = self._zynmixer.get_level(mixer_chan)
                    min = 0
                    max = 1
                    val = min + (cval * (max - min))
                    ctrlid = f'level{mixer_chan}'
                    now = monotonic()
                    then = self._knobmoves.get(ctrlid)
                    within_time = ((then is not None) and ((now - then) < 0.2))

                    if within_time or (abs(curval - val) < ((max - min) * 0.01)):
                        self._zynmixer.set_level(mixer_chan, val)
                        self._knobmoves[ctrlid] = now
