# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine)
# 
# zynthian_engine is the base class for the Zynthian Synth Engine
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

#import sys
import os
import copy
import liblo
from os.path import isfile, isdir, join
from subprocess import Popen, PIPE, STDOUT
from threading  import Thread
from queue import Queue, Empty

#------------------------------------------------------------------------------
# OSC Port for Synth Engines
#------------------------------------------------------------------------------

osc_port=6693

#------------------------------------------------------------------------------
# Synth Engine Base Class
#------------------------------------------------------------------------------

class zynthian_engine:
	name=""
	nickname=""
	parent=None

	audio_driver="jack"
	midi_driver="jack"

	command=None
	command_env=None
	proc=None
	thread=None
	queue=None

	user_gid=1000
	user_uid=1000

	osc_target=None
	osc_target_port=osc_port
	osc_server=None
	osc_server_port=None

	bank_list=None
	instr_list=None
	control_list=None

	midi_chan=0
	max_chan=10

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

	def __init__(self, parent=None):
		self.parent=parent
		self.clean()
		self.start()
		self.load_bank_list()

	def __del__(self):
		self.stop()
		self.clean()

	def clean(self):
		self.midi_chan=0
		for i in range(16):
			self.bank_index[i]=0
			self.bank_name[i]=""
			self.instr_index[i]=0
			self.instr_name[i]=""

	def proc_enqueue_output(self):
		for line in self.proc.stdout:
			self.queue.put(line)

	def proc_get_lines(self, tout=0.1, limit=2):
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

	def start(self, start_queue=False, shell=False):
		if not self.proc:
			print("Starting Engine " + self.name)
			self.proc=Popen(self.command,shell=shell,bufsize=1,universal_newlines=True,stdin=PIPE,stdout=PIPE,stderr=STDOUT,env=self.command_env)
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
			#self.proc.stdout.close()
			#self.proc.stdin.close()
			self.proc.kill()
			self.proc=None

	def proc_cmd(self, cmd, tout=0.1):
		if self.proc:
			print("PROC_CMD: "+cmd)
			#self.proc.stdin.write(bytes(cmd + "\n", 'UTF-8'))
			self.proc.stdin.write(cmd + "\n")
			self.proc.stdin.flush()
			return self.proc_get_lines(tout)

	def _osc_init(self):
		try:
			self.osc_target=liblo.Address(self.osc_target_port)
			print("OSC target in port %s" % str(self.osc_target_port))
			self.osc_server=liblo.Server()
			self.osc_server_port=self.osc_server.get_port()
			print("OSC server running in port %s" % str(self.osc_server_port))
			#print("OSC Server running");
			self.osc_init()
		except liblo.AddressError as err:
			print("ERROR: OSC Server can't be initialized (%s). Running without OSC feedback." % (str(err)))

	def osc_init(self):
			self.osc_server.add_method(None, None, self.cb_osc_all)

	def cb_osc_all(self, path, args, types, src):
		print("OSC MESSAGE '%s' from '%s'" % (path, src.url))
		for a, t in zip(args, types):
			print("argument of type '%s': %s" % (t, a))

	def set_midi_chan(self, i):
		print('MIDI Chan Selected: ' + str(i))
		self.midi_chan=i

	def next_chan(self):
		#self.set_midi_chan(self.midi_chan+1)
		#return True
		count=0
		nchan=len(self.bank_index)
		i=self.midi_chan
		while count<nchan:
			i+=1
			if i>=nchan:
				i=0
			if self.instr_name[i]:
				break
		if self.midi_chan!=i:
			self.set_midi_chan(i)
			return True
		else:
			return False

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
		self.instr_name[self.midi_chan]=None

	def load_bank_filelist(self, dpath, fext):
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

	def load_bank_cmdlist(self,cmd):
		i=0
		self.bank_list=[]
		print('Getting Bank List for ' + self.name)
		output=check_output(cmd, shell=True)
		lines=output.decode('utf8').split('\n')
		for f in lines:
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
			self.parent.zynmidi.set_midi_bank_msb(self.midi_chan, i)
			self.reset_instr()
		print('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')

	def set_instr(self, i):
		last_instr_index=self.instr_index[self.midi_chan]
		last_instr_name=self.instr_name[self.midi_chan]
		self.instr_index[self.midi_chan]=i
		self.instr_name[self.midi_chan]=self.instr_list[i][2]
		print('Instrument Selected: ' + self.instr_name[self.midi_chan] + ' (' + str(i)+')')
		if last_instr_index!=i or not last_instr_name:
			self.parent.zynmidi.set_midi_instr(self.midi_chan, self.instr_list[i][1][0], self.instr_list[i][1][1], self.instr_list[i][1][2])
			self.load_instr_config()

	def get_path(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		path=self.bank_name[chan]
		if self.instr_name[chan]:
			path=path + '/' + self.instr_name[chan]
		return path

	def get_fullpath(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		return self.nickname + "#" + str(chan+1) + " > " + self.get_path(chan)


#******************************************************************************
