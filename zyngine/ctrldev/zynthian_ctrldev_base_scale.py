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
   
   ### Next the instance variables, set up by init() function, are different for each instance
   ### cols = 8
   ### rows = 8
   ### target_notes = []
   ### target_notes_reverse = {} # To get pads with same MIDI note to light them up when pressed
   ### col_versatz = -5
   ### active_mode = "Major"
   ### active_scale = 0 # means "C"
   
   def __init__(self, pad_cols, pad_rows):
      self.cols = pad_cols
      self.rows = pad_rows
      self.target_notes = [] # Instance variable
      self.target_notes_reverse = {}
      self.active_mode = None
      self.col_versatz = 0 # 0 means linear, no offset 

   
   # def init_scale(self, tonic: int, mode_name: str, note_start: int, col_versatz: int):
   #    """tonic : tonic of scale as midinote 0-11 (semitones)
   #       mode_name:   name of mode from self._modes
   #       note_start:  number of the tone in scale with octaves (12 would be second octave tonic)
   #       col_versatz: each row can start with a different offset, so -5 means in C-Major-Scale an "F" above the C in row-1 line
   #    """
   #    self.tonic = tonic
   #    self.col_versatz = col_versatz
   #    self.active_mode = mode_name
   #    self.pad1_midi_note = note_start  # midi_note for pad1
      
   #    self.target_notes = []         # Reset for new scale
   #    self.target_notes_reverse = {} # Reset for new scale
      
   #    for i in range(self.cols * self.rows):
   #       in_row = i // self.cols
   #       h = i + (in_row * col_versatz)
   #       if console_debug: print(f"{h} ", end="", flush=True)
   #       note_new = self._harmony_calculate_midi_note(h)
         
   #       self.target_notes.append(note_new) # always as "C scale"
   #       # Reverse mapping
   #       self.target_notes_reverse.setdefault(note_new, []).append(i) # always as "C-scale"
         
   #       if console_debug: 
   #          print(f"({note_new}),  ", end="\t", flush=True)
   #          if  (i+1) % 8 == 0: # self.cols == 0: 
   #             print("*", end="\n", flush=True) # Newline
   #    return



   def init_scale(self, 
                     tonic: int         = 0,       # (C) semitone distance counted from from C = 0
                     mode_name: str     = "Major", # mode as str from Array 
                     col_versatz: int   = -5,      # per row recess
                     middle_c: int      = 36,      # must be middle_c % 12 = 60
                     middle_pad_nr: int = 3):      # padnr of middle tonic 
      
      """tonic : tonic of scale as midinote 0-11 (semitones)
         mode_name:   name of mode from self._modes
         middle_C:  number of the tone in scale with octaves (12 would be second octave tonic)
         col_versatz: each row can start with a different offset, so -5 means in C-Major-Scale an "F" above the C in row-1 line
      """
      
      
      self.tonic       = tonic
      self.col_versatz = col_versatz
      self.middle_c    = middle_c
      self.active_mode = mode_name
      
      self.target_notes = []         # Reset for new scale
      self.target_notes_reverse = {} # Reset for new scale
          
      if middle_pad_nr < 0 : middle_pad_nr = 0
      if middle_pad_nr >= self.cols * self.rows:
         middle_pad_nr = self.cols * self.rows -1
  
      mode = self.modes[self.active_mode]    
      pad_counter = -1
      
      for i in range (-middle_pad_nr, (self.cols*self.rows) - middle_pad_nr):
         pad_counter += 1
         
         row_nr = pad_counter // self.cols
         
         note_nr_in_scale = i + (row_nr * col_versatz)
         
         
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



   # def _harmony_calculate_midi_note(self, note_in_scale) -> int:
   #    """Parameters:
   #       scale: string with name of scale
   #       note: integer representing the starting point in the scale. If start is bigger than 
   #             the length of the specified scale it adds start % len(scale) * 12 to the result.
   #             So you can cycle through the number of keyboard keys to get their MIDI notes
   #    """
   #    try:
   #       mode = self.modes[self.active_mode]
   #       pos_in_mode = note_in_scale % len(mode) #
   #       octave = note_in_scale // len(mode)
   #       return mode[pos_in_mode] + (octave * 12) # is based "C-Scale"
   #    except KeyError:
   #       logging.error(f"Error: Mode '{self.active_mode}' not found!")
   #       return -1 # -1 is error, there is no MIDI note -1
   #    except Exception as e:
   #       logging.error(f"Error calculating MIDI note: {e}")
   #       return -1

   def is_tonic_by_padnr(self, padnr:int)-> bool:
      return self.target_notes[padnr] % 12 == 0


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