#! /zynthian/venv/bin/python
# -*- coding: utf-8 -*-

# TODO: Display rows are of different types.
# Row two appears to be monochrome green, only brightness varies

# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Ableton Push 1"
#
# Copyright (C) 2025 Brumby
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

"""
Ableton Push 1 Driver for Zynthian

This driver provides basic functionality for the Ableton Push 1 controller:
- Rudimentary mixer mode with volume knobs for chains 1-7 and main volume on knob 8
  (activated by pressing the "Volume" button)
- Pad array mode for the sequencer (activated by pressing the "User" button)
- Illuminated pad array with selectable scales and modes (activated by pressing the "Scales" button)

NOTE: This driver is incomplete but in a usable state.

In Mixer mode, knobs 1-4 control chain volumes 1-4 instead of acting as Zynpots.
In other modes, they function as regular Zynpots for the Zynthian GUI.

Illuminated buttons indicate active functions.
Current driver modes are indicated by blinking mode buttons.

Display usage:
- Top two rows are exclusively for mixer display
- Bottom two rows are for scales and sequencer modes
"""

import logging
import traceback

#### Local debug configuration
debug_mode = True
if debug_mode:
    # Set up logger for this driver to isolate debug messages
    logger = logging.getLogger("ABL-Push_1")
    logger.setLevel(logging.DEBUG)
    
    # Create console handler with formatted output
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
### End of local debug configuration

# Brumby's custom imports
from time import sleep  # Pause between sysex events (Push 1 is slow)
from zyngine.ctrldev.zynthian_ctrldev_base_scale import Harmony  # Custom class for scales mode
from zyngine.ctrldev.zynthian_ctrldev_base_extended import RunTimer, KnobSpeedControl, ButtonTimer, CONST

# Push 1 event definitions
# import zyngine.ctrldev.ableton.push1_consts as ABL  # external Button definitions
# ABL is now defined as class at end of ile.


# Zynthian core modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Ableton Push 1 Driver Class
# ------------------------------------------------------------------------------------------------------------------

# zynthian_ctrldev_zynpad - base class for sequencer pad control
# zynthian_ctrldev_zynmixer - base class for main mixer control

# Push 1 MIDI mapping note values
# DO NOT DELETE - essential reference
ABL_PAD_START = 36  # First pad = pad_36
ABL_PAD_END = 99    # Last pad = pad_99

class zynthian_ctrldev_ableton_push_1_v2(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):
    """Driver class for Ableton Push 1 controller"""
    
    logging.info("Push 1 initializing class instance")
    # Web log will show this message during initialization

    # Device IDs for recognition (obtained from zynthian_ctrldev_manager.load_driver())
    # dev_ids = ["Ableton Push IN 2", "Ableton Push IN 1"]
    dev_ids = ["Ableton Push IN 2"]  # Data only appears on Port 2
    
    driver_name = "Ableton Push v1"  # Optional - class name used if not specified
    driver_description = "Interface Ableton Push v1 with zynpad and zynmixer functionality"

    ################################
    
    # Colors for LED pads in Sequencer mode
    # TODO: Palette needs adjustment
    # Reference: https://pushmod.blogspot.com/p/pad-color-table.html
    # ORIGINAL PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    PAD_COLOURS = [61, 36, 63, 54, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]  # Current (non-functional)
    STARTING_COLOUR = 123  # GREEN
    STOPPING_COLOUR = 120  # RED
    RUNNING_COLOR = 3      # WHITE

    # Event type constants (duplicates exist in base_extended)
    # evtype = (ev[0] >> 4) & 0x0F
    EV_NOTE_OFF = 0x8      # 3 bytes
    EV_NOTE_ON = 0x9       # 3 bytes
    EV_AFTERTOUCH = 0xA    # 3 bytes (polyphonic per note)
    EV_CC = 0xB            # 3 bytes
    EV_PC = 0xC            # 2 bytes
    EV_CHAN_PRESS = 0xD    # 2 bytes
    EV_PITCHBEND = 0xE     # 3 bytes: ev[1] = LSB 0-127; ev[2] = MSB 0-127
    EV_SYSTEM = 0xF        # Variable length (1+ bytes), system type = ev[0] & 0x0F
    
    # Device operation modes
    DEV_MODE_NONE = None
    DEV_MODE_PAD = 1       # Sequencer pad mode
    DEV_MODE_SCALES = 2    # Keyboard/scales mode
    DEV_MODE_MIXER = 3     # Mixer mode
    
    device_mode_active = DEV_MODE_NONE  # Initial mode (no mode selected)

    # Initialize scales harmony system
    scales = Harmony(8, 8)
    scales.init_scale(
        tonic=0, 
        mode_name="Major", 
        col_versatz=-5, 
        middle_c=48, 
        middle_pad_nr=4
    )

    def __init__(self, state_manager, idev_in, idev_out=None):
        """Initialize the Push 1 driver
        
        Args:
            state_manager: Zynthian state manager instance
            idev_in: Input device ID
            idev_out: Output device ID (optional)
        """
        logging.info("Ableton Push 1 detected on USB")
        # TODO: Add confirmation message when correct USB device is found
        
        # Call parent constructor (saves state_manager, chainmanager, idev_in, idev_out)
        super().__init__(state_manager, idev_in, idev_out)
        
        # Initialize knob easing/speed control
        # TODO: Experiment with values during live operation
        self._knobs_ease = KnobSpeedControl()
        
        # Initialize device feedback controllers
        self._leds_mono = Feedback_Mono_LEDs(idev_out)  # Mono LED buttons (right/left of pads)
        self._leds_bi = Feedback_Bi_LEDs(idev_out)      # Bi-color display buttons
        self._leds_rgb = Feedback_RGB_LEDs(idev_out)    # RGB pad LEDs
        self._display = Feedback_Display(idev_out)      # Text display
        self._display.first_screen()
        self.mixer_init()  # Initialize mixer display
        
        # Required when sending translated MIDI events
        self.unroute_from_chains = True
        
        # Device state variables
        self.shift = False      # SHIFT button pressed state
        self.shift_note = 0     # Octave shift amount

    def init(self):
        """Initialize the device - called from parent class"""
        try: 
            logging.info("Initializing Ableton Push 1 - BRUMBY")
            
            # Set initial device mode
            self.set_device_mode_new(self.DEV_MODE_MIXER)
            
            # Setup LED states for control buttons
            # Illuminate monochrome buttons that should be lit
            bright_buttons = [
                36, 37, 38, 39, 40, 41, 42, 43,   
                ABL.BTN_START[1], ABL.BTN_OK[1], ABL.BTN_ESC[1], ABL.BTN_LEFT[1], 
                ABL.BTN_RIGHT[1], ABL.BTN_UP[1], ABL.BTN_DOWN[1], ABL.BTN_SCALES[1], 
                ABL.BTN_USER[1]
            ]
            
            for btn in bright_buttons:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.MONO_LED_LIT)

            # Set dim state for specific buttons
            dim_buttons = [ABL.BTN_REC[1], ABL.BTN_SHIFT[1]]
            for btn in dim_buttons:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.MONO_LED_DIM)
                
            # Set bi-color LEDs to dim orange
            bi_buttons = [
                ABL.BTN_R1_C1[1], ABL.BTN_R1_C2[1], ABL.BTN_R1_C3[1], ABL.BTN_R1_C4[1]
            ]
            for btn in bi_buttons:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.BI_ORANGE_DIM)

            # Setup device pad array dimensions
            self.cols = 8
            self.rows = 8
            super().init()  # Activate parent initialization (required!)
            
            # Setup scales mode if active
            if self.device_mode_active == self.DEV_MODE_SCALES:
                self.scales_set_dev_to_scales_mode()
                
        except Exception as e:
            logger.error("Exception during initialization: %s", e)
            logger.error("Traceback: %s", traceback.format_exc())

    def end(self):
        """Clean up device state - called from parent class"""
        logging.info("Shutting down Ableton Push 1 - BRUMBY")
        super().end()

