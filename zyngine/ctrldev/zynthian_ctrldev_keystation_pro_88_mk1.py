#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Minimalistic Zynthian Control Device Driver for M-Audio Keystation Pro 88
# used for Zynthina with touch screen (but without rotary encoders)
# The device driver can controll the gui with the 4 knobs
# 
# The keystation pro 88 no LED, so there is no feedback possible on the device 
# also it doesn't send key on and of messages, just program change on press,
# so its not possible to detect long and short presses.
#
# Rotary Encoders are simulatet with Knobs 18, 19, 10, 11
# 
# this sample driver shows how easy it is to write a custom driver
# for a specific MIDI controller
#
# everything that is not essential is commented out
#

# Strange, when this driver throws an exception, the midi event is processed, as if the midi_event() sends back "False"
# I realized this, when I had a mistake in my send_midi function (library zynseq was not importet)
# need further exploration

import logging
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base
from zynlibs.zynseq import zynseq #  to send midi directly from this driver

logger = logging.getLogger('zynthian')

class zynthian_ctrldev_keystation_pro_88_mk1(zynthian_ctrldev_base):

   # Device identification
   # dev_id = ["Keystation Pro 88"] # not essential
      
   # found no way to list the dev_ids on linux console. 
   # They are different in Zynthian to that what I found in linux console # 
   # with debugging it is easy to find the correct dev_ids. Found no other way. You could try 
   # device name with " IN 1" and "IN 2" at the end
   # dev_ids = ["Keystation Pro 88 IN 1", "Keystation Pro 88 IN 2"] #  these values are ESSENTIAL for the driver to connect it to the device
   dev_ids = ["Keystation Pro 88 IN 1"] #  these values are ESSENTIAL for the driver to connect it to the device. Data is just at Port 1

   # driver_name = "Keystation Pro 88 Minimal" # not essential, just for information in logs
   
   # driver_description = "Minimalistic Zynthian Control Device Driver für M-Audio Keystation Pro 88" 
   # not essential. just for information in logs

   # driver_version = "0.1" 
   
   # Helper variables for potentiometers. Hack, because ZYNPOT_ABS didn't work for me...   
   zynpot_0 = 0
   zynpot_1 = 0
   zynpot_2 = 0
   zynpot_3 = 0    
   
   # evtype = (ev[0] >> 4) & 0x0F ->
   EV_NOTE_OFF    = 0x8 # 3 Bytes
   EV_NOTE_ON     = 0X9 # 3 Bytes
   EV_AFTERTOUSCH = 0xA # 3 Bytes (polyphonic = per note)
   EV_CC          = 0xB # 3 Bytes
   EV_PC          = 0xC # 2 Bytes
   EV_CHAN_PRESS  = 0xD #  2 Bytes
   EV_PITCHBEND   = 0xE # 3 bytes ev[1] = LSB 0-127; ev[2] = MSB 0-127
   EV_SYSTEM      = 0xF #  Systemtype = ev[0] & 0x0F
    
   
   def midi_event(self, ev):
         """Easy MIDI event handler for Keystation Pro 88"""
         # self.unroute_from_chains = False # otherwise no Keyboard anymore, just a controller
         # self.enabled = True
         evtype = (ev[0] >> 4) & 0x0F
         
         if len(ev) == 3: logger.debug(f"MIDI Event empfangen: {ev} {ev[0]} {ev[1]} {ev[2]}")
         
         if len(ev) > 0:
            status= ev[0] & 0xF0 # Which midi message type (note on, note off, control change, etc.  )
            # channel = ev[0] & 0x0F #  not usesd,
         
         if evtype in [self.EV_NOTE_ON, self.EV_NOTE_OFF, self.EV_AFTERTOUSCH, self.EV_PITCHBEND]:
            return self.send_midi(ev)
            
         
         if len(ev) == 3: # most times 3 bytes and we need 3 bytes
               # status = ev[0] & 0xF0 # Which midi message type (note on, note off, control change, etc.  )
               # channel = ev[0] & 0x0F #  not usesd, just for information
               data1 = ev[1] # Note number or controller number
               data2 = ev[2] # Note velocity or controller value
                
               
               # We simulate a rotary encoder with the knobs
               # We send the difference between the last value and the new value
               # to the state manager ("ZYNPOT_ABS" would be easieer to use, but it doesn't work for me. It was never called in my tests)
               # The state manager will handle the rest
               # We have to store the last value of the knob
               # We have 4 knobs for 4 virtual rotary encoders
               # Knob 18 -> ZYNPOT 0
               # Knob 19 -> ZYNPOT 1
               # Knob 10 -> ZYNPOT 2
               # Knob 11 -> ZYNPOT 3
               
               # yes I know, first time use of a knob lets jump the value from 0 to the knob value
               # but I don't know how to get the current value of the knob at start up
               # maybe someone can help me with that
               
               # 0xB0 is Control Change on MIDI Channel 1
               # 10 is the controller number for the first knob
               # data2 is the value of the knob (0-127)


               if status == 0xb0 and data1 == 104:  # 42 is knob 18 in "keystations Preset 10. (Press Recall and choose 10)"
                  # if controller sends relative values, that is: negative values for left turn and positive values for right turn,
                  # you can use:
                  # pot = data2
                  # but my keystation pro 88 MK1 sends only absolute knob values from 0 to 127
                  # so I have to calculate the difference to the last value
                  pot = data2-self.zynpot_0 # calculates relative change of the value to use "ZYNPOT" instead of "ZYNPOT_ABS" 
                  self.zynpot_0 = data2 # store the new value for the next change
                  
                  self.state_manager.send_cuia("ZYNPOT", [0, pot]) 
                  return True # Event processed. restarts event loop
               
               if status == 0xb0 and data1 == 105:   # 34 is knob 19 in "Preset-Recall 10"
                  pot = data2-self.zynpot_1
                  self.zynpot_1 = data2
                  self.state_manager.send_cuia("ZYNPOT", [1, pot])
                  return True # Event processed. restarts event loop
               
               if ev[0] == 0xb0 and data1 == 85:   # 10 is knob 10 in "Preset-Recall 10"
                  pot = data2-self.zynpot_2
                  self.zynpot_2 = data2
                  self.state_manager.send_cuia("ZYNPOT", [2, pot])
                  return True # Event processed. restarts event loop
               
               if ev[0] == 0xb0 and data1 == 86:    # 2 is knob 11 in "Preset-Recall 10"
                  pot = data2-self.zynpot_3
                  self.zynpot_3 = data2
                  self.state_manager.send_cuia("ZYNPOT", [3, pot])
                  return True # Event processed. restarts event loop
                      
         """ if len(ev) == 3: # PC has 3 bytes.

               # To use Buttons on Keystation 88 pro MK1 for "back" and "OK" is no good idea, because
               # all Buttons are sending just a program change when pressed.
               # You would miss them as Buttons for changing in Zynthina. But nevertheless here as example how to use it
               
               # status = ev[0] & 0xF0 # Which midi message type (note on, note off, control change, etc.  )
               # channel = ev[0] & 0x0F #  not usesd, just for information
               data1 = ev[1] # Note number or controller number    
               
               
               # Buttons for "Ok" and "Back"
               if status == 0xC0 and data1 == 0:  # Button "Back"
                  self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [1,"S"])
                  # self.state_manager.send_cuia("BACK")
                  return True # Event processed. restarts event loop
               
               if status == 0xC0 and data1 == 1:  # Button "OK"
                  self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [3,"S"])
                  # self.state_manager.send_cuia("SELECT")
                  return True # Event processed. restarts event loop """
         
               
         return False #  event not processed by this driver. Zynthian queue has to process it further down the row
      
   def send_midi (self, ev):
      chain = self.chain_manager.get_active_chain()
            # print(chain.midi_chan)
            # @todo: find out how to get 'last' active chain, for now: just back out.
        
      if chain.midi_chan is None:
            return False
        
      status = (ev[0] & 0xF0) | chain.midi_chan
      self.zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
      return True


