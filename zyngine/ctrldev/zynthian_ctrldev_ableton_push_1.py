#! /zynthian/venv/bin/python
# -*- coding: utf-8 -*-

# TODO: DIsplay rowas are of different type. 
# Row two seams to be monochrome green, just brightnes


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

import logging
import traceback


#### just local debug
debug_mode = True
if debug_mode:
        
    # Eigenen Logger für Ihre Library erstellen
    logger = logging.getLogger("ABL-Push_1")  # Eindeutiger Name für Ihre Library

    # Nur für Ihren Logger Level setzen
    logger.setLevel(logging.DEBUG)  # Nur DIESER Logger zeigt Debug messages

    # Handler for your logger (optional)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

### end of just local debug


# Brumbys new imports
from time import sleep # pause between sysex events.
import zyngine.ctrldev.ableton.push1_consts as ABL
from zyngine.ctrldev.zynthian_ctrldev_base_scale import Harmony
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_engine import zynthian_engine # to send directly to soundengine...
from zyngine.ctrldev.zynthian_ctrldev_base_extended import RunTimer, KnobSpeedControl, ButtonTimer, CONST

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Ableton Push 1
# ------------------------------------------------------------------------------------------------------------------

# zynthian_ctrldev_zynpad is class for Controlling the sequencer with pads
#zynthian_ctrldev_zynmixer cpntrolls the main mixer


# note werte Push 1 Midimapping
# don't delete.
ABL_PAD_START = 36 # 1. Pad = pad_36
ABL_PAD_END   = 99 # letztes Paad = pad_99


class zynthian_ctrldev_ableton_push_1(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    logging.info("Push 1 initializes instance of class")
    # Weblog shows this messages

    # dev_ids = ["Ableton Push IN 2", "Ableton Push IN 1"] # get by stepping through zynthian_ctrldev_manager.load_driver()
    dev_ids = ["Ableton Push IN 2"] # get by stepping through zynthian_ctrldev_manager.load_driver(). Data just at Port 2
    
    driver_name = "Ableton Push v1" # not essential. class name would be used otherwise
    driver_description = "Interface Ableton Push v1  with zynpad and zynmixer"

    ################################
    
    # Colors for LED-Pads in Sequencermode # TODO: Palette has to be fixed 
    # siehe: https://pushmod.blogspot.com/p/pad-color-table.html
    # ORIGINAL PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    PAD_COLOURS =            [61, 36, 63, 54,      104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15] # not running
    STARTING_COLOUR = 123 # GREEM
    STOPPING_COLOUR = 120 # RED
    RUNNING_COLOR   = 3 # WHITE

    # equal vars are in base_extended...
    # evtype = (ev[0] >> 4) & 0x0F ->
    EV_NOTE_OFF    = 0x8 # 3 Bytes
    EV_NOTE_ON     = 0X9 # 3 Bytes
    EV_AFTERTOUCH  = 0xA # 3 Bytes (polyphonic = per note)
    EV_CC          = 0xB # 3 Bytes
    EV_PC          = 0xC # 2 Bytes
    EV_CHAN_PRESS  = 0xD # 2 Bytes
    EV_PITCHBEND   = 0xE # 3 bytes ev[1] = LSB 0-127; ev[2] = MSB 0-127
    EV_SYSTEM      = 0xF # varies from 1 to many Bytes ### Systemtype = ev[0] & 0x0F
    
    
    # dev_modes
    DEV_MODE_NONE    = None
    DEV_MODE_PAD     = 1    
    DEV_MODE_SCALES  = 2 # keyboard modes
    DEV_MODE_MIXER   = 3
    # DEV_MODE_DRUMS = 2
    # pad_mode_active = PAD_MODE_SEQ
    device_mode_active = DEV_MODE_NONE # initial mode
    
    ### would be nice to see on display if class is found
    ### self._display   = Feedback_Display(idev_out)    # Text display
    
    scales = Harmony(8,8)
    scales.init_scale(tonic=0, 
                      mode_name="Major", 
                      col_versatz=-5, 
                      middle_c=48, 
                      middle_pad_nr=4)    

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        logging.info("Found Push 1 on USB")
        # would be nice to say, correct USB Device is found
        
        # super.__init__ saves state_manger, chainmanger, idev_in and idev_out
        # nothing more.
        super().__init__(state_manager, idev_in, idev_out)      
        
        # to slow knob-events.translates 127 to -1
        # TODO experiment with setup values when live
        self._knobs_ease = KnobSpeedControl()
        
        # Indecators of the device LEDs and Text # NOT USED
        self._leds_mono = Feedback_Mono_LEDs(idev_out)  # control buttons right and left from pads
        self._leds_bi   = Feedback_Bi_LEDs(idev_out)    # display buttons below display, above pads
        self._leds_rgb  = Feedback_RGB_LEDs(idev_out)   # pads in rgb
        self._display   = Feedback_Display(idev_out)    # Text display
        self.mixer_init() # Text display for mixer # suerp()__init__ has to be called earlier to set idev_out
        
        
        # seems to be necessary, because we send translated midi_events. o
        self.unroute_from_chains = True
        return

    # called from parent
    def init(self):
        try: 
            logging.info("called init. Setting up Ableton Push 1 - BRUMBY")
            self.shift = False # BTN_SHIFT is pressed    
            self.shift_note = 0 # Octave buttons      
      
            
            # set initial device mode
            self.set_device_mode_new(self.DEV_MODE_MIXER)
            
            
            # setup LEDS in Ctrl-Buttons
            # Monochrome Tasten die hell leuchten sollen
            for t in [ 36,37,38,39,40,41,42,43,   
                    ABL.BTN_START[1], ABL.BTN_OK[1], ABL.BTN_ESC[1], ABL.BTN_LEFT[1], 
                    ABL.BTN_RIGHT[1], ABL.BTN_UP[1], ABL.BTN_DOWN[1], ABL.BTN_SCALES[1], 
                    ABL.BTN_USER[1]
                    ]:                
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_LIT)

            # monochrome Buttons than should be dim state
            for t in [ ABL.BTN_REC[1], ABL.BTN_SHIFT[1] ]: # ,ABL_REC, ABL_SHIFT]:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_DIM) 
                
            # Bicolor LEDs dim ## CC20-27 + 102-109
            for t in [ABL.BTN_R1_C1[1], ABL.BTN_R1_C2[1], ABL.BTN_R1_C3[1], ABL.BTN_R1_C4[1]]:
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.BI_ORANGE_DIM) 

            ### lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
            # setup device pad arry size
            self.cols = 8
            self.rows = 8 # war 2 20250829-2134
            super().init()  # aktiviert. Muss aktiviert sein!
            # self.pads_off()
            if self.device_mode_active == self.DEV_MODE_SCALES:
                self.scales_set_dev_to_scales_mode()
                
        #except:
        #    print("Fehler aufgetreten: {e}")
        except Exception as e:
            print("Exception aufgetreten:")
            # Gibt den vollständigen Traceback aus
            # traceback.print_exc()
            logger.error("Exception aufgetreten: %s", e)
            logger.error("Traceback: %s", traceback.format_exc())
        
    # called from parent
    def end(self):
        # logging.error("end Ableton Push 1 - BRUMBY")
        super().end()
        ### Disable session mode on launchkey
        ## lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0) # device, channel, note, velocity