#################################################################################################################
##################     START of SCALES FUNCTIONS     ##########################################################
   
    def scales_set_dev_to_scales_mode(self):
        """Configure device for scales/keyboard mode"""
        self.device_mode_active = self.DEV_MODE_SCALES
        
        # Visual feedback - blink Scales button
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT_BLINK)
        
        # Clear pads and set scale colors
        self.pads_off()
        self.scales_set_pad_colors()
        
        # Display scale information
        scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
        scale_n_mode += " - knob 7+8"
        self._display.write_xy_mem(scale_n_mode, 0, 2)
        
        # Setup display text for scales mode
        btn_txt_row2 = "|modes here      |       |       ||   G#  |    A   |  A#   |   B   |"
        btn_txt_row3 = "|   C   |   C#   |   D   |   D#  ||   E   |    F   |  F#   |   G   |"
        
        self._display.write_xy_mem(btn_txt_row2, 0, 2)
        self._display.write_xy_mem(scale_n_mode, 0, 2)  # Overwrite with scale info
        self._display.write_xy_mem(btn_txt_row3, 0, 3)
        self._display.update_screen()
        
        # Setup pad LEDs and octave buttons
        self.scale_update_leds(self.scales.tonic)
        for btn in [ABL.BTN_OCTAVE_DOWN[1], ABL.BTN_OCTAVE_UP[1]]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.MONO_LED_LIT)
        
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT)

    def scales_cleanup(self):
        """Clean up scales mode - reset LEDs and display"""
        # Clear display
        clear_text = "|       |       |        |       ||       |        |       |       |"
        self._display.write_xy_mem(clear_text, 0, 2)
        self._display.write_xy_mem(clear_text, 0, 3)
        self._display.update_screen()
        
        # Turn off scale selection LEDs
        scale_buttons = [
            ABL.BTN_R2_C1[1], ABL.BTN_R2_C2[1], ABL.BTN_R2_C3[1], ABL.BTN_R2_C4[1],
            ABL.BTN_R2_C5[1], ABL.BTN_R2_C6[1], ABL.BTN_R2_C7[1], ABL.BTN_R2_C8[1],
            ABL.BTN_R1_C5[1], ABL.BTN_R1_C6[1], ABL.BTN_R1_C7[1], ABL.BTN_R1_C8[1]
        ]
        for btn in scale_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.BI_LED_OFF)
        
        # Reset Scales button and octave buttons
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT_BLINK)
        for btn in [ABL.BTN_OCTAVE_DOWN[1], ABL.BTN_OCTAVE_UP[1]]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.MONO_LED_OFF)

    def scale_update_leds(self, index_activated):
        """Update scale selection LED indicators
        
        Args:
            index_activated: Index of the currently active scale (0-11)
        """
        scale_buttons = [
            ABL.BTN_R2_C1[1], ABL.BTN_R2_C2[1], ABL.BTN_R2_C3[1], ABL.BTN_R2_C4[1],
            ABL.BTN_R2_C5[1], ABL.BTN_R2_C6[1], ABL.BTN_R2_C7[1], ABL.BTN_R2_C8[1],
            ABL.BTN_R1_C5[1], ABL.BTN_R1_C6[1], ABL.BTN_R1_C7[1], ABL.BTN_R1_C8[1]
        ]
        
        # Set all scale buttons to dim green
        for btn in scale_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.BI_GREEN_DIM)
        
        # Set active scale button to blinking
        lib_zyncore.dev_send_ccontrol_change(
            self.idev_out, 0, scale_buttons[index_activated], ABL.BI_GREEN_DIM_BLINK
        )

    def scales_set_tonic(self, step):
        """Change scale tonic (root note)
        
        Args:
            step: Relative change amount (positive or negative)
        """
        if step > 63:
            step -= 128  # Convert encoder wrap-around to negative
        
        # Slow down knob sensitivity
        self.steps_tonic = getattr(self, 'steps_tonic', 0) + step
        if abs(self.steps_tonic) <= 10:
            return  # Apply change only every 10 steps
        self.steps_tonic = 0
        
        # Calculate new tonic with bounds checking
        new_tonic = self.scales.tonic + step
        if new_tonic < 0:
            new_tonic = 11  # Wrap to B
        if new_tonic > 11:
            new_tonic = 0   # Wrap to C
        
        self.scales.tonic = new_tonic
        
        # Update display and LEDs
        scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
        scale_n_mode += " - knob 7+8"
        self._display.write_xy_mem(scale_n_mode, 0, 2)
        self._display.update_screen()
        self.scale_update_leds(new_tonic)

    def scales_set_mode(self, step):
        """Change scale mode (major, minor, etc.)
        
        Args:
            step: Relative change amount (positive or negative)
        """
        if step > 63:
            step -= 128  # Convert encoder wrap-around to negative
        
        # Slow down knob sensitivity
        self.steps_mode = getattr(self, 'steps_mode', 0) + step
        if abs(self.steps_mode) <= 10:
            return  # Apply change only every 10 steps
        self.steps_mode = 0
        
        # Get available mode names and current mode index
        modenames = self.scales.harmony_get_mode_names()
        nr_of_modes = len(modenames)
        current_index = 0
        
        # Set default mode if not already set
        if not self.scales.active_mode:
            self.scales.active_mode = modenames[0]  # "Chromatic"
        
        # Find current mode index
        for i in range(nr_of_modes):
            if modenames[i] == self.scales.active_mode:
                current_index = i
                break
        
        # Calculate new mode index with wrapping
        new_index = current_index + step
        if new_index >= nr_of_modes:
            new_index = 0
        elif new_index < 0:
            new_index = nr_of_modes - 1
        
        # Apply new mode
        new_mode = modenames[new_index]
        self.scales.active_mode = new_mode
        self.scales.init_scale(self.scales.tonic, self.scales.active_mode)
        
        # Update visual feedback
        self.scales_set_pad_colors()
        scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
        scale_n_mode += " - knob 7+8"
        self._display.write_xy_mem(scale_n_mode, 0, 2)
        self._display.update_screen()

    def scales_set_pad_colors(self):
        """Set LED colors for all pads based on current scale"""
        for pad_nr in range(64):
            new_note = self.scales.harmony_get_target_note(pad_nr)
            
            # Color tonic notes differently
            if self.scales.is_tonic_by_padnr(pad_nr):
                r, g, b = 0, 0, 255  # Blue for tonic
            else:
                r, g, b = 200, 200, 200  # White for other notes
            
            self._leds_rgb.set_rgb(pad_nr, r, g, b, overlay=False)

    def process_scale_event(self, ev) -> bool:
        """Process MIDI events in scales mode
        
        Args:
            ev: MIDI event bytes
            
        Returns:
            bool: True if event was processed, False otherwise
        """
        if self.device_mode_active != self.DEV_MODE_SCALES:
            return False  # Not in scales mode
    
        note = ev[1]
        
        # Filter for pad events (sound-producing notes)
        if ABL_PAD_START <= note <= ABL_PAD_END:
            evtype = (ev[0] >> 4) & 0x0F 
            
            # Handle pitch bend from ribbon controller
            if evtype == self.EV_PITCHBEND:
                self._forward_like_niels_did(ev)
                
            # Handle note events
            if evtype in [self.EV_NOTE_ON, self.EV_NOTE_OFF, self.EV_AFTERTOUCH]:
                pad_nr = note - 35  # Convert to hardware pad number
                
                # Translate note according to current scale
                note_translated = self.scales.harmony_get_target_note(pad_nr - 1)
                note_translated += self.shift_note  # Apply octave shift
                
                # Adjust velocity (Push 1 is velocity-insensitive)
                vel = ev[2]
                if evtype == self.EV_NOTE_ON:
                    vel = min(ev[2] * 2, 255)  # Boost velocity but cap at max
                
                # Forward translated event
                new_ev = bytes([ev[0], note_translated, vel])
                self._forward_like_niels_did(new_ev)
                return True
        
        # Process control buttons and knobs
        def helper_set_new_tonic(tonic):
            """Helper function to change scale tonic"""
            if self.scales.set_new_tonic(tonic):
                scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
                scale_n_mode += " - knob 7+8"
                self._display.write_xy_mem(scale_n_mode, 0, 2)
                self._display.update_screen()
                self.scale_update_leds(tonic)
            return True
        
        # Check for button press events
        search_key = (ev[0], ev[1])
        if ev[2] > 0:  # Button down events only
            # Scale selection buttons
            scale_mapping = {
                ABL.BTN_R2_C1: 0, ABL.BTN_R2_C2: 1, ABL.BTN_R2_C3: 2, ABL.BTN_R2_C4: 3,
                ABL.BTN_R2_C5: 4, ABL.BTN_R2_C6: 5, ABL.BTN_R2_C7: 6, ABL.BTN_R2_C8: 7,
                ABL.BTN_R1_C5: 8, ABL.BTN_R1_C6: 9, ABL.BTN_R1_C7: 10, ABL.BTN_R1_C8: 11
            }
            
            if search_key in scale_mapping:
                return helper_set_new_tonic(scale_mapping[search_key])
            
            # Scale and mode knobs
            if search_key == ABL.KNOB_7:
                self.scales_set_tonic(ev[2])
                return True
            if search_key == ABL.KNOB_8:
                self.scales_set_mode(ev[2])
                return True
                
            # Octave buttons
            if search_key == ABL.BTN_OCTAVE_UP:
                self.shift_note += 12
                return True
            if search_key == ABL.BTN_OCTAVE_DOWN:
                self.shift_note -= 12
                return True
                
        return False

