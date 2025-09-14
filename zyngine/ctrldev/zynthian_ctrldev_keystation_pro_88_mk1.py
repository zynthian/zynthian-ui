#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Minimalistic Zynthian Control Device Driver for M-Audio Keystation Pro 88
# Designed for Zynthian with touch screen (but without rotary encoders)
# The device driver can control the GUI using the 4 knobs
# The Keystation Pro 88 has no LEDs, so no visual feedback is possible on the device
# It also doesn't send key on/off messages, only program change messages on press,
# making it impossible to detect long and short presses.
# Rotary encoders are simulated with knobs 18, 19, 10, and 11
# This sample driver demonstrates how easy it is to write a custom driver
# for a specific MIDI controller

# Note: When this driver throws an exception, the MIDI event is still processed
# as if midi_event() returned "False". This was noticed when there was an error
# in the send_midi function (zynseq library was not imported).
# This requires further investigation

import logging
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base
from zynlibs.zynseq import zynseq  # For sending MIDI directly from this driver

logger = logging.getLogger('zynthian')

class zynthian_ctrldev_keystation_pro_88_mk1(zynthian_ctrldev_base):
    # Device identification
    # dev_id = ["Keystation Pro 88"]  # Optional
    
    # There's no straightforward way to list device IDs on the Linux console
    # The device IDs in Zynthian differ from those found in the Linux console
    # Debugging is the easiest way to find the correct device IDs
    # You can try using the device name with " IN 1" and " IN 2" suffixes
    
    dev_ids = ["Keystation Pro 88 IN 1"]  # These values are essential

    # driver_name = "Keystation Pro 88 Minimal"  # Optional, for log information
    # driver_description = "Minimalistic Zynthian Control Device Driver for M-Audio Keystation Pro 88" 
    # driver_version = "0.1" 
    
    # Helper variables for potentiometers. Workaround because ZYNPOT_ABS didn't work
    zynpot_0 = 0
    zynpot_1 = 0
    zynpot_2 = 0
    zynpot_3 = 0    
    
    # MIDI event types
    EV_NOTE_OFF = 0x8  # 3 bytes
    EV_NOTE_ON = 0x9  # 3 bytes
    EV_AFTERTOUCH = 0xA  # 3 bytes (polyphonic = per note)
    EV_CC = 0xB  # 3 bytes
    EV_PC = 0xC  # 2 bytes
    EV_CHAN_PRESS = 0xD  # 2 bytes
    EV_PITCHBEND = 0xE  # 3 bytes: ev[1] = LSB 0-127; ev[2] = MSB 0-127
    EV_SYSTEM = 0xF  # System type = ev[0] & 0x0F
    
    def midi_event(self, ev):
        """MIDI event handler for Keystation Pro 88"""
        evtype = (ev[0] >> 4) & 0x0F
        
        if len(ev) == 3:
            logger.debug(f"MIDI event received: {ev} {ev[0]} {ev[1]} {ev[2]}")
        
        if len(ev) > 0:
            status = ev[0] & 0xF0  # MIDI message type (note on, note off, control change, etc.)
            # channel = ev[0] & 0x0F  # Not used
        
        # Forward certain events directly to MIDI output
        if evtype in [self.EV_NOTE_ON, self.EV_NOTE_OFF, self.EV_AFTERTOUCH, self.EV_PITCHBEND]:
            return self.send_midi(ev)
        
        # Process 3-byte events (control changes)
        if len(ev) == 3:
            data1 = ev[1]  # Note number or controller number
            data2 = ev[2]  # Note velocity or controller value
            
            # Simulate rotary encoders with knobs
            # We send the difference between the last value and the new value
            # to the state manager ("ZYNPOT_ABS" would be easier but didn't work)
            # The state manager will handle the rest
            # We have to store the last value of each knob
            # We have 4 knobs for 4 virtual rotary encoders:
            # Knob 18 -> ZYNPOT 0
            # Knob 19 -> ZYNPOT 1
            # Knob 10 -> ZYNPOT 2
            # Knob 11 -> ZYNPOT 3
            
            # Note: First use of a knob will jump from 0 to the current knob value
            # There's currently no way to get the initial value of the knob at startup
            
            # 0xB0 is Control Change on MIDI Channel 1
            if status == 0xB0:
                if data1 == 104:  # Knob 18 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_0  # Calculate relative change
                    self.zynpot_0 = data2  # Store new value for next change
                    self.state_manager.send_cuia("ZYNPOT", [0, pot])
                    return True  # Event processed
                
                elif data1 == 105:  # Knob 19 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_1
                    self.zynpot_1 = data2
                    self.state_manager.send_cuia("ZYNPOT", [1, pot])
                    return True
                
                elif data1 == 85:  # Knob 10 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_2
                    self.zynpot_2 = data2
                    self.state_manager.send_cuia("ZYNPOT", [2, pot])
                    return True
                
                elif data1 == 86:  # Knob 11 in "Preset-Recall 10"
                    pot = data2 - self.zynpot_3
                    self.zynpot_3 = data2
                    self.state_manager.send_cuia("ZYNPOT", [3, pot])
                    return True
        
        # Process program change events (buttons)
        # Note: Using buttons on Keystation 88 Pro MK1 for "back" and "OK" is not ideal
        # because all buttons send only a program change when pressed, with no way to
        # detect long vs short presses
        if len(ev) >= 2:
            if ev[0] & 0xF0 == 0xC0:  # Program Change event
                data1 = ev[1]  # Program number
                
                # Map program changes to UI actions
                if data1 == 0:  # Button "Back"
                    self.state_manager.send_control("BACK")
                    return True
                
                elif data1 == 1:  # Button "OK"
                    self.state_manager.send_control("SELECT")
                    return True
        
        return False  # Event not processed by this driver
    
    def send_midi(self, ev):
        """Send MIDI event to active chain"""
        chain = self.chain_manager.get_active_chain()
        
        if chain is None or chain.midi_chan is None:
            return False
        
        status = (ev[0] & 0xF0) | chain.midi_chan
        zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
        return True