#################################################################################################################
##################     START   of scales fucntions     ##########################################################
   
    # when changing to scales mode: start here
    # new in this class, to setup scales_mode = keyboard mode
    def scales_set_dev_to_scales_mode(self):
        self.device_mode_active = self.DEV_MODE_SCALES
        # visual feedback, let Scales Button blink
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT_BLINK)
        self.pads_off() # akk pad leds off
        self.scales_set_pad_colors() # set LEDs for scale mode
        self._display.clear()
        scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
        self._display.write_xy_mem(scale_n_mode, 0, 2)
        
        btn_txt_row0 = "| ZynP1 | ZynP2  | ZynP3 | ZynP4 ||       |        | Scale | Mode  |"
        # btn_txt_row1 = f"|   {chr(12)} {chr(11)} {chr(10)}  | {chr(9)} {chr(8)}  {chr(7)}  {chr(6)}    |       |       |"
        btn_txt_row1 = "                                                                    "
        btn_txt_row2 = "|modes here      |       |       ||   G#  |    A   |  A#   |   B   |"
        btn_txt_row3 = "|   C   |   C#   |   D   |   D#  ||   E   |    F   |  F#   |   G   |"
        
        self._display.write_xy_mem(btn_txt_row0, 0, 0)
        self._display.write_xy_mem(btn_txt_row1, 0, 1)
        self._display.write_xy_mem(btn_txt_row2, 0, 2)
        self._display.write_xy_mem(scale_n_mode, 0, 2) # Scale and scale over row2
        self._display.write_xy_mem(btn_txt_row3, 0, 3)
        self._display.update_screen()
        # set PAD LEDS
        self.scale_update_leds(self.scales.tonic) # 0 is 'C'
        # set up buttons
        for t in [ABL.BTN_OCTAVE_DOWN[1], ABL.BTN_OCTAVE_UP[1]]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_LIT)

    
    # Leaving scales mode: remove anything that is initailized
    def scales_cleanup(self): # set of any LED and display changes
        # cleadup display
        btn_txt_row0 = "| ZynP1 | ZynP2 |  ZynP3 | ZynP4 ||       |        |       |       |"
        btn_txt_row2 = "|       |       |        |       ||       |        |       |       |"
        self._display.write_xy_mem(btn_txt_row0, 0, 0)
        self._display.write_xy_mem(btn_txt_row2, 0, 1)
        self._display.write_xy_mem(btn_txt_row2, 0, 2)
        self._display.write_xy_mem(btn_txt_row2, 0, 3)
        self._display.update_screen()
        
        # cleanup scale LED 
        scale_buttons = [
                    ABL.BTN_R2_C1[1], ABL.BTN_R2_C2[1], ABL.BTN_R2_C3[1], ABL.BTN_R2_C4[1],
                    ABL.BTN_R2_C5[1], ABL.BTN_R2_C6[1], ABL.BTN_R2_C7[1], ABL.BTN_R2_C8[1],
                    ABL.BTN_R1_C5[1], ABL.BTN_R1_C6[1], ABL.BTN_R1_C7[1], ABL.BTN_R1_C8[1]
                    ]
        for t in scale_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.BI_LED_OFF) 
        # set up buttons
        for t in [ABL.BTN_OCTAVE_DOWN[1], ABL.BTN_OCTAVE_UP[1]]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_OFF)

    
    
    # LED are setup to passive and the the actiavated LED is set 
    def scale_update_leds(self, index_activated): # index defines blinkin LED
        # Bicolor LEDs dim ## CC20-27 + 102-109
        scale_buttons = [
                    ABL.BTN_R2_C1[1], ABL.BTN_R2_C2[1], ABL.BTN_R2_C3[1], ABL.BTN_R2_C4[1],
                    ABL.BTN_R2_C5[1], ABL.BTN_R2_C6[1], ABL.BTN_R2_C7[1], ABL.BTN_R2_C8[1],
                    ABL.BTN_R1_C5[1], ABL.BTN_R1_C6[1], ABL.BTN_R1_C7[1], ABL.BTN_R1_C8[1]
                    ]
        for t in scale_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.BI_GREEN_DIM) 
        # set scale LED blinking
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, scale_buttons[index_activated], ABL.BI_GREEN_DIM_BLINK) 

           
    def scales_set_tonic(self, step):
        if step > 63: step -=128 # make left turn values (+ 64 to +127) to negative value
        # slowing down knob by factor ten
        self.steps_tonic = getattr(self, 'steps_tonic', 0) + step
        if not abs(self.steps_tonic) > 10: return # slow down. each 10th step
        self.steps_tonic = 0;
        
        # calculate new tonic 
        new_tonic = self.scales.tonic + step
        if new_tonic < 0:  new_tonic = 11  # target: B
        if new_tonic > 11: new_tonic = 0   # target: C
        self.scales.tonic = new_tonic # set tonic. thats all nothing to recalculate
        
        # set Display and LED from select buttons. PAD-LED  don't need update, because mode isn't changed
        scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
        self._display.write_xy_mem(scale_n_mode, 0, 2)
        self._display.update_screen()
        self.scale_update_leds(new_tonic)
        return
       
        
    def scales_set_mode(self, step):
        if step > 63: step -=128 # 127 = -1   # make left turn values negative     
        # lower knob speed by 10
        self.steps_mode = getattr(self, 'steps_mode', 0) + step
        if not abs(self.steps_mode) > 10: return # slow down. each 10th steop
        self.steps_mode = 0;
        
        # all mode names
        modenames = self.scales.harmony_get_mode_names()
        nr_of_modes = len(modenames)
        result = None
        
        # if not mode is set, get first name
        if not self.scales.active_mode: self.scales.active_mode = modenames[0] # "Chromatic"
        
        for i in range(nr_of_modes):
            if modenames[i] == self.scales.active_mode:
                result = i
                break
        if not result is None:
            result += step
            if result >= nr_of_modes: result = 0
            elif result < 0 : result = nr_of_modes-1
            
            new_mode = modenames[result]
            self.scales.active_mode = new_mode
        else:
            logging.error("Bug in set_mode")
        # do the magic
        self.scales.init_scale(self.scales.tonic, self.scales.active_mode)
        # colorize pad array with tonic
        self.scales_set_pad_colors()
        # Display
        scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
        self._display.write_xy_mem(scale_n_mode, 0, 2) # just little part with new text
        self._display.update_screen() # just second row is dirty_tagged and updated
        # because just mode changes, no change of tonic LEDs and Display

    # est color of 64 keyboard pads
    def scales_set_pad_colors(self):        
    # def set_dev_scale_color(self):
        # self._leds_rgb.all_off(True) # led_states must not be deleted. is done in next lines. just for debugging
        for pad_nr in range(64):
            new_note = self.scales.harmony_get_target_note(pad_nr)
            # if self.scales.is_tonic_by_midnote(new_note): ### NOT WORKING CONPLETELY
            if self.scales.is_tonic_by_padnr(pad_nr):
                r = 0; g = 0; b = 255
                # print (f"found: Tonic {new_note}")
            else:
                r = 200; g = 200; b = 200 
            # self.set_pad_rgb(pad_nr, r, g, b) ## OLD FUnction
            self._leds_rgb.set_rgb(pad_nr, r, g, b, overlay=False)
        pass       

    # scale modes own midi_event routine, called by midi_event func
    def process_scale_event(self, ev) -> bool:
        if not self.device_mode_active == self.DEV_MODE_SCALES: # keyboard modus is selected
            return False # we are not in scales mode
    
                   
            
        ##### event part for sounds
        # Filter out note events created by push 1 when touching Knobs and Ribbon 
        note = ev[1]
        if ABL_PAD_START <= note <= ABL_PAD_END: # just note events, which should sound.
            # filter for getting any vent that is sound event
            
                      
            evtype = (ev[0] >> 4) & 0x0F 
            
            if evtype == self.EV_PITCHBEND: # ribbon working as pitchwheel
                self._forward_like_niels_did(ev) 
                
            # processing note events
            if evtype in [self.EV_NOTE_ON, self.EV_NOTE_OFF, self.EV_AFTERTOUCH]:
                            
                # logging.debug(f"Scales mode -BRUMBY")
                pad_nr = note -35# translates input note to hardware pad_nr
                
                # here magic for different sccale layouts happens.
                # it translates midi_note events to the translated note_events
                note_translated = self.scales.harmony_get_target_note(pad_nr-1) # midinotes are based 0 pad_nr based 1
                
                # ocatve_buttons used
                note_translated += self.shift_note
                
                vel = ev[2] # my push1 is insensitive so I double any velocity val
                if evtype == self.EV_NOTE_ON: 
                    vel = ev[2] *2 # this creates junk with aftertouch und pitchbend..
                    if vel > 255: vel = 255
                new_ev = bytes([ev[0], note_translated, vel])
                #if note_translated % 12 == 0: # Oktave detected
                #    pass
                # for note_on events following.
                
                self._forward_like_niels_did(new_ev) # 
                return True #  return to caller and mark event as processed
            
        # here any other ebent 
        # self.EV_CC, self.EV_CHAN_PRESS, self.EV_SEXSTEM, self.EV_PC
        # and ALL events from Pads < PAD_START and Pads > PAD_END
        
        # we want to process display buttons:
        ## helper for display buttons
        def helper_set_new_tonic(tonic):
            if self.scales.set_new_tonic(tonic):
                    # yes it changed. update display
                    scale_n_mode = self.scales.harmony_get_scale_name_with_mode()
                    self._display.write_xy_mem(scale_n_mode, 0, 2)
                    self._display.update_screen()
                    self.scale_update_leds(tonic)
                    ###
            return True
        
        ### processing of Control Buttons and knobs starts here   
        ### because we set up push1_consts.py this way, it's so easy 
        ### to get differnt controls CC,PC,Note_on,Note_of...
        ### so we get a very clean event-function. just name and function call.
        search_key = [ev[0], ev[1]] # build search key from event
        if ev[2] > 0: # just btn down eventes
            match search_key:                
                case ABL.BTN_R2_C1:
                    helper_set_new_tonic(0); return True    
                case ABL.BTN_R2_C2:
                    helper_set_new_tonic(1); return True
                case ABL.BTN_R2_C3: 
                    helper_set_new_tonic(2); return True
                case ABL.BTN_R2_C4: 
                    helper_set_new_tonic(3); return True
                case ABL.BTN_R2_C5: 
                    helper_set_new_tonic(4); return True
                case ABL.BTN_R2_C6: 
                    helper_set_new_tonic(5); return True
                case ABL.BTN_R2_C7: 
                    helper_set_new_tonic(6); return True
                case ABL.BTN_R2_C8: 
                    helper_set_new_tonic(7); return True
                case ABL.BTN_R1_C5: 
                    helper_set_new_tonic(8); return True
                case ABL.BTN_R1_C6: 
                    helper_set_new_tonic(9); return True
                case ABL.BTN_R1_C7: 
                    helper_set_new_tonic(10); return True
                case ABL.BTN_R1_C8: 
                    helper_set_new_tonic(11); return True   
                    
                # Display Knobs here      
                # knobs
                case ABL.KNOB_7: # scale
                    self.scales_set_tonic(ev[2]); return True
                case ABL.KNOB_8: # mode
                    self.scales_set_mode(ev[2]); return True  
                
                # Octave Buttons
                case ABL.BTN_OCTAVE_UP:
                    self.shift_note += 12
                case ABL.BTN_OCTAVE_DOWN:
                    self.shift_note -= 12
                      
                case _:
                    return False # event not for any of the defined buttons
                
              
        return False           


