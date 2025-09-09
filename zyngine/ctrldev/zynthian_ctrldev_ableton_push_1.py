#!/usr/bin/python3
# -*- coding: utf-8 -*-

# lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, 0)
# lib_zyncore.dev_send_midi_event(self.idev_out, sysex_data, len(sysex_data))
# lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)

# 20250821: Brumby INITIAL Version copied from Launchpad Mini Mk3.
# Ergolge:
# 1. Device wird erkannt und die einzelnen Functionen werden aufgerufen
# 2. Es werden Session angezeigt, Sogar mit den 4 verschiedenen Farben. Allerdings an falscher Stelle!
# 3. Die Shifttaste leuchtet, wenn man sie drückt!
###
# 20250828
# 4. Pad-Anzeige funktioniert. Es kann noch nicht geschaltet werden. Farben sind wohl auch nicht ganz richtig
# 5. Start und Stop geht, aber die oben und Unten sind vertauscht
###
# 250829
# 6 Zustand von 4 wieder erreicht. 
# 5 geht nicht mehr!
# 7 Zustand von 5 ist wieder erreicht. Toggle row ist unten statt oben.
###
# 8 Ergolg Pads funktionieren!. Allerdings lassen sich unbelegte Platze einschalten.
# 9 Die Gui Potis funktionieren
#   Erinnerung: Die Potis CC71-CC79 haben auch ein Touchfunktion. Allerdings mit anfassen des Knopfes und Loslassen.
#   Das können wir deshalb nicht als keypress verwenden.
#   Die Tasten unter dem Display aber schon!
# 10 poti 0-3 werden als Zypod 1-4 erkannt
#   todo Tasten unterhalb des Displays als ZYNPOD-Buttons
# 11 ABL_OK und ABL_ESC funktionieren nicht. 
#    -- ABL_OK hat nicht den richtigen GUISTEUERWERT
#    -- ABL_ESC wird nicht mit der Taste angesteuert
# 12 ABL_OK und ABL_ESC funktionieren.
# 
# Bemerkung: Alle Tasten, die eine Funktion haben, leuchten. Es wird aber KEIN Leuchstatus gelöscht, wenn er schon gesetzt war!
#
# todo Display mit Sysex ansteuern

# 250830 0310
# 13 Ich kann die Statusmeldung überschreiben und aus irgendeinem Grund wird Hallo Welt ausgegeben.
 
# 20250831-0057
# Das Display funktioniert. Ich kann Texte beliebig positionieren und den Bildschirm löschen.

#20250901-0015
#Sicherung funktionsfähig


####
####
####


## from pushmod.blospot.com
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
#  0 - Off
ABL_KEY_LED_OFF = 0
#  1 - Dim
ABL_KEY_LED_DIM = 1
#  2 - Dim Blink
ABL_KEY_LED_DIM_BLINK = 2
#  3 - Dim Blink Fast
ABL_KEY_LED_DIM_BLINK_FAST = 3
#  4 - Lit
ABL_KEY_LED_LIT = 4
#  5 - Lit Blink
ABL_KEY_LED_LIT_BLINK = 5
#  6 - Lit Blink Fast
ABL_KEY_LED_LIT_BLINK_FAST = 6
#  7 -> 127 - Lit
#########  END MONOCHROMATIC LED ##################

#Bi-color LED table
#These are the colors which will be set on the bi-color (red/green) buttons:

ABL_BI_LED_OFF = 0                  # 0 - Off (Black)
ABL_BI_RED_DIM = 1                  # 1 - Red Dim
ABL_BI_RED_DIM_BLINK = 2            # 2 - Red Dim Blink
ABL_BI_RED_DIM_BLINK_FAST = 3       # 3 - Red Dim Blink Fast
ABL_BI_RED = 4                      # 4 - Red
# 5 - Red Blink
ABL_BI_RED_BLINK = 5
# 6 - Red Blink Fast
ABL_BI_RED_BLINK_FAST = 6
# 7 - Orange Dim
ABL_BI_ORANGE_DIM = 7
# 8 - Orange Dim Blink
ABL_BI_ORANGE_DIM_BLINK = 8
# 9 - Orange Dim Blink Fast
ABL_BI_ORANGE_DIM_BLINK_FAST = 9
#10 - Orange
ABL_BI_ORANGE = 10
#11 - Orange Blink
ABL_BI_ORANGE_BLINK = 11
#12 - Orange Blink Fast
ABL_BI_ORANGE_BLINK_FAST = 12
#13 - Yellow (Lime) Dim
ABL_BI_YELLOW_DIM = 13
#14 - Yellow Dim Blink
ABL_BI_YELLOW_DIM_BLINK = 14
#15 - Yellow Dim Blink Fast
ABL_BI_YELLOW_DIM_BLINK_FAST = 15
#16 - Yellow (Lime)
ABL_BI_YELLOW = 16
#17 - Yellow Blink
ABL_BI_YELLOW_BLINK = 17
#18 - Yellow Blink Fast
ABL_BI_YELLOW_BLINK_FAST = 18
#19 - Green Dim
ABL_BI_GREEN_DIM = 19
#20 - Green Dim Blink
ABL_BI_GREEN_DIM_BLINK = 20
#21 - Green Dim Blink Fast
ABL_BI_GREEN_DIM_BLINK_FAST = 21
#22 - Green
ABL_BI_GREEN = 22
#23 - Green Blink
ABL_BI_GREEN_BLINK = 23
#24 - Green Blink Fast
ABL_BI_GREEN_BLINK_FAST = 24
#25 -> 127 - Green

# note werte Push 1 Midimapping
ABL_PAD_START = 36
ABL_PAD_END   = 99

# CC Werte der Tasten
ABL_REC   = 86
ABL_PLAY  = 85

ABL_OK    = 62
ABL_ESC   = 63 # Abbruch, Zurück

ABL_TRACK = 112

ABL_ARROW_LEFT  = 44
ABL_ARROW_RIGHT = 45
ABL_ARROW_UP    = 46
ABL_ARROR_DOWN  = 47
ABL_SHIFT       = 49

# DISPLAY Buttons Row 1
ABL_BUTTON_DISPL_R1_0 = 20
# ...
ABL_BUTTON_DISPL_R1_8 = 27
# Display Buttons Row 2
ABL_BUTTON_DISPL_R2_0 = 102
# ...
ABL_BUTTON_DISPL_R2_8 = 109



# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Ableton Push 1"
#
# Copyright (C) 2025 Julius Brumby 
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



import logging

# Brumbs imports
#from ableton_push1_display import Push1Display
from time import sleep

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad # , zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Ableton Push 1
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_ableton_push_1(zynthian_ctrldev_zynpad):      # , zynthian_ctrldev_zynmixer):


    logging.error("Klassenaufruf - Ableton Push 1 - BRUMBY")
    # Im Weblog wird angezeigt, dass der Treiber geladen wurde

    dev_ids = ["Ableton Push IN 2"]
    driver_name = "Ableton Push v1"
    driver_description = "Interface Ableton Push v1  with zynpad and zynmixer"

    # Folgende Farben sind wohl die Sequencer Farben??
    # siehe: https://pushmod.blogspot.com/p/pad-color-table.html
    # ORIGINAL PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    PAD_COLOURS =            [61, 36, 63, 54,      104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    STARTING_COLOUR = 123
    STOPPING_COLOUR = 120

    # pad_modes
    PAD_MODE_SEQ = 0
    PAD_MODE_DRUMS = 1
    PAD_MODE_SCALES = 2
    
    # pad_mode_active = PAD_MODE_SEQ
    pad_mode_active = PAD_MODE_SCALES

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        logging.info("__init__ Ableton Push 1 - BRUMBY")
        self.shift = False
        super().__init__(state_manager, idev_in, idev_out)
        
        # self.pad_mode_active = self.PAD_MODE_SCALES

        # self.zynmixer = state_manager.zynmixer    # Mixer object  
        
        # Initialize display        
        self.display = Display(idev_out)
        self.display.clear()
        sleep(0.1) # necessary delays, otherwise the next command is ignored

        self.display.brightnes(63)
        sleep(0.1)

        self.display.write_xy(b'* Pot 1 * Pot 2 ** Pot 3 * Pot 4 *', 0,0)
        sleep(0.1)