##################     END of SCALES FUNCTIONS     ##########################################################
###############################################################################################################

#######################################################################################    
###             MIXER FUNCTIONS FOR DISPLAY ACTION from zynmixer                   ###
        
    def mixer_init(self):
        """Initialize mixer display functionality
        
        Mixer is the main functionality, so it must be setup in init function
        """
        # Create constants for mixer display layout
        self.MIXER_DISP_ROW_VOLUME = 1
        self.MIXER_DISP_ROW_BALANCE = 0
        
        self.KNOB_VOLUME = ABL.KNOB_8
        self._mixer_chains_bank = 0
            
        self._display_mixer = Feedback_Display(self.idev_out)
        self.mixer_set_dev_to_mixermode()
        
        return
    
    def mixer_set_dev_to_mixermode(self):
        """Configure device for mixer mode"""
        # Create mixer display content
        btn_txt_row0 = "  Ch 1     Ch 2    Ch 3     Ch 4    Ch 5     Ch 6    Ch 7     Main  "
        btn_text_row2 = self._display_mixer.format_help
        
        self._display_mixer.write_xy_mem(btn_txt_row0, 0, 0)
        self._display_mixer.update_screen()
        
    def mixer_cleanup(self):
        """Clean up mixer mode - currently no specific cleanup needed"""
        pass

    def update_mixer_active_chain(self, active_chain):
        """Update hardware indicators for active chain
        
        Args:
            active_chain: Index of the currently active audio chain
        """
        try:
            mix_state = self.zynmixer.get_state()
            for c in mix_state.keys():
                if c[:5] == "chan_":
                    chan_nr = int(c[5:7])
                    ch_level = self.zynmixer.zctrls[chan_nr]['level'].get_value()
                    self._display_mixer.write_to_knobx_mem(ch_level, chan_nr, self.MIXER_DISP_ROW_VOLUME, as_bar=True)
            self._display_mixer.update_screen()
        except Exception as e:
            logging.error(f"Error in update_mixer_active_chain: {e}")
            logging.exception(traceback.format_exc())
            
    def update_mixer_strip(self, chan, symbol, value):
        """Update hardware indicators for a mixer strip: mute, solo, level, balance, etc.
        
        Args:
            chan: Mixer channel index
            symbol: Control name ('level', 'balance', 'mute', 'solo', 'mono', 'm+s', 'phase')
            value: Control value
        """
        try:
            match symbol:
                case 'level':
                    if chan > 7: 
                        chan = 7  # Main channel
                    self._display_mixer.write_to_knobx_mem(value, chan, self.MIXER_DISP_ROW_VOLUME, as_bar=True)
                    self._display_mixer.update_screen()
                    return True
                
                case 'balance' | 'mute' | 'solo' | 'mono' | 'm+s' | 'phase':
                    # These controls are recognized but not yet implemented for display
                    pass
                
                case _:
                    logging.debug(f"Update mixer strip: UNKNOWN SYMBOL! chan: {chan}; symbol: {symbol} value: {value}")
                    return False
            
            logging.debug(f"Update mixer strip: NOT IMPLEMENTED! chan: {chan}; symbol: {symbol} value: {value}")

        except Exception as e:
            logging.error(f"Error in update_mixer_strip: {e}")
            logging.exception(traceback.format_exc())
    
    def process_mixer_event(self, ev) -> bool:
        """Process MIDI events in mixer mode
        
        Args:
            ev: MIDI event bytes
            
        Returns:
            bool: True if event was processed, False otherwise
        """
        if len(ev) != 3:
            return False  # Need 3-byte events
        
        # Handle mixer knob events (volume control)
        search_knob = (ev[0], ev[1])
        if search_knob in [ABL.KNOB_1, ABL.KNOB_2, ABL.KNOB_3, ABL.KNOB_4,
                     ABL.KNOB_5, ABL.KNOB_6, ABL.KNOB_7, ABL.KNOB_8]:
            return self._update_control("level", ev, 0, 100)
        
        return False
    
    def _update_control(self, type: str, ev: bytes, minv, maxv):
        """Update mixer control value based on MIDI event
        
        Args:
            type: Control type ('level' or 'balance')
            ev: MIDI event bytes
            minv: Minimum value
            maxv: Maximum value
            
        Returns:
            bool: True if control was updated, False otherwise
        """
        ccnum = ev[1] & 0x7F
        ccval = ev[2] & 0x7F
        
        # Determine which mixer channel to control
        if ev[:2] == bytes(self.KNOB_VOLUME):  # Main volume knob
            mixer_chan = 255 
        else:
            # Calculate chain index based on knob position and bank
            index = (ccnum - ABL.KNOB_1[1]) + self._mixer_chains_bank * 8
            chain = self.chain_manager.get_chain_by_index(index)
            if chain is None or chain.chain_id == 0:
                return False
            mixer_chan = chain.mixer_chan

        # Get current value and set function based on control type
        if type == "level":
            value = self.zynmixer.get_level(mixer_chan)
            set_value = self.zynmixer.set_level
        elif type == "balance":
            value = self.zynmixer.get_balance(mixer_chan)
            set_value = self.zynmixer.set_balance
        else:
            return False

        # Apply relative change from encoder
        value *= 100  # Convert 0.0-1.0 range to 0-100
        value += ccval if ccval < 64 else ccval - 128  # Handle encoder rotation
        value = max(minv, min(value, maxv))  # Clamp to valid range
        set_value(mixer_chan, value / 100)  # Convert back to 0.0-1.0 range
        return True
    
