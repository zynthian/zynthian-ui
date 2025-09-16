# Ableteton Push 1

### Definition of all buttons, pads and knobs
#knobs and Buttons are CC-Events
#knobs also have touch function with midi note event
#
#ribbon is type modwheel !!! Just one byte ev[0]
#ribbon has also touch function with midi note even
#
# pad has note event


#####
# Buttons are defined with ther action Message. Noteon, Control Change


### SYSEX
#SYSEX_PREAMBLE = []
#SYSEX_END      = []

# Display
# Write text to display	240,71,127,21,<24+line(0-3)>,0,<Nchars+1>,<Offset>,<Chars>,247
# Clear display line	240,71,127,21,<28+line(0-3)>,0,0,247
#SYSEX_INST_WRITE_LINE_0 = bytes([24])
#SYSEX_INST_WRITE_LINE_1 = bytes([25])
#SYSEX_INST_WRITE_LINE_2 = bytes([26])
#SYSEX_INST_WRITE_LINE_3 = bytes([27])
 

# Knobs 1-9
KNOB_1 = [0xB0, 71] # CC71
KNOB_2 = [0xB0, 72] # CC72
KNOB_3 = [0xB0, 73]
KNOB_4 = [0xB0, 74]
KNOB_5 = [0xB0, 75] # CC75
KNOB_6 = [0xB0, 76] # CC76
KNOB_7 = [0xB0, 77] # CC77
KNOB_8 = [0xB0, 78] # CC78
KNOB_9 = [0xB0, 79] # CC79
KNOB_10 = [0xB0, 14] # CC79
KNOB_11 = [0xB0, 15] # CC79


# Touch
KNOB_1_T = [0x90,0] # "C-1" sic! 
KNOB_2_T = [0x90,1] # "C#-1"
KNOB_3_T = [0x90,2] # "D-1"
KNOB_4_T = [0x90,3] # "D#-1"
KNOB_5_T = [0x90,4] # Note 4
KNOB_6_T = [0x90,5] # Note 5
KNOB_7_T = [0x90,6] # note 6
KNOB_8_T = [0x90,7] # note 7
KNOB_9_T = [0x90,8] # Note 8
KNOB_10_T = [0x90,9]
KNOB_11_T = [0x90,10]

RIBBON_TOUCH_T  = [0x90,12] # "C0" note 12
RIBBON_PITCH    = [0xE0]    # Mod-wheel ?? ### Achtung einziger Identifier, der nur 1 byte hat!!! ###

# Monochromatic Buttons
# Alle Button sind CC / Alle PAD sind Noteon
BTN_TAP_TEMPO    = [0xB0, 3] 
BTN_METRONOME    = [0xB0, 9]


BTN_FIXED_LENGTH = [0xB0, 90]
BTN_AUTOMATION   = [0xB0, 89]
BTN_DUPLICATE    = [0xB0, 88]

BTN_NEW          = [0xB0, 87]
BTN_REC          = [0xB0, 86]
BTN_START        = [0xB0, 85]

#########  RECHTS ############
BTN_PAN          = [0xB0, 115] # CC115
BTN_VOLUME       = [0xB0, 114] # CC114

BTN_CLIP         = [0xB0, 113]
BTN_TRACK        = [0xB0, 112]

BTN_BROWSE       = [0xB0, 111]
BTN_DEVICE       = [0xB0, 110]


BTN_ESC          = [0xB0, 63]
BTN_OK           = [0xB0, 62]
BTN_SOLO         = [0xB0, 61]
BTN_MUTE         = [0xB0, 60]
BTN_USER         = [0xB0, 59]
BTN_SCALES       = [0xB0, 58]
BTN_ACCENT       = [0xB0, 57]
BTN_REPEAT       = [0xB0, 56]
BTN_OCTAVE_UP    = [0xB0, 55]
BTN_OCTAVE_DOWN  = [0xB0, 54]

BTN_ADD_TRACK    = [0xB0, 53]
BTN_ADD_EFFECT   = [0xB0, 52]
BTN_SESSION      = [0xB0, 51]
BTN_NOTE         = [0xB0, 50]
BTN_SHIFT        = [0xB0, 49]
BTN_SELECT       = [0xB0, 48]

BTN_UP           = [0xB0, 46]
BTN_DOWN         = [0xB0, 47]
BTN_LEFT         = [0xB0, 44]
BTN_RIGHT        = [0xB0, 45]