#       Positionierungshilfe
#        self.display.write_xy(b'123456789A123456789B123456789C123456789D123456789E123456789F123456789', 0,1)
#        sleep(0.1)

        self.display.write_xy(b'** Zynthian Push1Driver 0.1 **', 17,2)
        sleep(0.1)

        self.display.write_xy(b'++  Make MusicNot War ++', 20,3)

    def init(self):
        logging.error("init Ableton Push 1 - BRUMBY")

        # Hier muss die Trackstaste zum Leuchten gebracht werden am Push 1
        # Enable session mode on launchkey
        # Track-Taste CC112 # ABL_TRACK
        # lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 112, ABL_KEY_LED_LIT) # 2!
        # CC62 = OK; CC63 = Back (ABL_OK, ABL_ESC
        # lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 62, ABL_KEY_LED_LIT_BLINK) # 2!
        
        # Monochrome Tasten die hell leuchten sollen
        for t in [ 36,37,38,39,40,41,42,43,   ABL_PLAY, ABL_OK, ABL_ESC, ABL_ARROW_LEFT, ABL_ARROW_RIGHT, ABL_ARROW_UP, ABL_ARROR_DOWN]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL_KEY_LED_LIT) # 2!

        # monochrome Tasten die dim leuchten sollen
        for t in [ABL_REC, ABL_SHIFT]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL_KEY_LED_DIM) # 2!

        # Bicolortasten die dim leuchten sollen CC20-27 + 102-109
        for t in [21, 23]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, 13) # 2!

        ### lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        self.cols = 8
        self.rows = 8 # war 2 20250829-2134
        super().init()  # aktiviert. Muss aktiviert sein!
        self.pads_off()
        

    def end(self):
        # logging.error("end Ableton Push 1 - BRUMBY")
        super().end()
        ### Disable session mode on launchkey
        ## lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0) # device, channel, note, velocity


    # this function is called by zynseq when a sequencer state is changed
    # we will update pad LED to show state
    def update_seq_state(self, bank, seq, state, mode, group):
            
        # Onlyreturn if Push1 driver is not in sequencer_mode_view
        if not self.pad_mode_active == self.PAD_MODE_SEQ: return
        
        # logging.info(f"BRUMBY bank={bank}; seq={seq}; state={state}; mode={mode}; group:{group}")
        if self.idev_out is None or bank != self.zynseq.bank:
                return

        col, row = self.zynseq.get_xy_from_pad(seq)
        note = ABL_PAD_END +1 -(row+1) * 8 + col
            # logging.info(f"BRUMBY-P col={col}; row={row} ergibt note:{note}")

            # Alles abfangen, was ausserhalb des Pad-Bereichs ist BRUMBY_NEU.
            #if (note > ABL_PAD_END) or (note < ABL_PAD_START):
            #       return

        try:
                if mode == 0 or group > 16:
                    chan = 0
                    vel = 0
                elif state == zynseq.SEQ_STOPPED:
                    chan = 0
                    vel = self.PAD_COLOURS[group]
                elif state == zynseq.SEQ_PLAYING:
                    chan = 2
                    vel = self.PAD_COLOURS[group]
                elif state in [zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC]:
                    chan = 1
                    vel = self.STOPPING_COLOUR
                elif state == zynseq.SEQ_STARTING:
                    chan = 1
                    vel = self.STARTING_COLOUR

                else: # Wenn nichts passt Pad-Beleuchtung ausschalten
                    chan = 0
                    vel = 0
                    
        except Exception as e: # Bei Fehler Pad-beleuchtung ausschalten
                chan = 0
                vel = 0

        # set pad color with velocity value
        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)




    def pad_off(self, col, row):
        # note = 96 + row * 16 + col # statt 96 -> 91 für Push
        note = ABL_PAD_END +1 -(row+1) * 8 + col
        logging.error(f"BRUMBY: row={row}; col={col} pad-note={note}")
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    def pads_off(self):
        dbg = False
        logging.error("BRUMBY: pas_off")
        for row in range(self.rows):
            for col in range(self.cols):
                self.pad_off(col, row)

    def midi_event(self, ev):
        logging.error(f"midi_event   Ableton Push 1 - BRUMBY {ev}")
        evtype = (ev[0] >> 4) & 0x0F

        # evtype= EV_NOTE_ON
        if evtype == 0x9:

            note = ev[1] & 0x7F # das ist überflüssig, weil note immer < 127 ist

            # Alle Noteevents ausfiltern, die nicht von den Pads kommen
            if note < ABL_PAD_START: 
                return True
            if note > ABL_PAD_END: 
                return True # ignore every note_on not from pads

            logging.error(f"BRUMBY: note={note}")

            # Entered session mode so set pad LEDs
            # QUESTION: What kind of message is this? Only SysEx messages can be bigger than 3 bytes.
            # if ev == b'\x90\x90\x0C\x7F':
            # self.update_seq_bank() 

            # Toggle pad
            # Hier wird der midi-Notenwert in einen x,y Wert umgewandelt, um die Sequencer-Bank entsprechend zu toggeln.
            
            if self.pad_mode_active == self.PAD_MODE_SCALES:
                # hier muss er Translator für scales hin!
                logging.error(f"midi_event  Ableton Push 1 - BRUMBY: PAD in SCALES mode - not implemented yet") 
                return False

                
            
            
            
            if self.pad_mode_active == self.PAD_MODE_SEQ:
                try:
                # BRUMBY_NEU
                
                    col = (note - ABL_PAD_START) // 8 # statt 96 -> 91
                    row = (note - ABL_PAD_START) % 8  # Statt 96 -> 91
                    # row = 7 - row; 
                    col = 7 - col;
                    pad = row * self.zynseq.col_in_bank + col 

                    logging.error(f"midi_event 1 MEINER  Ableton Push 1 - BRUMBY: row={row}; col={col}; pad={pad}")
               
                    if pad < self.zynseq.seq_in_bank:
                        self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad)
                        return True
                except:
                    pass
            
            return False

        # GUI Control Changes
        # evtype = EV_CC
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F

            # Der Status der Schift taste CC49 wird abgefragt. CCVall <> 0 heisst gedruückt. Andernfalls losgelassen
            if ccnum == 49:
                # SHIFT
                self.shift = ccval != 0
                if self.shift:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL_KEY_LED_LIT_BLINK)
                else:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL_KEY_LED_DIM)
                return True

            # Jetzt wird alles ausgefiltert, das den Wert 0 hat, damit das loslassen der Taste als CC ausgefiltert wird
            elif ccnum == 0 or ccval == 0:
                return True

            # Ab hier kann mann die Tastendrücke auswerten

            elif (self.shift and 20 < ccnum < 29) or (20 < ccnum < 25):
                chain = self.chain_manager.get_chain_by_position(
                    ccnum - 21, midi=False)
                if chain and chain.mixer_chan is not None and chain.mixer_chan < 17:
                    self.zynmixer.set_level(chain.mixer_chan, ccval / 127.0)

            # Zynpoties Werte an GUI
            # Potis Oben 72 - 75 die ersten 4
            elif 70 < ccnum < 80:
                # self.state_manager.send_cuia("ZYNPOT_ABS", [ccnum - 72, ccval/127])
                val = ccval
                if val > 68:
                  val = (val - 128)
                # falsch geraten, nicht ZYNPT_REL. Vielleicht ZYNPOT?
                self.state_manager.send_cuia("ZYNPOT", [ccnum - 71, val])
                logging.error(f"BRUMBY: Poti={ccnum-71} val={val}")
                return True


            elif (ccnum == ABL_OK) or  (ccnum == 23):
                logging.error("ABL_OK BRUMBY")
                self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [3,"S"])
                return True

            elif ccnum == 21:
                logging.error("ZYNPUT_BUT 1 ESC BRUMBY")
                self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [1,"S"])
                return True


            elif ccnum == ABL_ESC:
                logging.error("ABL_ESC BRUMBY")
                self.state_manager.send_cuia("BACK")
                return True



            elif ccnum == 45: # BRUMBY
            # elif ccnum == 0x66:
                # TRACK RIGHT
                self.state_manager.send_cuia("ARROW_RIGHT")
                return False

            elif ccnum == 44:
            # elif ccnum == 0x67:
                # TRACK LEFT
                self.state_manager.send_cuia("ARROW_LEFT")
                return False

            elif ccnum == 46:
            # elif ccnum == 0x68:
                # UP
                self.state_manager.send_cuia("ARROW_UP")
                return True

            elif ccnum == 47:
            # elif ccnum == 0x69:
                # DOWN
                self.state_manager.send_cuia("ARROW_DOWN")
                return True

            elif ccnum == ABL_PLAY:
                # PLAY
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
                else:
                    self.state_manager.send_cuia("TOGGLE_PLAY")
                return True
            elif ccnum == ABL_REC:
                # RECORD
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
                else:
                    self.state_manager.send_cuia("TOGGLE_RECORD")
                return True
            elif (ccnum > 35) and (ccnum < 44):
                self.zynseq.select_bank (8- (ccnum - 36))
                # Leuchstatus ändern
                for t in [ 36,37,38,39,40,41,42,43]:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL_KEY_LED_DIM) # 2!
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, ABL_KEY_LED_LIT_BLINK_FAST) # 2!
                return True


        # evtype = MIDI_PC ??
        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1) ## wahrscheinlich wird hier update_seq_state aufgerufen
            return True
        
        return False