###                END of Mixer functions                            ###
#########################################################################

#########################################################################
###           Start of Sequencer / Pad Functions                      ###
    def process_sequencer_event(self, ev) -> bool:
        """Process MIDI events in sequencer mode
        
        Args:
            ev: MIDI event bytes
            
        Returns:
            bool: True if event was processed, False otherwise
        """
        if not self.device_mode_active == self.DEV_MODE_PAD:
            return False  # Not in sequencer mode
        
        cc = ev[1]  # Controller number for bank calculation
        
        # Handle scene selection buttons
        search_key = [ev[0], ev[1]]
        if ev[2] > 0:  # Button down events only
            scene_buttons = [
                ABL.BTN_BEAT_1_QUATER, ABL.BTN_BEAT_2_QUATER_T, ABL.BTN_BEAT_3_EIGHTH,
                ABL.BTN_BEAT_4_EIGHTH_T, ABL.BTN_BEAT_5_SIXTEENTH, ABL.BTN_BEAT_6_SIXTEENTH_T,
                ABL.BTN_BEAT_7_THIRTYSECOND, ABL.BTN_BEAT_8_THIRTYSECOND_T
            ]
            
            if search_key in scene_buttons:
                return self.sequencer_set_scene(cc)
        
        # Handle pad events for sequencer control
        evtype = (ev[0] >> 4) & 0x0F
        note = ev[1] & 0x7F
        
        # Filter program change events (Push 1 doesn't send these)
        if evtype == self.EV_PC:
            return True  # Ignore program change events
        
        # Handle note events for sequencer pads
        if evtype == self.EV_NOTE_ON:
            try:
                pad_nr = note - ABL_PAD_START  # Convert to pad number (0-63)
                col = pad_nr // 8
                row = pad_nr % 8
                col = 7 - col  # Flip column orientation
                
                # Calculate sequencer pad index and toggle play state
                pad = row * self.zynseq.col_in_bank + col
                logging.debug(f"BRUMBY: row={row}; col={col}; pad={pad}")
                if pad < self.zynseq.seq_in_bank:
                    self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
                    return True
            except Exception:
                pass  # Silently handle pad calculation errors
        
        return False

    def update_seq_state(self, bank, seq, state, mode, group):
        """Update sequencer state indicators
        
        Args:
            bank: Sequencer bank number
            seq: Sequence number
            state: Sequence state (playing, stopped, etc.)
            mode: Sequence mode
            group: Sequence group
        """
        try:
            # Only update if in sequencer mode and bank matches
            if not self.device_mode_active == self.DEV_MODE_PAD:
                return
            if self.idev_out is None or bank != self.zynseq.bank:
                return

            # Calculate pad position and MIDI note
            col, row = self.zynseq.get_xy_from_pad(seq)
            note = ABL_PAD_END + 1 - (row + 1) * 8 + col

            # Determine LED color based on sequence state
            try:
                if mode == 0 or group > 16:
                    chan = 0
                    vel = 0
                elif state == zynseq.SEQ_STOPPED:
                    chan = 0
                    vel = self.PAD_COLOURS[group]
                elif state == zynseq.SEQ_PLAYING:
                    chan = 2
                    vel = self.RUNNING_COLOR
                elif state in [zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC]:
                    chan = 1
                    vel = self.STOPPING_COLOUR
                elif state == zynseq.SEQ_STARTING:
                    chan = 1
                    vel = self.STARTING_COLOUR
                else:
                    chan = 0
                    vel = 0
            except Exception:
                chan = 0
                vel = 0

            # Update pad LED
            lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)
        except ValueError as e:
            print(f"Error updating sequencer state: {e}")

    def refresh(self):
        """Refresh LED states - called from parent class"""
        if self.device_mode_active == self.DEV_MODE_PAD:
            return super().refresh()

    def pad_off(self, col, row):
        """Turn off specific pad LED
        
        Args:
            col: Column index (0-7)
            row: Row index (0-7)
        """
        note = ABL_PAD_END + 1 - (row + 1) * 8 + col
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    def sequencer_set_scene(self, ccnum):
        """Set active sequencer scene/bank
        
        Args:
            ccnum: Controller number identifying the scene
            
        Returns:
            bool: True if scene was changed, False otherwise
        """
        self.zynseq.select_bank(8 - (ccnum - 36))
        
        # Update scene button LEDs
        scene_buttons = [36, 37, 38, 39, 40, 41, 42, 43]
        for btn in scene_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, btn, ABL.MONO_LED_DIM)
        
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, ABL.MONO_LED_LIT_BLINK_FAST)
        return True
        
    def pads_off(self):
        """Turn off all pad LEDs"""
        for row in range(self.rows):
            for col in range(self.cols):
                self.pad_off(col, row)

    def _forward_like_niels_did(self, ev):
        """Forward MIDI events to active chain (based on Niels' implementation)
        
        Args:
            ev: MIDI event bytes
            
        Returns:
            bool: True if event was forwarded, False otherwise
        """
        chain = self.chain_manager.get_active_chain()
        if chain.midi_chan is None:
            return False
        
        status = (ev[0] & 0xF0) | chain.midi_chan
        self.zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
        return True

    def set_device_mode_new(self, new_mode):
        """Change device operation mode
        
        Args:
            new_mode: New mode to activate (DEV_MODE_MIXER, DEV_MODE_PAD, DEV_MODE_SCALES)
            
        Returns:
            bool: True if mode was changed successfully, False otherwise
        """
        try:
            if new_mode == self.device_mode_active:
                return True  # Already in requested mode
            
            # Clean up current mode
            match self.device_mode_active:
                case self.DEV_MODE_MIXER:
                    lib_zyncore.dev_send_ccontrol_change(
                        self.idev_out, 0, ABL.BTN_VOLUME[1], ABL.MONO_LED_LIT)
                    self.mixer_cleanup()
                    
                case self.DEV_MODE_PAD:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_USER[1], ABL.MONO_LED_LIT)
                    self.pads_off()
                    
                case self.DEV_MODE_SCALES:
                    self.scales_cleanup()
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT)
                    self.pads_off()
            
            # Set new mode
            self.device_mode_active = new_mode
            
            # Initialize new mode
            match new_mode:
                case self.DEV_MODE_MIXER:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_VOLUME[1], ABL.MONO_LED_LIT_BLINK)
                    return self.mixer_set_dev_to_mixermode()
                    
                case self.DEV_MODE_PAD:
                    self.refresh()
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_USER[1], ABL.MONO_LED_LIT_BLINK)
                    
                case self.DEV_MODE_SCALES:
                    self.scales_set_dev_to_scales_mode()
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT_BLINK)
                    
                case _:
                    logging.error("DEVICE Mode not defined. Programming Error")
                    return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error in set_device_mode_new: {e}")
            logger.exception(traceback.format_exc())
            return False

    def midi_event(self, ev):
        """Main MIDI event handler - called for all incoming MIDI events
        
        Args:
            ev: MIDI event bytes
            
        Returns:
            bool: True if event was processed, False otherwise
        """
        # Debug logging for button events
        if len(ev) > 1 and debug_mode:
            search_key = (ev[0], ev[1])
            btn_name = self.button_name_from_midi_event(search_key)
            if btn_name != "":
                logger.debug(f"\n - Button: {btn_name} on chan. {ev[0] & 0x0F} gives midi_event: {hex(ev[0])} {hex(ev[1])} {hex(ev[2])} = {int(ev[1])}, {int(ev[2])}")
        
        # Handle shift button (momentary modifier)
        if len(ev) > 2:
            val_or_vel = ev[2]
            is_key_push = val_or_vel > 0
            
            search_key = (ev[0], ev[1])
            if search_key == ABL.BTN_SHIFT:
                self.shift = is_key_push
                # Visual feedback for shift state
                if self.shift:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL.MONO_LED_LIT_BLINK)
                else:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL.MONO_LED_DIM)
                return True
             
        # Handle mode change buttons
        if len(ev) > 2 and ev[2] > 0:  # Button down events
            search_key = (ev[0], ev[1])
            if search_key == ABL.BTN_VOLUME:
                return self.set_device_mode_new(self.DEV_MODE_MIXER)
            elif search_key == ABL.BTN_SCALES:
                return self.set_device_mode_new(self.DEV_MODE_SCALES)
            elif search_key == ABL.BTN_USER:
                return self.set_device_mode_new(self.DEV_MODE_PAD)
        
        # Route events to current mode handler
        match self.device_mode_active:
            case self.DEV_MODE_MIXER:
                if self.process_mixer_event(ev):
                    return True
            case self.DEV_MODE_PAD:
                if self.process_sequencer_event(ev):
                    return True
            case self.DEV_MODE_SCALES:
                if self.process_scale_event(ev):
                    return True
        
        # Handle GUI control events
        if self.process_gui_events(ev):
            return True
        
        return False  # Event not processed

    def process_gui_events(self, ev) -> bool:
        """Process GUI control events (knobs and buttons)
        
        Args:
            ev: MIDI event bytes
            
        Returns:
            bool: True if event was processed, False otherwise
        """
        if len(ev) < 3:
            return False  # Need 3-byte events
        
        search_key = (ev[0], ev[1])
        data_val = ev[2] & 0x7F
        
        # Handle knob events with easing
        knob_mapping = {
            ABL.KNOB_1: (0, False),
            ABL.KNOB_2: (1, False),
            ABL.KNOB_3: (2, False),
            ABL.KNOB_4: (3, True)
        }
        
        if search_key in knob_mapping:
            knob_id, is_shifted = knob_mapping[search_key]
            delta = self._knobs_ease.feed(bytes(search_key), data_val, is_shifted)
            self.state_manager.send_cuia("ZYNPOT", [knob_id, delta])
            return True
        
        # Handle button press events
        if data_val > 0:  # Button down events only
            button_mapping = {
                ABL.BTN_OK: ("V5_ZYNPOT_SWITCH", [3, "S"]),
                ABL.BTN_R1_C1: ("V5_ZYNPOT_SWITCH", [0, "S"]),
                ABL.BTN_R1_C2: ("V5_ZYNPOT_SWITCH", [1, "S"]),
                ABL.BTN_R1_C3: ("V5_ZYNPOT_SWITCH", [2, "S"]),
                ABL.BTN_ESC: ("BACK", None),
                ABL.BTN_RIGHT: ("ARROW_RIGHT", None),
                ABL.BTN_LEFT: ("ARROW_LEFT", None),
                ABL.BTN_UP: ("ARROW_UP", None),
                ABL.BTN_DOWN: ("ARROW_DOWN", None),
                ABL.BTN_START: ("TOGGLE_PLAY", "TOGGLE_MIDI_PLAY"),
                ABL.BTN_REC: ("TOGGLE_RECORD", "TOGGLE_MIDI_RECORD")
            }
            
            if search_key in button_mapping:
                action, shift_action = button_mapping[search_key]
                if self.shift and shift_action:
                    action = shift_action
                
                if isinstance(action, tuple):
                    self.state_manager.send_cuia(action[0], action[1])
                else:
                    self.state_manager.send_cuia(action)
                return True
               
        return False
    
    def button_name_from_midi_event(self, ev):
        """Get button name from MIDI event for debugging
        
        Args:
            ev: MIDI event bytes or search key
            
        Returns:
            str: Button name or empty string if not found
        """
        if len(ev) < 2:
            return None
        
        if len(ev) > 2:
            data = ev[2]
        search_key = (ev[0] & 0xF0, ev[1])
        
        # Search for button definition in ABL module
        for name in dir(ABL):
            if not name.startswith('__') and name.isupper():
                attr = getattr(ABL, name)
                if attr == search_key:
                    return name
        
        return ""  # Button not found in config

