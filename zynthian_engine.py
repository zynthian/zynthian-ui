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
import re
import copy
import socket
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
	parent=None

	command=None
	command_env=None
	proc=None
	thread=None
	queue=None

	user_gid=1000
	user_uid=1000

	bank_list=None
	instr_list=None
	control_list=None

	midi_chan=0

	bank_index=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	bank_name=["","","","","","","","","","","","","","","",""]

	instr_index=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	instr_name=["","","","","","","","","","","","","","","",""]

	instr_ctrl_config=[None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None]

	default_ctrl_config=[
		('volume',7,96,127),
		#('expression',11,127,127),
		('modulation',1,0,127),
		#('reverb',91,64,127),
		#('chorus',93,64,127),
		('filter Q',71,64,127),
		('filter cutoff',74,64,127)
	]

	def __init__(self,parent=None):
		self.parent=parent
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

	def load_bank_filelist(self,dpath,fext):
		i=0
		fext='.'+fext
		xlen=len(fext)
		self.bank_list=[]
		print('Getting Bank List for ' + self.name)
		for f in sorted(os.listdir(dpath)):
			if (isfile(join(dpath,f)) and f[-xlen:].lower()==fext):
				title=str.replace(f[:-xlen], '_', ' ')
				self.bank_list.append((f,i,title))
				i=i+1

	def load_bank_dirlist(self,dpath):
		i=0
		self.bank_list=[]
		print('Getting Bank List for ' + self.name)
		for f in sorted(os.listdir(dpath)):
			if isdir(join(dpath,f)):
				title=str.replace(f, '_', ' ')
				self.bank_list.append((f,i,title))
				i=i+1

	def load_bank_list(self):
		self.bank_list=[]

	def load_instr_list(self):
		self.instr_list=[]

	def load_instr_config(self):
		self.instr_ctrl_config[self.midi_chan]=copy.copy(self.default_ctrl_config)

	def set_bank(self, i):
		last_bank_index=self.bank_index[self.midi_chan]
		self.bank_index[self.midi_chan]=i
		self.bank_name[self.midi_chan]=self.bank_list[i][2]
		self.load_instr_list()
		if last_bank_index!=i:
			zynmidi.set_midi_bank_msb(self.midi_chan, i)
			self.reset_instr()
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')

	def set_instr(self, i):
		last_instr_index=self.instr_index[self.midi_chan]
		self.instr_index[self.midi_chan]=i
		self.instr_name[self.midi_chan]=self.instr_list[i][2]
		print('Instrument Selected: ' + self.instr_name[self.midi_chan] + ' (' + str(i)+')')
		if last_instr_index!=i:
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
	command=None
	osc_paths_data=[]
	#bank_dir="/usr/share/zynaddsubfx/banks"
	bank_dir="./data/zynbanks"

	map_list=(
		([
			('volume',Template('/part$part/Pvolume'),96,127),
			#('volume',7,96,127),
			('modulation',1,0,127),
			('filter Q',71,64,127),
			('filter cutoff',74,64,127)
		],0,'main'),
		([
			('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'extra'),
		([
			('bandwidth',75,64,127),
			('modulation amplitude',76,127,127),
			('resonance frequency',77,64,127),
			('resonance bandwidth',78,64,127)
		],0,'resonance')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		if os.environ.get('ZYNTHIANX'):
			self.command_env=os.environ.copy()
			self.command_env['DISPLAY']=os.environ.get('ZYNTHIANX')
			self.command=("./software/zynaddsubfx/build/src/zynaddsubfx", "-O", "alsa", "-I", "alsa", "-P", str(zyngine_osc_port), "-l", "zynconf/zasfx_4ch.xmz")
		else:
			self.command=("./software/zynaddsubfx/build/src/zynaddsubfx", "-O", "alsa", "-I", "alsa", "-U", "-P", str(zyngine_osc_port), "-l", "zynconf/zasfx_4ch.xmz")
		super().__init__(parent)

	def load_bank_list(self):
		self.load_bank_dirlist(self.bank_dir)

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

	def cb_osc_paths(self, path, args, types, src):
		for a, t in zip(args, types):
			if not a or t=='b':
				continue
			print("=> %s (%s)" % (a,t))
			a=str(a)
			postfix=prefix=firstchar=lastchar=''
			if a[-1:]=='/':
				tnode='dir'
				postfix=lastchar='/'
				a=a[:-1]
			elif a[-1:]==':':
				tnode='cmd'
				postfix=':'
				a=a[:-1]
				continue
			elif a[0]=='P':
				tnode='par'
				firstchar='P'
				a=a[1:]
			else:
				continue
			parts=a.split('::')
			if len(parts)>1:
				a=parts[0]
				pargs=parts[1]
				if tnode=='par':
					if pargs=='i':
						tnode='ctrl'
						postfix=':i'
					elif pargs=='T:F':
						tnode='bool'
						postfix=':b'
					else:
						continue
			parts=a.split('#',1)
			if len(parts)>1:
				n=int(parts[1])
				if n>0:
					for i in range(0,n):
						title=prefix+parts[0]+str(i)+postfix
						path=firstchar+parts[0]+str(i)+lastchar
						self.osc_paths.append((path,tnode,title))
			else:
				title=prefix+a+postfix
				path=firstchar+a+lastchar
				self.osc_paths_data.append((path,tnode,title))

#-------------------------------------------------------------------------------
# FluidSynth Engine Class
#-------------------------------------------------------------------------------

class zynthian_fluidsynth_engine(zynthian_synth_engine):
	name="FluidSynth"
	#command=("/usr/local/bin/fluidsynth", "-p", "FluidSynth", "-a", "alsa" ,"-g", "1")
	command=("/usr/bin/fluidsynth", "-p", "FluidSynth", "-a", "alsa" ,"-g", "1")
	#synth.midi-bank-select => mma
	soundfont_dir="./data/soundfonts"
	bank_id=0

	map_list=(
		([
			('volume',7,96,127),
			#('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'main'),
		([
			('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'extra')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		self.parent=parent
		self.start(True)
		self.load_bank_list()

	def stop(self):
		self.proc_cmd("quit",2)
		super().stop()

	def load_bank_list(self):
		self.load_bank_filelist(self.soundfont_dir,"sf2")

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
		self.proc_cmd("load " + self.soundfont_dir + '/' + self.bank_list[i][0],20)
		self.bank_id=self.bank_id+1
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')
		self.load_instr_list()

	def load_instr_config(self):
		super().load_instr_config()

#-------------------------------------------------------------------------------
# setBfree Engine Class
#-------------------------------------------------------------------------------

class zynthian_setbfree_engine(zynthian_synth_engine):
	name="setBfree"
	pgm_dir="./data/setbfree"
	command=("/usr/local/bin/setBfree", "midi.driver=alsa", "-p", pgm_dir+"/all.pgm")

	map_list=(
		([
			('swellpedal',1,96,127),
#			('swellpedal 2',11,96,127),
			('percussion on/off',80,1,1),
			('rotary speed',91,0,2),
#			('rotary speed toggle',64,0,3)
			('vibrato on/off',92,1,4)
		],0,'main'),
		([
			('16',70,8,8),
			('5 1/3',71,8,8),
			('8',72,8,8),
			('4',73,8,8)
		],0,'drawbars low'),
		([
			('2 2/3',74,8,8),
			('2',75,8,8),
			('1 3/5',76,8,8),
			('1 1/3',77,8,8)
		],0,'drawbars hi'),
		([
			('drawbar 1',78,8,8),
			('percussion on/off',80,1,1),
			('percussion decay',81,1,1),
			('percussion harmonic',82,1,1)
		],0,'percussion'),
		([
			('vibrato routing',92,1,4),
			('vibrato selector',83,5,5),
			('overdrive character',93,1,6),
			('overdrive inputgain',21,1,127)
			#('overdrive outputgain',22,1,127)
		],0,'vibrato & overdrive')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		super().__init__(parent)

	def load_bank_list(self):
		self.load_bank_filelist(self.pgm_dir,"pgm")

	def load_instr_list(self):
		self.instr_list=[]

		pgm_fpath=self.pgm_dir+'/'+self.bank_list[self.get_bank_index()][0]
		with open(pgm_fpath) as f:
			lines = f.readlines()
			ptrn=re.compile("^([\d]+)[\s]*\{[\s]*name\=\"([^\"]+)\"")
			i=0
			for line in lines:
				m=ptrn.match(line)
				if m:
					try:
						prg=int(m.group(1))-1
						title=m.group(2)
						if prg>=0:
							self.instr_list.append((i,[0,0,prg],title))
							i=i+1
					except:
						pass

#-------------------------------------------------------------------------------
# Linuxsampler Engine Class
#-------------------------------------------------------------------------------

class zynthian_linuxsampler_engine(zynthian_synth_engine):
	name="LinuxSampler"
	port=6688
	sock=None
	command=("/usr/bin/linuxsampler","--lscp-port",str(port))
	lscp_dir="./data/lscp"

	map_list=(
		([
			('volume',7,96,127),
			#('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'main'),
		([
			('expression',11,127,127),
			('modulation',1,0,127),
			('reverb',91,64,127),
			('chorus',93,2,127)
		],0,'extra')
	)
	default_ctrl_config=map_list[0][0]

	def __init__(self,parent=None):
		super().__init__(parent)

	def lscp_connect(self):
		if not self.sock:
			self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			self.sock.connect(("127.0.0.1",self.port))
		return self.sock
   
	def lscp_send(self,data):
		if self.lscp_connect():
			self.sock.send(data.encode()) 

	def load_bank_list(self):
		self.load_bank_filelist(self.lscp_dir,"lscp")

	def load_instr_list(self):
		self.instr_list=[]
		lscp_fpath=self.lscp_dir+'/'+self.bank_list[self.get_bank_index()][0]
		with open(lscp_fpath) as f:
			lines = f.readlines()
			ptrn=re.compile("^MAP MIDI_INSTRUMENT")
			i=0
			for line in lines:
				m=ptrn.match(line)
				if m:
					try:
						parts=line.split();
						title=str.replace(parts[11][1:-1], '_', ' ')
						self.instr_list.append((i,[0,int(parts[4]),int(parts[5])],title))
						i=i+1
					except:
						pass

	def set_bank(self, i):
		super().set_bank(i)
		#Send LSCP script
		lscp_fpath=self.lscp_dir+'/'+self.bank_list[self.get_bank_index()][0]
		with open(lscp_fpath) as f:
			lines = f.readlines()
			for line in lines:
				self.lscp_send(line)
				#print("LSCP: "+line)


#-------------------------------------------------------------------------------
