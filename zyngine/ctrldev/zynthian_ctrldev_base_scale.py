#!/zynthian/venv/bin/python

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
  
   def __init__(self, pad_cols, pad_rows):
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
      
   def init_scale(self, 
                     tonic: int         = None,       # (C) semitone distance counted from from C = 0
                     mode_name: str     = None,       # mode as str. look in _SCALES 
                     col_versatz: int   = None,       # per row recess
                     middle_c: int      = None,       # must be middle_c % 12 = 60  
                     middle_pad_nr: int = None):      # padnr of middle tonic. pad where middle_c is placed
      
      """tonic : tonic of scale as midinote 0-11 (semitones)
         mode_name:   name of mode from self._modes
         middle_C:  number of the tone in scale with octaves (12 would be second octave tonic)
         col_versatz: each row can start with a different offset, so -5 means in C-Major-Scale an "F" above the C in row-1 line
      """
      # for new tonic initialization is not necessary. Tonics just change returnvlaiues of notes
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
         
      # if middle_pad_nr < 0 : middle_pad_nr = 0
      # if middle_pad_nr >= self.cols * self.rows:
      #    middle_pad_nr = self.cols * self.rows -1

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

   def set_new_tonic(self, new_tonic:int):
      if new_tonic == self.tonic: return False
      if new_tonic < 0:  new_tonic = 11  # target: B
      if new_tonic > 11: new_tonic = 0   # target: C
      self.tonic = new_tonic
      return True # yes update display. we changed it

   def step_to_next_tonic(self, step):
      if step > 63: step -=128 # for controller sending 127 for -1
      new_tonic = self.scales.tonic + step
      if new_tonic < 0:  new_tonic = 11  # target: B
      if new_tonic > 11: new_tonic = 0   # target: C
      self.scales.tonic = new_tonic

   def is_tonic_by_padnr(self, pad_nr:int)-> bool:
      res = self.target_notes[pad_nr]
      res2 = res % 12
      return res2 == 0
      #return self.target_notes[padnr] % 12 == 0


   def is_tonic_by_midnote(self, midi_note:int) -> bool:
      return (midi_note - self.tonic) % 12
      
   def get_equi_sound_pads_with_midi_note(self, midi_note) -> list:
      # Subtract tonic to get internal representation
      internal_note = midi_note - self.tonic
      return self.target_notes_reverse.get(internal_note, [])     
   
   def get_equi_sound_pads_with_pad_nr(self, pad_nr):
      midi_note = self.target_notes[pad_nr]
      return self.target_notes_reverse.get(midi_note,[])      

   def harmony_get_mode_len(self, mode:str) -> int:
      """Return count of tones mode"""
      try:
         return len(self.modes[mode])
      except KeyError:
         logging.error(f"Error: get_mode_len: mode '{mode}' not defined")
         return 0

   def harmony_get_mode_names(self):
      return list(self.modes)
   
   def harmony_get_scale_name_with_mode (self) -> str:
      result = self.scales[self.tonic] + ' ' + self.active_mode
      result = result.ljust(20)[:20]
      return result
   
   def harmony_get_target_note(self, pad_nr: int) -> int:
      if not 0 <= pad_nr < len(self.target_notes): 
         logging.error("Program error, pad_nr out of range for len(target_notes)")
         return None
      return self.target_notes[pad_nr] + self.tonic
   
   def harmony_get_padnrs_with_same_note(self, midi_note: int):
      internal_note = midi_note - self.tonic
      return self.target_notes_reverse.get(internal_note, [])
   
   
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