#    def send_sysex(self, data):
        return
        # Send SysEx universal inquiry.
        # It's answered by some devices with a SysEx message.
        # def send_sysex_universal_inquiry(self):
        if self.idev_out > 0:
            #msg = bytes(SYSEX_DATA_SET_USER_MODE)
            #logging.error(f"BRUMBY: set user mode SYSEX={msg};")
            #lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            #sleep (0.05)

            #    "240 71 127 21 24 0 69 0 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 247")
            s  = "240 71 127 21 25 0 69 0 32 32 32 72 101 108 108 111 32 87 111 114 108 100 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 247"
            s2 = "240 71 127 21 26 0 69 0 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 247"
            #    "240 71 127 21 27 0 69 0 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 247"

            # s = "240 71 127 21 25 0 69 0 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 247"
            
            # String S
            integers = [int(x) for x in s.split()]
            msg = bytes(integers) 
            logging.error(f"BRUMBY: DISPLAY LINE2 SYSEX={msg};")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

            # String S2
            integers = [int(x) for x in s2.split()]
            msg = bytes(integers) 
            logging.error(f"BRUMBY: DISPLAY LINE3 SYSEX={msg};")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))


            #logging.error(f"BRUMBY: MIDDLE OF send_sysex;")
    
            #logging.error(f"BRUMBY: SYSEX={data};")
            #lib_zyncore.dev_send_midi_event(self.idev_out, data, len(data))

            #sleep(0.05)
            logging.error(f"BRUMBY: END OF send_sysex;")
        

