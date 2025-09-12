#! /zynthian/venv/bin/python


# -*- coding: utf-8 -*-

# 20250910-0044
# Alle Konstanten ausgelagert.

####
####
####



# note werte Push 1 Midimapping
# don't delete.
ABL_PAD_START = 36 # 1. Pad = pad_36
ABL_PAD_END   = 99 # letztes Paad = pad_99

# # CC Werte der Tasten
# ABL_REC   = 86
# # ABL_PLAY  = 85

# ABL_OK    = 62
# ABL_ESC   = 63 # Abbruch, Zurück

# ABL_TRACK = 112

# ABL_ARROW_LEFT  = 44
# ABL_ARROW_RIGHT = 45
# ABL_ARROW_UP    = 46
# ABL_ARROR_DOWN  = 47
# ABL_SHIFT       = 49

# # DISPLAY Buttons Row 1
# ABL_BUTTON_DISPL_R1_0 = 20
# # ...
# ABL_BUTTON_DISPL_R1_8 = 27
# # Display Buttons Row 2
# ABL_BUTTON_DISPL_R2_0 = 102
# # ...
# ABL_BUTTON_DISPL_R2_8 = 109



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

# Brumbys imports
from time import sleep # pause between sysex events.
#mport sys # for button detection
# vor editor use following.
# import ableton.push1_consts as ABL
from zyngine.ctrldev.zynthian_ctrldev_base_scale import Harmony
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_engine import zynthian_engine # to send directly to soundengine...


# for running driver this way:
import zyngine.ctrldev.ableton.push1_consts as ABL


# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Ableton Push 1
# ------------------------------------------------------------------------------------------------------------------

# zynthian_ctrldev_zynpad is class for Controlling the sequencer with pads
#zynthian_ctrldev_zynmixer cpntrolls the main mixer

class zynthian_ctrldev_ableton_push_1(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):


    logging.error("Klassenaufruf - Ableton Push 1 - BRUMBY")
    # Im Weblog wird angezeigt, dass der Treiber geladen wurde

    dev_ids = ["Ableton Push IN 2", "Ableton Push IN 1"] # get by stepping through zynthian_ctrldev_manager.load_driver()
    driver_name = "Ableton Push v1" # not essential. class name would be used otherwise
    driver_description = "Interface Ableton Push v1  with zynpad and zynmixer"

    # Folgende Farben sind wohl die Sequencer Farben??
    # siehe: https://pushmod.blogspot.com/p/pad-color-table.html
    # ORIGINAL PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    PAD_COLOURS =            [61, 36, 63, 54,      104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    STARTING_COLOUR = 123
    STOPPING_COLOUR = 120

    # dev_modes
    DEV_MODE_NONE = None
    DEV_MODE_PAD = 1
    DEV_MODE_DRUMS = 2
    DEV_MODE_SCALES = 3
    
    EV_NOTE_ON  = 0X9
    EV_NOTE_OFF = 0x8
    EV_CC       = 0XB
    
    # pad_mode_active = PAD_MODE_SEQ
    device_mode_active = DEV_MODE_SCALES
    
    scales = Harmony(8,8)
    scales.init_scale("Major", 36, -5) # -3 = new start per row 
    

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        logging.info("Created Instance from Ableton Push 1 driver - BRUMBY")
        
        # super.__init__ saves state_manger, chainmanger, idev_in and idev_out
        # nothing more.
        super().__init__(state_manager, idev_in, idev_out)
        
        
        self.shift = False     
        self.device_mode_active = self.DEV_MODE_SCALES
        self.set_dev_scale_color()
        
        
        # self.zynmixer = state_manager.zynmixer    # Mixer object  
        
        # set push to live mode
        # seems not to do anything
        #sysex = bytes(ABL.SYSEX_DATA_SET_LIVE_MODE)
        #lib_zyncore.dev_send_midi_event(self.idev_out, sysex, len(sysex))
        #sleep(0.01)
        
        # Initialize display        
        self.display = Display(idev_out)
        self.display.clear()
        sleep(0.1) # necessary delays, otherwise the next command is ignored

        self.display.brightnes(36)
        sleep(0.1)

        self.display.write_xy(b'* Pot 1 * Pot 2 ** Pot 3 * Pot 4 *', 0,0)
        sleep(0.1)