##################     END   of scales fucntions     ##########################################################
###############################################################################################################

#######################################################################################    
###             Mixer FUNCTIONS FOR DISPLAY ACTION from zynmixer.                   ###
        
    # def mixer_helper_bar(self, value) -> str:
    #     field_width =  8# width of anzeige
    #     int_val = int(value * field_width)
    #     if float(value) > 0.0: # always minimum 1 bar if any sound!
    #         int_val += 1
    #     erg = "".ljust(int_val,chr(6)).ljust(10)[:field_width]
    #     # erg = "".ljust(int(value*10),"|").ljust(15)[:field_width]
    #     return erg 
    
    def mixer_helper_write_to_knobx_fieldy(self, text: any, knob_x:int, field_y:int, as_bar:bool = False):
        """writes to a specified place below a knob
           knob_x is the knob from 0 to 7 (push_1 has 9 knobs, but nith has no display)
           field_y is the row written to see consts: _MIXER_DISP_ROW_* 
           text can be text or float value
        """
        if knob_x > 7:
            knob_x = 7
            logging.error("knob_x bigger 7 not implemented. Sum channel is directed to 7")
        if isinstance(text, (int, float)): # when text of type float or int  change it to str
            if as_bar: 
                text = self.mixer_helper_float_to_ascii_Bar(text)
            else:
                text = str(text)
            
        fields_start_knobs  = [0,9, 17,26, 34,43,  51,60]
        knobx_start = fields_start_knobs[knob_x]
        text=text.ljust(8)[:8] # make text with minimal 10 and max 10 chars
        self._display_mixer.write_xy_mem(text, knobx_start, field_y)        
        
    def mixer_helper_float_to_ascii_Bar(self, value:float):
        fieldlen = 8
        int_val = int(value * fieldlen) # val is 0.0 to 1.0. we want range 0-7
        return "".ljust(int_val, chr(6)).ljust(fieldlen) # fill up with spaces to overwrite old values

    def mixer_init(self):
        """mixer display functions are called during start. 
           Mixer is main functionality, so it hast to be setup in intit _function
        """
        # create consts for mixer display
        self.MIXER_DISP_ROW_VOLUME = 0
        self.MIXER_DISP_ROW_BALANCE = 1
        self.MIXER_DISP_ROW_3 = 2
        self.MIXER_DISP_ROW_4 = 3
            
        self._display_mixer = Feedback_Display(self.idev_out);
        self.mixer_set_dev_to_mixermode()
        
        return
    

    def mixer_set_dev_to_mixermode(self):
                
        # creat private mixer display
        
        btn_txt_row0 = "| Ch 1 | Ch 2   | Ch 33 | Ch 4 || Ch 5  | Ch 6   | Ch 7  | Ch 8  |"
        btn_txt_row1 = "        | This is the Mixer Display                                 "
        btn_txt_row2 = f"|modes here   {chr(5)} {chr(6)} {chr(5)}{chr(6)}  |           |"
        btn_txt_row3 = "|       |       |      |       ||       |        |       |       |"
        
        btn_text_row2 = self._display_mixer.format_help
        
        self._display_mixer.write_xy_mem(btn_txt_row0, 0, 0)
        self._display_mixer.write_xy_mem(btn_txt_row1, 0, 1)
        self._display_mixer.write_xy_mem(btn_txt_row2, 0, 2)
        self._display_mixer.write_xy_mem( "Volume Mode".ljust(20)[:15], 0, 2 ) # Mode of knobs
        self._display_mixer.write_xy_mem(btn_txt_row3, 0, 3)
        self._display_mixer.update_screen()
        
        # paint into tha test data
        ch1_level = self.zynmixer.zctrls[0]['level'].get_value() # is this a set level or the real sound lovel
        ch1_level_bar = self.mixer_helper_float_to_ascii_Bar(ch1_level)
        first_knob_nr = 0
        self.mixer_helper_write_to_knobx_fieldy(ch1_level_bar,  first_knob_nr, self.MIXER_DISP_ROW_VOLUME)
               
        self._display_mixer.update_screen()# send display_data to display


    def mixer_cleanup(self):
        pass

    ### just copy the derived functions in the this driver and implement them accordingly 
    # DONT CHANGE FUNC NAME (is inherited)
    def update_mixer_active_chain(self, active_chain):
        """Update hardware indicators for active_chain"""
        
        try:
            mix_state = self.zynmixer.get_state()
            volume = self.zynmixer.zctrls[0]['level'].get_value()
            for c in mix_state.keys():
                if c[:5] == "chan_":
                    chan_nr = int(c[5:7])
                    ch_level = self.zynmixer.zctrls[chan_nr]['level'].get_value() # we use level from here, so we no field exists
                    ch_level_bar = self.mixer_helper_float_to_ascii_Bar(ch_level)
                    self.mixer_helper_write_to_knobx_fieldy(ch_level_bar, chan_nr, self.MIXER_DISP_ROW_VOLUME)

                    # write names
                    # Check if chain exists
                    # if zynmixer.get_chain_level(chain_index) is not None:
                        # Namen von der Engine holen
                    #engine_index = self.zynmixer.get_chain_engine(chan_nr)
                    #engine_info = lib_zyncore.get_engine_info(engine_index)
                    # name = engine_info.get('name', f"CH{chan_nr}")
                    # name = self.zynmixer.get_chain_name(chan_nr)
                    # name = self.zynmixer.
            self._display_mixer.update_screen()    
            # logging.error(f"not implemented active_chain: {active_chain}")
            return
        except Exception as e:
            logging.error(f"Error in update_mixer_active_chain: {e}")
            logging.exception(traceback.format_exc())
            
            
            
            
            
    # DONT CHANGE FUNC NAME (is inherited)    
    def update_mixer_strip(self, chan, symbol, value):
        """Update hardware indicators for a mixer strip: mute, solo, level, balance, etc.
        *SHOULD* be implemented by child class

        chan - Mixer strip index
        symbol - Control name
        value - Control value
        """
        
        try:
            match symbol:
                case 'level':
                    if chan > 7: 
                        chan = 7
                    self.mixer_helper_write_to_knobx_fieldy(value, chan, self.MIXER_DISP_ROW_VOLUME, as_bar=True)
                    self._display_mixer.update_screen()
                    return  # Wichtig: Return nach erfolgreicher Verarbeitung!
                
                case 'balance': 
                    # Implementierung für balance
                    pass
                
                case 'mute':
                    # Implementierung für mute
                    pass
                
                case 'solo':
                    # Implementierung für solo
                    pass
                
                case 'mono':
                    # Implementierung für mono
                    pass
                
                case 'm+s': # Mono / Stereo
                    # Implementierung für m+s
                    pass
                
                case 'phase':
                    # Implementierung für phase
                    pass
                
                case _:
                    # Fall für unbekannte symbols
                    logging.debug(
                        f"Update mixer strip for {type(self).__name__}: UNKNOWN SYMBOL! chan: {chan}; symbol: {symbol} value: {value}")
                    return
            
            # Diese Zeile wird nur erreicht, wenn ein Case gematcht aber nicht behandelt wurde
            logging.debug(
                f"Update mixer strip for {type(self).__name__}: NOT IMPLEMENTED! chan: {chan}; symbol: {symbol} value: {value}")

        except Exception as e:
            logging.error(f"Error in update_mixer_strip: {e}")
            logging.exception(traceback.format_exc())
        
    def process_mixer_event(self, ev) -> bool:
        #self.zyn
        #self.zynmixer.setlevel()
        pass
    
    