# ------------------------------------------------------------------------------

#// Special Dispay Characters
##define UP_ARROW                            0
##define DOWN_ARROW                          1
##define THREE_STACKED_HORIZONTAL_LINES      2
##define VERTICAL_LINE_AND_HORIZONTAL_LINE   3
##define HORIZONTAL_LINE_AND_VERTICAL_LINE   4
##define TWO_VERTICAL_LINES                  5
##define TWO_SIDE_BY_SIDE_HORIZONTAL_LINES   6
##define FOLDER_SYMBOL                       7
##define SPLIT_VERTICAL_LINES                8
##define FLAT_SYMBOLS                        27
##define THREE_SIDE_BY_SIDE_DOTS             28
##define FULL_BLOCK                          29
##define RIGHT_ARROW                         30
##define LEFT_ARROW                          31

class Display:
    
    display_mem = [[32] * 68 for _ in range(4)] # 4 Zeilen mit 68 Spalten
            
    def __init__ (self, idev_out):
        self.dbg = True
        self.idev_out = idev_out
        # if self.dbg: 
        logging.error(f"BRUMBY: Class Display instantiiert")



    def clear (self):
        # clear out display_memory with blanks.
        self.display_mem = [[32] * 68 for _ in range(4)] # 4 Zeilen mit 68 Spalten
        
    
        """Overwrites whole display with ascii 32"""
        #if self.idve_out == 0:
        #   pass
        #logging.error(f"BRUMBY: Display.clear:  idev_out={self.idev_out}")

        # SYSEX_ZEILE_LÖSCHEN = 240,71,127,21,<28+line(0-3)>,0,0,247
        s0 = bytes([240,71,127,21,28,0,0,247]) # Zeile 0
        s1 = bytes([240,71,127,21,29,0,0,247]) # Zeile 1
        s2 = bytes([240,71,127,21,30,0,0,247]) # Zeile 2
        s3 = bytes([240,71,127,21,31,0,0,247]) # Zeile 3
        for x in  [s0, s1, s2, s3]:
            lib_zyncore.dev_send_midi_event(self.idev_out, x, len(x))
            sleep(0.05)

        # logging.error(f"BRUMBY: Display.clear: end of func idev_out={self.idev_out}")

    def refresh (self):
        # display memory to display
        for row in range(4):
            #msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])
            text = bytes(self.display_mem[row])
            text_len = len(text)
            col = 0
            # here the magic happens and sysex is cunstructed
            #            240, 71, 127, 21, <24+line(0-3)>,0,   <Nchars+1>,<Offset>,<Chars>,      247
            msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])
            # logging.error(f"BRUMBY: Display.refresh SYSEX={msg}")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)
        return
        # not implemented yet
           


    def write_xy (self, text, col_in, row_in):
        # schreibt Text an Position col_in, row_in in display memory und auf Display
        # mit refresh
        
        # Koordinaten prüfen
        if(row_in > 3): row_in = 3
        if(row_in < 0): row_in = 0
        if(col_in > 63): col_in = 63
        if(col_in < 0): col_in = 0
        
        # Textlänge prüfen, ob im erlaubten Bereich.
        text_len = len(text)
        if text_len + col_in > 68 : text = text[:68-col_in] # Rest abschneiden
        text_len = len(text)
        
        self.display_mem[row_in][col_in:col_in+text_len] = list(text)
        self.refresh()
        return
        
        
        """ #dbg = False
        #if dbg: logging.error(f"BRUMBY: Display.write_xy text={text}x={col_in} y={row_in}")
        row=row_in; 
        col=col_in
        if not type(text) is bytes:
            text = 'TypError b\'text\' erwartet'
            logging.error(f"BRUMBY: TypeError b'text' erwartet und nicht {text}->{type(text)}")

        if (row < 0)  : row = 0
        if (row > 3) : row = 3
        if (col < 0) : col = 0
        if (col > 63): col = 63 # nur der erste Char von text wäre druckbar

        #if dbg: logging.error(f"BRUMBY: Display.write_xy 2 text={text}x={col_in} y={row_in}")

        # Textlänge prüfen, ob im erlaubten Bereich.
        text_len = len(text)
        if text_len + col > 68 : text = text[:68-col] # Rest abschneiden
        text_len = len(text)
        
        # here the magic happens and sysex is cunstructed
        #            240, 71, 127, 21, <24+line(0-3)>,0,   <Nchars+1>,<Offset>,<Chars>,      247
        msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])

        #if dbg: logging.error(f"BRUMBY: Display.write_xy 4 SYSEX={msg}")

        lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
        # time.sleep(0.5)
        #if dbg: logging.error(f"BRUMBY: END_OF_Display.write_xy 2 ")
 """