#       Positionierungshilfe
        self.display.write_xy(b'123456789A123456789B123456789C123456789D123456789E123456789F123456789', 0,1)
        sleep(0.1)

        self.display.write_xy(b'** Zynthian Push1Driver 0.1 **', 17,2)
        sleep(0.1)

        self.display.write_xy(b'++  Make MusicNot War ++', 20,3)
        self.unroute_from_chains = True
        return

    def init(self):
        try: 
            logging.info("called init. Setting up Ableton Push 1 - BRUMBY")

            # Hier muss die Trackstaste zum Leuchten gebracht werden am Push 1
            # Enable session mode on launchkey
            # Track-Taste CC112 # ABL_TRACK
            # lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 112, ABL.MONO_LED_LIT) # 2!
            # CC62 = OK; CC63 = Back (ABL_OK, ABL_ESC
            # lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 62, ABL.MONO_LED_LIT_BLINK) # 2!
            
            # Monochrome Tasten die hell leuchten sollen
            for t in [ 36,37,38,39,40,41,42,43,   
                    ABL.BTN_START[1], ABL.BTN_OK[1], ABL.BTN_ESC[1], ABL.BTN_LEFT[1], 
                    ABL.BTN_RIGHT[1], ABL.BTN_UP[1], ABL.BTN_DOWN[1], ABL.BTN_SCALES[1] ]:
                
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_LIT)

            # monochrome Buttons than should be dim state
            for t in [ ABL.BTN_REC[1], ABL.BTN_SHIFT[1] ]: # ,ABL_REC, ABL_SHIFT]:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_DIM) 
                
            # Bicolor LEDs dim ## CC20-27 + 102-109
            for t in [21, 23]:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.BI_ORANGE_DIM) 

            ### lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
            self.cols = 8
            self.rows = 8 # war 2 20250829-2134
            super().init()  # aktiviert. Muss aktiviert sein!
            # self.pads_off()
            if self.device_mode_active == self.DEV_MODE_SCALES:
                self.set_dev_scale_color()
                
        except ValueError as e:
            print(f"Fehler aufgetreten: {e}")
        

    def end(self):
        # logging.error("end Ableton Push 1 - BRUMBY")
        super().end()
        ### Disable session mode on launchkey
        ## lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0) # device, channel, note, velocity

### Mixer FUNCTIONS FOR DISPLAY ACTION from zynmixer.
### just copy the derived functions in the this driver and implement them accordingly 
    def update_mixer_active_chain(self, active_chain):
        """Update hardware indicators for active_chain"""
        logging.error(f"not implemented active_chain: {active_chain}")
        
    def update_mixer_strip(self, chan, symbol, value):
        """Update hardware indicators for a mixer strip: mute, solo, level, balance, etc. # oh my goodness, what means etc. ?
        *SHOULD* be implemented by child class

        chan - Mixer strip index
        symbol - Control name
        value - Control value
        
        Idiea for display
        |||||||||||  = lefel indicator
        M S L B      = M=Mute; S=Solo L=changing the Lefel; B=changing balance; But what else ???
        """
        logging.debug(
            f"Update mixer strip for {type(self).__name__}: NOT IMPLEMENTED! chan: {chan}; symbol: {symbol} value: {value}")

### END of Mixer functions.

### Start of SEQUENCER FUNCTIONS
    # this function is called by zynseq when a sequencer state is changed
    # we will update pad LED to show state
    def update_seq_state(self, bank, seq, state, mode, group):
        try:
            # return
            # Onlyreturn if Push1 driver is not in sequencer_mode_view
            if not self.device_mode_active == self.DEV_MODE_PAD: 
                return
            
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
        except ValueError as e:
            print(f"Fehler aufgetreten: {e}")




    def pad_off(self, col, row):
        # note = 96 + row * 16 + col # statt 96 -> 91 für Push
        note = ABL_PAD_END +1 -(row+1) * 8 + col  # recalculate midi note from col and row
        # logging.info(f"BRUMBY: row={row}; col={col} pad-note={note}")
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