###                END of Mixer functions.                            ###
#########################################################################


#########################################################################
###           Start of Sequencer / Pad Functions                      ###
    def process_sequencer_event(self, ev) -> bool:
        """event function in sequencer state"""
        # if using shift button with knob, then not following we are not in any mode
        # if not self.device_mode_active == self.DEV_MODE_MIXER: # keyboard modus is selected
        #     return False #  we ignored here any event, we are not in Sequencer mode
        

   
    # tzynseq updates LED states
    # we have update pad LED to show state
    # DONT CHANGE FUNC NAME (is inherited)
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
                        vel = self.RUNNING_COLOR
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

    # for LED feedback bei pad mode (Sequencer)
    # DONT CHANGE FUNC NAME (is inherited)
    def refresh(self): # form zynseq classe
        # if not filtered, the pad loop kills any other LED setup
        if self.device_mode_active == self.DEV_MODE_PAD:
            return super().refresh()

    # DONT CHANGE FUNC NAME (is inherited)
    def pad_off(self, col, row):
        # note = 96 + row * 16 + col # statt 96 -> 91 für Push
        note = ABL_PAD_END +1 -(row+1) * 8 + col  # recalculate midi note from col and row
        # logging.info(f"BRUMBY: row={row}; col={col} pad-note={note}")
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    # scenebuttons = right from pads
    def sequencer_set_scene(self, ccnum):
        # seams inconsistent, GUI says Scene. Api is: select Bank, or I misunderstood
        self.zynseq.select_bank (8- (ccnum - 36)) 
        # change LED state
        for t in [ 36,37,38,39,40,41,42,43]:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, t, ABL.MONO_LED_DIM) # 2!
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, ABL.MONO_LED_LIT_BLINK_FAST) # 2!
        return True        
        
        
    def process_sequencer_event(self, ev) -> bool:
        """event function in sequencer state"""
        if not self.device_mode_active == self.DEV_MODE_PAD: # keyboard modus is selected
            return False #  we ignored here any event, we are not in Sequencer mode
        
        cc = ev[1] # controller used to calculate bank. keys are in line
        # cc_val=ev[2]
        
        search_key = [ev[0], ev[1]]
        if ev[2] > 0: # just btn down eventes
            match search_key:                
                case ABL.BTN_BEAT_1_QUATER:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_2_QUATER_T:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_3_EIGHTH:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_4_EIGHTH_T:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_5_SIXTEENTH:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_6_SIXTEENTH_T:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_7_THIRTYSECOND:
                    return self.sequencer_set_scene(cc)
                case ABL.BTN_BEAT_8_THIRTYSECOND_T:
                    return self.sequencer_set_scene(cc)
                case _: 
                    pass
                     
        
        evtype = (ev[0] >> 4) & 0x0F
        note = ev[1] & 0x7F
        
        ### Program Change Event from Push 1 # It doesn't send such !!! just for explanatioin
        # We filter them out. Push 1 has no midi in and sends nor PC. 
        #  Or should we leave them in. 
        if evtype == self.EV_PC: # 0xC:
        ##     val1 = ev[1] & 0x7F
        ##     self.zynseq.select_bank(val1 + 1) #### That would shange Bank /Scene in Sequencer. We do it with Beat_Buttons
             return True #  
         
         
        # we do pad calculation with pads numbered woth control registers
        if evtype == self.EV_NOTE_ON: # 0x9: # fitler just for note_on events
            # all Pads send note_on events
            # push are oriented buttom left to top right with cc 36 to 99 eq C2 to Eb7
            try:
                pad_nr = note - ABL_PAD_START# eq C2 or ABL.PAD_36# so padnr ranges from 0 - 63 eq (range(64)
                col = pad_nr // 8 # 
                row = pad_nr % 8  # 
                col = 7 - col; # midi notes start from bottom, so recalculate row   
                
                # don't understand following XXXXXXXXXXXXXXXXX
                pad = row * self.zynseq.col_in_bank + col 
                logging.debug(f"BRUMBY: row={row}; col={col}; pad={pad}")
                if pad < self.zynseq.seq_in_bank:
                    # this is the complete magic. Start and stop a track in a scene (bank)
                    self.zynseq.libseq.togglePlayState(self.zynseq.bank, pad) # yes Scene is bank !!!
                    return True 
            except:
                pass
            
        
    ###############          End of derived Sequencer Functions.                  #####################
    ###################################################################################################

    # Just for me a helper function to set all pads off
    def pads_off(self):
        
        # logging.debug("BRUMBY: pads_off")
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

    def set_device_mode_new(self, new_mode):
        try:
            if new_mode == self.device_mode_active: return # devmode was same
            
            # clean up old device state
            # NO USE RETURNS
            match self.device_mode_active:
                case self.DEV_MODE_MIXER:
                    # deinit mixer
                    lib_zyncore.dev_send_ccontrol_change(
                        self.idev_out, 0, ABL.BTN_VOLUME[1], ABL.MONO_LED_LIT)
                    self.mixer_cleanup()
                    
                case self.DEV_MODE_PAD:
                    # there is no cleanup. do following
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_USER[1], ABL.MONO_LED_LIT)
                    self.pads_off()                
                    
                case self.DEV_MODE_SCALES:
                    # deinit  scales mode
                    self.scales_cleanup()
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT)
                    self.pads_off() # clean up visible state. all pad leds off
                    
            # now you can save new active mode        
            self.device_mode_active = new_mode
            
            # Now Setup new device mode
            # HERE USE RETURNS
            match new_mode:
                case self.DEV_MODE_MIXER:
                    # init mixer
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_VOLUME[1], ABL.MONO_LED_LIT_BLINK)
                    return self.mixer_set_dev_to_mixermode()
                    
                case self.DEV_MODE_PAD:
                    self.refresh() # refreshe LEDs for Sequencer mode of this driver.
                    # there is no clean_up method. so do following
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_USER[1], ABL.MONO_LED_LIT_BLINK)
                    
                case self.DEV_MODE_SCALES:
                    self.scales_set_dev_to_scales_mode()
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ABL.BTN_SCALES[1], ABL.MONO_LED_LIT_BLINK)
                    
            
                case _:
                    # code not defined 
                    logging.error("DEVICE Mode not defined. Programming Error")
                    
            # if not done till now, mark as succed        
            return True #  Whatever event is processed   
        
        except Exception as e:
            logger.error(f"Error in set_device_mode_new: {e}")
            logger.exception(traceback.format_exc())
           
       



    def midi_event(self, ev):
        
        ### For debugging purposes block can be commented out !
        dbg = True
        if len(ev) > 1 and dbg:
            search_key = [ev[0], ev[1]] # ev to search_key
            btn_name = self.button_name_from_midi_event(search_key) # ev[0] and ev[1] fields are proved. so any status can be a button 
            if not btn_name == "": # just log known btns
                logger.debug(f"Button: {btn_name} on chan. {ev[0] & 0x0F} gives midi_event: {hex(ev[0])} {hex(ev[1])} {hex(ev[2])} = {int(ev[1])}, {int(ev[2])}, {int(ev[2])}")

        evtype               = None
        chan_or_instruction  = None
        note_or_register     = None
        val_or_vel           = None
        
        ### end of debug
        
        if len(ev) > 1: # Btn is possible
            
            if len(ev) > 2: 
                val_or_vel = ev[2]
                is_key_push = val_or_vel > 0
                
            search_key = [ev[0], ev[1]] # ev to search_key
            match search_key:
                    case None:
                        pass
                    case ABL.BTN_SHIFT: # as momentary button NOT toggle! has to be hold for functions change
                        self.shift =  is_key_push # set shift variable. but just momenatary
                        # visual feedback with button LED
                        if self.shift:
                            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL.MONO_LED_LIT_BLINK)
                        else: # key is teleased
                            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 49, ABL.MONO_LED_DIM)
                        return True # event processed. No further action required
             
                    case ABL.BTN_VOLUME: # mode change to mixer? It isn't best chosen.
                        if is_key_push:
                            return self.set_device_mode_new(self.DEV_MODE_MIXER)                        
                    
                    case ABL.BTN_SCALES:    
                        if is_key_push:
                            return self.set_device_mode_new(self.DEV_MODE_SCALES)
                    
                    case ABL.BTN_USER:
                        if is_key_push:
                            return self.set_device_mode_new(self.DEV_MODE_PAD)
                    case _:
                        pass
                    
        # try to process the ev with active mode
        match self.device_mode_active:
            case self.DEV_MODE_MIXER:
                if self.process_mixer_event(ev): # dom't return if  False
                    return True
            case self.DEV_MODE_PAD:
                if self.process_sequencer_event(ev):
                    return True
            case self.DEV_MODE_SCALES:
                if self.process_scale_event(ev):
                    return True
            case _:
                pass # no actual devicemode
         
        # if nothing els then
        #if self.process_scale_event(ev):
        #    return True  
            
        # now the Gui events. 
        # Gui events moved to:
        if self.process_gui_events(ev): return True
        
        # nothing below the line ???
        return False # that should be all
 


    #########  GUI EVENTS     ####################################
    # to clean up the code GUI events are processed here
    def process_gui_events(self,ev) -> bool:
        
        # on this device any button or knob we use sends 3-byte-events
        # otherwise event is no control 
        if not len(ev) >= 3: return False
        
        # bild button search event
        search_key = [ev[0], ev[1]]
        data_val = ev[2] & 0x7F
        
        # TODO remove if knob ease is fine
        # # make left turs on knobs negative
        # def helper_knob_calculation(ccval):
        #     if ccval > 64: ccval -= 128
        #     return ccval 
        # # this could be changed to 
        # # delta = self._knobs_ease.feed(btn_id, ev[2], self._is_shiftedxxx)
        # data_val_for_knobs = helper_knob_calculation(data_val)
        
        match search_key:
            
            # Knobs
            case ABL.KNOB_1:
                # translate 127 to -1 and slow down
                delta = self._knobs_ease.feed(bytes(ABL.KNOB_1), data_val, is_shifted=False) 
                self.state_manager.send_cuia("ZYNPOT", [0, delta]); return True
                # self.state_manager.send_cuia("ZYNPOT", [0, data_val_for_knobs]); return True
            case ABL.KNOB_2:
                delta = self._knobs_ease.feed(bytes(ABL.KNOB_1), data_val, is_shifted=False) 
                self.state_manager.send_cuia("ZYNPOT", [1, delta]); return True
            case ABL.KNOB_3:
                delta = self._knobs_ease.feed(bytes(ABL.KNOB_3), data_val, is_shifted=False) 
                self.state_manager.send_cuia("ZYNPOT", [2, delta]); return True
            case ABL.KNOB_4:
                delta = self._knobs_ease.feed(bytes(ABL.KNOB_4), data_val, is_shifted=True)
                self.state_manager.send_cuia("ZYNPOT", [3, delta]); return True
                # self.state_manager.send_cuia("ZYNPOT", [3, data_val_for_knobs]); return True
            case _: pass
        
        if data_val > 0: # just key-down events
            match search_key:
                # Buttons
                case ABL.BTN_OK, ABL.BTN_R1_C3:
                    self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [3,"S"]); return True
                case ABL.BTN_R1_C1:
                    self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [0,"S"]) ; return True    
                case ABL.BTN_R1_C2:
                    self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [1,"S"]) ; return True    
                case ABL.BTN_R1_C3:
                    self.state_manager.send_cuia("V5_ZYNPOT_SWITCH",  [2,"S"]) ; return True    
                
                case ABL.BTN_ESC:
                    self.state_manager.send_cuia("BACK"); return True
                case ABL.BTN_RIGHT:
                    self.state_manager.send_cuia("ARROW_RIGHT"); return False
                case ABL.BTN_LEFT:
                    self.state_manager.send_cuia("ARROW_LEFT"); return False
                case ABL.BTN_UP: #  CC46
                    self.state_manager.send_cuia("ARROW_UP"); return True
                case ABL.BTN_DOWN:
                    self.state_manager.send_cuia("ARROW_DOWN"); return True
                case ABL.BTN_START: # ehemals ABL_PLAY:
                    if self.shift: # shift button pressed
                        self.state_manager.send_cuia("TOGGLE_MIDI_PLAY"); return True
                    else:
                        self.state_manager.send_cuia("TOGGLE_PLAY"); return True
                case ABL.BTN_REC: # ABL_REC:
                    if self.shift:
                        self.state_manager.send_cuia("TOGGLE_MIDI_RECORD"); return True
                    else:
                        self.state_manager.send_cuia("TOGGLE_RECORD"); return True
                case _: pass
               
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
                    # logging.debug(f"midi_event {ev} {ev[0]}, {ev[1]}, from Button with name: {name} and value: {data}")
                    return name
        # logging.debug(f"midi_event {ev} from Button not defined with value: {data}")
        return "" # "<event is no button-evemt or button is missing in config file.>"
        
          
    def set_pad_rgb(self, pad_nr: int, r:int ,g:int ,b:int):
        logging.error(" set_pad_rb aufgerufen. not implemented")
        # # Sysex : 240,71,127,21,4,0,8,<Pad(0-71)>,0,<r1>,<r2>,<g1>,<g2>,<b1>,<b2>,247
        # # pad = 0-71  NICHT PAD_36 - PAD_99 
        # # blogspot.com
        # # To set a pad color to a RGB(0-255) value, the RGB values need to be set into "Push" format, for example:
        # # r1 = r /(integer division) 16 
        # # r2 = r %(modulo) 16
        # # So a value of R132 would become: r1=8 r2=4.
        # # The pad index if from 0 to 71, zero being the bottom left pad, all the way up to the second row button to the right (second row of buttons is RGB).
        # if r > 255: r = 255; 
        # if r < 0: r = 0
        # if g > 255: g = 255; 
        # if g < 0: g = 0
        # if b > 255: b = 255; 
        # if b < 0: b = 0
        # if not 0 <= pad_nr <= 64: 
        #     logging.error(f"Padnr wrong. not in 1..64 pad_nr = {pad_nr}")
        #     return False
        #
        # r1= r // 16  ; r2= r % 16
        # g1= g // 16  ; g2= g % 16
        # b1= b // 16  ; b2= b % 16
        # sysex = bytes ([240,71,127,21,4,0,8,pad_nr,0,r1,r2,g1,g2,b1,b2,247] )   
        # lib_zyncore.dev_send_midi_event(self.idev_out, sysex, len(sysex))

   