# ------------------------------------------------------------------------------
# Special Classes for Ableton Push 1 Display and Feedback
#####################################################################################

class Feedback_Display:
    """Class for controlling Ableton Push 1 text display"""
    
    # Display character constants (Akai-specific character set)
    DISP_ARROW_UP = 0
    DISP_ARROW_DOWN = 1
    DISP_ARROW_RIGHT = 30
    DISP_ARROW_LEFT = 31
    DISP_HORIZONTAL_LINES_THREE_STACKED = 2
    DISP_HORIZONTAL_LINE_LOW = 95
    DISP_HOIZONTAL_LINE_SPLIT = 6
    DISP_VERTICAL_LINE_AND_HORIZONTAL_LINE = 3
    DISP_HORIZONTAL_LINE_AND_VERTICAL_LINE = 4
    DISP_VERTICAL_LINES_TWO = 5
    DISP_VERTICAL_LINE_MID = 174
    DISP_SPLIT_VERTICAL_LINES = 8
    DISP_FOLDER_SYMBOL = 7
    DISP_FLAT_SYMBOLS = 27
    DISP_THREE_SIDE_BY_SIDE_DOTS = 28
    DISP_FULL_BLOCK = 29
    DISP_LITTLE_BOX_SHIFTED_HIGH_MIDDLE = 9
    DISP_AE_UC = 10
    DISP_CEDILLE_UC = 11
    DISP_OE_UC = 12
    DISP_UE_UC = 13
    DISP_SZ = 14
    DISP_A_GRAVE = 15
    DISP_AE_LC = 16
    DISP_CEDILE = 17
    DISP_E_LC_GRAVE = 18
    DISP_E_LC_EGUT = 19
    DISP_E_LC_CIRCUM = 20
    DISP_I_LC_TREMA = 21
    DISP_N_LC_WITH_TILDE = 22
    DISP_OE_LC = 23
    DISP_DIV_STROKE = 24
    DISP_CIRC_WITH_DIV_STROKE = 25
    DISP_UE_LC = 26

    # Mapping from Akai character codes to Unicode
    akai_to_unicode = {
        0: "↑", 1: "↓", 30: "→", 31: "←", 2: "≡", 6: "╌", 95: "_",
        3: "┤", 4: "├", 5: "║", 8: "⫼", 174: "|", 7: "📁", 27: "♭",
        28: "⋮", 29: "█", 9: "▫", 10: "Ä", 11: "Ç", 12: "Ö", 13: "Ü",
        14: "ß", 15: "à", 16: "ä", 17: "ç", 18: "è", 19: "é", 20: "ê",
        21: "ï", 22: "ñ", 23: "ö", 24: "⁄", 25: "Ø", 26: "ü"
    }
    
    format_help = b'123456789A123456789B123456789C123456789D123456789E123456789F123456789'
        
    def __init__(self, idev_out):
        """Initialize display controller
        
        Args:
            idev_out: Output device ID
        """
        self.idev_out = idev_out
        self.display_mem = [[32] * 68 for _ in range(4)]  # 4 rows, 68 columns
        self._disp_line_dirty = [False, False, False, False]

    def clear(self):
        """Clear entire display (fill with spaces)"""
        self.display_mem = [[32] * 68 for _ in range(4)]
        
        # Send SYSEX commands to clear each display line
        sysex_commands = [
            bytes([240, 71, 127, 21, 28, 0, 0, 247]),  # Line 0
            bytes([240, 71, 127, 21, 29, 0, 0, 247]),  # Line 1
            bytes([240, 71, 127, 21, 30, 0, 0, 247]),  # Line 2
            bytes([240, 71, 127, 21, 31, 0, 0, 247])   # Line 3
        ]
        
        for cmd in sysex_commands:
            lib_zyncore.dev_send_midi_event(self.idev_out, cmd, len(cmd))
            sleep(0.01)
        
        self._disp_line_dirty = [False, False, False, False]

    def update_screen(self):
        """Update display with changed content"""
        for row in range(4):
            if self._disp_line_dirty[row]:
                text = bytes(self.display_mem[row])
                text_len = len(text)
                col = 0
                
                # Construct SYSEX message for line update
                msg = bytes([240, 71, 127, 21, row + 24, 0, text_len + 1, col]) + text + bytes([247])
                lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
                sleep(0.01)
                self._disp_line_dirty[row] = False

    def write_xy_mem(self, text, col_in, row_in):
        """Write text to display memory at specified position
        
        Args:
            text: Text to display (str, bytes, or number)
            col_in: Column position (0-67)
            row_in: Row position (0-3)
        """
        # Convert input to bytes
        if isinstance(text, str):
            text = text.encode()
        elif isinstance(text, bytes):
            pass  # Already bytes
        elif isinstance(text, (int, float)):
            text = str(text).encode()
        else:
            text = "Type error".encode()
        
        # Validate coordinates
        row_in = max(0, min(3, row_in))
        col_in = max(0, min(63, col_in))
        
        # Truncate text if it exceeds display bounds
        text_len = len(text)
        if text_len + col_in > 68:
            text = text[:68 - col_in]
        text_len = len(text)
        
        # Update display memory and mark as dirty
        self.display_mem[row_in][col_in:col_in + text_len] = list(text)
        self._disp_line_dirty[row_in] = True

    def write_to_knobx_mem(self, text, knob_x, row_y, as_bar=False):
        """Write text below specified knob position
        
        Args:
            text: Text to display
            knob_x: Knob index (0-7)
            row_y: Row position
            as_bar: Whether to display as volume bar
        """
        if knob_x > 7:
            knob_x = 7
            logging.error("Knob index >7 not implemented. Using main channel.")
        
        # Convert numbers to text and handle bar display
        if isinstance(text, (int, float)):
            if as_bar:
                fieldlen = 8
                if float(text) == 0.0:
                    text = "<off>".ljust(fieldlen)
                else:
                    int_val = int(text * fieldlen)
                    if int_val == 0:
                        text = ".".ljust(fieldlen)
                    else:
                        text = "".ljust(int_val, chr(self.DISP_VERTICAL_LINES_TWO)).ljust(fieldlen)
            else:
                text = str(text).ljust(8)
        
        # Calculate display position and write text
        fields_start_knobs = [0, 9, 17, 26, 34, 43, 51, 60]
        knobx_start = fields_start_knobs[knob_x]
        text = text.ljust(8)[:8]
        self.write_xy_mem(text, knobx_start, row_y)

    def contrast(self, i=None):
        """Set or get display contrast
        
        Args:
            i: Contrast value (0-63) or None to read current value
            
        Returns:
            int: Current contrast value or None if reading not supported
        """
        if i is not None:
            i = max(0, min(63, i))  # Clamp to valid range
            msg = bytes([240, 71, 127, 21, 122, 0, 1, i, 247])
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            return i
        
        # Reading contrast not currently implemented
        return None

    def brightnes(self, i=None):
        """Set or get display brightness
        
        Args:
            i: Brightness value (0-63) or None to read current value
            
        Returns:
            int: Current brightness value or None if reading not supported
        """
        if i is not None:
            i = max(0, min(63, i))  # Clamp to valid range
            msg = bytes([240, 71, 127, 21, 124, 0, 1, i, 247])
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            return i
        
        # Reading brightness not currently implemented
        return None

    def first_screen(self):
        """Display welcome/splash screen"""
        self.clear()
        sleep(0.1)
        self.write_xy_mem(b'** Zynthian Push1Driver 0.2 **', 17, 2)
        self.write_xy_mem(b'++  Make MusicNot War ++', 20, 3)
        self.update_screen()