# This might belong to the display setup
# Contrast request	240,71,127,21,122,0,0,247
# Contrast set		240,71,127,21,122,0,1,<contrast 0-127>, 247
# Brightness request	240,71,127,21,124,0,0,247
# Brightness set	240,71,127,21,124,0,1,<brightness 0-127>,247

    def contrast (self, i=None) -> int:
        """
        Setzt oder liest den Kontrast des Geräts via SysEx.
    
        Args:
            i (int, optional): Der gewünschte Kontrastwert (typischerweise 0-127).
                            Wenn None, wird der aktuelle Kontrast gelesen.
    
        Returns:
            int: Der aktuelle Kontrastwert (nach Setzung oder Abfrage).
    
        Raises:
            ValueError: Wenn der Kontrastwert außerhalb des gültigen Bereichs liegt.
        """
    
        # Überprüfen, ob ein Wert zum Setzen übergeben wurde

        if i is not None:

           if i < 0  : i = 0
           if i > 63: 
              i = 63
              logging.error(f"Constrast values more than 63, seem to do nothing. values set to 63")


           # set contrast
           #            240,71,127,21,122,0,1,<contrast 0-127>, 247
           msg = bytes([240,71,127,21,122,0,1,i               , 247])
           lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
           return i
        
        # send sysexrequest
        # Contrast request	240,71,127,21,122,0,0,247
        msg = bytes([240,71,127,21,122,0,0,247])

        # lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

        # Return Contrast. Not implemented
        return None



    def brightnes (self, i=None) -> int:
        logging.error(f"BRUMBY")

        if i is not None:

           if i < 9: i = 0
           if i > 63: 
              i = 63
              logging.error(f"Brightnes values more than 63, seem to do nothing. values set to 63")

           logging.error(f"BRUMBY brightnes={i}")

           # set brightnes
           #            240,71,127,21,124,0,1,<brightness 0-127>,247

           msg = bytes([240,71,127,21,124,0,1,i               , 247])
           lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
           logging.error(f"BRUMBY zu brightnes={i} geändert")


        

        # send sysexrequest
        # Brightness request	240,71,127,21,124,0,0,247
        # commented out; getting return value not implemented yet. don't know how to
        # msg = bytes([240,71,127,21,124,0,0,247])
        # lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

        # Return Brightnes. Not implemented
        return None












# Zynthian specific modules
# from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad # , zynthian_ctrldev_zynmixer
# from zyncoder.zyncore import lib_zyncore
# from zynlibs.zynseq import zynseq
