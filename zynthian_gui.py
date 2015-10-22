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

import sys
import alsaseq
import alsamidi
import liblo
from tkinter import *
from ctypes import *
from datetime import datetime
from string import Template
from subprocess import check_output
from threading  import Thread

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

lib_rencoder=None
rencoder_pin_a=[25,26,4,0]
rencoder_pin_b=[27,21,3,7]

#-------------------------------------------------------------------------------
# Get Zynthian Hardware Version
#-------------------------------------------------------------------------------
with open("../zynthian_hw_version.txt","r") as fh:
	hw_version=fh.read()

#-------------------------------------------------------------------------------
# Swap pins if needed
if hw_version=="PROTOTYPE-1":
	rencoder_pin_a,rencoder_pin_b=rencoder_pin_b,rencoder_pin_a
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Controller GUI Class
#-------------------------------------------------------------------------------
class zynthian_controller:
	width=77
	height=106
	trw=70
	trh=13

	frame=None
	triangle=None
	shown=False

	def __init__(self, indx, cnv, x, y, tit, chan, ctrl, val=0, max_val=127):
		if val>max_val:
			val=max_val
		self.canvas=cnv
		self.x=x
		self.y=y
		self.title=tit
		self.index=indx
		self.chan=chan
		if isinstance(ctrl, Template):
			self.ctrl=ctrl.substitute(part=chan)
		else:
			self.ctrl=ctrl
		self.value=val
		self.init_value=None
		self.max_value=max_val
		self.setup_rencoder()
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
			if self.ctrl!=0:
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
		if self.frame:
			self.canvas.coords(self.frame,(self.x, self.y, x2, self.y, x2, y2, self.x, y2))
		else:
			self.frame=self.canvas.create_polygon((self.x, self.y, x2, self.y, x2, y2, self.x, y2), outline=bordercolor, fill=bgcolor)

	def erase_frame(self):
		if self.frame:
			self.canvas.delete(self.frame)
			self.frame=None

	def plot_triangle(self):
		if self.value>self.max_value: self.value=self.max_value
		elif self.value<0: self.value=0
		x1=self.x+2
		y1=self.y+int(0.8*self.height)+self.trh
		x2=x1+self.trw*self.value/self.max_value
		y2=y1-self.trh*self.value/self.max_value
		if self.triangle:
			self.canvas.coords(self.triangle_bg,(x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh))
			self.canvas.coords(self.triangle,(x1, y1, x2, y1, x2, y2))
		else:
			self.triangle_bg=self.canvas.create_polygon((x1, y1, x1+self.trw, y1, x1+self.trw, y1-self.trh), fill=bg2color)
			self.triangle=self.canvas.create_polygon((x1, y1, x2, y1, x2, y2), fill=lightcolor)

	def erase_triangle(self):
		if self.triangle:
			self.canvas.delete(self.triangle_bg)
			self.canvas.delete(self.triangle)
			self.triangle_bg=self.triangle=None

	def config(self, tit, chan, ctrl, val, max_val=127):
		self.title=str(tit)
		self.label_title.config(text=self.title)
		self.chan=chan
		if isinstance(ctrl, Template):
			self.ctrl=ctrl.substitute(part=chan)
		else:
			self.ctrl=ctrl
		self.max_value=max_val
		self.set_value(val)
		self.setup_rencoder()
		
	def setup_rencoder(self):
		print("SETUP RENCODER "+str(self.index)+": "+str(self.ctrl))
		self.init_value=None
		try:
			if isinstance(self.ctrl, str):
				if zyngui.osc_target:
					liblo.send(zyngui.osc_target, self.ctrl)
				lib_rencoder.setup_midi_rencoder(self.index,rencoder_pin_a[self.index],rencoder_pin_b[self.index],self.chan,0,c_char_p(self.ctrl.encode('UTF-8')),self.value,self.max_value)
			elif self.ctrl==0:
				lib_rencoder.setup_midi_rencoder(self.index,rencoder_pin_a[self.index],rencoder_pin_b[self.index],self.chan,self.ctrl,None,4*self.value,4*(self.max_value-1))
			elif self.ctrl>0:
				lib_rencoder.setup_midi_rencoder(self.index,rencoder_pin_a[self.index],rencoder_pin_b[self.index],self.chan,self.ctrl,None,self.value,self.max_value)
		except Exception as err:
			#print(err)
			pass

	def set_value(self, v, set_rencoder=False):
		if (v>self.max_value):
			v=self.max_value
		if (v!=self.value):
			self.value=v
			if self.shown and set_rencoder:
				lib_rencoder.set_value_midi_rencoder(self.index,v)
			if self.ctrl==0:
				self.label_value.config(text=str(self.value+1))
			else:
				self.label_value.config(text=str(self.value))
				if self.shown:
					self.plot_triangle()

	def set_init_value(self, v):
		if self.init_value is None:
			self.init_value=v
			self.set_value(v,True)
			print("RENCODER INIT VALUE "+str(self.index)+": "+str(v))

	def read_rencoder(self):
		val=lib_rencoder.get_value_midi_rencoder(self.index)
		if self.ctrl==0:
			val=int(val/4)
		self.set_value(val)
		#print ("RENCODER VALUE: " + str(self.index) + " => " + str(val))

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
		self.splash_img = PhotoImage(file = "./img/zynthian_gui_splash.gif")
		self.canvas.create_image(0, 0, image = self.splash_img, anchor = NW)
		self.show(tms)

	def hide(self):
		self.canvas.pack_forget()

	def show(self, tms=2000):
		self.canvas.pack(expand = YES, fill = BOTH)
		top.after(tms, self.hide)

