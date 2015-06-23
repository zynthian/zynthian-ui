#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Zynthian GUI

This is the main file for the Zynthian GUI

author: José Fernandom Moyano (ZauBeR)
created: 2015-05-18
modified:  2015-05-18
"""

from os import listdir
from os.path import isfile, isdir, join
#from time import sleep
import alsaseq
import alsamidi
from tkinter import *
#from tkinter.ttk import *
#import threading
#import queue
from ctypes import *
#import string

#-------------------------------------------------------------------------------
# Define some Constants and Parameters for the GUI
#-------------------------------------------------------------------------------

width=320
height=240

bgcolor="#002255"
bg2color="#2c5aa0"
bg3color="#5f7aa2"
bordercolor="#0064fa"
textcolor="#0064fa"
lightcolor="#f8cf2b"

splash_image="./img/zynthian_gui_splash.gif"

#-------------------------------------------------------------------------------
# Intrument Bank Configuration
#-------------------------------------------------------------------------------

#bank_dir="/usr/share/zynaddsubfx/banks"
bank_dir="./software/zynaddsubfx-instruments/banks"

default_zcontrollers_config=(
	('modulation',1,80),
	('expression',11,80),
	('filter Q',71,80),
	('filter cutoff',74,80)
);

#-------------------------------------------------------------------------------
# Define some MIDI Functions
#-------------------------------------------------------------------------------

bank_msb_selected=0;
bank_lsb_selected=0;
prg_selected=0;

def set_midi_control(ctrl,val):
    alsaseq.output( (alsaseq.SND_SEQ_EVENT_CONTROLLER, 1, 0, 0, (0, 0), (0, 0), (0, 0), (0, 0, 0, 0, ctrl, val)) )

def set_midi_bank_msb(msb):
    bank_msb_selected=msb
    set_midi_control(0,msb)

def set_midi_bank_lsb(lsb):
    bank_lsb_selected=lsb
    set_midi_control(32,lsb)

def set_midi_prg(prg):
    bank_lsb=int(prg/128)
    prg=prg%128
    print("Set MIDI Bank LSB: " + str(bank_lsb))
    set_midi_bank_lsb(bank_lsb)
    print("Set MIDI Program: " + str(prg))
    prg_selected=prg
    event=alsamidi.pgmchangeevent(0, prg)
    alsaseq.output(event)

#-------------------------------------------------------------------------------
# Controller GUI Class
#-------------------------------------------------------------------------------
class zynthian_controller:
    width=77
    height=94
    trw=70
    trh=13

    def __init__(self, cnv, x, y, tit, ctrl, val=0):
        self.canvas=cnv
        self.x=x
        self.y=y
        self.title=tit
        self.ctrl=ctrl
        self.value=val
        self.plot_frame()
        self.plot_triangle()
        self.label_title = Label(self.canvas,
            text=self.title,
            wraplength=self.width-6,
            justify=LEFT,
            bg=bgcolor,
            fg=textcolor)
        self.label_title.place(x=self.x+3, y=self.y+4, anchor=NW)
        self.label_value = Label(self.canvas,
            text=str(self.value),
            bg=bgcolor,
            fg=lightcolor)
        self.label_value.place(x=self.x+3, y=self.y+int(0.7*self.height), anchor=NW)

    def plot_frame(self):
        x2=self.x+self.width
        y2=self.y+self.height
        self.canvas.create_polygon((self.x, self.y, x2, self.y, x2, y2, self.x, y2), outline=bordercolor, fill=bgcolor)

    def plot_triangle(self):
        if (self.value>127): self.value=127
        elif (self.value<0): self.value=0
        x1=self.x+2
        y1=self.y+int(0.8*self.height)+self.trh
        x2=x1+self.trw*self.value/127
        y2=y1-self.trh*self.value/127
        self.canvas.create_polygon((x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh-1), fill=bg2color)
        self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=lightcolor)

    def set_value(self, v):
        if (v!=self.value):
            self.value=v
            self.label_value.config(text=str(self.value))
            self.plot_triangle()

#-------------------------------------------------------------------------------
# Zynthian Splash GUI Class
#-------------------------------------------------------------------------------
class zynthian_splash:
    def __init__(self, tms=1000):
        # Add Background Image inside a Canvas
        self.canvas = Canvas(
            width = width,
            height = height,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg = bgcolor)
        self.canvas.create_image(0, 0, image = splash_img, anchor = NW)
        self.canvas.pack(expand = YES, fill = BOTH)
        top.after(tms, self.hide_splash)

    def hide_splash(self):
        self.canvas.pack_forget()

#-------------------------------------------------------------------------------
# Zynthian Listbox GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_list:
    width=162
    height=192
    
    def __init__(self, image_bg=None):
        list_data=[]
        
        # Add Background Image inside a Canvas
        self.canvas = Canvas(
            width = width,
            height = height,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg = bgcolor)
        if (image_bg):
            self.canvas.create_image(0, 0, image = image_bg, anchor = NW)
        self.canvas.pack(expand = YES, fill = BOTH)

        self.plot_frame();

        # Add ListBox
        self.listbox = Listbox( self.canvas,
            #width=19,
            #height=12,
            width=19,
            height=9,
            font=("Helvetica",11),
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=bgcolor,
            fg=textcolor,
            selectbackground=lightcolor,
            selectforeground=bgcolor)
        self.listbox.place(relx=0.5, rely=0.5, anchor=CENTER)
        self.listbox.bind('<<ListboxSelect>>', lambda event :self.click_listbox())

        # Add ListBox Buttons
        self.button_up = Button(self.canvas,
            width=17,
            height=1,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=bgcolor,
            activebackground=bgcolor,
            fg=textcolor,
            padx=1,
            pady=1,
            text=' ',
            compound='center',
            command=self.click_up)
        self.button_up.config(image = button_up_img, width=0, height=0)
        self.button_up.place(relx=0.5, y=1, anchor=N)

        self.button_down = Button(self.canvas,
            width=17,
            height=1,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=bgcolor,
            activebackground=bgcolor,
            fg=textcolor,
            padx=1,
            pady=1,
            text=' ',
            compound='center',
            command=self.click_down)
        self.button_down.config(image = button_down_img, width=0, height=0)
        self.button_down.place(relx=0.5, y=height-2, anchor=S)

    def hide(self):
        self.canvas.pack_forget()

    def show(self):
        self.canvas.pack(expand = YES, fill = BOTH)
        
    def plot_frame(self):
        rx=(width-self.width)/2
        ry=(height-self.height)/2
        rx2=width-rx-1
        ry2=height-ry-1
        self.canvas.create_polygon((rx, ry, rx2, ry, rx2, ry2, rx, ry2), outline=bordercolor, fill=bgcolor)

    def get_list_data(self):
        self.list_data=[]

    def fill_list(self):
        self.get_list_data()
        self.listbox.delete(0, END)
        for item in self.list_data:
            self.listbox.insert(END, item)

    def click_up(self):
        self.listbox.yview_scroll(-3, 'units')

    def click_down(self):
        self.listbox.yview_scroll(+3, 'units')

    def click_listbox(self):
        cursel=self.listbox.curselection()
        index=int(cursel[0])
        self.selected=self.list_data[index]
        self.select_action(index)

    def select(self, index):
        print('Selected: ' + str(index))

#-------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_list):

    def __init__(self):
        super().__init__(gui_bg)
        self.fill_list()
    
    def get_list_data(self):
        self.list_data=[]
        for f in sorted(listdir(bank_dir)):
            if isdir(join(bank_dir,f)):
                self.list_data.append(f)

    def select_action(self, index):
        set_midi_bank_msb(index)
        print('Bank Selected: ' + self.selected + ' (' + str(index)+')')
        zyngui_instr.fill_list(self.selected)
        self.hide()
        zyngui_instr.show()

#-------------------------------------------------------------------------------
# Zynthian Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_instr(zynthian_gui_list):

    def __init__(self):
        super().__init__(gui_bg)
        # Add Bank Button  (top-left)
        self.button_bank = Button(self.canvas,
            width=8,
            height=1,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=bgcolor,
            activebackground=bgcolor,
            activeforeground=textcolor,
            fg=textcolor,
            padx=1,
            pady=1,
            #font=("Helvetica",14),
            text=' ',
            compound='center',
            command=self.click_but_bank)
        self.button_bank.config(image = button_bank_img, width=0, height=0)
        self.button_bank.place(x=0, y=0, anchor=NW)
        
        # Add Selected Bank Title (bottom-left)
        self.bank_title = StringVar()
        self.label_bank = Label(self.canvas,
            font=("Helvetica",8),
            textvariable=self.bank_title,
            #wraplength=80,
            justify=LEFT,
            bg=bgcolor,
            fg=lightcolor)
        #self.label_bank.place(x=240, y=-2, anchor=NW) => top-right
        self.label_bank.place(x=0, y=220, anchor=NW)

        # Controllers
        self.zcontrollers_config=default_zcontrollers_config;
        self.zcontrollers=[]
        self.zcontrollers.append(zynthian_controller(self.canvas,-1,24,self.zcontrollers_config[0][0],self.zcontrollers_config[0][1],self.zcontrollers_config[0][2]))
        self.zcontrollers.append(zynthian_controller(self.canvas,-1,121,self.zcontrollers_config[1][0],self.zcontrollers_config[1][1],self.zcontrollers_config[1][2]))
        self.zcontrollers.append(zynthian_controller(self.canvas,243,24,self.zcontrollers_config[2][0],self.zcontrollers_config[2][1],self.zcontrollers_config[2][2]))
        self.zcontrollers.append(zynthian_controller(self.canvas,243,121,self.zcontrollers_config[3][0],self.zcontrollers_config[3][1],self.zcontrollers_config[3][2]))

        # Init Controllers Map
        self.zcontroller_map={}
        for zc in self.zcontrollers:
            self.zcontroller_map[zc.ctrl]=zc

        # Init Zyncoders (Rotary Encoders)
        try:
            global lib_rencoder
            lib_rencoder=cdll.LoadLibrary("midi_rencoder/midi_rencoder.so")
            if lib_rencoder.init_rencoder()>=0:
                for i, zc in enumerate(self.zcontrollers):
                    lib_rencoder.setup_zyncoder(i,zc.ctrl,zc.value)
                    print("Init Zyncoder: %s" % str(i))
            # Start Rencoder Monitoring
            self.rencoder_read();
        except Exception as e:
            print("Can't init Zyncoders: %s" % str(e))

        # Start MIDI Monitoring
        #self.midi_read();
        
    def set_controller_config(self, cfg):
        for i in range(0,4):
            self.set_controller(i,cfg[i][0],cfg[i][1],cfg[i][2]);

    def set_controller(self, i, tit, ctrl, val):
        del self.zcontroller_map[self.zcontrollers[i].ctrl]
        self.zcontrollers[i].title=tit
        self.zcontrollers[i].ctrl=ctrl
        self.zcontrollers[i].set_value(val)
        self.zcontroller_map[ctrl]=self.zcontrollers[i]
        try:
            lib_rencoder.setup_zyncoder(i,ctrl,val)
        except:
            pass

    def get_list_data(self, selected):
        self.list_data=[]
        instr_dir=join(bank_dir,selected)
        print('Getting Instrument List for ' + instr_dir)
        for f in sorted(listdir(instr_dir)):
            #print(f)
            if (isfile(join(instr_dir,f)) and f[-4:]=='.xiz'):
                prg=int(f[0:4])-1
                title=f[5:-4]
                self.list_data.append((f,prg,title))

    def fill_list(self, selected):
        self.bank_title.set(str.replace(selected, '_', ' '))
        self.get_list_data(selected)
        self.listbox.delete(0, END)
        for item in self.list_data:
            self.listbox.insert(END, item[2])

    def select_action(self, index):
        prg=self.list_data[index][1]
        print('Instrument Selected: ' + self.selected[2] + ' (' + str(prg) +')')
        set_midi_prg(prg)
        self.set_controller_config(self.zcontrollers_config);

    def click_but_bank(self):
        self.hide()
        zyngui_bank.show()

    def midi_read(self):
        while alsaseq.inputpending():
            event = alsaseq.input()
            if event[0] == alsaseq.SND_SEQ_EVENT_CONTROLLER: 
                ctrl = event[7][4]
                val = event[7][5]
                print ("MIDI CTRL: " + str(ctrl) + " => " + str(val))
                if ctrl in zyngui_instr.zcontroller_map.keys():
                    zyngui_instr.zcontroller_map[ctrl].set_value(val)
        top.after(100, self.midi_read)

    def rencoder_read(self):
        for i in range(0,4):
            val=lib_rencoder.get_value_zyncoder(i)
            self.zcontrollers[i].set_value(val)
            #print ("RENCODER: " + str(i) + " => " + str(val))
        top.after(100, self.rencoder_read)
        
#-------------------------------------------------------------------------------
# ALSA MIDI client initialization
#-------------------------------------------------------------------------------

alsaseq.client( "Zynthian_gui", 1, 1, True )
#alsaseq.connectto( 0, 130, 0 )
alsaseq.start()

#-------------------------------------------------------------------------------
# Create Top Level Window with Fixed Size
#-------------------------------------------------------------------------------

top = Tk()
top.geometry(str(width)+'x'+str(height))
top.maxsize(width,height)
top.minsize(width,height)

#-------------------------------------------------------------------------------
# Image Loading
#-------------------------------------------------------------------------------

splash_img = PhotoImage(file = "./img/zynthian_gui_splash.gif")
gui_bg = PhotoImage(file = "./img/zynthian_gui.gif")
button_up_img = PhotoImage(file = "./img/zynthian_button_up.gif")
button_down_img = PhotoImage(file = "./img/zynthian_button_down.gif")
button_bank_img = PhotoImage(file = "./img/zynthian_button_bank.gif")

#-------------------------------------------------------------------------------
# GUI initialization
#-------------------------------------------------------------------------------

splash=zynthian_splash(1000)
zyngui_bank=zynthian_gui_bank()
zyngui_instr=zynthian_gui_instr()

#-------------------------------------------------------------------------------
# Main Loop
#-------------------------------------------------------------------------------

top.mainloop()

#-------------------------------------------------------------------------------