# ------------------------------------------------------------------------------




class Feedback_Display:
    
    #// Special Dispay Characters
    # char0) bis cahr(31) order by Symbol_name
    # char(32) to char(127) is like ASCII
    # partly from https://pushmod.blogspot.com has no valid evmail adress, so I couldnt send him the updated list!
    # login per google didnt work on his blog for safte reasons. What a pitty, I wanted to thank for his work with the complete list 
    # of symbos
 
    DISP_ARROW_UP                          =  0   # ↑ (U+2191)
    DISP_ARROW_DOWN                        =  1   # ↓ (U+2193)
    DISP_ARROW_RIGHT                       =  30  # → (U+2192)
    DISP_ARROW_LEFT                        =  31  # ← (U+2190)

    DISP_HORIZONTAL_LINES_THREE_STACKED    =  2   # ≡ (U+2261)
    DISP_HORIZONTAL_LINE_LOW               =  95  # _ (U+005F) Lowbar
    DISP_HOIZONTAL_LINE_SPLIT              =  6   # ╌ (U+254C) LIGHT DOUBLE DASH HORIZONTAL

    DISP_VERTICAL_LINE_AND_HORIZONTAL_LINE =  3   # ┤ (U+2524)
    DISP_HORIZONTAL_LINE_AND_VERTICAL_LINE =  4   # ├ (U+251C)

    DISP_VERTICAL_LINES_TWO                =  5   # ║ (U+2551)
    DISP_VERTICAL_LINE_MID                 =  174 # | (U+007C)
    DISP_SPLIT_VERTICAL_LINES              =  8   # ⫼ (U+2AFC)

    DISP_FOLDER_SYMBOL                     =  7   # 📁 (U+1F4C1)
    DISP_FLAT_SYMBOLS                      =  27  # ♭ (U+266D)
    DISP_THREE_SIDE_BY_SIDE_DOTS           =  28  # ⋮ (U+22EE)
    DISP_FULL_BLOCK                        =  29  # █ (U+2588)
    DISP_LITTLE_BOX_SHIFTED_HIGH_MIDDLE    =  9   # ▫ (U+25AB) Little box shifted high middle

    DISP_AE_UC                             =  10  # Ä (U+00C4)
    DISP_CEDILLE_UC                        =  11  # Ç (U+00C7)
    DISP_OE_UC                             =  12  # Ö (U+00D6)
    DISP_UE_UC                             =  13  # Ü (U+00DC)
    DISP_SZ                                =  14  # ß (U+00DF)
    DISP_A_GRAVE                           =  15  # à (U+00E0)
    DISP_AE_LIC                            =  16  # ä (U+00E4)
    DISP_CEDILE                            =  17  # ç (U+00E7)
    DISP_E_LC_GRAVE                        =  18  # è (U+00E8)
    DISP_E_LC_EGUT                         =  19  # é (U+00E9)
    DISP_E_LC_CIRCUM                       =  20  # ê (U+00EA)
    DISP_I_LC_TREMA                        =  21  # ï (U+00EF)
    DISP_N_LC_WITH_TILDE                   =  22  # ñ (U+00F1)
    DISP_OE_LC                             =  23  # ö (U+00F6)
    DISP_DIV_STROKE                        =  24  # ⁄ (U+2044)
    DISP_CIRC_WITH_DIV_STROKE              =  25  # Ø (U+00D8)
    DISP_UE_LC                             =  26  # ü (U+00FC)


    # with 32 (SPACE) starts pritable part from ASCII-Table
    akai_to_unicode = {
        # Pfeile
        0: "↑",    # DISP_ARROW_UP (U+2191)
        1: "↓",    # DISP_ARROW_DOWN (U+2193)
        30: "→",   # DISP_ARROW_RIGHT (U+2192)
        31: "←",   # DISP_ARROW_LEFT (U+2190)
        
        # Horizontale Linien
        2: "≡",    # DISP_HORIZONTAL_LINES_THREE_STACKED (U+2261)
        6: "╌",    # DISP_HOIZONTAL_LINE_SPLIT (U+2550)
        95: "_",   # DISP_HORIZONRAL_LINE_LOW (U+005F) # might not look same
        
        # Kombinierte Linien
        3: "┤",    # DISP_VERTICAL_LINE_AND_HORIZONTAL_LINE (U+2524)
        4: "├",    # DISP_HORIZONTAL_LINE_AND_VERTICAL_LINE (U+251C)
        
        # Vertikale Linien
        5: "║",    # DISP_VERTICAL_LINES_TWO (U+2551)
        8: "⫼",    # DISP_SPLIT_VERTICAL_LINES (U+2AFC)
        174: "|",  # DISP_VERTICAL_LINE_MID (U+007C) #  might not look same
        
        # Symbole
        7: "📁",   # DISP_FOLDER_SYMBOL (U+1F4C1)
        27: "♭",   # DISP_FLAT_SYMBOLS (U+266D)
        28: "⋮",   # DISP_THREE_SIDE_BY_SIDE_DOTS (U+22EE)
        29: "█",   # DISP_FULL_BLOCK (U+2588)
        9: "▫",    # DISP_HIGH_LITTLE_BOX (U+25AB - Kleines hochgestelltes Kästchen)
        
        # Umlaute und Sonderzeichen
        10: "Ä",   # DISP_AE_UC (U+00C4)
        11: "Ç",   # DISP_CEDILLE_UC (U+00C7)
        12: "Ö",   # DISP_OE_UC (U+00D6)
        13: "Ü",   # DISP_UE_UC (U+00DC)
        14: "ß",   # DISP_SZ (U+00DF)
        15: "à",   # DISP_A_GRAVE (U+00E0)
        16: "ä",   # DISP_AE_LC (U+00E4)
        17: "ç",   # DISP_CEDILE (U+00E7)
        18: "è",   # DISP_E_LC_GRAVE (U+00E8)
        19: "é",   # DISP_E_LC_EGUT (U+00E9)
        20: "ê",   # DISP_E_LC_CIRCUM (U+00EA)
        21: "ï",   # DISP_I_LC_WITH_3_POINTS_ABOVE (U+00EF - i mit Trema)
        22: "ñ",   # DISP_N_LC_WITH_TILDE (U+00F1)
        23: "ö",   # DISP_OE_LC (U+00F6)
        24: "⁄",   # DISP_DIV_STROKE (U+2044)
        25: "Ø",   # DISP_CIRC_WITH_DIV_STROKE (U+00D8)
        26: "ü",   # DISP_UE_LC (U+00FC)
    }
    
    format_help = b'123456789A123456789B123456789C123456789D123456789E123456789F123456789'
        
    
    display_mem = [[32] * 68 for _ in range(4)] # 4 Zeilen mit 68 Spalten
    # _disp_line_dirty =[False, False, False, False]        
            
            
    def __init__ (self, idev_out):
        # self.dbg = True
        self.idev_out = idev_out
        self._disp_line_dirty =[False, False, False, False]
        # if self.dbg: 
        #logging.error(f"BRUMBY: Class Display instantiiert")



    def clear (self):
        """Overwrites whole display with ascii 32""" 
        # logging.info(f"Display.clear: end of func idev_out={self.idev_out}")
      
        # clear out display_memory with blanks.
        self.display_mem = [[32] * 68 for _ in range(4)] # 4 Zeilen mit 68 Spalten
            
        # SYSEX_ZEILE_LÖSCHEN = 240,71,127,21,<28+line(0-3)>,0,0,247
        s0 = bytes([240,71,127,21,28,0,0,247]) # Zeile 0
        s1 = bytes([240,71,127,21,29,0,0,247]) # Zeile 1
        s2 = bytes([240,71,127,21,30,0,0,247]) # Zeile 2
        s3 = bytes([240,71,127,21,31,0,0,247]) # Zeile 3
        for x in  [s0, s1, s2, s3]:
            lib_zyncore.dev_send_midi_event(self.idev_out, x, len(x))
            sleep(0.01)
        self._disp_line_dirty =[False, False, False, False]


    def update_screen (self):
        # move display memory to display with sysex
        for row in range(4):
            if self._disp_line_dirty[row]:
                #msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])
                text = bytes(self.display_mem[row])
                text_len = len(text)
                col = 0
                # here the magic happens and sysex is cunstructed
                #            240, 71, 127, 21, <24+line(0-3)>,0,   <Nchars+1>,<Offset>,<Chars>,      247
                msg = bytes([240, 71, 127, 21, row+24,        0,   text_len+1,  col]) + text+ bytes([247])
                # logging.error(f"BRUMBY: Display.update SYSEX={msg}")
                lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
                sleep(0.01)
                self._disp_line_dirty[row] = False
        return
           

    def write_xy_mem (self, text, col_in:int, row_in:int):
        # writes to display memory at Position col_in, row_in in display memory und auf Display
        # mit update
        
        #convert text to bytes
        if isinstance(text, str):
            # print("Die Variable ist ein String (Text)")
            text = text.encode()
        elif isinstance(text, bytes):
            # print("Die Variable ist Bytes")
            pass # is fine
        elif isinstance(text, (int, float)): # is a number?
            text = str(text).encode()
        else:
            # print("type error")
            text = "Typeerror in textconversion".encode()
        
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
        self._disp_line_dirty[row_in] = True
        # self.update()
        return
        
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
        
        ### send sysexrequest
        ### Contrast request	240,71,127,21,122,0,0,247
        # msg = bytes([240,71,127,21,122,0,0,247])
        # lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
        ### Return Contrast. Not implemented. Must be in event chain ais sysex anwser
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

        # Return Brightnes. Not implemented. Answer comes as sysex in event chain
        return None
    
    def first_screen(self):
        self.clear()
        # self.brightnes(36)
        sleep(0.1)
        #self.write_xy_mem(b'* Pot 1 * Pot 2 ** Pot 3 * Pot 4 *', 0,0)
     #  Positionierungshilfe
        #self.write_xy_mem(b'123456789A123456789B123456789C123456789D123456789E123456789F123456789', 0,1)
        self.write_xy_mem(b'** Zynthian Push1Driver 0.1 **', 17,2)
        self.write_xy_mem(b'++  Make MusicNot War ++', 20,3)
        self.update_screen()
        return