# bottom up
BTN_TEMP1_QUATER            = [0xB0, 36]
BTN_TEMP2_QUATER_T          = [0xB0, 37]
BTN_TEMP3_EIGHTH            = [0xB0, 38]
BTN_TEMP4_EIGHTH_T          = [0xB0, 39]
BTN_TEMP5_SIXTEENTH         = [0xB0, 40]
BTN_TEMP6_SIXTEENTH_T       = [0xB0, 41]
BTN_TEMP7_THIRTYSECOND      = [0xB0, 42]
BTN_TEMP8_THIRTYSECOND_T    = [0xB0, 43]

BTN_MASTER       = [0xB0, 28]
BTN_STOP         = [0xB0, 29]

# Bicolor Buttons in the middle, below the display
# They have two colors, red and green.
BTN_R1_C1        = [0xB0, 20]
BTN_R1_C2        = [0xB0, 21]
BTN_R1_C3        = [0xB0, 22]
BTN_R1_C4        = [0xB0, 23]
BTN_R1_C5        = [0xB0, 24]
BTN_R1_C6        = [0xB0, 25]
BTN_R1_C7        = [0xB0, 26]
BTN_R1_C8        = [0xB0, 27]

BTN_R2_C1        = [0xB0, 102]
BTN_R2_C2        = [0xB0, 103]
BTN_R2_C3        = [0xB0, 104]
BTN_R2_C4        = [0xB0, 105]
BTN_R2_C5        = [0xB0, 106]
BTN_R2_C6        = [0xB0, 107]
BTN_R2_C7        = [0xB0, 108]
BTN_R2_C8        = [0xB0, 109]

# Have RGB-LED
PAD_36            = [0x90, 36] # note
PAD_37            = [0x90, 37] # note
PAD_38            = [0x90, 38] # note
PAD_39            = [0x90, 39] # note
PAD_40            = [0x90, 40] # note
PAD_41            = [0x90, 41] # note
PAD_42            = [0x90, 42] # note
PAD_43            = [0x90, 43] # note

PAD_44            = [0x90, 44] # note
PAD_45            = [0x90, 45] # note
PAD_46            = [0x90, 46] # note
PAD_47            = [0x90, 47] # note
PAD_48            = [0x90, 48] # note
PAD_49            = [0x90, 49] # note
PAD_50            = [0x90, 50] # note
PAD_51            = [0x90, 51] # note

PAD_52            = [0x90, 52] # note
PAD_53            = [0x90, 53] # note
PAD_54            = [0x90, 54] # note
PAD_55            = [0x90, 55] # note
PAD_56            = [0x90, 56] # note
PAD_57            = [0x90, 57] # note
PAD_58            = [0x90, 58] # note
PAD_59            = [0x90, 59] # note

PAD_60            = [0x90, 60] # note
PAD_61            = [0x90, 61] # note
PAD_62            = [0x90, 62] # note
PAD_63            = [0x90, 63] # note
PAD_64            = [0x90, 64] # note
PAD_65            = [0x90, 65] # note
PAD_66            = [0x90, 66] # note
PAD_67            = [0x90, 67] # note

PAD_68            = [0x90, 68] # note
PAD_69            = [0x90, 69] # note
PAD_70            = [0x90, 70] # note
PAD_71            = [0x90, 71] # note
PAD_72            = [0x90, 72] # note
PAD_73            = [0x90, 73] # note
PAD_74            = [0x90, 74] # note
PAD_75            = [0x90, 75] # not

PAD_76            = [0x90, 76] # note
PAD_77            = [0x90, 77] # note
PAD_78            = [0x90, 78] # note
PAD_79            = [0x90, 79] # note
PAD_80            = [0x90, 80] # note
PAD_81            = [0x90, 81] # note
PAD_82            = [0x90, 82] # note
PAD_83            = [0x90, 83] # note

PAD_84            = [0x90, 84] # note
PAD_85            = [0x90, 85] # note
PAD_86            = [0x90, 86] # note
PAD_87            = [0x90, 87] # note
PAD_88            = [0x90, 88] # note
PAD_89            = [0x90, 89] # note
PAD_90            = [0x90, 90] # note
PAD_91            = [0x90, 91] # note

PAD_92            = [0x90, 92] # note
PAD_93            = [0x90, 96] # note
PAD_94            = [0x90, 94] # note
PAD_95            = [0x90, 95] # note
PAD_96            = [0x90, 96] # note
PAD_97            = [0x90, 97] # note
PAD_98            = [0x90, 98] # note
PAD_99            = [0x90, 99] # note


## from pushmod.blosgpot.com
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
SYSEX_DATA_SET_LIVE_MODE=  [240,71,127,21,98,0,1,0,247]

# Set User mode	240,71,127,21,98,0,1,1,247
SYSEX_DATA_SET_USER_MODE=  [240,71,127,21,98,0,1,1,247]

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

#Bi-color LED table
#These are the colors which will be set on the bi-color (red/green) buttons below display

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
#25 -> 127 - Green


