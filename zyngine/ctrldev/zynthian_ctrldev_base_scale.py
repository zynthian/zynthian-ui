#!/zynthian/venv/bin/python

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


# how to use this Class minimalistic
#
"""
   scales = Harmony()  # set pad array
   scales.init_scale() # set scales, modes, etc
   
   pushed_pad_nr = 5
   target_note = scales.harmony_get_target_note(pushed_pad_nr)
   
   ### send this target_note as note_on_event. See REMARK
"""
### REMARK
### a self programmed driver doesn'send anymore  note_on events down the line.
# drivers are intended as control drivers for zynthian divices not any more for sound genarating
# I think there was a latency problem with keyboard drivers. 
# I use following hack on  PI 4 and it seams to work for me. 
# One (?) possible way is to send your new events with zynseq.libseq.sendMidiCommand 
"""
# EXAMPLE HERE:
### solution to send new events down the chain comes from niels in Zynthian forum
   def _forward_new_midi_event(self, ev):
        
        # get selected chain in mixer 
        chain = self.chain_manager.get_active_chain()            .
        
        # is it midi chain
        if chain.midi_chan is None: # is it a midi chain?
            return False
        
        # set up vars
        status = (ev[0] & 0xF0) | chain.midi_chan
        self.zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
        return True # work is done.  main event can start over and get a new midi event.
     """


### START OF LIBRARY

import logging

# Do not change. Only if this file is started directly from console
console_debug = False