#-------------------------------------------------------------------------------
# Zynthian Info GUI Class
#-------------------------------------------------------------------------------
class zynthian_info:
	shown=False

	def __init__(self):
		self.canvas = Canvas(
			width = 70*width/100,
			height = 70*height/100,
			bd=1,
			highlightthickness=0,
			relief='flat',
			bg = bgcolor)

		self.text = StringVar()
		self.label_text = Label(self.canvas,
			font=("Helvetica",10,"normal"),
			textvariable=self.text,
			#wraplength=80,
			justify=LEFT,
			bg=bgcolor,
			fg=lightcolor)
		self.label_text.place(x=1, y=0, anchor=NW)

	def clean(self):
		self.text.set("")

	def set(self, text):
		self.text.set(text)

	def add(self, text):
		self.text.set(self.text.get()+text)

	def hide(self):
		if self.shown:
			self.shown=False
			self.canvas.pack_forget()

	def show(self, text):
		self.text.set(text)
		if not self.shown:
			self.shown=True
			self.canvas.pack(expand = YES, fill = BOTH)

#-------------------------------------------------------------------------------
# Zynthian Listbox GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_list:
	width=162
	height=215
	lb_width=19
	lb_height=10
	lb_x=width/2
	wide=False
	shown=False
	index=0
	list_data=[]

	def __init__(self, image_bg=None, wide=False):
		list_data=[]

		if wide:
			self.wide=True
			self.width=240
			self.lb_width=29
			self.lb_x=5

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

		self.plot_frame()

		# Add ListBox
		self.listbox = Listbox(self.canvas,
			width=self.lb_width,
			height=self.lb_height,
			font=("Helvetica",11),
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg=bgcolor,
			fg=textcolor,
			selectbackground=lightcolor,
			selectforeground=bgcolor,
			selectmode=BROWSE)
		self.listbox.place(x=self.lb_x, y=height-5, anchor=SW)
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
			self.set_select_path()

	def is_shown(self):
		try:
			self.canvas.pack_info()
			return True
		except:
			return False

	def plot_frame(self):
		if self.wide:
			rx=0
			rx2=self.width
		else:
			rx=(width-self.width)/2
			rx2=width-rx-1
		ry=height-self.height
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

	def set_select_path(self):
		pass

