# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_modui)
# 
# zynthian_engine implementation for MOD-UI (LV2 plugin host)
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

import os
import copy
import logging
import requests
import websocket
from time import sleep
from subprocess import check_output
from threading  import Thread
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# ZynAddSubFX Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_modui(zynthian_engine):
	name="MOD-UI"
	nickname="MD"
	max_chan=1

	base_api_url='http://localhost:8888'
	websocket_url='ws://localhost:8888/websocket'
	websocket=None

	bank_dirs=[
		#('MY', os.getcwd()+"/my-data/mod-pedalboards"),
		('_', os.getcwd()+"/data/mod-pedalboards")
	]

	hw_ports={}
	plugin_info={}
	graph={}
	default_ctrl_list=[]
	ctrl_list=[]
	ctrl_dict={}
	touched=False
	refreshed_ts=None

	def __init__(self,parent=None):
		self.parent=parent
		self.clean()
		self.load_bank_list()
		self.start()
		#self.osc_init()

	def clean(self):
		self.graph={}
		self.ctrl_dict={}
		self.plugin_info={}
		self.touched=True
		super().clean()

	def reset(self):
		self.graph={}
		self.ctrl_dict={}
		self.plugin_info={}
		self.touched=True
		self.midi_chan=0
		if not self.loading_snapshot:
			for i in range(16):
				self.instr_index[i]=0
				self.instr_name[i]=""
				self.instr_set[i]=None
				self.ctrl_config[i]=None

	def start(self):
		self.start_loading()
		if not self.is_service_active():
			logging.info("START MOD-HOST & MOD-UI services...")
			check_output(("systemctl start mod-host && systemctl start mod-ui"),shell=True)
		self.start_websocket()
		self.stop_loading()

	def stop(self):
		self.start_loading()
		#self.stop_websocket()
		if self.is_service_active():
			logging.info("STOP MOD-HOST & MOD-UI services...")
			check_output(("systemctl stop mod-host && systemctl stop mod-ui"),shell=True)
		self.stop_loading()

	def refresh(self):
		if self.touched:
			self.touched=False
			self.refreshed_ts=time()
			#generate preset list
			self.load_instr_list()
			#generate controller list
			self.generate_ctrl_list()
			#logging.debug("CONTROLLER LIST ...\n"+str(self.ctrl_list))
			#when loading a patch => change to control screen
			if self.parent.active_screen in ['chan','bank'] and len(self.ctrl_list):
				self.parent.show_screen('control')
			#refresh screen
			self.parent.refresh_screen()
		elif self.refreshed_ts and (time()-self.refreshed_ts)>0.5:
			self.refreshed_ts=None

	def is_service_active(self, service="mod-ui"):
		cmd="systemctl is-active "+str(service)
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: "+str(e)
		if result.strip()=='active': return True
		else: return False

	def start_websocket(self):
		logging.info("Connecting to MOD-UI websocket...")
		i=0
		while i<100:
			try:
				self.websocket = websocket.create_connection(self.websocket_url)
				break
			except:
				i=i+1
				sleep(0.1)
		if i<100:
			self.ws_thread=Thread(target=self.task_websocket, args=())
			self.ws_thread.daemon = True # thread dies with the program
			self.ws_thread.start()
			return True
		else:
			return False 

	def stop_websocket(self):
		logging.info("Closing MOD-UI websocket...")
		if self.websocket:
			self.websocket.close()

	def task_websocket(self):
		self.enable_midi_devices()
		while True:
			try:
				received =  self.websocket.recv()
				logging.debug("WS >> %s" % received)
				args = received.split() 
				command = args[0]

				if command == "ping":
					self.enable_midi_devices()
					self.websocket.send("pong")
					logging.debug("WS << pong")

				elif command == "add_hw_port":
					if args[3]=='1': pdir="output"
					else: pdir="input"
					self.add_hw_port_cb(args[2],pdir,args[1],args[4],args[5])

				elif command == "add":
					if args[2][0:4] == "http":
						logging.info("ADD PLUGIN: "+args[1]+" => "+args[2])
						self.add_plugin_cb(args[1],args[2],args[3],args[4])

				elif command == "remove":
					if args[1] == ":all":
						logging.info("REMOVE ALL PLUGINS")
						self.reset()
					elif args[1]:
						logging.info("REMOVE PLUGIN: "+args[1])
						self.remove_plugin_cb(args[1])

				elif command == "connect":
					self.graph_connect_cb(args[1],args[2])

				elif command == "disconnect":
					self.graph_disconnect_cb(args[1],args[2])

				elif command == "param_set":
					self.set_param_cb(args[1],args[2],args[3])

				elif command == "midi_map":
					pass

				elif command == "loading_start":
						logging.info("LOADING START")

				elif command == "loading_end":
					logging.info("LOADING END")
					self.graph_autoconnect_midi_input()
					if self.loading_snapshot:
						self.load_snapshot_post()

				elif command == "bundlepath":
					logging.info("BUNDLEPATH %s" % args[1])
					self.bundlepath_cb(args[1])

				elif command == "stop":
					return

			except websocket._exceptions.WebSocketConnectionClosedException:
				if self.is_service_active("mod-ui"):
					try:
						self.websocket = websocket.create_connection(self.websocket_url)
					except:
						sleep(0.1)
				else:
					return
			except Exception as e:
				logging.error("task_websocket() => %s (%s)" % (e,type(e)))
				sleep(1)

	def api_get_request(self, path, data=None, json=None):
		res=requests.get(self.base_api_url + path, data=data, json=json)
		if res.status_code != 200:
			logging.error("GET call to MOD-UI API: "+str(res.status_code) + " => " +self.base_api_url + path)
		else:
			return res.json()

	def api_post_request(self, path, data=None, json=None):
		res=requests.post(self.base_api_url + path, data=data, json=json)
		if res.status_code != 200:
			logging.error("POST call to MOD-UI API: "+str(res.status_code) + " => " +self.base_api_url + path)
		else:
			return res.json()

	def bundlepath_cb(self, bpath):
		bdirname=bpath.split('/')[-1]
		for i in range(len(self.bank_list)):
			#print("BUNDLE PATH SEARCH => %s <=> %s" % (self.bank_list[i][0].split('/')[-1], bdirname))
			if self.bank_list[i][0].split('/')[-1]==bdirname:
				self.bank_index[self.midi_chan]=i
				self.bank_name[self.midi_chan]=self.bank_list[i][2]
				self.bank_set[self.midi_chan]=copy.deepcopy(self.bank_list[i])
				logging.info('Bank Selected: ' + self.bank_name[self.midi_chan] + ' (' + str(i)+')')

	def add_hw_port_cb(self, ptype, pdir, pgraph, pname, pnum):
		if ptype not in self.hw_ports:
			self.hw_ports[ptype]={}
		if pdir not in self.hw_ports[ptype]:
			self.hw_ports[ptype][pdir]={}
		self.hw_ports[ptype][pdir][pgraph]={'name':pname,'num':pnum}
		self.graph_autoconnect_midi_input()
		#print("ADD_HW_PORT => "+pgraph+", "+ptype+", "+pdir)

	def add_plugin_cb(self, pgraph, puri, posx, posy):
		pinfo=self.api_get_request("/effect/get",data={'uri':puri})
		if pinfo:
			self.ctrl_dict[pgraph]={}
			#Add parameters to dictionary
			for param in pinfo['ports']['control']['input']:
				try:
					#If there is range info (should be!!) ...
					if param['valid'] and param['ranges'] and len(param['ranges'])>2:
						#If there is Scale Points info ...
						if param['scalePoints'] and len(param['scalePoints'])>0:
							ppoints={}
							spoints=[]
							fpoints=[]
							for p in param['scalePoints']:
								if p['valid']:
									ppoints[p['label']]=p['value']
									spoints.append(p['label'])
									fpoints.append(p['value'])
							val=fpoints.index(param['ranges']['default'])
							if not val: val=fpoints[0]
							param['ctrl']=[param['shortName'], pgraph+'/'+param['symbol'], val, '|'.join(spoints), ppoints]
						#If it's a normal controller ...
						else:
							pranges=param['ranges']
							r=pranges['maximum']-pranges['minimum']
							if param['properties'] and 'integer' in param['properties'] and r<128:
								if r==1:
									if pranges['default']==0: val='off'
									else: val='on'
									param['ctrl']=[param['shortName'], pgraph+'/'+param['symbol'], val, 'off|on', {'off':0,'on':1}]
								else:
									pranges['mult']=1
									val=pranges['mult']*(pranges['default']-pranges['minimum'])
									param['ctrl']=[param['shortName'], pgraph+'/'+param['symbol'], val, r, pranges]
							else:
								if r>0: pranges['mult']=127/r
								else: pranges['mult']=1
								val=pranges['mult']*(pranges['default']-pranges['minimum'])
								param['ctrl']=[param['shortName'], pgraph+'/'+param['symbol'], val, 127, pranges]
					#If there is no range info (should be!!) => Default MIDI CC controller with 0-127 range
					else:
						param['ctrl']=[param['shortName'], pgraph+'/'+param['symbol'], 0, 127, None]
					self.ctrl_dict[pgraph][param['symbol']]=param['ctrl']
				except Exception as err:
					logging.error("Configuring Controllers: "+pgraph+" => "+str(err))
			#Add bypass control
			ctrl=['enabled', pgraph+'/:bypass', 'on', 'off|on', {'off':1,'on':0}]
			self.ctrl_dict[pgraph][':bypass']=ctrl
			pinfo['ports']['control']['input'].insert(0,{'symbol':':bypass', 'ctrl':ctrl})
			#Add position info
			pinfo['posx']=int(round(float(posx)))
			pinfo['posy']=int(round(float(posy)))
			#Add to info array
			self.plugin_info[pgraph]=pinfo
			self.touched=True

	def remove_plugin_cb(self, pgraph):
		if pgraph in self.graph:
			del self.graph[pgraph]
		if pgraph in self.ctrl_dict:
			del self.ctrl_dict[pgraph]
		if pgraph in self.plugin_info:
			del self.plugin_info[pgraph]
		self.touched=True

	def graph_connect_cb(self, src, dest):
		if src not in self.graph:
			self.graph[src]=[]
		self.graph[src].append(dest)

	def graph_disconnect_cb(self, src, dest):
		if src in self.graph:
			if dest in self.graph[src]:
				self.graph[src].remove(dest)

	def graph_reset(self):
		graph=copy.deepcopy(self.graph)
		for src in graph:
			for dest in graph[src]:
				self.api_get_request("/effect/disconnect/"+src+","+dest)
				#print("API /effect/disconnect/"+src+","+dest)
		self.api_get_request("/reset")

	#Connect unconnected MIDI-USB devices to the "input plugin" ...
	def graph_autoconnect_midi_input(self):
		midi_master="/graph/serial_midi_in"
		if midi_master in self.graph:
			for dest in self.graph[midi_master]:
				for src in self.hw_ports['midi']['input']:
					if src not in self.graph:
						self.api_get_request("/effect/connect/"+src+","+dest)

	def enable_midi_devices(self):
		res=self.api_get_request("/jack/get_midi_devices")
		#logging.debug("API /jack/get_midi_devices => "+str(res))
		if 'devList' in res:
			data=[]
			for dev in res['devList']: 
				if dev not in res['devsInUse']: data.append(dev)
			if len(data)>0:
				self.api_post_request("/jack/set_midi_devices",json=data)
				#print("API /jack/set_midi_devices => "+str(data))

	def load_bank_list(self):
		self.load_bank_dirlist(self.bank_dirs)

	def load_instr_list(self):
		self.instr_list=[]
		for pgraph in self.plugin_info:
			for prs in self.plugin_info[pgraph]['presets']:
				#title=self.plugin_info[pgraph]['name']+':'+prs['label']
				title=prs['label']
				self.instr_list.append((prs['uri'],[0,0,0],title,pgraph))
				logging.debug("Add Preset "+title)

	def load_bundle(self, path):
		self.graph_reset()
		res = self.api_post_request("/pedalboard/load_bundle/",data={'bundlepath':path})
		if not res or not res['ok']:
			logging.error("Loading Bundle "+path)
		else:
			return res['name']

	def load_preset(self, plugin, preset):
		res = self.api_get_request("/effect/preset/load/"+plugin,data={'uri':preset})

	def _set_bank(self, bank, chan=None):
		self.start_loading()
		self.load_bundle(bank[0])
		self.stop_loading()

	def _set_instr(self, instr, chan=None):
		self.start_loading()
		self.load_preset(instr[3],instr[0])
		self.stop_loading()

	def load_ctrl_config(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		self.ctrl_config[chan]=self.ctrl_list

	def generate_ctrl_list(self):
		self.ctrl_list=[]
		for pgraph in sorted(self.plugin_info, key=lambda k: self.plugin_info[k]['posx']):
			#logging.debug("PLUGIN %s => X=%s" % (pgraph,self.plugin_info[pgraph]['posx']))
			c=1
			ctrl_set=[]
			for param in self.plugin_info[pgraph]['ports']['control']['input']:
				try:
					#logging.debug("CTRL LIST PLUGIN %s PARAM %s" % (pgraph,ctrl))
					ctrl_set.append(param['ctrl'])
					if len(ctrl_set)>=4:
						#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
						self.ctrl_list.append([ctrl_set,0,self.plugin_info[pgraph]['name']+'#'+str(c)])
						ctrl_set=[]
						c=c+1
				except Exception as err:
					logging.error("Generating Controller Screens: "+pgraph+" => "+str(err))
					pass
			if len(ctrl_set)>=1:
				#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
				self.ctrl_list.append([ctrl_set,0,self.plugin_info[pgraph]['name']+'#'+str(c)])
		if len(self.ctrl_list)==0:
			logging.info("Loading Controller Defaults")
			self.ctrl_list=self.default_ctrl_list
		self.load_ctrl_config()

	def set_ctrl_value(self, ctrl, val):
		ctrl[2]=val
		if isinstance(ctrl[1],str) and len(ctrl[4])>=2:
			if isinstance(val,str): val=ctrl[4][val]
			else:
				pranges=ctrl[4]
				val=pranges['minimum']+val/pranges['mult']
			self.websocket.send("param_set "+ctrl[1]+" "+str("%.6f" % val))
			logging.debug("WS << param_set "+ctrl[1]+" "+str("%.6f" % val))

	def set_param_cb(self, pgraph, symbol, val):
		try:
			ctrl=self.ctrl_dict[pgraph][symbol]
			if isinstance(ctrl[1],str) and len(ctrl[4])>=2:
				try:
					val=float(val)
					pranges=ctrl[4]
					ctrl[2]=int(pranges['mult']*(val-pranges['minimum']))
				except:
					if symbol==':bypass': val=int(val)
					ctrl[2]=list(ctrl[4].keys())[list(ctrl[4].values()).index(val)] #TODO optimize??
				#Refresh control in screen when needed!!
				if self.parent.active_screen=='control' and self.parent.screens['control'].mode=='control':
					self.parent.screens['control'].refresh_controller_value(ctrl)
		except Exception as err:
			logging.error("Parameter Not Found: "+pgraph+"/"+symbol+" => "+str(err))

	#Send All Controller Values to Synth
	def set_all_ctrl(self):
		for ch in range(16):
			if self.ctrl_config[ch]:
				for ctrlcfg in self.ctrl_config[ch]:
					for ctrl in ctrlcfg[0]:
						self.set_ctrl_value(ctrl, ctrl[2])

	def load_snapshot(self, fpath):
		self._load_snapshot(fpath)
		self.set_all_bank()
		return True

	def load_snapshot_post(self):
		try:
			#self.set_all_instr()
			self.set_all_ctrl()
			self.parent.refresh_screen()
			self.loading_snapshot=False
			return True
		except Exception as e:
			logging.error("%s" % e)
			return False

#******************************************************************************