# Following from: https://github.com/Carlborg/hardpush/blob/master/hardpush.ino
# All scales seem to work as 12-semitone scales. (otherwise they would need the octave-distance at the end)
_MODES = { # Define scales in the form 'semitones added to tonic'
  'Chromatic':          [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 
  "Major":              [0, 2, 4, 5, 7, 9, 11], 
  "Minor":              [0, 2, 3, 5, 7, 8, 10],
  "Dorian":             [0, 2, 3, 5, 7, 9, 10],
  "Mixolydian":         [0, 2, 4, 5, 7, 9, 10],
  "Lydian":             [0, 2, 4, 6, 7, 9, 11],
  "Phrygian":           [0, 1, 3, 5, 7, 8, 10],
  "Locrian":            [0, 1, 3, 4, 7, 8, 10],
  "Diminished":         [0, 1, 3, 4, 6, 7, 9, 10], 
  "Whole-Half":         [0, 2, 3, 5, 6, 8, 9, 11], 
  "Whole Tone":         [0, 2, 4, 6, 8, 10],
  "Minor Blues":        [0, 3, 5, 6, 7, 10],
  "Minor Pentatonic":   [0, 3, 5, 7, 10],
  "Major Pentatonic":   [0, 2, 4, 7, 9],
  "Harmonic Minor":     [0, 2, 3, 5, 7, 8, 11],
  "Melodic Minor":      [0, 2, 3, 5, 7, 9, 11],  # Fixed spelling: "Melodic" instead of "Melodig"
  "Super Locrian":      [0, 1, 3, 4, 6, 8, 10], 
  "Bhairav":            [0, 1, 4, 5, 7, 8, 11],
  "Hungarian Minor":    [0, 2, 3, 6, 7, 8, 11],
  "Minor Gypsy":        [0, 1, 4, 5, 7, 8, 10],   # Fixed spelling: "Gypsy" instead of "Gipsy"
  "Hirojoshi":          [0, 2, 3, 7, 8],
  "In-Sen":             [0, 1, 5, 7, 10],
  "Iwato":              [0, 1, 5, 6, 10],
  "Kumoi":              [0, 2, 3, 7, 9],
  "Pelog":              [0, 1, 3, 4, 7, 8],
  "Spanish":            [0, 1, 3, 4, 5, 6, 8, 10]
}

_SCALES = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B" ] # same as midi-notes 0-11

### How to get names and values from a dictionary:
## list(scales)        # ['Chromatic', 'Major', 'Minor', 'Dorian', 'Mixolydian', 'Lydian', 'Phrygian', 'Locrian', 'Diminished', 'Whole-Half', 'Whole Tone', 'Minor Blues', 'Minor Pentatonic', 'Major Pentatonic', 'Harmonic Minor', 'Melodic Minor', 'Super Locrian', 'Bhairav', 'Hungarian Minor', 'Minor Gypsy', 'Hirojoshi', 'In-Sen', 'Iwato', 'Kumoi', 'Pelog', 'Spanish']
## list(scales)[0]     # "Chromatic"
## scales['Chromatic'] # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


### Begin class definition Harmony ##############################################
class Harmony:

   # Class variables: Hardware of device and Scales don't change in instances 
   modes = _MODES
   scales = _SCALES
  
   def __init__(self, pad_cols=8, pad_rows=8):
      """pad_cols : number of cols of the pad array
         pad_rows : number of rows of the pad array 
         mostly 8 by 8
      """
      self.cols = pad_cols
      self.rows = pad_rows
      self.target_notes = [] # Instance variable
      self.target_notes_reverse = {}
      self.active_mode = None
      self.col_versatz = None # 0 means linear, no offset 
      self.middle_pad_nr = None
      self.middle_c = None
      self.must_redraw_led_colors = False
      self._lock = 0

   # helper functions
   def is_initialized(self):
      if self.target_notes == []: return False
      if self.target_notes_reverse == {}: return False
      if type(self.active_mode) == None: return False
      if type(self.col_versatz) == None: return False
      if type(self.middle_pad_nr) == None: return False
      if type(self.middle_c) == None: return False
      return True
   
   def must_reset_led_colors(self) -> bool:
      return self.must_redraw_led_colors
   
   # here setup for scale and mode with defaults. 
   # can be caled as scales = init_scale()   
   def init_scale(self, 
                     tonic: int         = 0,       # (C) semitone distance counted from from C = 0
                     mode_name: str     = "Major",  # mode as str. look in _SCALES 
                     col_versatz: int   = -5,       # per row recess
                     middle_c: int      = 48,       # must be middle_c % 12 = 60  
                     middle_pad_nr: int = 5):       # padnr of middle tonic. pad where middle_c is placed
      
      """Defaults set:  C Major with next row is sub_dominant to row before. Middle_C is on 5th pad  
      
         tonic :        tonic of scale as 0 <= semitones <= 11 (semitones)
         mode_name:     name of mode from self._modes
         col_versatz:   shift next row by col_versatz steps. e.g. -5 makes sub_dominant above tonic
         middle_c:      must be real midi notd c (c % 12 == 0). this will later be shifted by the 
                        tonic value 60 as middle c has to be % 12 == 0
         middle_pad_nr: which pad should be middle of your pad array 
      """
      # for new tonic initialization is not necessary. Tonics just changes return values of notes
      if not tonic is None:
         if tonic > 11: tonic = 0; 
         if tonic < 0: tonic = len(self.scales)-1
         self.tonic       = tonic      
      # Fallback for tonic
      if self.tonic is None:
         self.tonic = 0 # Set to C
         logging.error("tonic not set. Fallback is 0 ='C'")
      
      
      # any value afterwards will reinitialiue the class   
      is_dirty = False # reinitialize?
      if not col_versatz is None:
         if not self.col_versatz == col_versatz:
            is_dirty = True
            self.must_redraw_led_colors = True
            self.col_versatz = col_versatz
      # col_versatz not intialiued
      if self.col_versatz is None:
         is_dirty = True
         self.must_redraw_led_colors = True
         self.col_versatz = -5 # upwards 1 fourth lower the scale -> in C-Major an F above the C and so on
         logging.error("row recess not set. Fallback vlaue is -5")
      
      
      if not middle_c is None:
         if not self.middle_c  == middle_c:
            is_dirty = True
            self.must_reset_led_colors = True
            middle_c = middle_c // 12 * 12 # makes middle_c % 12 == 0
            self.middle_c    = middle_c
      if self.middle_c is None:
         self.middle_c = 48 # must be middle_c % 12 = 0
         is_dirty = True
         logging.error("middle_C not set. Will be set to Midi_note=48")
      
      if not mode_name is None:
         if not mode_name in self.modes:
            logging.error(f"modename: {mode_name}")
         else:
            if not self.active_mode == mode_name:  
               # if len of new mode is different to before, LED Colors must be rewritten   
               self.must_redraw_led_colors = True 
               self.active_mode = mode_name
               is_dirty = True
      if self.active_mode is None:
         self.active_mode = "Major"
         self.must_redraw_led_colors = True
         is_dirty = True
         logging.error("mode not set. Falback is: Major")           
      
      if not middle_pad_nr is None:
         if middle_pad_nr < 0 : middle_pad_nr = 0 # center of scale is pad1
         if middle_pad_nr >= self.cols * self.rows:
            middle_pad_nr = self.cols * self.rows -1 # center of scale is last pad  
         if not self.middle_pad_nr == middle_pad_nr:   
            self.middle_pad_nr = middle_pad_nr
            self.must_redraw_led_colors = True
            is_dirty = True
      if self.middle_pad_nr is None:
         self.middle_pad_nr = 4
         self.must_redraw_led_colors = True
         is_dirty == True    
      
      # if not is_dirty: return # if just tonica changed go back
      
      self.target_notes = []         # Reset for new scale
      self.target_notes_reverse = {} # Reset for new scale
      mode = self.modes[self.active_mode]   
      
      pad_counter = -1
      
      for i in range (- self.middle_pad_nr, (self.cols*self.rows) - self.middle_pad_nr):
         pad_counter += 1       
         
         row_nr = pad_counter // self.cols
         note_nr_in_scale = i + (row_nr * self.col_versatz)
         
         octave = note_nr_in_scale // len(mode) 
         if console_debug: print (f"{octave}:{pad_counter}=", end="")
         
         note_in_mode = note_nr_in_scale % len(mode)  
         note = mode[note_in_mode]
         note += octave * 12
         note += self.middle_c
         
         # store notes without tonic for internal represetation
         self.target_notes.append(note) # always as "C scale"
         # Reverse mapping
         self.target_notes_reverse.setdefault(note, []).append(pad_counter)
         
         if console_debug: 
            actual_note = note + tonic
            print(f"({actual_note}),  ", end="\t", flush=True)
            if  (pad_counter+1) % self.cols == 0: 
               print("*", end="\n", flush=True) # Newline at end of row
      return

   # direct set from program
   def set_new_tonic(self, new_tonic:int):
      """new_tonic is next tonic in selected scale"""
      if new_tonic == self.tonic: return False
      if new_tonic < 0:  new_tonic = 11  # target: B
      if new_tonic > 11: new_tonic = 0   # target: C
      self.tonic = new_tonic
      return True # yes update display. we changed it

   # for Knob Control. step to next
   def step_to_next_tonic(self, step):
      """For Knob Control. 127 converted -1"""
      if step > 63: step -=128 # for controller sending 127 for -1
      new_tonic = self.scales.tonic + step
      if new_tonic < 0:  new_tonic = 11  # target: B
      if new_tonic > 11: new_tonic = 0   # target: C
      self.scales.tonic = new_tonic

   # pad nr must be colorized as tonic
   def is_tonic_by_padnr(self, pad_nr:int)-> bool:
      res = self.target_notes[pad_nr]
      res2 = res % 12
      return res2 == 0
      #return self.target_notes[padnr] % 12 == 0

   # midi note, which hast to be colorized as tonic
   def is_tonic_by_midnote(self, midi_note:int) -> bool:
      return (midi_note - self.tonic) % 12 == 0
   
   # get back list of pads, that have same midi_note   
   def get_equi_sound_pads_with_midi_note(self, midi_note) -> list:
      # Subtract tonic to get internal representation
      internal_note = midi_note - self.tonic
      return self.target_notes_reverse.get(internal_note, [])     
   
   # get back list of pads, that have same midi_note by pad_nr
   def get_equi_sound_pads_with_pad_nr(self, pad_nr):
      midi_note = self.target_notes[pad_nr]
      return self.target_notes_reverse.get(midi_note,[])      

   # scale contains how much notes
   def harmony_get_mode_len(self, mode:str) -> int:
      """Return count of tones mode"""
      try:
         return len(self.modes[mode])
      except KeyError:
         logging.error(f"Error: get_mode_len: mode '{mode}' not defined")
         return 0

   # get back a list if strings containing mode names
   def harmony_get_mode_names(self):
      return list(self.modes)
   
   # get scale and mode as string
   def harmony_get_scale_name_with_mode (self) -> str:
      """actual scale and mode as string for display"""
      result = self.scales[self.tonic] + ' ' + self.active_mode
      result = result.ljust(20)[:20]
      return result
   
   # THIS IS THE MAIN FUNCTION THAT DOES THE MAGIC
   # transaltes pad_nr to midi_notes in the selected mode and scale !!!
   def harmony_get_target_note(self, pad_nr: int) -> int:
      if not 0 <= pad_nr < len(self.target_notes): 
         logging.error("Program error, pad_nr out of range for len(target_notes)")
         return None
      return self.target_notes[pad_nr] + self.tonic
   
   # def harmony_get_padnrs_with_same_note(self, midi_note: int):
   #    internal_note = midi_note - self.tonic
   #    return self.target_notes_reverse.get(internal_note, [])
   
   
### End of class definition Harmony ##############################################



### For test purposes from command line
if __name__ == "__main__":
   console_debug = True
   print()
   h = Harmony(8, 8)
   # h.init_scale(0, "Diminished", 0, -5)
   h.init_scale_2()
   print()
#   print(h.harmony_get_scale_names())
#   print(h.harmony_get_midi_note("Kumoi", 4))
#   print(h.harmony_get_scale_len("Kumoi"))