# --------------------------------------------------------------------------
# Feedback LEDs controller
# --------------------------------------------------------------------------
class Feedback_Mono_LEDs:
                #Takt          Notenlängen               Pfeile        Track-Modifier        Copy/Del/undo 
    _all_mono = [3,9,  28,29,  36,37,38,39,40,41,42,43,  44,45,46,47,  48,49,50,51,52,53,54,55,56,57,58,59,61,62,63,  85,86,87,88,89,90,  110,111,11,113,114,115,   116,117,118,119, ]
    
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()
        
    def all_off(self, overlay = False):
        for note in self._all_mono:
           lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, 0)
           if not overlay:
               self._led_state[note] = 0
        return
    
    
    def set_mono(self, note:int, grey_val:int, overlay=False):
        lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, grey_val) # grey_val something of ABL.MONO_LED_DIM) 
        if not overlay:
               self._led_state[note] = 0
        return
    
    def refresh_one(self, note):
        if self._led_state[note]: # is one saved?
            lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, self._led_state[note])
        
    def refresh(self):
        for note in self._all_mono:
            if self._led_state[note]:
                lib_zyncore.dev_send_ccontrol_change(self._idev, 0, note, self._led_state[note])
                
    
class Feedback_Bi_LEDs:
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()

    def all_off(self):
        pass
        
