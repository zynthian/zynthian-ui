# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Controller (zynthian_controller)
#
# zynthian controller
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

import math
import liblo
import logging
from time import monotonic

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman

# ----------------------------------------------------------------------------

MIDI_CC_MODE_DETECT_TIMEOUT = 0.2
MIDI_CC_MODE_DETECT_STEPS = 8


class zynthian_controller:

    def __init__(self, engine, symbol, options=None):
        """ Instantiate a new zynthian controller

        engine - Engine object containing parameter to control
        symbol - String identifying the control
        options - Optional dictionary of controller {parameter:value} pairs
        """
        self.reset(engine, symbol, options)

    def reset(self, engine, symbol, options=None):
        """ Reset to default settings

        engine - Engine object containing parameter to control
        symbol - String identifying the control
        options - Optional dictionary of controller {parameter:value} pairs
        """

        self.engine = engine
        self.symbol = symbol
        self.processor = None
        self.name = self.short_name = symbol
        self.group_symbol = "ctrls"
        self.group_name = "Ctrls"
        self.readonly = False

        self.value = 0  # Absolute value of the control
        self.value_default = None  # Default value to use when reset control
        self.value_min = None  # Minimum value of control range
        # Mid-point value of control range (used for toggle controls)
        self.value_mid = None
        self.value_max = None  # Maximum value of control range
        self.value_range = 0  # Span of permissible values
        # Factor to scale each up/down nudge
        # TODO: This is not set if configure is not called or options not passed
        self.nudge_factor = None
        self.nudge_factor_fine = None  # Fine factor to scale
        self.labels = None  # List of discrete value labels
        self.ticks = None  # List of discrete value labels
        self.range_reversed = False  # Flag if ticks order is reversed
        self.is_toggle = False  # True if control is Boolean toggle
        self.is_integer = True  # True if control is Integer
        self.is_logarithmic = False  # True if control uses logarithmic scale
        self.is_path = False  # True if the control is a file path (i.e. LV2's atom:Path)
        self.path_file_types = None  # List of supported file types
        self.not_on_gui = False  # True to hint to GUI to show control
        self.display_priority = float("inf")  # Hint of order in which to display control (higher comes first)

        self.is_dirty = True  # True if control value changed since last UI update

        # Parameters to send values if engine-specific send method not available
        self.midi_chan = None  # MIDI channel to send CC messages from control
        self.midi_cc = None  # MIDI CC number to send CC messages from control
        self.midi_feedback = None  # [chan,cc] for MIDI control feedback
        self.midi_cc_momentary_switch = False
        self.midi_cc_mode = -1                  # CC mode: -1=unknown,  0=abs, 1=rel1, 2=rel2, 3=rel3
        self.midi_cc_mode_detecting = 0         # Used by CC mode detection algorithm
        self.midi_cc_mode_detecting_ts = 0      # Used by CC mode detection algorithm
        self.midi_cc_mode_detecting_count = 0   # Used by CC mode detection algorithm
        self.midi_cc_mode_detecting_zero = 0    # Used by CC mode detection algorithm
        self.midi_cc_last_ts = 0                # Timestamp of last MIDI CC message, used to debounce toggle
        self.osc_port = None  # OSC destination port
        self.osc_path = None  # OSC path to send value to
        self.graph_path = None  # Complex map of control to engine parameter

        self.label2value = None  # Dictionary for fast conversion from discrete label to value
        self.value2label = None  # Dictionary for fast conversion from discrete value to label
        if options:
            self.set_options(options)

    def set_options(self, options):
        """ Set individual parameters - updating behaviour as appropriate"""

        if 'processor' in options:
            self.processor = options['processor']
        if 'symbol' in options:
            self.symbol = options['symbol']
        if 'name' in options:
            self.name = options['name']
            if self.short_name == self.symbol:
                self.short_name = self.name
        if 'short_name' in options:
            self.short_name = options['short_name']
        if 'group_name' in options:
            self.group_name = options['group_name']
        if 'group_symbol' in options and options['group_symbol'] is not None:
            self.group_symbol = options['group_symbol']
        if 'value' in options:
            self.value = options['value']
        if 'value_default' in options:
            self.value_default = options['value_default']
        if 'value_min' in options:
            self.value_min = options['value_min']
        if 'value_max' in options:
            value_max = options['value_max']
            # Selector
            if isinstance(value_max, str):
                self.labels = value_max.split('|')
            elif isinstance(value_max, list):
                if isinstance(value_max[0], list):
                    self.labels = value_max[0]
                    self.ticks = value_max[1]
                else:
                    self.labels = value_max
            # Numeric
            elif isinstance(value_max, int):
                self.value_max = value_max
                self.is_integer = True
            elif isinstance(value_max, float):
                self.value_max = value_max
                self.is_integer = False
        if 'labels' in options:
            self.labels = options['labels']
        if 'ticks' in options:
            self.ticks = options['ticks']
        if 'is_toggle' in options:
            self.is_toggle = options['is_toggle']
        if 'midi_cc_momentary_switch' in options:
            self.midi_cc_momentary_switch = options['midi_cc_momentary_switch']
        if 'is_integer' in options:
            self.is_integer = options['is_integer']
        if 'nudge_factor' in options:
            self.nudge_factor = options['nudge_factor']
        if 'is_logarithmic' in options:
            self.is_logarithmic = options['is_logarithmic']
        if 'is_path' in options:
            self.is_path = options['is_path']
        if 'path_file_types' in options:
            self.path_file_types = options['path_file_types']
        if 'midi_chan' in options:
            self.midi_chan = options['midi_chan']
        if 'midi_cc' in options:
            self.midi_cc = options['midi_cc']
        if 'osc_port' in options:
            self.osc_port = options['osc_port']
        if 'osc_path' in options:
            self.osc_path = options['osc_path']
        if 'graph_path' in options:
            self.graph_path = options['graph_path']
        if 'not_on_gui' in options:
            self.not_on_gui = options['not_on_gui']
        if 'display_priority' in options:
            self.display_priority = options['display_priority']
        if 'envelope' in options and options['envelope'] is not None:
            self.envelope = options['envelope']
        self._configure()

    def _configure(self):
        """Reconfigure based on current parameters"""

        self.value_range = None

        if self.is_path:
            return

        if self.labels:
            # Detect toggle (on/off)
            if len(self.labels) == 2:
                self.is_toggle = True
                if not self.ticks:
                    if self.value_min is None:
                        self.value_min = 0
                    if self.value_max is None:
                        self.value_max = 127

            # Generate ticks if needed ...
            if not self.ticks:
                n = len(self.labels)
                self.ticks = []
                if self.value_min is None:
                    self.value_min = 0
                if self.value_max is None:
                    self.value_max = n - 1
                value_range = self.value_max - self.value_min
                if n == 1:
                    # This shouldn't happen!
                    self.value_max = self.value_min
                    self.ticks.append(self.value_min)
                elif self.is_integer:
                    for i in range(n):
                        self.ticks.append(
                            self.value_min + int(i * value_range / (n - 1)))
                else:
                    for i in range(n):
                        self.ticks.append(
                            self.value_min + i * value_range / (n - 1))

            # Calculate min, max
            if self.ticks[0] <= self.ticks[-1]:
                if self.value_min is None:
                    self.value_min = self.ticks[0]
                if self.value_max is None:
                    self.value_max = self.ticks[-1]
                self.range_reversed = False
            else:
                self.value_min = self.ticks[-1]
                self.value_max = self.ticks[0]
                self.range_reversed = True

            # Generate dictionary for fast conversion labels=>values
            self.label2value = {}
            self.value2label = {}
            for i in range(len(self.labels)):
                self.label2value[str(self.labels[i])] = self.ticks[i]
                self.value2label[str(self.ticks[i])] = self.labels[i]

        # Common configuration
        if self.value_min is None:
            self.value_min = 0
        if self.value_max is None:
            self.value_max = 127
        self.value_range = self.value_max - self.value_min

        if self.value_mid is None:
            if self.is_integer:
                self.value_mid = self.value_min + int(self.value_range / 2)
            else:
                self.value_mid = self.value_min + self.value_range / 2

        self._set_value(self.value)
        if self.value_default is None:
            self.value_default = self.value

        if not self.nudge_factor:
            if self.is_logarithmic:
                self.nudge_factor = 0.01  # TODO: Use number of divisions
                self.nudge_factor_fine = 0.003 * self.nudge_factor
            elif not self.is_integer and not self.is_toggle:
                if self.value_range <= 1.0:
                    self.nudge_factor = 0.01
                    self.nudge_factor_fine = 0.001
                elif self.value_range <= 20:
                    self.nudge_factor = 0.1
                    self.nudge_factor_fine = 0.01
                elif self.value_range <= 250:
                    self.nudge_factor = 1
                    self.nudge_factor_fine = 0.1
                elif self.value_range <= 2500:
                    self.nudge_factor = 10
                    self.nudge_factor_fine = 1
                else:
                    self.nudge_factor = self.value_range / 200
                    self.nudge_factor_fine = 1.0
            elif self.engine:
                if self.value_range <= 250:
                    self.nudge_factor = 1
                    self.nudge_factor_fine = 1
                elif self.value_range <= 2500:
                    self.nudge_factor = 10
                    self.nudge_factor_fine = 1
                elif self.value_range <= 25000:
                    self.nudge_factor = 100
                    self.nudge_factor_fine = 10
                elif self.value_range <= 250000:
                    self.nudge_factor = 1000
                    self.nudge_factor_fine = 100
                elif self.value_range <= 2500000:
                    self.nudge_factor = 10000
                    self.nudge_factor_fine = 1000
                else:
                    self.nudge_factor = 100000
                    self.nudge_factor_fine = 10000
            else:
                self.nudge_factor = 1
                self.nudge_factor_fine = 1
        # Set a good default for fine adjustment if coarse factor was specified
        elif not self.nudge_factor_fine:
            self.nudge_factor_fine = 0.1 * self.nudge_factor

        #logging.debug(f"CTRL '{self.name}' => RANGE={self.value_range} NUDGE FACTOR={self.nudge_factor}, FINE={self.nudge_factor_fine}, LOGARITHMIC={self.is_logarithmic}")

        if self.midi_feedback is None and self.midi_chan is not None and self.midi_cc is not None:
            self.midi_feedback = [self.midi_chan, self.midi_cc]

    def set_readonly(self, flag=True):
        if flag != self.readonly:
            self.readonly = flag
            self.is_dirty = True

    def get_path(self):
        if self.osc_path:
            return str(self.osc_path)
        elif self.graph_path:
            return str(self.graph_path)
        elif self.midi_chan is not None and self.midi_cc is not None:
            return "{}#{}".format(self.midi_chan, self.midi_cc)
        else:
            return None

    def set_midi_chan(self, chan):
        self.midi_chan = chan

    def get_value(self):
        return self.value

    def nudge(self, val, send=True, fine=False):
        if self.is_path:
            logging.debug(f"OPEN FILE SELECTOR FOR TYPES: {self.path_file_types} ")
            zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_FILE_SELECTOR,
                                  cb_func=self.set_value,
                                  fexts=self.path_file_types,
                                  root_dirs=None,
                                  path=self.value)
            return True

        if self.ticks:
            index = self.get_value2index() + val
            if index < 0:
                index = 0
            if index >= len(self.ticks):
                index = len(self.ticks) - 1
            self.set_value(self.ticks[index], send)
            return True

        if fine:
            factor = self.nudge_factor_fine
        else:
            factor = self.nudge_factor
        if factor is None:
            return False

        if self.is_logarithmic and self.value_range:
            log_val = math.log10((9 * self.value - (10 * self.value_min - self.value_max)) / self.value_range)
            log_val = min(1, max(0, log_val + val * factor))
            self.set_value((math.pow(10, log_val) * self.value_range + (10 * self.value_min - self.value_max)) / 9)
        else:
            self.set_value(self.value + val * factor, send)
        return True

    def toggle(self):
        if self.is_toggle:
            if self.value == self.value_min:
                self.set_value(self.value_max, send=True)
            else:
                self.set_value(self.value_min, send=True)

    def _set_value(self, val):
        if self.is_path:
            self.value = str(val)
            return
        if isinstance(val, str):
            self.value = self.get_label2value(val)
            return
        elif self.is_toggle:
            if val == self.value_min or val == self.value_max:
                if self.is_integer:
                    self.value = int(val)
                else:
                    self.value = val
            else:
                if val < self.value_mid:
                    self.value = self.value_min
                else:
                    self.value = self.value_max
            return
        elif self.ticks:
            # TODO Do something here?
            pass
        elif self.is_integer:
            val = int(val)

        if val > self.value_max:
            self.value = self.value_max
        elif val < self.value_min:
            self.value = self.value_min
        else:
            self.value = val

    def set_value(self, val, send=True):
        if self.readonly:
            return
        old_val = self.value
        self._set_value(val)
        if old_val == self.value:
            return
        self.send_value(send)
        self.is_dirty = True

    def send_value(self, send=True):
        mval = None
        if self.engine and send:
            # Send value using engine method...
            try:
                self.engine.send_controller_value(self)
            # Send value using OSC/MIDI ...
            except:
                try:
                    if self.osc_path:
                        # logging.debug("Sending OSC Controller '{}', {} => {}".format(self.symbol, self.osc_path, self.get_ctrl_osc_val()))
                        liblo.send(self.engine.osc_target, self.osc_path, self.get_ctrl_osc_val())
                    elif self.midi_cc:
                        mval = self.get_ctrl_midi_val()
                        # logging.debug("Sending MIDI Controller '{}', CH{}#CC{}={}".format(self.symbol, self.midi_chan, self.midi_cc, mval))
                        self.send_midi_cc(mval)
                except Exception as e:
                    logging.warning("Can't send controller '{}' => {}".format(self.symbol, e))

        # Send feedback to MIDI controllers => What MIDI controllers? Those selected as MIDI-out?
        # TODO: Set midi_feeback to MIDI learn
        if self.midi_feedback:
            self.send_midi_feedback(mval)

    def send_midi_cc(self, mval=None):
        if mval is None:
            mval = self.get_ctrl_midi_val()
        try:
            izmop = self.processor.chain.zmop_index
        except:
            izmop = None

        # Try sending directly to chain's zmop
        if izmop is not None and izmop >= 0:
            lib_zyncore.zmop_send_ccontrol_change(izmop, self.midi_chan, self.midi_cc, mval)
        # If not possible, send to fake-UI zmip,
        # but if active MIDI channel is enabled, this would reach all chains in the MIDI channel
        # what generates issues when combining some engines (for instance, fluidsynth + pianoteq)
        else:
            lib_zyncore.ui_send_ccontrol_change(self.midi_chan, self.midi_cc, mval)

    def send_midi_feedback(self, mval=None):
        if mval is None:
            mval = self.get_ctrl_midi_val()
        try:
            lib_zyncore.ctrlfb_send_ccontrol_change(self.midi_feedback[0], self.midi_feedback[1], mval)
        except Exception as e:
            logging.warning("Can't send controller feedback '{}' => Val={}".format(self.symbol, e))

    # Get index of list entry closest to given value
    def get_value2index(self, val=None):
        if val is None:
            val = self.value
        try:
            if self.ticks:
                index = 0
                dval = abs(self.ticks[0] - val)
                for i in range(1, len(self.ticks)):
                    ndval = abs(self.ticks[i] - val)
                    if ndval < dval:
                        dval = ndval
                        index = i
                    else:
                        break
                return index
            else:
                return None
        except Exception as e:
            logging.error(e)

    def get_value2label(self, val=None):
        if val is None:
            val = self.value
        i = self.get_value2index(val)
        if i is not None:
            return self.labels[i]
        else:
            return val

    def get_label2value(self, label):
        try:
            if self.ticks:
                return self.label2value[str(label)]
            else:
                logging.error(f"No labels/ticks defined for {label}")

        except Exception as e:
            logging.error(e)

    def get_ctrl_midi_val(self):
        try:
            if self.value_range == 0:
                return 0
            elif self.is_logarithmic:
                val = int(127 * math.log10((9 * self.value - (10 *
                          self.value_min - self.value_max)) / self.value_range))
            else:
                val = min(
                    127, int(127 * (self.value - self.value_min) / self.value_range))
        except Exception as e:
            logging.error(e)
            val = 0

        return val

    def get_ctrl_osc_val(self):
        if self.is_toggle:
            return self.value > 0
        return self.value

    def reset_value(self):
        """Reset value to default"""
        self.set_value(self.value_default)

    # --------------------------------------------------------------------------
    # State management functions
    # --------------------------------------------------------------------------

    def get_state(self, full=True):
        """Get controller state as dictionary

        full : True to get state of all parameters or false for off-default values
        """
        state = {}
        try:
            if full:
                if math.isnan(self.value):
                    state['value'] = None
                else:
                    state['value'] = self.value
            elif self.value != self.value_default:
                state['value'] = self.value
        except:
            state['value'] = self.value
        if self.midi_cc_momentary_switch:
            state['midi_cc_momentary_switch'] = self.midi_cc_momentary_switch
        return state

    # ----------------------------------------------------------------------------
    # MIDI CC processing
    # ----------------------------------------------------------------------------

    def midi_control_change(self, val, send=True):
        # CC mode not detected yet!
        if self.midi_cc_mode == -1:
            self.midi_cc_mode_detect(val)

        # CC mode absolute
        if self.midi_cc_mode == 0:
            if self.range_reversed:
                val = 127 - val
            if self.is_logarithmic:
                value = self.value_min + self.value_range * (math.pow(10, val/127) - 1) / 9
            elif self.is_toggle:
                now = monotonic()
                if now - self.midi_cc_last_ts < 0.02:
                    return # Debounce
                self.midi_cc_last_ts = now
                if self.midi_cc_momentary_switch:
                    if val >= 64:
                        self.toggle()
                    return
                else:
                    if val >= 64:
                        value = self.value_max
                    else:
                        value = self.value_min
            else:
                value = self.value_min + val * self.value_range / 127

            self.set_value(value, send)

        elif self.midi_cc_mode > 0:
            # CC mode relative (1, 2 or 3)
            match self.midi_cc_mode:
                case 1:
                    if val == 64:
                        return
                    dval = val - 64
                case 2:
                    if val == 0:
                        return
                    if val >= 64:
                        dval = val - 128
                    else:
                        dval = val
                case 3:
                    if val == 16:
                        return
                    dval = val - 16
                case 4:
                    if val < 64:
                        dval = -1
                    else:
                        dval = 1
                case _:
                    logging.error(f"Wrong MIDI CC mode {self.midi_cc_mode}")
                    return

            if self.is_logarithmic:
                if dval > 0:
                    value = self.value * (1 + dval/10)
                else:
                    value = self.value / (1 + dval/10)
            elif self.is_toggle:
                if self.midi_cc_momentary_switch:
                    if dval > 0:
                        self.toggle()
                    return
                else:
                    if dval > 0:
                        value = self.value_max
                    else:
                        value = self.value_min
            else:
                self.nudge(dval, send=send)
                return

            self.set_value(value, send)

    def midi_cc_mode_reset(self):
        self.midi_cc_mode = -1

    def midi_cc_mode_set(self, cc_mode):
        self.midi_cc_mode = cc_mode

    def midi_cc_mode_detect(self, val):
        """
        Relative 1 : The knob will send values 55-63 when turned in a negative direction and values
         65-73 when turned in a positive direction. The turn speed determines the parameter response.

        Relative 2 : The knob will send values 118-127 when turned in a negative direction and values
        1-9 when turned in a positive direction. The turn speed determines the parameter response.

        Relative 3 : The knob will send values 7-15 when turned in a negative direction and values
        17-24 when turned in a positive direction. The turn speed determines the parameter response.

        Please note that a “0” value will be sent between each steps.
        In relative mode 1, moving (slowly) right will send 65/64/65/64/65 etc… This addition of
        this “0” value has been made to prevent browsing issues in Ableton Live.
        This parameter was called “knob fix” in Midi Control Center, but has been hard implemented
        in the last firmware versions.

        Relative 4: The knob will send a value < 64 when turned in a negative direction and a value >= 64
        when turned in a positive direction. No acceleration. (Not auto-detected)
        """

        #logging.debug(f"CC val={val} => current mode={self.midi_cc_mode}, detecting mode {self.midi_cc_mode_detecting}"
        #              f" (count {self.midi_cc_mode_detecting_count}, zero {self.midi_cc_mode_detecting_zero})\n")

        # Always use absolute mode with toggle controllers
        if self.is_toggle:
            self.midi_cc_mode = 0
            self.midi_cc_mode_detecting = 0
            return

        # Mode autodetection timeout
        now = monotonic()
        if now - self.midi_cc_mode_detecting_ts > MIDI_CC_MODE_DETECT_TIMEOUT:
            self.midi_cc_mode_detecting_count = 0
        self.midi_cc_mode_detecting_ts = now

        # Relative mode 1
        if 55 <= val <= 73:
            if self.midi_cc_mode == 1:
                return
            if self.midi_cc_mode_detecting != 1:
                self.midi_cc_mode_detecting = 1
                self.midi_cc_mode_detecting_count = 0
                if val == 64:
                    self.midi_cc_mode_detecting_zero = 1
                else:
                    self.midi_cc_mode_detecting_zero = 0
            else:
                if val == 64 and self.midi_cc_mode_detecting_zero <= 0:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 1
                    else:
                        self.midi_cc_mode_detecting_zero = 1
                        self.midi_cc_mode_detecting_count += 1
                elif val != 64 and self.midi_cc_mode_detecting_zero == 1:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 1
                    else:
                        self.midi_cc_mode_detecting_zero = -1
                        self.midi_cc_mode_detecting_count += 1
                elif self.midi_cc_mode_detecting_zero == 0:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 1
                    elif val == 63 or val == 65:
                        self.midi_cc_mode_detecting_count += 1
                else:
                    self.midi_cc_mode_detecting_count = 0

        # Relative mode 2
        elif 0 <= val <= 6 or 122 <= val <= 127:
            if self.midi_cc_mode == 2:
                return
            if self.midi_cc_mode_detecting != 2:
                self.midi_cc_mode_detecting = 2
                self.midi_cc_mode_detecting_count = 0
                if val == 0:
                    self.midi_cc_mode_detecting_zero = 1
                else:
                    self.midi_cc_mode_detecting_zero = 0
            else:
                if val == 0 and self.midi_cc_mode_detecting_zero <= 0:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 2
                    else:
                        self.midi_cc_mode_detecting_zero = 1
                        self.midi_cc_mode_detecting_count += 1
                elif val != 0 and self.midi_cc_mode_detecting_zero == 1:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 2
                    else:
                        self.midi_cc_mode_detecting_zero = -1
                        self.midi_cc_mode_detecting_count += 1
                elif self.midi_cc_mode_detecting_zero == 0:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 2
                    elif val == 1 or val == 127:
                        self.midi_cc_mode_detecting_count += 1
                else:
                    self.midi_cc_mode_detecting_count = 0

        # Relative mode 3
        elif 7 <= val <= 24:
            if self.midi_cc_mode == 3:
                return
            if self.midi_cc_mode_detecting != 3:
                self.midi_cc_mode_detecting = 3
                self.midi_cc_mode_detecting_count = 0
                if val == 16:
                    self.midi_cc_mode_detecting_zero = 1
                else:
                    self.midi_cc_mode_detecting_zero = 0
            else:
                if val == 16 and self.midi_cc_mode_detecting_zero <= 0:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 3
                    else:
                        self.midi_cc_mode_detecting_zero = 1
                        self.midi_cc_mode_detecting_count += 1
                elif val != 16 and self.midi_cc_mode_detecting_zero == 1:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 3
                    else:
                        self.midi_cc_mode_detecting_zero = -1
                        self.midi_cc_mode_detecting_count += 1
                elif self.midi_cc_mode_detecting_zero == 0:
                    if self.midi_cc_mode_detecting_count >= MIDI_CC_MODE_DETECT_STEPS:
                        self.midi_cc_mode = 3
                    elif val == 15 or val == 17:
                        self.midi_cc_mode_detecting_count += 1
                else:
                    self.midi_cc_mode_detecting_count = 0

        else:
            self.midi_cc_mode_detecting = 0
            self.midi_cc_mode = 0

# ******************************************************************************