### End of derived Sequencer Functions.

    # Just for me a helper function to set all pads off
    def pads_off(self):
        dbg = False
        logging.debug("BRUMBY: pads_off")
        for row in range(self.rows):
            for col in range(self.cols):
                self.pad_off(col, row)


    # https://discourse.zynthian.org/t/driver-for-ableton-push-1-first-steps/12166/8
    def _forward_like_niels_did(self, ev):
        # Direct keybed to chains
        #if (channel == 1):
        chain = self.chain_manager.get_active_chain()
            # print(chain.midi_chan)
            # @todo: find out how to get 'last' active chain, for now: just back out.
        
        if chain.midi_chan is None:
            return False
        
        status = (ev[0] & 0xF0) | chain.midi_chan
        self.zynseq.libseq.sendMidiCommand(status, ev[1], ev[2])
        return True
        
        # if not processed you call
        # return super()._on_midi_event(ev)`

    def midi_event(self, ev):
        try: # if midievent is too short it fails...
            btn_name = self.button_name_from_midi_event(ev)
            logging.debug(f"Button: {btn_name} gives midi_event: {ev} = {ev[0]}, {ev[1]} {ev[2]}")
        except:
            pass
        
        #return False # prüfen ob sofortige Umleitung eine Note spield???!!!!
         
        evtype = (ev[0] >> 4) & 0x0F

        

        note = ev[1] & 0x7F # das ist überflüssig, weil note immer < 127 ist

        # filter every note on not from pads. knobs have, when touched also note_on messages
        if note < ABL_PAD_START: 
            return True
        if note > ABL_PAD_END: 
            return True # ignore every note_on not from pads

        logging.debug(f"BRUMBY: note on event with note={note}")

        # Toggle pad
        # Hier wird der midi-Notenwert in einen x,y Wert umgewandelt, um die Sequencer-Bank entsprechend zu toggeln.
        
        
        if evtype in [self.EV_NOTE_ON, self.EV_NOTE_OFF] and self.device_mode_active == self.DEV_MODE_SCALES:
                # hier muss er Translator für scales hin!
                logging.debug(f"Scales mode -BRUMBY")
                pad_nr = note -35# get pad_nr from note
                note_translated = self.scales.harmony_get_target_note(pad_nr-1) # midinotes arf based 0 pad_nr based 1
                new_ev = bytes([ev[0], note_translated, ev[2]*2])
                #if note_translated % 12 == 0: # Oktave detected
                #    pass
                # for note_on events following.
                
                self._forward_like_niels_did(new_ev)
                return True #  not processed, has to be processed further

        # evtype= EV_NOTE_ON
        if evtype == 0x9:               
            
            if self.device_mode_active == self.DEV_MODE_PAD:
                try:
                    col = (note - ABL_PAD_START) // 8 # statt 96 -> 91
                    row = (note - ABL_PAD_START) % 8  # Statt 96 -> 91
                    # row = 7 - row; 
                    col = 7 - col; # midi notes start from bottom, so recalculate row
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

            # Sate of shoft button CC49 wird abgefragt. CCVall > 0  means pressed 
            if ccnum == ABL.BTN_SHIFT[1]:
            # if ccnum == 49:
                # SHIFT
                self.shift = ccval != 0 # set shift variable
                # visual feedback with button LED
                if self.shift:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL.MONO_LED_LIT_BLINK)
                else:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL.MONO_LED_DIM)
                return True # event processed. No further action required
             
            # From here filter any event with velocyty=0 We just need pressed vaues to come through
            elif ccnum == 0 or ccval == 0:
                return False # Warning: With "return True" no further processing in zynthian. 
                            # So no Controlchange with data=0 gets through to zynthian.
                            # Is that, what we want ???
                            # Also bank changes are msb or isit LSB are filtered waay.
                            # I assume, it has to return False, so Zynthian can do bank chanages !!! 

            # From here only positive Values are processed!

            # Displays bi-color Buttons
            elif (self.shift and 20 < ccnum < 29) or (20 < ccnum < 25):
                chain = self.chain_manager.get_chain_by_position(ccnum - 21, midi=False)
                if chain and chain.mixer_chan is not None and chain.mixer_chan < 17:
                    self.zynmixer.set_level(chain.mixer_chan, ccval / 127.0) # "/127.0" creates a float val from 0.0 .. 1.0
                
            # This swtches between this drivers pad states: Sequencer and Scales
            elif (ccnum == ABL.BTN_SCALES[1]):
                logging.info("BRUMBY: BTN_SCALES")
                if not self.device_mode_active == self.DEV_MODE_SCALES:
                    self.device_mode_active = self.DEV_MODE_SCALES
                    # visual feedback, let Scales Button blink
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT_BLINK)
                    self.pads_off() # akk pad leds off
                    self.set_dev_scale_color()
                else:
                    self.device_mode_active = self.DEV_MODE_PAD
                    # visual feedback, set LED to solid on
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT)
                    self.pads_off() # clean up visible state. all pad leds off
                    self.refresh() # refreshe LEDs for Sequencer mode of this driver.
                    
                return True
            
            # Gui events ausgelagert zu:
            if self.process_gui_events(ev): return True
            


        # evtype = MIDI_Program Change 
        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1) 
            return True
        
        # default return, when no match
        return False # When nothing matches, False shows that midi event has to be processed further

    # to clean up the code GUI events are processed here
    def process_gui_events(self,ev) -> bool:
        
        if ev[0] & 0xF0 == 0xB0: # event is midi CC ?
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
        
        
            # Zynpoties Werte an GUI
            # Potis Oben 72 - 75 die ersten 4
            # if 70 < ccnum < 80: 
            if ABL.KNOB_1[1] <= ccnum <= ABL.KNOB_4[1]: 
                # self.state_manager.send_cuia("ZYNPOT_ABS", [ccnum - 72, ccval/127])
                val = ccval
                if val > 68:
                  val = (val - 128)
                # falsch geraten, nicht ZYNPT_REL. Vielleicht ZYNPOT?
                self.state_manager.send_cuia("ZYNPOT", [ccnum - 71, val])
                logging.debug(f"BRUMBY: Poti={ccnum-71} val={val}")
                return True


            elif (ccnum == ABL.BTN_OK[1]) or  (ccnum == 23):
                logging.debug("ABL_OK BRUMBY")
                self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [3,"S"])
                return True


            # elif ccnum == 21: Does that work?
            elif ccnum == ABL.BTN_R1_C2[1]: # Zweiter Button unter dem Display
                logging.debug("ZYNPUT_BUT 1 ESC BRUMBY")
                self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [1,"S"])
                return True


            elif ccnum == ABL.BTN_ESC[1]:
                # logging.debug("BTN_ESC BRUMBY")
                self.state_manager.send_cuia("BACK")
                return True


            # elif ccnum == 45: 
            elif ccnum == ABL.BTN_RIGHT[1]:
            # elif ccnum == 0x66:
                # TRACK RIGHT
                self.state_manager.send_cuia("ARROW_RIGHT")
                return False


            # elif ccnum == 44:
            elif ccnum == ABL.BTN_LEFT[1]:
            # elif ccnum == 0x67:
                # TRACK LEFT
                self.state_manager.send_cuia("ARROW_LEFT")
                return False


            elif ccnum == ABL.BTN_UP[1]: #  CC46
            # elif ccnum == 0x68:
                # UP
                self.state_manager.send_cuia("ARROW_UP")
                return True


            elif ccnum == ABL.BTN_DOWN[1]:
            # elif ccnum == 47:
                # DOWN
                self.state_manager.send_cuia("ARROW_DOWN")
                return True


            elif ccnum == ABL.BTN_START[1]: # ehemals ABL_PLAY:
                # PLAY
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
                else:
                    self.state_manager.send_cuia("TOGGLE_PLAY")
                return True


            elif ccnum == ABL.BTN_REC[1]: # ABL_REC:
                # RECORD
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
                else:
                    self.state_manager.send_cuia("TOGGLE_RECORD")
                return True


            # These are the note_length Buttons right of pads in Sequencer mode to start and stop a whole row of sequences
            elif (ccnum > 35) and (ccnum < 44):
                self.zynseq.select_bank (8- (ccnum - 36))
                # Leuchstatus ändern
                for t in [ 36,37,38,39,40,41,42,43]:
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_DIM) # 2!
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, ABL.MONO_LED_LIT_BLINK_FAST) # 2!
                return True

        
        return False #  event is not processed
    
    def button_name_from_midi_event(self, ev): ###, button_event): # button_event is a Constant from import abl.
        # create key_data from midi event
        # if too slow, we have to revert the array to a named array with buttonevent as name
        if len(ev) < 2 : return None # event is too short to get two byte data. Time event or so?
        if len(ev) > 2: data = ev[2]
        search_key = [ ev[0] & 0xF0, ev[1] ]
        for name in dir(ABL): # all vars as textstring
            if not name.startswith('__'): # no attributes with '__'
                attr = getattr(ABL, name)
                if attr == search_key and name.isupper():
                    logging.debug(f"midi_event {ev} {ev[0]}, {ev[1]}, from Button with name: {name} and value: {data}")
                    return name
        logging.debug(f"midi_event {ev} from Button not defined with value: {data}")
        return None
            
    def set_dev_scale_color(self):
        for pad_nr in range(64):
            new_note = self.scales.harmony_get_target_note(pad_nr)
            if new_note % 12 == 0:
                r = 0; g = 0; b = 255
            else:
                r = 200; g = 200; b = 200 
            self.set_pad_rgb(pad_nr, r, g, b)
        pass
          
    def set_pad_rgb(self, pad_nr: int, r:int ,g:int ,b:int):
        # Sysex : 240,71,127,21,4,0,8,<Pad(0-71)>,0,<r1>,<r2>,<g1>,<g2>,<b1>,<b2>,247
        # pad = 0-71  NICHT PAD_36 - PAD_99 
        # blogspot.com
        # To set a pad color to a RGB(0-255) value, the RGB values need to be set into "Push" format, for example:
        # r1 = r /(integer division) 16 
        # r2 = r %(modulo) 16
        # So a value of R132 would become: r1=8 r2=4.
        # The pad index if from 0 to 71, zero being the bottom left pad, all the way up to the second row button to the right (second row of buttons is RGB).
        if r > 255: r = 255; 
        if r < 0: r = 0
        if g > 255: g = 255; 
        if g < 0: g = 0
        if b > 255: b = 255; 
        if b < 0: b = 0
        if not 0 <= pad_nr <= 64: 
            logging.error(f"Padnr wrong. not in 1..64 pad_nr = {pad_nr}")
            return False
        
        r1= r // 16  ; r2= r % 16
        g1= g // 16  ; g2= g % 16
        b1= b // 16  ; b2= b % 16
        sysex = bytes ([240,71,127,21,4,0,8,pad_nr,0,r1,r2,g1,g2,b1,b2,247] )   
        lib_zyncore.dev_send_midi_event(self.idev_out, sysex, len(sysex))

    def send_sysex(self, data):
        return
        # Send SysEx universal inquiry.
        # It's answered by some devices with a SysEx message.
        # def send_sysex_universal_inquiry(self):
        if self.idev_out > 0:
            
            #msg = bytes(ABL.SYSEX_DATA_SET_USER_MODE)
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

    def update (self):
        # move display memory to display with sysex
        for row in range(4):
            #msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])
            text = bytes(self.display_mem[row])
            text_len = len(text)
            col = 0
            # here the magic happens and sysex is cunstructed
            #            240, 71, 127, 21, <24+line(0-3)>,0,   <Nchars+1>,<Offset>,<Chars>,      247
            msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])
            # logging.error(f"BRUMBY: Display.update SYSEX={msg}")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)
        return
        # not implemented yet
           


    def write_xy (self, text, col_in, row_in):
        # schreibt Text an Position col_in, row_in in display memory und auf Display
        # mit update
        
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
        self.update()
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