# RGB LED Class for the pads rgb-LEDs           
class Feedback_RGB_LEDs:
    
    # _led_states = {}
    
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()
        self._led_state = {}

    def all_off(self, overlay):
        for pad_nr in range(ABL_PAD_END+1-ABL_PAD_START):
            self.set_rgb(pad_nr,0,0,0, overlay)
            if not overlay:
               self._led_state[pad_nr] = [0,0,0]
        return
    
    def refresh(self): # whole array of pads
        for pad_nr in range(ABL_PAD_END+1-ABL_PAD_START):
            self.refresh_one(pad_nr)
    
    
    def refresh_one(self, pad_nr): # get back to saved value
        self.set_rgb(pad_nr, self._led_state[pad_nr][0], self._led_state[pad_nr][1], self._led_state[pad_nr][2])
        
    
    def off_col_row(self, col, row):
        # note = 96 + row * 16 + col # statt 96 -> 91 für Push
        note = ABL_PAD_END +1 -(row+1) * 8 + col  # recalculate midi note from col and row
        # logging.info(f"BRUMBY: row={row}; col={col} pad-note={note}")
        lib_zyncore.dev_send_note_on(self._idev, 0, note, 0) # this is palette mode.

    def set_rgb(self, pad_nr: int, r:int ,g:int ,b:int, overlay=False):
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
        
        # self._led_state.setdefault(pad_nr, []).append(i)
        if not overlay:
            self._led_state[pad_nr] = [r,g,b]
        
        r1= r // 16  ; r2= r % 16
        g1= g // 16  ; g2= g % 16
        b1= b // 16  ; b2= b % 16
        sysex = bytes ([240,71,127,21,4,0,8,pad_nr,0,r1,r2,g1,g2,b1,b2,247] )   
        # lib_zyncore.dev
        lib_zyncore.dev_send_midi_event(self._idev, sysex, len(sysex))