# --------------------------------------------------------------------------
# Feedback LED controller classes
# --------------------------------------------------------------------------

class Feedback_Mono_LEDs:
    """Controller for monochrome LEDs"""
    
    _all_mono = [3, 9, 28, 29, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 
                 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 61, 62, 63, 
                 85, 86, 87, 88, 89, 90, 110, 111, 11, 113, 114, 115, 116, 117, 118, 119]
    
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()
        
    def all_off(self, overlay=False):
        """Turn off all monochrome LEDs"""
        for note in self._all_mono:
            lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, 0)
            if not overlay:
                self._state[note] = 0

    def set_mono(self, note, grey_val, overlay=False):
        """Set monochrome LED state
        
        Args:
            note: LED note number
            grey_val: Brightness value
            overlay: Whether to update internal state
        """
        lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, grey_val)
        if not overlay:
            self._state[note] = grey_val

    def refresh_one(self, note):
        """Refresh single LED state from memory"""
        if note in self._state:
            lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, self._state[note])

    def refresh(self):
        """Refresh all LED states from memory"""
        for note in self._all_mono:
            if note in self._state:
                lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, self._state[note])

class Feedback_Bi_LEDs:
    """Controller for bi-color LEDs (not fully implemented)"""
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()

    def all_off(self):
        """Turn off all bi-color LEDs"""
        pass  # Implementation needed

class Feedback_RGB_LEDs:
    """Controller for RGB pad LEDs"""
    
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()

    def all_off(self, overlay=False):
        """Turn off all RGB LEDs"""
        for pad_nr in range(ABL_PAD_END + 1 - ABL_PAD_START):
            self.set_rgb(pad_nr, 0, 0, 0, overlay)

    def refresh(self):
        """Refresh all RGB LED states from memory"""
        for pad_nr in range(ABL_PAD_END + 1 - ABL_PAD_START):
            self.refresh_one(pad_nr)

    def refresh_one(self, pad_nr):
        """Refresh single RGB LED state from memory"""
        if pad_nr in self._state:
            r, g, b = self._state[pad_nr]
            self.set_rgb(pad_nr, r, g, b)

    def off_col_row(self, col, row):
        """Turn off LED at specific column/row position
        
        Args:
            col: Column index (0-7)
            row: Row index (0-7)
        """
        note = ABL_PAD_END + 1 - (row + 1) * 8 + col
        lib_zyncore.dev_send_note_on(self._idev, 0, note, 0)

    def set_rgb(self, pad_nr, r, g, b, overlay=False):
        """Set RGB LED color
        
        Args:
            pad_nr: Pad number (0-63)
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            overlay: Whether to update internal state
        """
        # Clamp color values
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        if not 0 <= pad_nr <= 63:
            logging.error(f"Invalid pad number: {pad_nr}")
            return False
        
        # Save state if not overlay
        if not overlay:
            self._state[pad_nr] = [r, g, b]
        
        # Convert RGB to Push format (4-bit components)
        r1, r2 = r // 16, r % 16
        g1, g2 = g // 16, g % 16
        b1, b2 = b // 16, b % 16
        
        # Send SYSEX message
        sysex = bytes([240, 71, 127, 21, 4, 0, 8, pad_nr, 0, r1, r2, g1, g2, b1, b2, 247])
        lib_zyncore.dev_send_midi_event(self._idev, sysex, len(sysex))
        
        
        
