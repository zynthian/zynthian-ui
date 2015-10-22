#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Zynthian GUI: zynthian_engine.py

Synth engine classes for Zynthian GUI

author: José Fernandom Moyano (ZauBeR)
email: fernando@zauber.es
created: 2015-07-11
modified:  2015-07-11
"""

import sys
import os
from os.path import isfile, isdir, join
from string import Template
from subprocess import Popen, PIPE, STDOUT
from threading  import Thread
from queue import Queue, Empty

from zynthian_midi import *

#-------------------------------------------------------------------------------
# MIDI Interface Initialization
#-------------------------------------------------------------------------------

global zynmidi
zynmidi=zynthian_midi("Zynthian_gui")

#-------------------------------------------------------------------------------
# OSC Interface Initialization
#-------------------------------------------------------------------------------

global zyngine_osc_port
zyngine_osc_port=6699

#-------------------------------------------------------------------------------
# Synth Engine Base Class
#-------------------------------------------------------------------------------

class zynthian_synth_engine:
	name=""
	command=None
	command_env=None
	proc=None
	thread=None
	queue=None

	user_gid=1000
	user_uid=1000

	bank_list=None
	instr_list=None	

	midi_chan=0

	bank_index=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	bank_name=["","","","","","","","","","","","","","","",""]

	instr_index=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	instr_name=["","","","","","","","","","","","","","","",""]

	instr_ctrl_config=[None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None]

	default_ctrl_config=(
		('volume',7,96,127),
		#('expression',11,127,127),
		('modulation',1,0,127),
		#('reverb',91,64,127),
		#('chorus',93,64,127),
		('filter Q',71,64,127),
		('filter cutoff',74,64,127)
	)

	def __init__(self):
		self.start()
		self.load_bank_list()

	def __del__(self):
		self.stop()

	def proc_enqueue_output(self):
		for line in self.proc.stdout:
			self.queue.put(line)

	def proc_get_lines(self,tout=0.1,limit=2):
		n=0
		lines=[]
		while True:
			try:
				lines.append(self.queue.get(timeout=tout))
				n=n+1
				if (n==limit):
					tout=0.1
			except Empty:
				break
		return lines

	def chuser(self):
		def result():
			os.setgid(self.user_gid)
			os.setuid(self.user_uid)
		return result

	def start(self,start_queue=False):
		if not self.proc:
			print("Starting Engine " + self.name)
			self.proc=Popen(self.command,shell=False,bufsize=1,universal_newlines=True,stdin=PIPE,stdout=PIPE,stderr=STDOUT,env=self.command_env)
			#,preexec_fn=self.chuser()
			if start_queue:
				self.queue=Queue()
				self.thread=Thread(target=self.proc_enqueue_output, args=())
				self.thread.daemon = True # thread dies with the program
				self.thread.start()
				self.proc_get_lines(2)

	def stop(self):
		if self.proc:
			print("Stoping Engine " + self.name)
			self.proc.stdout.close()
			self.proc.stdin.close()
			self.proc.kill()
			self.proc=None

	def proc_cmd(self,cmd,tout=0.1):
		if self.proc:
			print("PROC_CMD: "+cmd)
			#self.proc.stdin.write(bytes(cmd + "\n", 'UTF-8'))
			self.proc.stdin.write(cmd + "\n")
			self.proc.stdin.flush()
			return self.proc_get_lines(tout)

	def set_midi_chan(self, i):
		print('MIDI Chan Selected: ' + str(i))
		self.midi_chan=i

	def get_midi_chan(self):
		return self.midi_chan

	def get_bank_index(self):
		return self.bank_index[self.midi_chan]

	def get_instr_index(self):
		return self.instr_index[self.midi_chan]

	def get_instr_ctrl_config(self):
		return self.instr_ctrl_config[self.midi_chan]

	def reset_instr(self):
		self.instr_index[self.midi_chan]=0
		self.instr_name[self.midi_chan]=""

	def load_bank_list(self):
		self.bank_list=[]

	def load_instr_list(self):
		self.instr_list=[]

	def load_instr_config(self):
		self.instr_ctrl_config[self.midi_chan]=self.default_ctrl_config

	def set_bank(self, i):
		last_bank_index=self.bank_index[self.midi_chan]
		self.bank_index[self.midi_chan]=i
		self.bank_name[self.midi_chan]=self.bank_list[i][2]
		self.load_instr_list()
		if last_bank_index!=i:
			self.reset_instr()
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')

	def set_instr(self, i):
		self.instr_index[self.midi_chan]=i
		self.instr_name[self.midi_chan]=self.instr_list[i][2]
		print('Instrument Selected: ' + self.instr_name[self.midi_chan] + ' (' + str(i)+')')
		zynmidi.set_midi_instr(self.midi_chan, self.instr_list[i][1][0], self.instr_list[i][1][1], self.instr_list[i][1][2])
		self.load_instr_config()

	def get_path(self):
		path=self.bank_name[self.midi_chan]
		if self.instr_name[self.midi_chan]:
			path=path + ' / ' + self.instr_name[self.midi_chan]
		return path

#-------------------------------------------------------------------------------
# ZynAddSubFX Engine Class
#-------------------------------------------------------------------------------

class zynthian_zynaddsubfx_engine(zynthian_synth_engine):
	name="ZynAddSubFX"

	#bank_dir="/usr/share/zynaddsubfx/banks"
	bank_dir="./software/zynaddsubfx-instruments/banks"

	default_ctrl_config=(
		('volume',Template('/part$part/Pvolume'),96,127),
		#('volume',7,96,127),
		('modulation',1,0,127),
		('filter Q',71,64,127),
		('filter cutoff',74,64,127)
		#('modulation',1,0,127),
		#('expression',11,127,127),
		#('filter Q',71,64,127),
		#('filter cutoff',74,64,127),
		#('bandwidth',75,64,127),
		#('modulation amplitude',76,127,127),
		#('resonance freq',77,64,127),
		#('resonance bw',78,64,127),
		#('reverb',91,64,127),
		#('chorus',93,64,127),
	)

	def __init__(self):
		if os.environ.get('ZYNTHIANX'):
			self.command_env=os.environ.copy()
			self.command_env['DISPLAY']="localhost:10.0"
			self.command=("./software/zynaddsubfx/build/src/zynaddsubfx", "-O", "alsa", "-I", "alsa", "-P", str(zyngine_osc_port), "-l", "zynconf/zasfx_4ch.xmz")
		else:
			#self.command=("./software/zynaddsubfx/build/src/zynaddsubfx", "-O", "alsa", "-I", "alsa", "-U")
			self.command=("./software/zynaddsubfx/build/src/zynaddsubfx", "-O", "alsa", "-I", "alsa", "-U", "-P", str(zyngine_osc_port), "-l", "zynconf/zasfx_4ch.xmz")
		super().__init__()
		
	def load_bank_list(self):
		self.bank_list=[]
		print('Getting Bank List for ' + self.name)
		i=0
		for f in sorted(os.listdir(self.bank_dir)):
			if isdir(join(self.bank_dir,f)):
				title=str.replace(f, '_', ' ')
				self.bank_list.append((f,i,title))
				i=i+1

	def load_instr_list(self):
		self.instr_list=[]
		instr_dir=join(self.bank_dir,self.bank_list[self.bank_index[self.midi_chan]][0])
		print('Getting Instrument List for ' + self.bank_name[self.midi_chan])
		for f in sorted(os.listdir(instr_dir)):
			#print(f)
			if (isfile(join(instr_dir,f)) and f[-4:].lower()=='.xiz'):
				prg=int(f[0:4])-1
				bank_lsb=int(prg/128)
				bank_msb=self.bank_index[self.midi_chan]
				prg=prg%128
				title=str.replace(f[5:-4], '_', ' ')
				self.instr_list.append((f,[bank_msb,bank_lsb,prg],title))

	def load_instr_config(self):
		super().load_instr_config()

#-------------------------------------------------------------------------------
# FluidSynth Engine Class
#-------------------------------------------------------------------------------

class zynthian_fluidsynth_engine(zynthian_synth_engine):
	name="FluidSynth"
	#command=("/usr/local/bin/fluidsynth", "-p", "FluidSynth", "-a", "alsa" ,"-g", "1")
	command=("/usr/bin/fluidsynth", "-p", "FluidSynth", "-a", "alsa" ,"-g", "1")

	bank_dir="./sf2"
	bank_id=0

	default_ctrl_config=(
		('volume',7,96,127),
		#('expression',11,127,127),
		('modulation',1,0,127),
		('reverb',91,64,127),
		('chorus',93,2,127)
	)

	def __init__(self):
		self.start(True)
		self.load_bank_list()

	def stop(self):
		self.proc_cmd("quit",2)
		super().stop()

	def load_bank_list(self):
		self.bank_list=[]
		print('Getting Bank List for ' + self.name)
		i=0
		for f in sorted(os.listdir(self.bank_dir)):
			if (isfile(join(self.bank_dir,f)) and f[-4:].lower()=='.sf2'):
				title=str.replace(f[:-4], '_', ' ')
				self.bank_list.append((f,i,title))
				i=i+1

	def load_instr_list(self):
		self.instr_list=[]
		print('Getting Instrument List for ' + self.bank_name[self.midi_chan])
		lines=self.proc_cmd("inst " + str(self.bank_id))
		for f in lines:
			try:
				prg=int(f[4:7])
				bank_msb=int(f[0:3])
				bank_lsb=int(bank_msb/128)
				bank_msb=bank_msb%128
				title=str.replace(f[8:-1], '_', ' ')
				self.instr_list.append((f,[bank_msb,bank_lsb,prg],title))
			except:
				pass

	def set_bank(self, i):
		self.bank_index[self.midi_chan]=i
		self.bank_name[self.midi_chan]=self.bank_list[i][2]
		if self.bank_id>0:
			self.proc_cmd("unload " + str(self.bank_id),2)
		self.proc_cmd("load " + self.bank_dir + '/' + self.bank_list[i][0],20)
		self.bank_id=self.bank_id+1
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')
		self.load_instr_list()

	def load_instr_config(self):
		super().load_instr_config()

#-------------------------------------------------------------------------------