#-------------------------------------------------------------------------------
# Zynthian Admin GUI Class
#-------------------------------------------------------------------------------
class zynthian_admin(zynthian_gui_list):
	zselector=None
	command=None
	thread=None

	def __init__(self):
		super().__init__(gui_bg_logo,True)
		self.label_title = Label(self.canvas,
			text="Admin",
			font=("Helvetica",13,"bold"),
			justify=LEFT,
			bg=bgcolor,
			fg=lightcolor)
		self.label_title.place(x=84,y=-2,anchor=NW)
		self.fill_list()
		self.zselector=zynthian_controller(2,self.canvas,243,25,"Action",0,0,0,len(self.list_data))
    
	def get_list_data(self):
		self.list_data=(
			(self.update_system,0,"Update Operating System"),
			(self.update_software,0,"Update Zynthian Software"),
			(self.update_zynlib,0,"Update Zynthian Library"),
			(self.update_userlib,0,"Update User Library"),
			(self.open_reverse_ssh,0,"Open Reverse SSH"),
			(self.power_off,0,"Power Off")
		)

	def show(self):
		super().show()
		if self.zselector:
			self.zselector.config("Action",0,0,self.get_cursel(),len(self.list_data))
			#self.zselector.config("Action",0,0,len(self.list_data))

	def select_action(self, i):
		self.list_data[i][0]()

	def rencoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_rencoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select Admin Action ' + str(sel))
			self.select_listbox(sel)
			
	def execute_command(self):
		print("Executing Command: "+self.command)
		zyngui.add_info("\nExecuting: "+self.command)
		try:
			result=check_output(self.command, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: "+str(e)
		print(result)
		zyngui.add_info("\n"+str(result))
		zyngui.hide_info_timer(3000)
		self.command=None

	def start_command(self,cmd):
		if not self.command:
			print("Starting Command: " + cmd)
			self.command=cmd
			self.thread=Thread(target=self.execute_command, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()

	def update_system(self):
		print("UPDATE SYSTEM")
		zyngui.show_info("UPDATE SYSTEM")
		self.start_command("apt-get -y update; apt-get -y upgrade")

	def update_software(self):
		print("UPDATE SOFTWARE")
		zyngui.show_info("UPDATE SOFTWARE")
		self.start_command("su pi -c 'git pull'")

	def update_zynlib(self):
		print("UPDATE ZYN LIBRARY")
		zyngui.show_info("UPDATE ZYN LIBRARY")
		self.start_command("ls zynbanks")

	def update_userlib(self):
		print("UPDATE USER LIBRARY")
		zyngui.show_info("UPDATE USER LIBRARY")
		self.start_command("ls my_zynbanks")

	def open_reverse_ssh(self):
		print("OPEN REVERSE SSH")
		zyngui.show_info("OPEN REVERSE SSH")
		self.start_command("ifconfig")

	def power_off(self):
		print("POWER OFF")
		#check_output("systemctl poweroff", shell=True)
		check_output("poweroff", shell=True)
		sys.exit()

#-------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_engine(zynthian_gui_list):
	zselector=None
	zyngine=None

	def __init__(self):
		super().__init__(gui_bg_logo,True)
		self.label_title = Label(self.canvas,
			text="Engine",
			font=("Helvetica",13,"bold"),
			justify=LEFT,
			bg=bgcolor,
			fg=lightcolor)
		self.label_title.place(x=84,y=-2,anchor=NW)
		self.fill_list()
		self.zselector=zynthian_controller(2,self.canvas,243,25,"Engine",0,0,1,len(self.list_data))
		#self.set_select_path()
    
	def get_list_data(self):
		self.list_data=(
			("ZynAddSubFX",0,"ZynAddSubFX"),
			("FluidSynth",1,"FluidSynth")
		)

	def show(self):
		super().show()
		if self.zselector:
			self.zselector.config("Engine",0,0,self.get_cursel(),len(self.list_data))
			#self.zselector.config("Engine",0,0,len(self.list_data))

	def select_action(self, i):
		zyngui.set_engine(self.list_data[i][2])
		zyngui.set_mode_chan_select()
		
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
			#print('Pre-select Engine ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		pass
		#self.select_path.set("Zynthian")

#-------------------------------------------------------------------------------
# Zynthian MIDI Channel Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_chan(zynthian_gui_list):
	zselector=None
	max_chan=4

	def __init__(self):
		super().__init__(gui_bg, True)
		self.fill_list()
		self.index=zyngui.zyngine.get_midi_chan()
		self.zselector=zynthian_controller(2,self.canvas,243,25,"Channel",0,0,self.index+1,len(self.list_data))
		self.set_select_path()
    
	def get_list_data(self):
		self.list_data=[]
		for i in range(0,self.max_chan):
			instr=zynmidi.get_midi_instr(i)
			self.list_data.append((str(i+1),i,"Chan #"+str(i+1)+" -> Bank("+str(instr[0])+","+str(instr[1])+") Prog("+str(instr[2])+")"))

	def show(self):
		self.fill_list()
		self.index=zyngui.zyngine.get_midi_chan()
		super().show()
		if self.zselector:
			self.zselector.config("Channel",0,0,self.index,len(self.list_data))
		self.select_listbox(self.index)

	def select_action(self, i):
		zyngui.zyngine.set_midi_chan(i)
		zyngui.zyngui_bank.fill_list()
		zyngui.set_mode_bank_select()

	def rencoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_rencoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select MIDI Chan ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.name)

#-------------------------------------------------------------------------------
# Zynthian Bank Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_bank(zynthian_gui_list):
	zselector=None

	def __init__(self):
		super().__init__(gui_bg, True)
		self.fill_list()
		self.index=zyngui.zyngine.get_bank_index()
		self.zselector=zynthian_controller(2,self.canvas,243,25,"Bank",0,0,self.index+1,len(self.list_data))
		self.set_select_path()
    
	def get_list_data(self):
		self.list_data=zyngui.zyngine.bank_list

	def show(self):
		self.index=zyngui.zyngine.get_bank_index()
		super().show()
		if self.zselector:
			self.zselector.config("Bank",0,0,self.index,len(self.list_data))

	def select_action(self, i):
		zyngui.zyngine.set_bank(i)
		zyngui.zyngui_instr.fill_list()
		zyngui.set_mode_instr_select()

	def rencoder_read(self):
		_sel=self.zselector.value
		self.zselector.read_rencoder()
		sel=self.zselector.value
		if (_sel!=sel):
			#print('Pre-select Bank ' + str(sel))
			self.select_listbox(sel)

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.name + "#" + str(zyngui.zyngine.get_midi_chan()+1))

