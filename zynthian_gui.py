#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Zynthian GUI: zynthian_gui.py

Main file and GUI classes for Zynthian GUI

author: José Fernandom Moyano (ZauBeR)
email: fernando@zauber.es
created: 2015-05-18
modified:  2015-07-11
"""

try:
	import RPi.GPIO as GPIO
except RuntimeError:
	print("Error importing RPi.GPIO! This is probably because you need superuser privileges.")

import alsaseq
import alsamidi
from tkinter import *
from ctypes import *

from zynthian_engine import *

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
# Controller GUI Class
#-------------------------------------------------------------------------------
class zynthian_controller:
	width=77
	height=106
	trw=70
	trh=13

	shown=False

	def __init__(self, indx, cnv, x, y, tit, ctrl, val=0, max_val=127):
		if (val>max_val):
			val=max_val
		self.canvas=cnv
		self.x=x
		self.y=y
		self.title=tit
		self.index=indx
		self.ctrl=ctrl
		self.value=val
		self.max_value=max_val
		self.setup_zyncoder()
		self.label_title = Label(self.canvas,
			text=self.title,
			wraplength=self.width-6,
			justify=LEFT,
			bg=bgcolor,
			fg=lightcolor)
		self.label_value = Label(self.canvas,
			text=str(self.value),
			font=("Helvetica",15),
			bg=bgcolor,
			fg=lightcolor)
		self.show()

	def show(self):
		if not self.shown:
			self.shown=True
			self.plot_frame()
			if (self.ctrl>0):
				self.plot_triangle()
			self.label_title.place(x=self.x+3, y=self.y+4, anchor=NW)
			self.label_value.place(x=self.x+int(0.3*self.width), y=self.y+int(0.5*self.height), anchor=NW)

	def hide(self):
		if self.shown:
			self.shown=False
			self.erase_frame()
			self.erase_triangle()
			self.label_title.place_forget()
			self.label_value.place_forget()

	def plot_frame(self):
		x2=self.x+self.width
		y2=self.y+self.height
		self.canvas.create_polygon((self.x, self.y, x2, self.y, x2, y2, self.x, y2), outline=bordercolor, fill=bgcolor)

	def erase_frame(self):
		x2=self.x+self.width
		y2=self.y+self.height
		self.canvas.create_polygon((self.x, self.y, x2, self.y, x2, y2, self.x, y2), outline=bgcolor, fill=bgcolor)

	def plot_triangle(self):
		if (self.value>self.max_value): self.value=self.max_value
		elif (self.value<0): self.value=0
		x1=self.x+2
		y1=self.y+int(0.8*self.height)+self.trh
		x2=x1+self.trw*self.value/self.max_value
		y2=y1-self.trh*self.value/self.max_value
		self.canvas.create_polygon((x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh-1), fill=bg2color)
		self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=lightcolor)

	def erase_triangle(self):
		x1=self.x+2
		y1=self.y+int(0.8*self.height)+self.trh
		x2=x1+self.trw
		y2=y1-self.trh-1
		self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=bgcolor)

	def config(self, tit, ctrl, val, max_val=127):
		self.title=str(tit)
		self.label_title.config(text=self.title)
		self.ctrl=ctrl
		self.max_value=max_val
		self.set_value(val)
		self.setup_zyncoder()
		
	def setup_zyncoder(self):
		try:
			if self.ctrl==0:
				lib_rencoder.setup_zyncoder(self.index,self.ctrl,4*self.value,4*(self.max_value-1))
			else:
				lib_rencoder.setup_zyncoder(self.index,self.ctrl,self.value,self.max_value)
		except:
			pass

	def set_value(self, v, set_zyncoder=False):
		if (v>self.max_value):
			v=self.max_value
		if (v!=self.value):
			self.value=v
			if self.shown and set_zyncoder:
				lib_rencoder.set_value_zyncoder(self.index,v)
			if self.ctrl==0:
				self.label_value.config(text=str(self.value+1))
			else:
				self.label_value.config(text=str(self.value))
				if self.shown:
					self.plot_triangle()

	def read_rencoder(self):
		val=lib_rencoder.get_value_zyncoder(self.index)
		if self.ctrl==0:
			val=int(val/4)
		self.set_value(val)
		#print ("RENCODER: " + str(self.index) + " => " + str(val))

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
		splash_img = PhotoImage(file = "./img/zynthian_gui_splash.gif")
		self.canvas.create_image(0, 0, image = splash_img, anchor = NW)
		self.show(tms)

	def hide(self):
		self.canvas.pack_forget()

	def show(self, tms=2000):
		self.canvas.pack(expand = YES, fill = BOTH)
		top.after(tms, self.hide)

#-------------------------------------------------------------------------------
# Zynthian Listbox GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_list:
	width=162
	height=215

	shown=False
	index=0
	list_data=[]

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

		self.plot_frame();

		# Add ListBox
		self.listbox = Listbox(self.canvas,
			width=19,
			height=10,
			font=("Helvetica",11),
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=bgcolor,
			fg=textcolor,
			selectbackground=lightcolor,
			selectforeground=bgcolor,
			selectmode=BROWSE)
		self.listbox.place(relx=0.5, y=height-5, anchor=S)
		self.listbox.bind('<<ListboxSelect>>', lambda event :self.click_listbox())

		# Add Select Path (top-left)
		self.select_path = StringVar()
		self.label_select_path = Label(self.canvas,
			font=("Helvetica",12,"bold"),
			textvariable=self.select_path,
			#wraplength=80,
			justify=LEFT,
			bg=bgcolor,
			fg=lightcolor)
		self.label_select_path.place(x=1, y=0, anchor=NW)
		
		self.show()

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.pack_forget()

	def show(self):
		if not self.shown:
			self.shown=True
			self.canvas.pack(expand = YES, fill = BOTH)
			self.select_listbox(self.index)
		
	def is_shown(self):
		try:
			self.canvas.pack_info()
			return True
		except:
			return False

	def plot_frame(self):
		rx=(width-self.width)/2
		ry=height-self.height
		rx2=width-rx-1
		ry2=height-1
		self.canvas.create_polygon((rx, ry, rx2, ry, rx2, ry2, rx, ry2), outline=bordercolor, fill=bgcolor)

	def get_list_data(self):
		self.list_data=[]

	def fill_list(self):
		self.get_list_data()
		self.listbox.delete(0, END)
		for item in self.list_data:
			self.listbox.insert(END, item[2])
		self.select(0)

	def get_cursel(self):
		cursel=self.listbox.curselection()
		if (len(cursel)>0):
			self.index=int(cursel[0])
		else:
			self.index=0
		return self.index

	def select_listbox(self,index):
		self.listbox.selection_clear(0,END)
		self.listbox.selection_set(index)
		self.listbox.see(index)

	def click_listbox(self):
		index=self.get_cursel()
		self.select_action(index)

	def select(self, index):
		self.index=index
		self.select_listbox(index)
		
#-------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_gui_list):
	zselector=None
	zyngine=None

	def __init__(self):
		super().__init__(gui_bg_logo)
		self.fill_list()
		self.zselector=zynthian_controller(2,self.canvas,243,25,"Engine",0,0,len(self.list_data))
		#self.set_select_path()
    
	def get_list_data(self):
		self.list_data=(
			("ZynAddSubFX",0,"ZynAddSubFX"),
			("FluidSynth",0,"FluidSynth")
		)

	def show(self):
		super().show()
		if self.zselector:
			#self.zselector.config("Engine",0,self.get_cursel(),len(self.list_data))
			self.zselector.config("Engine",0,0,2)

	def select_action(self, i):
		zyngui.set_engine(self.list_data[i][2])
		zyngui.set_mode_bank_select()
		
	def set_engine(self,name):
		if self.zyngine:
			if self.zyngine.name==name:
				return False
			else:
				self.zyngine.stop()

		if name=="ZynAddSubFX":
			self.zyngine=zynthian_zynaddsubfx_engine()
		elif name=="FluidSynth":
			self.zyngine=zynthian_fluidsynth_engine()

		return True

	def rencoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_rencoder()
		sel=self.zselector.value
		if (_sel!=sel):
			print('Pre-select Engine ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set("Zynthian")

#-------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_list):
	zselector=None

	def __init__(self):
		super().__init__(gui_bg)
		self.fill_list()
		self.zselector=zynthian_controller(2,self.canvas,243,25,"Bank",0,zyngui.zyngine.bank_index,len(self.list_data))
		self.set_select_path()
    
	def get_list_data(self):
		self.list_data=zyngui.zyngine.bank_list

	def show(self):
		super().show()
		if self.zselector:
			self.zselector.config("Bank",0,zyngui.zyngine.bank_index,len(self.list_data))

	def select_action(self, i):
		zyngui.zyngine.set_bank(i)
		zyngui.zyngui_instr.fill_list()
		zyngui.set_mode_instr_select()

	def rencoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_rencoder()
		sel=self.zselector.value
		if (_sel!=sel):
			print('Pre-select Bank ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.name)

#-------------------------------------------------------------------------------
# Zynthian Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_instr(zynthian_gui_list):

	def __init__(self):
		super().__init__(gui_bg)
		# Controllers
		self.zcontrollers_config=zyngui.zyngine.default_ctrl_config;
		self.zcontrollers=(
			zynthian_controller(0,self.canvas,-1,25,self.zcontrollers_config[0][0],self.zcontrollers_config[0][1],self.zcontrollers_config[0][2],self.zcontrollers_config[0][3]),
			zynthian_controller(1,self.canvas,-1,133,self.zcontrollers_config[1][0],self.zcontrollers_config[1][1],self.zcontrollers_config[1][2],self.zcontrollers_config[1][3]),
			zynthian_controller(2,self.canvas,243,25,self.zcontrollers_config[2][0],self.zcontrollers_config[2][1],self.zcontrollers_config[2][2],self.zcontrollers_config[2][3]),
			zynthian_controller(3,self.canvas,243,133,self.zcontrollers_config[3][0],self.zcontrollers_config[3][1],self.zcontrollers_config[3][2],self.zcontrollers_config[3][3])
		)
		# Init Controllers Map
		self.zcontroller_map={}
		for zc in self.zcontrollers:
			self.zcontroller_map[zc.ctrl]=zc
        
	def hide(self):
		if self.shown:
			super().hide()
			for zc in self.zcontrollers:
				zc.hide()

	def set_controller_config(self, cfg):
		for i in range(0,4):
			self.set_controller(i,cfg[i][0],cfg[i][1],cfg[i][2]);
			print("Init Zyncoder: %s" % str(i))

	def set_controller(self, i, tit, ctrl, val, max_val=127):
		try:
			del self.zcontroller_map[self.zcontrollers[i].ctrl]
		except:
			pass
		self.zcontrollers[i].config(tit,ctrl,val,max_val)
		self.zcontrollers[i].show()
		self.zcontroller_map[ctrl]=self.zcontrollers[i]

	def get_list_data(self):
		self.list_data=zyngui.zyngine.instr_list

	def set_mode_select(self):
		self.set_controller(2, "Instrument", 0, zyngui.zyngine.instr_index, len(self.list_data))
		self.zcontrollers[0].hide()
		self.zcontrollers[1].hide()
		self.zcontrollers[3].hide()
		self.listbox.config(selectbackground=bg3color)
		self.set_select_path()

	def set_mode_control(self):
		self.set_controller_config(self.zcontrollers_config)
		self.listbox.config(selectbackground=lightcolor)
		self.set_select_path()

	def select_action(self, i):
		zyngui.zyngine.set_instr(i)
		self.zcontrollers_config=zyngui.zyngine.instr_ctrl_config;
		zyngui.set_mode_instr_control()

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.get_path())

	def rencoder_read_select(self):
		_sel=self.zcontrollers[2].value
		self.zcontrollers[2].read_rencoder()
		sel=self.zcontrollers[2].value
		if (_sel!=sel):
			print('Pre-select Instrument ' + str(sel))
			self.select_listbox(sel)

	def rencoder_read_control(self):
		for zc in self.zcontrollers:
			zc.read_rencoder()

#-------------------------------------------------------------------------------
# Zynthian Main GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui:
	mode=0
	polling=False
	zyngine=None
	zyngui_engine=None
	zyngui_bank=None
	zyngui_instr=None
	
	def __init__(self):
		self.zyngui_engine=zynthian_gui_engine()
		self.lib_rencoder_init()
		self.set_mode_engine_select()
		self.gpio_switch_init()
		self.start_polling()

	def set_mode_engine_select(self):
		self.mode=0
		self.zyngui_engine.show()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		if self.zyngui_instr:
			self.zyngui_instr.hide()

	def set_mode_bank_select(self):
		self.mode=1
		self.zyngui_bank.show()
		if self.zyngui_engine:
			self.zyngui_engine.hide()
		if self.zyngui_instr:
			self.zyngui_instr.hide()
        
	def set_mode_instr_select(self):
		self.mode=2
		self.zyngui_instr.show()
		if self.zyngui_engine:
			self.zyngui_engine.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		self.zyngui_instr.set_mode_select()
        
	def set_mode_instr_control(self):
		self.mode=3
		self.zyngui_instr.show()
		if self.zyngui_engine:
			self.zyngui_engine.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		self.zyngui_instr.set_mode_control()

	def set_engine(self,name):
		if self.zyngui_engine.set_engine(name):
			self.zyngine=self.zyngui_engine.zyngine
			self.zyngui_bank=zynthian_gui_bank()
			self.zyngui_instr=zynthian_gui_instr()

	def start_polling(self):
		self.polling=True;
		self.midi_read();
		self.rencoder_read();
        
	def stop_polling(self):
		self.polling=False;
		
	def midi_read(self):
		while alsaseq.inputpending():
			event = alsaseq.input()
			if self.mode==3 and event[0] == alsaseq.SND_SEQ_EVENT_CONTROLLER: 
				ctrl = event[7][4]
				val = event[7][5]
				print ("MIDI CTRL: " + str(ctrl) + " => " + str(val))
				# Only read Modulation Wheel =>
				#if ctrl==1:
				if ctrl in self.zyngui_instr.zcontroller_map.keys():
					self.zyngui_instr.zcontroller_map[ctrl].set_value(val,True)
		if self.polling:
			top.after(40, self.midi_read)

	def rencoder_read(self):
		if self.mode==0:
			self.zyngui_engine.rencoder_read()
		elif self.mode==1:
			self.zyngui_bank.rencoder_read()
		elif self.mode==2:
			self.zyngui_instr.rencoder_read_select()
		elif self.mode==3:
			self.zyngui_instr.rencoder_read_control()
		if self.polling:
			top.after(40, self.rencoder_read)

	# Init Rotary Encoders C Library
	def lib_rencoder_init(self):
		try:
			global lib_rencoder
			lib_rencoder=cdll.LoadLibrary("midi_rencoder/midi_rencoder.so")
			lib_rencoder.init_rencoder()
		except Exception as e:
			print("Can't init Zyncoders: %s" % str(e))

	def gpio_switch1(self,chan):
		print('Switch 1')
		if self.mode==0:
			self.zyngui_engine.click_listbox()
		elif self.mode==1:
			self.zyngui_bank.click_listbox()
		elif self.mode==2:
			self.zyngui_instr.click_listbox()
		elif self.mode==3:
			self.set_mode_instr_select()

	def gpio_switch2(self,chan):
		print('Switch 2')
		if self.mode==1:
			self.set_mode_engine_select()
		elif self.mode>=2:
			self.set_mode_bank_select()

	# Init GPIO Switches
	def gpio_switch_init(self):
		sw1_chan=15
		sw2_chan=16

		GPIO.setmode(GPIO.BOARD)

		GPIO.setup(sw1_chan, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.add_event_detect(sw1_chan, GPIO.RISING, bouncetime=400)
		GPIO.add_event_callback(sw1_chan, self.gpio_switch1)

		GPIO.setup(sw2_chan, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.add_event_detect(sw2_chan, GPIO.RISING, bouncetime=400)
		GPIO.add_event_callback(sw2_chan, self.gpio_switch2)

#-------------------------------------------------------------------------------
# Create Top Level Window with Fixed Size
#-------------------------------------------------------------------------------

top = Tk()
top.geometry(str(width)+'x'+str(height))
top.maxsize(width,height)
top.minsize(width,height)

#-------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#-------------------------------------------------------------------------------

# Background Loading
gui_bg_logo = PhotoImage(file = "./img/zynthian_bg_logo_left.gif")
gui_bg = None

splash=zynthian_splash(1000)
zyngui=zynthian_gui()

#-------------------------------------------------------------------------------
# Main Loop
#-------------------------------------------------------------------------------

top.mainloop()

#-------------------------------------------------------------------------------
