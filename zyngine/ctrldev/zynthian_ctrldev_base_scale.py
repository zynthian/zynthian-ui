#!/zynthian/venv/bin/python


# Zynthian specific modules
# from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad # , zynthian_ctrldev_zynmixer
# from zyncoder.zyncore import lib_zyncore
# from zynlibs.zynseq import zynseq

# import zynthian_ctrldev_base

# Following from: https://github.com/Carlborg/hardpush/blob/master/hardpush.ino
# All scales seem to work with 12-halftones. (otherwise they would need the octave-distance at the end)4
SCALES = { # define scales on the form 'semitones added to tonic'
  'Chromatic':          [0,1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 
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
  "Melodig Minor":      [0, 2, 3, 5, 7, 9, 11],
  "Super Locrian":      [0, 1, 3, 4, 6, 8, 10], 
  "Bhairav":            [0, 1, 4, 5, 7, 8, 11],
  "Hungarian Minor":    [0, 2, 3, 6, 7, 8, 11],
  "Minor Gipsy":        [0, 1, 4, 5, 7, 8, 10], 
  "Hirojoshi":          [0, 2, 3, 7, 8],
  "In-Sen":             [0, 1, 5, 7, 10],
  "Iwato":              [0, 1, 5, 6, 10],
  "Kumoi":              [0, 2, 3, 7, 9],
  "Pelog":              [0, 1, 3, 4, 7, 8],
  "Spanish":            [0, 1, 3, 4, 5, 6, 8, 10]
}


### How to get the values
## print(list(scales)) # ['Chromatic', 'Major', 'Minor', 'Dorian', 'Mixolydian', 'Lydian', 'Phrygian', 'Locrian', 'Diminished', 'Whole-Half', 'Whole Tone', 'Minor Blues', 'Minor Pentatonic', 'Major Pentatonic', 'Harmonic Minor', 'Melodig Minor', 'Super Locrian', 'Bhairav', 'Hungarian Minor', 'Minor Gipsy', 'Hirojoshi', 'In-Sen', 'Iwato', 'Kumoi', 'Pelog', 'Spanish']
## print(list(scales)[0]) # "Chromatic"
## print(scales['Chromatic']) # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


class Harmony:
   
   scales = SCALES

   def __init__ (self):
      pass




   def get_midi_note(self, scale,start) -> int:
      """params
 
         scale: is string with name of scale

         start: is integer representing the starting point in the scale. if start is bigger than 
             the length of the specified scale it adds start % leng(scale) * 12 to the result. n
            So you ca    cycle through the number of keyboard keys to get their midi notes
      """
      try:
         print(scales[scale])
         l = scales[scale]
         pos = start%len(l)
         octave = start // len(l)
         print(f"[Debug note]: scale={scale}, start={start} pos={pos}, erg={l[pos]} von {l}")
         return l[pos] + (octave * 12 )
      except:
         print("Error: get_midi_note: Tonart nicht definiert!")


   def get_scale_len(self, scale) -> int:
      try:
         print(f"[Debug len]: scale={scale}, len={len(scales[scale])}")
         return len(scales[scale])
      except: print("Error: get_scale_len: Tonart nicht definiert!")

   def get_scale_names(self):
      return  list(scales)



h = Harmony()

print(h.get_scale_names())
print(h.get_midi_note("Kumoi", 4))
print(h.get_scale_len("Kumoi"))


"""
class zynthian_ctrldev_scale(zynthian_ctrldev_base):
   


   def __init(self):
      pass
"""