class ABL:
    # Ableton Push 1 consts

    ### Definition of all buttons, pads and knobs
    # knobs and Buttons are CC-Events
    # knobs also have touch function with midi note event
    #
    # ribbon is type modwheel !!! Just one byte ev[0]
    # ribbon has also touch function with midi note even
    #
    # pad have note event
    
    # Definitions contain full event[:2] Data. You must not distinguish between different Midi Message types
    # (Buttons are defined with their action Message. Noteon, Control Change)

    ### SYSEX
    # SYSEX_PREAMBLE = []
    # SYSEX_END      = []

    # Display
    # Write text to display	240,71,127,21,<24+line(0-3)>,0,<Nchars+1>,<Offset>,<Chars>,247
    # Clear display line	240,71,127,21,<28+line(0-3)>,0,0,247
    # SYSEX_INST_WRITE_LINE_0 = bytes([24])
    # SYSEX_INST_WRITE_LINE_1 = bytes([25])
    # SYSEX_INST_WRITE_LINE_2 = bytes([26])
    # SYSEX_INST_WRITE_LINE_3 = bytes([27])

    # Knobs 1-9
    KNOB_1 = (0xB0, 71)  # CC71
    KNOB_2 = (0xB0, 72)  # CC72
    KNOB_3 = (0xB0, 73)
    KNOB_4 = (0xB0, 74)
    KNOB_5 = (0xB0, 75)  # CC75
    KNOB_6 = (0xB0, 76)  # CC76
    KNOB_7 = (0xB0, 77)  # CC77
    KNOB_8 = (0xB0, 78)  # CC78
    KNOB_9 = (0xB0, 79)  # CC79
    KNOB_10 = (0xB0, 14)  # CC79
    KNOB_11 = (0xB0, 15)  # CC79

    # Touch
    KNOB_1_T = (0x90, 0)   # "C-1" sic! 
    KNOB_2_T = (0x90, 1)   # "C#-1"
    KNOB_3_T = (0x90, 2)   # "D-1"
    KNOB_4_T = (0x90, 3)   # "D#-1"
    KNOB_5_T = (0x90, 4)   # Note 4
    KNOB_6_T = (0x90, 5)   # Note 5
    KNOB_7_T = (0x90, 6)   # note 6
    KNOB_8_T = (0x90, 7)   # note 7
    KNOB_9_T = (0x90, 8)   # Note 8
    KNOB_10_T = (0x90, 9)
    KNOB_11_T = (0x90, 10)

    RIBBON_TOUCH_T = (0x90, 12)  # "C0" note 12
    RIBBON_PITCH = (0xE0,)       # Mod-wheel - Tupel mit einem Element!

    # Monochromatic Buttons
    # Alle Button sind CC / Alle PAD sind Noteon
    BTN_TAP_TEMPO = (0xB0, 3) 
    BTN_METRONOME = (0xB0, 9)

    BTN_FIXED_LENGTH = (0xB0, 90)
    BTN_AUTOMATION = (0xB0, 89)
    BTN_DUPLICATE = (0xB0, 88)

    BTN_NEW = (0xB0, 87)
    BTN_REC = (0xB0, 86)
    BTN_START = (0xB0, 85)

    #########  RECHTS ############
    BTN_PAN = (0xB0, 115)  # CC115
    BTN_VOLUME = (0xB0, 114)  # CC114

    BTN_CLIP = (0xB0, 113)
    BTN_TRACK = (0xB0, 112)

    BTN_BROWSE = (0xB0, 111)
    BTN_DEVICE = (0xB0, 110)

    BTN_ESC = (0xB0, 63)
    BTN_OK = (0xB0, 62)
    BTN_SOLO = (0xB0, 61)
    BTN_MUTE = (0xB0, 60)
    BTN_USER = (0xB0, 59)
    BTN_SCALES = (0xB0, 58)
    BTN_ACCENT = (0xB0, 57)
    BTN_REPEAT = (0xB0, 56)
    BTN_OCTAVE_UP = (0xB0, 55)
    BTN_OCTAVE_DOWN = (0xB0, 54)

    BTN_ADD_TRACK = (0xB0, 53)
    BTN_ADD_EFFECT = (0xB0, 52)
    BTN_SESSION = (0xB0, 51)
    BTN_NOTE = (0xB0, 50)
    BTN_SHIFT = (0xB0, 49)
    BTN_SELECT = (0xB0, 48)

    BTN_UP = (0xB0, 46)
    BTN_DOWN = (0xB0, 47)
    BTN_LEFT = (0xB0, 44)
    BTN_RIGHT = (0xB0, 45)

    # bottom up
    BTN_BEAT_1_QUATER = (0xB0, 36)
    BTN_BEAT_2_QUATER_T = (0xB0, 37)
    BTN_BEAT_3_EIGHTH = (0xB0, 38)
    BTN_BEAT_4_EIGHTH_T = (0xB0, 39)
    BTN_BEAT_5_SIXTEENTH = (0xB0, 40)
    BTN_BEAT_6_SIXTEENTH_T = (0xB0, 41)
    BTN_BEAT_7_THIRTYSECOND = (0xB0, 42)
    BTN_BEAT_8_THIRTYSECOND_T = (0xB0, 43)

    BTN_MASTER = (0xB0, 28)
    BTN_STOP = (0xB0, 29)

    # Bicolor Buttons in the middle, below the display
    # They have two colors, red and green.
    BTN_R1_C1 = (0xB0, 20)
    BTN_R1_C2 = (0xB0, 21)
    BTN_R1_C3 = (0xB0, 22)
    BTN_R1_C4 = (0xB0, 23)
    BTN_R1_C5 = (0xB0, 24)
    BTN_R1_C6 = (0xB0, 25)
    BTN_R1_C7 = (0xB0, 26)
    BTN_R1_C8 = (0xB0, 27)

    BTN_R2_C1 = (0xB0, 102)
    BTN_R2_C2 = (0xB0, 103)
    BTN_R2_C3 = (0xB0, 104)
    BTN_R2_C4 = (0xB0, 105)
    BTN_R2_C5 = (0xB0, 106)
    BTN_R2_C6 = (0xB0, 107)
    BTN_R2_C7 = (0xB0, 108)
    BTN_R2_C8 = (0xB0, 109)

    # Have RGB-LED
    PAD_36 = (0x90, 36)  # note
    PAD_37 = (0x90, 37)  # note
    PAD_38 = (0x90, 38)  # note
    PAD_39 = (0x90, 39)  # note
    PAD_40 = (0x90, 40)  # note
    PAD_41 = (0x90, 41)  # note
    PAD_42 = (0x90, 42)  # note
    PAD_43 = (0x90, 43)  # note

    PAD_44 = (0x90, 44)  # note
    PAD_45 = (0x90, 45)  # note
    PAD_46 = (0x90, 46)  # note
    PAD_47 = (0x90, 47)  # note
    PAD_48 = (0x90, 48)  # note
    PAD_49 = (0x90, 49)  # note
    PAD_50 = (0x90, 50)  # note
    PAD_51 = (0x90, 51)  # note

    PAD_52 = (0x90, 52)  # note
    PAD_53 = (0x90, 53)  # note
    PAD_54 = (0x90, 54)  # note
    PAD_55 = (0x90, 55)  # note
    PAD_56 = (0x90, 56)  # note
    PAD_57 = (0x90, 57)  # note
    PAD_58 = (0x90, 58)  # note
    PAD_59 = (0x90, 59)  # note

    PAD_60 = (0x90, 60)  # note
    PAD_61 = (0x90, 61)  # note
    PAD_62 = (0x90, 62)  # note
    PAD_63 = (0x90, 63)  # note
    PAD_64 = (0x90, 64)  # note
    PAD_65 = (0x90, 65)  # note
    PAD_66 = (0x90, 66)  # note
    PAD_67 = (0x90, 67)  # note

    PAD_68 = (0x90, 68)  # note
    PAD_69 = (0x90, 69)  # note
    PAD_70 = (0x90, 70)  # note
    PAD_71 = (0x90, 71)  # note
    PAD_72 = (0x90, 72)  # note
    PAD_73 = (0x90, 73)  # note
    PAD_74 = (0x90, 74)  # note
    PAD_75 = (0x90, 75)  # note

    PAD_76 = (0x90, 76)  # note
    PAD_77 = (0x90, 77)  # note
    PAD_78 = (0x90, 78)  # note
    PAD_79 = (0x90, 79)  # note
    PAD_80 = (0x90, 80)  # note
    PAD_81 = (0x90, 81)  # note
    PAD_82 = (0x90, 82)  # note
    PAD_83 = (0x90, 83)  # note

    PAD_84 = (0x90, 84)  # note
    PAD_85 = (0x90, 85)  # note
    PAD_86 = (0x90, 86)  # note
    PAD_87 = (0x90, 87)  # note
    PAD_88 = (0x90, 88)  # note
    PAD_89 = (0x90, 89)  # note
    PAD_90 = (0x90, 90)  # note
    PAD_91 = (0x90, 91)  # note

    PAD_92 = (0x90, 92)  # note
    PAD_93 = (0x90, 96)  # note
    PAD_94 = (0x90, 94)  # note
    PAD_95 = (0x90, 95)  # note
    PAD_96 = (0x90, 96)  # note
    PAD_97 = (0x90, 97)  # note
    PAD_98 = (0x90, 98)  # note
    PAD_99 = (0x90, 99)  # note

    ## from pushmod.blogspot.com
    #### PUSH 1 SYSEX #######################################

    # 71 is the manufacturer ID (Akai Electric Co. Ltd.)
    # 127 is the device ID (default it 127 - All Devices)
    # 21 is the product ID (Push)
    # The Device ID can be sent as 0 as well.

    # Identity request		240,126,0,6,1,247
    # Set pad color (RGB)		240,71,127,21,4,0,8,<Pad(0-71)>,0,<r1>,<r2>,<g1>,<g2>,<b1>,<b2>,247
    # Write text to display		240,71,127,21,<24+line(0-3)>,0,<Nchars+1>,<Offset>,<Chars>,247
    # Clear display line		240,71,127,21,<28+line(0-3)>,0,0,247
    # Set key aftertouch		240,71,127,21,92,0,1,0,247
    # Set channel aftertouch	240,71,127,21,92,0,1,1,247
    # Set Live version		240,71,127,21,96,0,4,65,<major>,<minor>,<bugfix>,247
    # Set Live mode			240,71,127,21,98,0,1,0,247
    SYSEX_DATA_SET_LIVE_MODE = (240, 71, 127, 21, 98, 0, 1, 0, 247)

    # Set User mode	240,71,127,21,98,0,1,1,247
    SYSEX_DATA_SET_USER_MODE = (240, 71, 127, 21, 98, 0, 1, 1, 247)

    # Set touch strip mode		240,71,127,21,99,0,1,<Mode>,247
    # Request white calibration information		240,71,127,21,107,0,0,247
    # Contrast request		240,71,127,21,122,0,0,247
    # Contrast set			240,71,127,21,122,0,1,<contrast 0-127>, 247
    # Brightness request		240,71,127,21,124,0,0,247
    # Brightness set	240,71,127,21,124,0,1,<brightness 0-127>,247
    ######### END PUSH 1 SYSEX ############################

    ### Monochromatic Keys/Pads #######################
    MONO_LED_OFF = 0                 # 0 - Off
    MONO_LED_DIM = 1                 # 1 - Dim
    MONO_LED_DIM_BLINK = 2           # 2 - Dim Blink
    MONO_LED_DIM_BLINK_FAST = 3      # 3 - Dim Blink Fast
    MONO_LED_LIT = 4                 # 4 - Lit
    MONO_LED_LIT_BLINK = 5           # 5 - Lit Blink  
    MONO_LED_LIT_BLINK_FAST = 6      # 6 - Lit Blink Fast
    #  7 -> 127 - Lit
    #########  END MONOCHROMATIC LED ##################

    # Bi-color LED table
    # These are the colors which will be set on the bi-color (red/green) buttons below display

    BI_LED_OFF = 0                  # 0 - Off (Black)
    BI_RED_DIM = 1                  # 1 - Red Dim
    BI_RED_DIM_BLINK = 2            # 2 - Red Dim Blink
    BI_RED_DIM_BLINK_FAST = 3       # 3 - Red Dim Blink Fast
    BI_RED = 4                      # 4 - Red
    BI_RED_BLINK = 5                # 5 - Red Blink
    BI_RED_BLINK_FAST = 6           # 6 - Red Blink Fast
    BI_ORANGE_DIM = 7               # 7 - Orange Dim
    BI_ORANGE_DIM_BLINK = 8         # 8 - Orange Dim Blink
    BI_ORANGE_DIM_BLINK_FAST = 9    # 9 - Orange Dim Blink Fast
    BI_ORANGE = 10                  # 10 - Orange   
    BI_ORANGE_BLINK = 11            # 11 - Orange Blink
    BI_ORANGE_BLINK_FAST = 12       # 12 - Orange Blink Fast
    BI_YELLOW_DIM = 13              # 13 - Yellow (Lime) Dim
    BI_YELLOW_DIM_BLINK = 14        # 14 - Yellow Dim Blink
    BI_YELLOW_DIM_BLINK_FAST = 15   # 15 - Yellow Dim Blink Fast       
    BI_YELLOW = 16                  # 16 - Yellow (Lime)
    BI_YELLOW_BLINK = 17            # 17 - Yellow Blink
    BI_YELLOW_BLINK_FAST = 18       # 18 - Yellow Blink Fast           
    BI_GREEN_DIM = 19               # 19 - Green Dim
    BI_GREEN_DIM_BLINK = 20         # 20 - Green Dim Blink
    BI_GREEN_DIM_BLINK_FAST = 21    # 21 - Green Dim Blink Fast      
    BI_GREEN = 22                   # 22 - Green
    BI_GREEN_BLINK = 23             # 23 - Green Blink
    BI_GREEN_BLINK_FAST = 24        # 24 - Green Blink Fast
    # 25 -> 127 - Green    