#-------------------------------------------------------------------------------
# Zynthian Instrument Selection GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui_instr(zynthian_gui_list):

	def __init__(self):
		super().__init__(gui_bg)
		# Controllers
		self.zcontrollers_config=zyngui.zyngine.default_ctrl_config
		self.zcontrollers=(
			zynthian_controller(0,self.canvas,-1,25,self.zcontrollers_config[0][0],zyngui.midi_chan,self.zcontrollers_config[0][1],self.zcontrollers_config[0][2],self.zcontrollers_config[0][3]),
			zynthian_controller(1,self.canvas,-1,133,self.zcontrollers_config[1][0],zyngui.midi_chan,self.zcontrollers_config[1][1],self.zcontrollers_config[1][2],self.zcontrollers_config[1][3]),
			zynthian_controller(2,self.canvas,243,25,self.zcontrollers_config[2][0],zyngui.midi_chan,self.zcontrollers_config[2][1],self.zcontrollers_config[2][2],self.zcontrollers_config[2][3]),
			zynthian_controller(3,self.canvas,243,133,self.zcontrollers_config[3][0],zyngui.midi_chan,self.zcontrollers_config[3][1],self.zcontrollers_config[3][2],self.zcontrollers_config[3][3])
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

	def get_controller_list(self):
		liblo.send(zyngui.osc_target, "/path-search","/part"+str(zyngui.midi_chan)+"/","")
		print("GET CONTROLLER LIST: "+str(zyngui.midi_chan))

	def set_controller_config(self, cfg):
		for i in range(0,4):
			self.set_controller(i,cfg[i][0],zyngui.midi_chan,cfg[i][1],cfg[i][2])

	def set_controller(self, i, tit, chan, ctrl, val, max_val=127):
		try:
			del self.zcontroller_map[self.zcontrollers[i].ctrl]
		except:
			pass
		self.zcontrollers[i].config(tit,chan,ctrl,val,max_val)
		self.zcontrollers[i].show()
		self.zcontroller_map[self.zcontrollers[i].ctrl]=self.zcontrollers[i]

	def get_list_data(self):
		self.list_data=zyngui.zyngine.instr_list

	def set_mode_select(self):
		self.zcontrollers[0].hide()
		self.zcontrollers[1].hide()
		self.zcontrollers[2].hide()
		self.zcontrollers[3].hide()
		self.set_controller(2, "Instrument",0,0,zyngui.zyngine.get_instr_index(),len(self.list_data))
		self.listbox.config(selectbackground=bg3color)
		self.select(zyngui.zyngine.get_instr_index())
		self.set_select_path()

	def set_mode_control(self):
		self.set_controller_config(self.zcontrollers_config)
		self.listbox.config(selectbackground=lightcolor)
		self.set_select_path()

	def select_action(self, i):
		zyngui.zyngine.set_instr(i)
		self.zcontrollers_config=zyngui.zyngine.get_instr_ctrl_config()
		if isinstance(zyngui.zyngine,zynthian_zynaddsubfx_engine) and zyngui.osc_target:
			self.get_controller_list()
			liblo.send(zyngui.osc_target, "/volume")
			zyngui.osc_server.recv()
		else:
			zyngui.set_mode_instr_control()

	def set_select_path(self):
		self.select_path.set(zyngui.zyngine.name[0:3] + "#" + str(zyngui.zyngine.get_midi_chan()+1) + " > " + zyngui.zyngine.get_path())

	def rencoder_read_select(self):
		_sel=self.zcontrollers[2].value
		self.zcontrollers[2].read_rencoder()
		sel=self.zcontrollers[2].value
		if (_sel!=sel):
			#print('Pre-select Instrument ' + str(sel))
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
	osc_target=None
	osc_server=None
	zyngui_splash=None
	zyngui_info=None
	zyngui_admin=None
	zyngui_engine=None
	zyngui_chan=None
	zyngui_bank=None
	zyngui_instr=None
	dtsw1=dtsw2=datetime.now()
	midi_chan=0
	
	def __init__(self):
		# GUI Objects Initialization
		#self.zyngui_splash=zynthian_splash(1000)
		self.zyngui_admin=zynthian_admin()
		self.zyngui_info=zynthian_info()
		self.zyngui_engine=zynthian_gui_engine()
		# Control Initialization (Rotary and Switches)
		try:
			self.osc_init()
			self.lib_rencoder_init()
			self.gpio_switch_init()
		except:
			pass
		self.set_mode_engine_select()
		self.start_polling()

	def show_info(self, text, tms=None):
		self.zyngui_info.show(text)
		self.zyngui_admin.hide()
		self.zyngui_engine.hide()
		if self.zyngui_chan:
			self.zyngui_chan.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		if self.zyngui_instr:
			self.zyngui_instr.hide()
		if tms:
			top.after(tms, self.hide_info)

	def add_info(self, text):
		self.zyngui_info.add(text)

	def hide_info_timer(self, tms=3000):
		top.after(tms, self.hide_info)

	def hide_info(self):
		self.zyngui_info.hide()
		self.restore_mode()

	def set_mode_admin(self):
		self.mode=-1
		self.zyngui_admin.show()
		self.zyngui_info.hide()
		self.zyngui_engine.hide()
		if self.zyngui_chan:
			self.zyngui_chan.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		if self.zyngui_instr:
			self.zyngui_instr.hide()

	def set_mode_engine_select(self):
		self.mode=0
		self.zyngui_engine.show()
		self.zyngui_info.hide()
		self.zyngui_admin.hide()
		if self.zyngui_chan:
			self.zyngui_chan.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		if self.zyngui_instr:
			self.zyngui_instr.hide()

	def set_mode_chan_select(self):
		self.mode=1
		self.zyngui_chan.show()
		self.zyngui_info.hide()
		self.zyngui_admin.hide()
		self.zyngui_engine.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		if self.zyngui_instr:
			self.zyngui_instr.hide()

	def set_mode_bank_select(self):
		self.mode=2
		self.zyngui_bank.show()
		self.zyngui_info.hide()
		self.zyngui_admin.hide()
		self.zyngui_engine.hide()
		if self.zyngui_chan:
			self.zyngui_chan.hide()
			self.midi_chan=self.zyngine.get_midi_chan()
		if self.zyngui_instr:
			self.zyngui_instr.hide()
        
	def set_mode_instr_select(self):
		self.mode=3
		self.zyngui_instr.show()
		self.zyngui_info.hide()
		self.zyngui_admin.hide()
		self.zyngui_engine.hide()
		if self.zyngui_chan:
			self.zyngui_chan.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		self.zyngui_instr.set_mode_select()
        
	def set_mode_instr_control(self):
		self.mode=4
		self.zyngui_instr.show()
		self.zyngui_info.hide()
		self.zyngui_admin.hide()
		self.zyngui_engine.hide()
		if self.zyngui_chan:
			self.zyngui_chan.hide()
		if self.zyngui_bank:
			self.zyngui_bank.hide()
		self.zyngui_instr.set_mode_control()

	def restore_mode(self):
		if self.mode==-1:
			self.set_mode_admin()
		elif self.mode==0:
			self.set_mode_engine_select()
		elif self.mode==1:
			self.set_mode_chan_select()
		elif self.mode==2:
			self.set_mode_bank_select()
		elif self.mode==3:
			self.set_mode_instr_select()
		elif self.mode==4:
			self.set_mode_instr_control()

	def set_engine(self,name):
		if self.zyngui_engine.set_engine(name):
			self.zyngine=self.zyngui_engine.zyngine
			self.zyngui_chan=zynthian_gui_chan()
			self.zyngui_bank=zynthian_gui_bank()
			self.zyngui_instr=zynthian_gui_instr()

	# Init Rotary Encoders C Library
	def lib_rencoder_init(self):
		global lib_rencoder
		global zyngine_osc_port
		try:
			lib_rencoder=cdll.LoadLibrary("midi_rencoder/midi_rencoder.so")
			lib_rencoder.init_rencoder(zyngine_osc_port)
			#lib_rencoder.init_rencoder(0)
		except Exception as e:
			lib_rencoder=None
			print("Can't init Zyncoders: %s" % str(e))

	# Init GPIO Switches
	def gpio_switch_init(self):
		sw1_chan=2
		sw2_chan=23
		lib_rencoder.setup_gpio_switch(0,sw1_chan)
		lib_rencoder.setup_gpio_switch(1,sw2_chan)

	def osc_init(self):
		global zyngine_osc_port
		try:
			self.osc_target = liblo.Address(zyngine_osc_port)
			self.osc_server = liblo.Server()
			#self.osc_server.add_method(None, None, self.cb_osc_all)
			self.osc_server.add_method("/volume", 'i', self.cb_osc_load_instr)
			self.osc_server.add_method("/paths", None, self.cb_osc_paths)
			self.osc_server.add_method(None, 'i', self.cb_osc_ctrl)
			#print("OSC server running in port " % (str(self.osc_server.get_port())))
			liblo.send(self.osc_target, "/echo")
			print("OSC Server running");
		except liblo.AddressError as err:
			print("ERROR: OSC Server can't be initialized (%s). Running without OSC feedback." % (str(err)))

	def gpio_switch1(self):
		dtus=lib_rencoder.get_gpio_switch_dtus(0)
		if dtus>0:
			#print("Switch 1 dtus="+str(dtus))
			if dtus>2000000:
				#print('Long Switch 1')
				self.zyngui_admin.power_off()
				return
			#print('Switch 1')
			self.dtsw1=datetime.now()
			if self.gpio_switch12():
				return
			elif self.mode==4:
				self.set_mode_instr_select()
			elif self.mode==3:
				self.zyngui_instr.click_listbox()
			elif self.mode==2:
				self.zyngui_bank.click_listbox()
			elif self.mode==1:
				self.zyngui_chan.click_listbox()
			elif self.mode==0:
				self.zyngui_engine.click_listbox()
			elif self.mode==-1:
				self.zyngui_admin.click_listbox()

	def gpio_switch2(self):
		dtus=lib_rencoder.get_gpio_switch_dtus(1)
		if dtus>0:
			if dtus>2000000:
				#print('Long Switch 2')
				self.set_mode_admin()
				return
			#print('Switch 2')
			self.dtsw2=datetime.now()
			if self.gpio_switch12():
				return
			elif self.mode>=3:
				self.set_mode_bank_select()
			elif self.mode==2:
				self.set_mode_chan_select()
			elif self.mode==1:
				self.set_mode_engine_select()
			elif self.mode==0:
				pass
			elif self.mode==-1:
				self.set_mode_engine_select()

	def gpio_switch12(self):
		if abs((self.dtsw1-self.dtsw2).total_seconds())<0.5:
			#print('Switch 1+2')
			self.set_mode_admin()
			return True

	def start_polling(self):
		self.polling=True
		self.poll_count=0
		self.midi_read()
		if lib_rencoder:
			self.rencoder_read()
		if self.osc_server:
			self.osc_read()

	def stop_polling(self):
		self.polling=False

	def midi_read(self):
		while alsaseq.inputpending():
			event = alsaseq.input()
			chan = event[7][0]
			if self.mode==4 and event[0] == alsaseq.SND_SEQ_EVENT_CONTROLLER and chan==self.midi_chan: 
				ctrl = event[7][4]
				val = event[7][5]
				print ("MIDI CTRL " + str(ctrl) + ", CH" + str(chan) + " => " + str(val))
				# Only read Modulation Wheel =>
				#if ctrl==1:
				if ctrl in self.zyngui_instr.zcontroller_map.keys():
					self.zyngui_instr.zcontroller_map[ctrl].set_value(val,True)
		if self.polling:
			top.after(40, self.midi_read)

	def rencoder_read(self):
		if self.mode==4:
			self.zyngui_instr.rencoder_read_control()
		elif self.mode==3:
			self.zyngui_instr.rencoder_read_select()
		elif self.mode==2:
			self.zyngui_bank.rencoder_read()
		elif self.mode==1:
			self.zyngui_chan.rencoder_read()
		elif self.mode==0:
			self.zyngui_engine.rencoder_read()
		elif self.mode==-1:
			self.zyngui_admin.rencoder_read()

		self.gpio_switch1()
		self.gpio_switch2()

		if self.polling:
			top.after(40, self.rencoder_read)
			#self.poll_count=self.poll_count+1
			#if self.poll_count % 20 == 0:
			#	print ("POLL "+str(self.poll_count))

	def osc_read(self):
		while self.osc_server.recv(0):
			pass
		if self.polling:
			top.after(40, self.osc_read)

	def cb_osc_load_instr(self, path, args):
		self.set_mode_instr_control()

	def cb_osc_paths(self, path, args, types, src):
		print("PATHS: ")
		for a, t in zip(args, types):
			#print("%s (%s)" % (a,t))
			if t!='b':
				liblo.send(self.osc_target, "/path-search","/part"+str(self.midi_chan)+"/"+a,"")
				print("%s (%s)" % (a, t))

	def cb_osc_bank_view(self, path, args):
		pass

	def cb_osc_ctrl(self, path, args):
		#print ("OSC CTRL: " + path + " => "+str(args[0]))
		if path in self.zyngui_instr.zcontroller_map.keys():
			self.zyngui_instr.zcontroller_map[path].set_init_value(args[0])

	def cb_osc_all(self, path, args, types, src):
		print("OSC MESSAGE '%s' from '%s'" % (path, src.url))
		for a, t in zip(args, types):
			print("argument of type '%s': %s" % (t, a))

#-------------------------------------------------------------------------------
# Create Top Level Window with Fixed Size
#-------------------------------------------------------------------------------

top = Tk()
top.geometry(str(width)+'x'+str(height))
top.maxsize(width,height)
top.minsize(width,height)
top.config(cursor="none")

#-------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#-------------------------------------------------------------------------------

# Image Loading
gui_bg_logo = PhotoImage(file = "./img/zynthian_bg_logo_left.gif")
gui_bg = None

zyngui=zynthian_gui()

#-------------------------------------------------------------------------------
# Main Loop
#-------------------------------------------------------------------------------

top.mainloop()

#-------------------------------------------------------------------------------
