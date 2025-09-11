#!/zynthian/venv/bin/python
import logging

# Do not change. Only if this file is started directly from console
console_debug = False

# Following from: https://github.com/Carlborg/hardpush/blob/master/hardpush.ino
# All scales seem to work as 12-semitone scales. (otherwise they would need the octave-distance at the end)
_SCALES = { # Define scales in the form 'semitones added to tonic'
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

### How to get names and values from a dictionary:
## list(scales)        # ['Chromatic', 'Major', 'Minor', 'Dorian', 'Mixolydian', 'Lydian', 'Phrygian', 'Locrian', 'Diminished', 'Whole-Half', 'Whole Tone', 'Minor Blues', 'Minor Pentatonic', 'Major Pentatonic', 'Harmonic Minor', 'Melodic Minor', 'Super Locrian', 'Bhairav', 'Hungarian Minor', 'Minor Gypsy', 'Hirojoshi', 'In-Sen', 'Iwato', 'Kumoi', 'Pelog', 'Spanish']
## list(scales)[0]     # "Chromatic"
## scales['Chromatic'] # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


### Begin class definition Harmony ##############################################
class Harmony:

   # Class variables: Hardware of device and Scales don't change in instances 
   scales = _SCALES
   
   ### Next the instance variables, set up by init() function, are different for each instance
   ### cols = 8
   ### rows = 8
   ### target_notes = []
   ### target_notes_reverse = {} # To get pads with same MIDI note to light them up when pressed
   ### col_versatz = -5
   ### active_scale = "Major"
   
   def __init__(self, pad_cols, pad_rows):
      self.cols = pad_cols
      self.rows = pad_rows
      self.target_notes = [] # Instance variable
      self.target_notes_reverse = {}
      self.active_scale = None
      self.col_versatz = 0 # 0 means linear, no offset 

   def init_scale(self, scale_name, note_start, col_versatz):
      """scale_name:   name of scale in self._scales
         note_start:  number of the tone in scale with octaves (12 would be second octave tonic)
         col_versatz: each row can start with a different offset, so -5 means in C-Major-Scale an "F" above the C in row-1 line
      """
      self.col_versatz = col_versatz
      self.active_scale = scale_name
      self.target_notes = []         # Reset for new scale
      self.target_notes_reverse = {} # Reset for new scale
      
      for i in range(self.cols * self.rows):
         in_row = i // self.cols
         h = i + note_start + (in_row * col_versatz)
         if console_debug: print(f"{h} ", end="")
         note_new = self._harmony_calculate_midi_note(h)
         
         self.target_notes.append(note_new)         
         # Reverse mapping
         self.target_notes_reverse.setdefault(note_new, []).append(i)
         
         if console_debug: 
            print(f"({note_new}),  ", end="\t")
            if i % self.cols == 0: print() # Newline


   def _harmony_calculate_midi_note(self, note) -> int:
      """Parameters:
         scale: string with name of scale
         note: integer representing the starting point in the scale. If start is bigger than 
               the length of the specified scale it adds start % len(scale) * 12 to the result.
               So you can cycle through the number of keyboard keys to get their MIDI notes
      """
      try:
         scale = self.scales[self.active_scale]
         pos_in_scale = note % len(scale) #
         octave = note // len(scale)
         return scale[pos_in_scale] + (octave * 12)
      except KeyError:
         logging.error(f"Error: Scale '{self.active_scale}' not found!")
         return -1 # -1 is error, there is no MIDI note -1
      except Exception as e:
         logging.error(f"Error calculating MIDI note: {e}")
         return -1
         

   def harmony_get_scale_len(self, scale) -> int:
      """Return count of tones in scale"""
      try:
         logging.debug(f"[Debug len]: scale={scale}, len={len(self.scales[scale])}")
         return len(self.scales[scale])
      except KeyError:
         logging.error(f"Error: get_scale_len: scale '{scale}' not defined")
         return 0

   def harmony_get_scale_names(self):
      return list(self.scales)
   
   def harmony_get_target_note(self, pad_nr: int) -> int:
      if not 0 <= pad_nr < len(self.target_notes): 
         logging.error("Program error, pad_nr out of range for len(target_notes)")
         return None
      return self.target_notes[pad_nr]
   
   def harmony_get_padnrs_with_same_note(self, midi_note: int):
      return self.target_notes_reverse.get(midi_note, [midi_note]) # If nothing is in map, midi_note itself is given back

### End of class definition Harmony ##############################################



### For test purposes from command line
if __name__ == "__main__":
   console_debug = False

   h = Harmony(8, 8)
   h.init_scale("Major", 0, -5)

#   print(h.harmony_get_scale_names())
#   print(h.harmony_get_midi_note("Kumoi", 4))
#   print(h.harmony_get_scale_len("Kumoi"))