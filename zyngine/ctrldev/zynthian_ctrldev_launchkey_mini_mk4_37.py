#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchkey Mini MK4 37"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#                         Jorge Razon <jrazon@gmail.com>
#
#
#******************************************************************************
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
#******************************************************************************
# This driver implements support for the Novation Launchkey Mini MK4 37-key
# controller in DAW mode with Transport mode encoders (relative CC values).
#
# Features:
# - Keyboard input (37 keys pass through to synths)
# - Pad buttons: Top row=Solo, Bottom row=Mute (8 mixer channels)
# - Three knob banks:
#   Bank 0: Mixer levels (channels 1-8)
#   Bank 1: ZYNPOT 0-3, Arrow L/R, Arrow U/D, Preset browse, SELECT/BACK
#   Bank 2: CC passthrough (CC 24-31)
# - Transport controls (Play, Record, Stop) with shift modifiers
#******************************************************************************
from time import sleep, time
from threading import Timer
import logging

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchkey Mini MK4 37
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchkey_mini_mk4_37(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["Launchkey Mini MK4 37 IN 2"]  # In DAW mode, everything comes through IN 2 (like MK3)
    driver_name = "Launchkey Mini MK4 37"
    driver_description = "Interface Novation Launchkey Mini Mk4 with Zynthian"
    unroute_from_chains = True  # Prevent automatic routing, we'll handle keyboard notes explicitly

    PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    STARTING_COLOUR = 123
    STOPPING_COLOUR = 120
    
    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.shift = False
        self.press_times = {}
        self.knob_bank = 1  # Track current knob bank (0 = mixer, 1 = zynpot+CC, 2 = CC) - default to bank 1
        self.last_select_back_time = 0  # Debounce timer for SELECT/BACK knob
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        # Enable DAW mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        sleep(0.2)
        # Set encoders to Transport mode (relative mode)
        # Channel 7 (B6h = 182 decimal), CC 30 (1Eh = 30 decimal), Value 5 (Transport mode)
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 6, 30, 5)
        sleep(0.1)
        self.cols = 8
        self.rows = 2
        super().init()
        # Light up navigation buttons
        self.update_button_leds()
        # Update pad LEDs immediately
        self.update_pad_leds()
        
        # Register callbacks for real-time updates using zynsigman
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_pad_leds)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.update_pad_leds)
        zynsigman.register_queued(zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_mixer_strip)
        zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_screen_change)

    def refresh(self):
        """Called when screen changes or chains are modified"""
        # Update pad LEDs to reflect current mixer state
        self.update_pad_leds()

    def update_button_leds(self):
        """Light up the navigation buttons and show bank state"""
        if self.idev_out is None:
            return
        # Light up navigation buttons (not 51/52, those show bank state)
        cc_buttons = [104, 105, 0x66, 0x67, 106, 107]
        for cc in cc_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, 127)
        
        # Update bank indicator LEDs
        # Button 51 lights for bank 0, button 52 for bank 1, both off for bank 2
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 51, 127 if self.knob_bank == 0 else 0)
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 52, 127 if self.knob_bank == 1 else 0)

    def end(self):
        # Unregister signal callbacks
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.update_pad_leds)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_MOVE_CHAIN, self.update_pad_leds)
        zynsigman.unregister(zynsigman.S_AUDIO_MIXER, self.zynmixer.SS_ZCTRL_SET_VALUE, self.update_mixer_strip)
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_screen_change)
        super().end()
        # Disable DAW mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)
    
    def update_mixer_strip(self, chan, symbol, value):
        """Update pad LEDs when mixer values change (mute/solo)"""
        # Only update if it's a mute or solo change
        if symbol in ['mute', 'solo']:
            self.update_pad_leds()
    
    def on_screen_change(self, screen):
        """Update pad LEDs when screen changes (catches chain add/remove)"""
        # Update LEDs when any screen is shown, as chains may have changed
        self.update_pad_leds()
    
    def update_pad_leds(self):
        """Update pad LEDs based on mixer mute/solo state"""
        if self.idev_out is None:
            return
        
        try:
            # Verify chain_manager and zynmixer are available
            if not hasattr(self, 'chain_manager') or not hasattr(self, 'zynmixer'):
                return
            
            # Update solo pads (top row: notes 96-103)
            # Pads 0-6: chains 0-6 (excluding master), Pad 7: master channel (no solo for master)
            for i in range(8):
                note = 96 + i
                try:
                    if i < 7:
                        # Pads 0-6: Regular chains (skip master channel if it appears in chain list)
                        chain = self.chain_manager.get_chain_by_position(i, midi=False)
                        
                        if chain and hasattr(chain, 'mixer_chan') and chain.mixer_chan is not None and chain.mixer_chan < 16:
                            mixer_chan = chain.mixer_chan
                            is_soloed = self.zynmixer.get_solo(mixer_chan)
                            vel = 14 if is_soloed else 118  # Yellow/orange if soloed, dim if not
                        else:
                            vel = 0  # No chain or master channel - LED off
                    else:
                        # Pad 7: Master channel - always off (no solo for master)
                        vel = 0
                except:
                    vel = 0  # Error - LED off
                
                lib_zyncore.dev_send_note_on(self.idev_out, 0, note, vel)
            
            # Update mute pads (bottom row: notes 112-119)
            # Pads 0-6: chains 0-6 (excluding master), Pad 7: master channel
            for i in range(8):
                note = 112 + i
                try:
                    if i < 7:
                        # Pads 0-6: Regular chains (skip master channel if it appears in chain list)
                        chain = self.chain_manager.get_chain_by_position(i, midi=False)
                        
                        if chain and hasattr(chain, 'mixer_chan') and chain.mixer_chan is not None and chain.mixer_chan < 16:
                            mixer_chan = chain.mixer_chan
                            is_muted = self.zynmixer.get_mute(mixer_chan)
                            vel = 5 if is_muted else 64  # Red if muted, green if unmuted
                        else:
                            vel = 0  # No chain or master channel - LED off
                    else:
                        # Pad 7: Master channel (mixer channel 16)
                        is_muted = self.zynmixer.get_mute(16)
                        vel = 5 if is_muted else 64  # Red if muted, green if unmuted
                except:
                    vel = 0  # Error - LED off
                
                lib_zyncore.dev_send_note_on(self.idev_out, 0, note, vel)
        except Exception:
            # Silently fail if something goes wrong
            pass

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        ev_chan = ev[0] & 0x0F
        
        # Handle note events (note-on and note-off)
        # Only process pad notes (96-119), let regular keyboard notes pass through
        if evtype == 0x9 or evtype == 0x8:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            
            # Block ALL pad notes (96-119) from reaching synths by consuming the event
            if 96 <= note <= 119:
                # Process solo pads (96-102 only, pad 103 is master - no solo)
                if 96 <= note <= 102 and evtype == 0x9 and vel > 0:
                    # Top row (96-102): Solo control for chains 0-6 (excluding master)
                    track = note - 96
                    chain = self.chain_manager.get_chain_by_position(track, midi=False)
                    
                    if chain and chain.mixer_chan is not None and chain.mixer_chan < 16:
                        mixer_chan = chain.mixer_chan
                        current_solo = self.zynmixer.get_solo(mixer_chan)
                        self.zynmixer.set_solo(mixer_chan, 0 if current_solo else 1)
                        self.update_pad_leds()
                
                # Process mute pads (112-119)
                elif 112 <= note <= 119 and evtype == 0x9 and vel > 0:
                    # Bottom row: Pads 0-6 for chains 0-6 (excluding master), Pad 7 for master
                    track = note - 112
                    
                    if track < 7:
                        # Pads 0-6: Regular chains (skip master if it appears in chain list)
                        chain = self.chain_manager.get_chain_by_position(track, midi=False)
                        
                        if chain and chain.mixer_chan is not None and chain.mixer_chan < 16:
                            mixer_chan = chain.mixer_chan
                            current_mute = self.zynmixer.get_mute(mixer_chan)
                            self.zynmixer.set_mute(mixer_chan, 0 if current_mute else 1)
                            self.update_pad_leds()
                    else:
                        # Pad 7: Master channel (mixer channel 16)
                        current_mute = self.zynmixer.get_mute(16)
                        self.zynmixer.set_mute(16, 0 if current_mute else 1)
                        self.update_pad_leds()
                
                # Block ALL pad notes (96-119, both on and off) from reaching synths
                return True
            
            # All other notes (keyboard) - explicitly route to chains
            else:
                # Keyboard notes: send them through to the MIDI routing system
                lib_zyncore.write_zynmidi(ev)
                return True
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            
            # Navigation button mappings (fire on button press)
            button_commands = {
                105: "MENU",
                106: "BACK",
                107: "PRESET",
                0x66: "ARROW_RIGHT",
                0x67: "ARROW_LEFT"
            }
            
            # Buttons 51 and 52: Bank switching (normal), Arrow Up/Down (with shift)
            if ccnum == 51 and ccval > 0:
                if self.shift:
                    self.state_manager.send_cuia("ARROW_UP")
                else:
                    self.knob_bank = (self.knob_bank - 1) % 3
                    self.update_button_leds()
                return True
            elif ccnum == 52 and ccval > 0:
                if self.shift:
                    self.state_manager.send_cuia("ARROW_DOWN")
                else:
                    self.knob_bank = (self.knob_bank + 1) % 3
                    self.update_button_leds()
                return True
            
            # Physical shift button (CC 0x3F)
            elif ccnum == 0x3F:
                self.shift = ccval > 0
                return True

            # Button 104: ZYNSWITCH 3 with press duration detection
            elif ccnum == 104:
                if ccval > 0:
                    self.press_times[ccnum] = time()
                else:
                    if ccnum in self.press_times:
                        duration = time() - self.press_times[ccnum]
                        press_type = 'S' if duration < 0.5 else 'B' if duration < 1.5 else 'L'
                        self.state_manager.send_cuia("ZYNSWITCH", [3, press_type])
                        del self.press_times[ccnum]
                return True
            # Knobs 1-8 (CC 85-92): Behavior depends on current bank (Transport mode = relative)
            elif 84 < ccnum < 93:
                if self.knob_bank == 0:
                    # Bank 0: Mixer channel levels
                    # Knobs 1-7: chains 0-6 (excluding master), Knob 8: master channel
                    knob_index = ccnum - 85  # 0-7
                    
                    # Convert relative encoder value to delta (Transport mode: 1/63 = CCW, 127/65 = CW)
                    delta = -1 if ccval < 64 else 1 if ccval > 64 else 0
                    
                    if delta != 0:
                        if knob_index < 7:
                            # Knobs 1-7: Regular chains (skip master if it appears in chain list)
                            chain = self.chain_manager.get_chain_by_position(knob_index, midi=False)
                            if chain and chain.mixer_chan is not None and chain.mixer_chan < 16:
                                mixer_chan = chain.mixer_chan
                                current_level = self.zynmixer.get_level(mixer_chan)
                                new_level = max(0.0, min(1.0, current_level + (delta * 0.01)))
                                self.zynmixer.set_level(mixer_chan, new_level)
                        else:
                            # Knob 8: Master channel (mixer channel 16)
                            current_level = self.zynmixer.get_level(16)
                            new_level = max(0.0, min(1.0, current_level + (delta * 0.01)))
                            self.zynmixer.set_level(16, new_level)
                    return True
                elif self.knob_bank == 1:
                    # Bank 1: ZYNPOT 0-3, Arrow L/R, Arrow U/D, Presets, SELECT/BACK
                    if 84 < ccnum < 89:
                        # Knobs 1-4: ZYNPOT 0-3 (Zynthian's main rotary encoders)
                        zynpot_index = ccnum - 85
                        delta = -1 if ccval < 64 else 1 if ccval > 64 else 0
                        
                        if delta != 0:
                            self.state_manager.send_cuia("ZYNPOT", [zynpot_index, delta])
                        
                        return True
                    elif ccnum == 89:
                        # Knob 5: Arrow Left/Right
                        self.state_manager.send_cuia("ARROW_LEFT" if ccval < 64 else "ARROW_RIGHT")
                        return True
                    elif ccnum == 90:
                        # Knob 6: Arrow Up/Down
                        self.state_manager.send_cuia("ARROW_UP" if ccval < 64 else "ARROW_DOWN")
                        return True
                    elif ccnum == 91:
                        # Knob 7: Preset browsing (previous/next with wraparound)
                        delta = -1 if ccval < 64 else 1 if ccval > 64 else 0
                        
                        if delta != 0:
                            try:
                                chain = self.state_manager.chain_manager.get_active_chain()
                                if chain and chain.current_processor:
                                    processor = chain.current_processor
                                    if hasattr(processor, 'preset_list') and processor.preset_list:
                                        current_index = processor.preset_index if hasattr(processor, 'preset_index') else 0
                                        new_index = (current_index + delta) % len(processor.preset_list)
                                        processor.set_preset(new_index)
                                        self.state_manager.send_cuia("refresh_screen", ["control"])
                                        self.state_manager.send_cuia("refresh_screen", ["audio_mixer"])
                            except Exception as e:
                                logging.warning(f"Preset browsing error: {e}")
                        return True
                    elif ccnum == 92:
                        # Knob 8: SELECT (CW) / BACK (CCW) with 600ms debounce
                        current_time = time()
                        if current_time - self.last_select_back_time < 0.6:
                            return True
                        self.last_select_back_time = current_time
                        
                        if ccval < 64:
                            self.state_manager.send_cuia("BACK")
                        elif ccval > 64:
                            self.state_manager.send_cuia("ZYNSWITCH", [3, 'S'])
                        return True
                    return True
                elif self.knob_bank == 2:
                    # Bank 2: CC passthrough (85-92 → 24-31)
                    lib_zyncore.write_zynmidi([0xB0 | ev_chan, ccnum - 61, ccval])
                    return True
            
            # Transport buttons (CC 74-77): ZynSwitch with press duration detection
            # Special case: Shift + CC 76 = TEMPO
            elif ccnum in [74, 75, 76, 77]:
                if self.shift and ccnum == 76 and ccval > 0:
                    self.state_manager.send_cuia("TEMPO")
                    return True
                
                zynswitch_index = {74: 0, 75: 1, 76: 3, 77: 2}[ccnum]
                if ccval > 0:
                    self.press_times[ccnum] = time()
                elif ccnum in self.press_times:
                    duration = time() - self.press_times[ccnum]
                    press_type = 'S' if duration < 0.5 else 'B' if duration < 1.5 else 'L'
                    self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, press_type])
                    del self.press_times[ccnum]
                return True

            # Play button (CC 0x73): PLAY (normal) / MIDI_PLAY (shift)
            elif ccnum == 0x73 and ccval > 0:
                self.state_manager.send_cuia("TOGGLE_MIDI_PLAY" if self.shift else "TOGGLE_PLAY")
                return True
            
            # Record button (CC 0x75): RECORD (normal) / MIDI_RECORD (shift)
            elif ccnum == 0x75 and ccval > 0:
                self.state_manager.send_cuia("TOGGLE_MIDI_RECORD" if self.shift else "TOGGLE_RECORD")
                return True
            
            # Navigation buttons: Send CUIA commands on button press
            elif ccnum in button_commands and ccval > 0:
                self.state_manager.send_cuia(button_commands[ccnum])
                return True

        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1)
            return True

        # Let unhandled MIDI events pass through
        return False
# ------------------------------------------------------------------------------------------------------------------
