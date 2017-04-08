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
from time import sleep,time
from subprocess import check_output
from threading  import Thread
from collections import OrderedDict
from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# MOD-UI Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_modui(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name="MOD-UI"
		self.nickname="MD"

		self.base_api_url='http://localhost:8888'
		self.websocket_url='ws://localhost:8888/websocket'
		self.websocket=None

		self.bank_dirs=[
			#('MY', os.getcwd()+"/my-data/mod-pedalboards"),
			('_', os.getcwd()+"/my-data/mod-pedalboards")
		]

		self.reset()
		self.start()

	def reset(self):
		super().reset()
		self.hw_ports={}
		self.graph={}
		self.plugin_info=OrderedDict()
		self.plugin_zctrls=OrderedDict()

	def start(self):
		self.start_loading()
		if not self.is_service_active():
			logging.info("STARTING MOD-HOST & MOD-UI services...")
			check_output(("systemctl start mod-host && systemctl start mod-ui"),shell=True)
		self.stop_loading()

	def stop(self):
		self.start_loading()
		#self.stop_websocket()
		if self.is_service_active():
			logging.info("STOPPING MOD-HOST & MOD-UI services...")
			check_output(("systemctl stop mod-host && systemctl stop mod-ui"),shell=True)
		self.stop_loading()

	def is_service_active(self, service="mod-ui"):
		cmd="systemctl is-active "+str(service)
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: "+str(e)
		if result.strip()=='active': return True
		else: return False

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)
		if not self.websocket:
			self.start_websocket()

	def del_layer(self, layer):
		super().del_layer(layer)
		self.graph_reset()

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)

	def set_bank(self, layer, bank):
		self.start_loading()
		self.load_bundle(bank[0])
		self.stop_loading()

	def load_bundle(self, path):
		self.graph_reset()
		res = self.api_post_request("/pedalboard/load_bundle/",data={'bundlepath':path})
		if not res or not res['ok']:
			logging.error("Loading Bundle "+path)
		else:
			return res['name']

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		preset_list=[]
		for pgraph in self.plugin_info:
			for prs in self.plugin_info[pgraph]['presets']:
				#title=self.plugin_info[pgraph]['name']+':'+prs['label']
				title=prs['label']
				preset_list.append((prs['uri'],[0,0,0],title,pgraph))
				logging.debug("Add Preset "+title)
		return preset_list

	def set_preset(self, layer, preset):
		self.start_loading()
		self.load_preset(preset[3],preset[0])
		self.stop_loading()

	def load_preset(self, plugin, preset):
		res = self.api_get_request("/effect/preset/load/"+plugin,data={'uri':preset})

	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		zctrls=OrderedDict()
		self._ctrl_screens=[]
		try:
			for pgraph in sorted(self.plugin_info, key=lambda k: self.plugin_info[k]['posx']):
				#logging.debug("PLUGIN %s => X=%s" % (pgraph,self.plugin_info[pgraph]['posx']))
				c=1
				ctrl_set=[]
				for param in self.plugin_info[pgraph]['ports']['control']['input']:
					try:
						#logging.debug("CTRL LIST PLUGIN %s PARAM %s" % (pgraph,ctrl))
						zctrls[param['ctrl'].graph_path]=param['ctrl']
						ctrl_set.append(param['ctrl'].graph_path)
						if len(ctrl_set)>=4:
							#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
							self._ctrl_screens.append([self.plugin_info[pgraph]['name']+'#'+str(c),ctrl_set])
							ctrl_set=[]
							c=c+1
					except Exception as err:
						logging.error("Generating Controller Screens: "+pgraph+" => "+str(err))
				if len(ctrl_set)>=1:
					#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
					self._ctrl_screens.append([self.plugin_info[pgraph]['name']+'#'+str(c),ctrl_set])
		except Exception as err:
			logging.error("Generating Controller List: %s"+str(err))
		return zctrls

	def send_controller_value(self, zctrl):
		val=float(zctrl.get_label2value())
		self.websocket.send("param_set %s %.6f" % (zctrl.graph_path, val))
		logging.debug("WS << param_set %s %.6f" % (zctrl.graph_path, val))

	#----------------------------------------------------------------------------
	# Websocket & MOD-UI API Management
	#----------------------------------------------------------------------------

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
					self.midi_map_cb(args[1],args[2],args[3],args[4])

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
		if self.zyngui.active_screen in ['layer','bank']:
			bdirname=bpath.split('/')[-1]
			if bdirname!='default.pedalboard':
				#Find bundle_path in bank list ...
				layer=self.layers[0]
				for i in range(len(layer.bank_list)):
					#logging.debug("BUNDLE PATH SEARCH => %s <=> %s" % (bank_list[i][0].split('/')[-1], bdirname))
					if layer.bank_list[i][0].split('/')[-1]==bdirname:
						bank_index=i
						bank_name=layer.bank_list[i][2]
						#Set Bank in GUI, layer and engine without reloading the bundle
						logging.info('Bank Selected from Bundlepath: ' + bank_name + ' (' + str(i)+')')
						self.zyngui.screens['bank'].select(i)
						layer.set_bank(i,False)
						#Show preset screen
						self.zyngui.show_screen('preset')
						break

	def add_hw_port_cb(self, ptype, pdir, pgraph, pname, pnum):
		if ptype not in self.hw_ports:
			self.hw_ports[ptype]={}
		if pdir not in self.hw_ports[ptype]:
			self.hw_ports[ptype][pdir]={}
		self.hw_ports[ptype][pdir][pgraph]={'name':pname,'num':pnum}
		self.graph_autoconnect_midi_input()
		logging.debug("ADD_HW_PORT => "+pgraph+", "+ptype+", "+pdir)

	def add_plugin_cb(self, pgraph, puri, posx, posy):
		pinfo=self.api_get_request("/effect/get",data={'uri':puri})
		if pinfo:
			self.plugin_zctrls[pgraph]={}
			#Add parameters to dictionary
			for param in pinfo['ports']['control']['input']:
				try:
					ctrl_graph=pgraph+'/'+param['symbol']
					#If there is range info (should be!!) ...
					if param['valid'] and param['ranges'] and len(param['ranges'])>2:
						#If there is Scale Points info ...
						if param['scalePoints'] and len(param['scalePoints'])>1:
							labels=[]
							values=[]
							for p in param['scalePoints']:
								if p['valid']:
									labels.append(p['label'])
									values.append(p['value'])
							try:
								val=labels[ticks.index(param['ranges']['default'])]
							except:
								val=labels[0]
							param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
								'graph_path': ctrl_graph,
								'value': val,
								'labels': labels,
								'values': values
							})
						#If it's a normal controller ...
						else:
							pranges=param['ranges']
							r=pranges['maximum']-pranges['minimum']
							if param['properties'] and 'integer' in param['properties']:
								if r==1:
									if pranges['default']==0: val='off'
									else: val='on'
									param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
										'graph_path': ctrl_graph,
										'value': val,
										'labels': ['off','on'],
										'values': [0,1]
									})
								else:
									param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
										'graph_path': ctrl_graph,
										'value': int(pranges['default']),
										'value_default': int(pranges['default']),
										'value_max': int(pranges['maximum']),
										'value_min': int(pranges['minimum'])
									})
							else:
								param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
									'graph_path': ctrl_graph,
									'value': pranges['default'],
									'value_default': pranges['default'],
									'value_max': pranges['maximum'],
									'value_min': pranges['minimum']
								})
					#If there is no range info (should be!!) => Default MIDI CC controller with 0-127 range
					else:
						param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
							'graph_path': ctrl_graph,
							'value': 0,
							'value_default': 0,
							'value_max': 0,
							'value_min': 127
						})
					#Add ZController to plugin_zctrl dictionary
					self.plugin_zctrls[pgraph][param['symbol']]=param['ctrl']
				except Exception as err:
					logging.error("Configuring Controllers: "+pgraph+" => "+str(err))
			#Add bypass Zcontroller
			bypass_zctrl=zynthian_controller(self,'enabled','enabled',{
				'graph_path': pgraph+'/:bypass',
				'value': 'on',
				'labels': ['off','on'],
				'values': [1,0]
			})
			self.plugin_zctrls[pgraph][':bypass']=bypass_zctrl
			pinfo['ports']['control']['input'].insert(0,{'symbol':':bypass', 'ctrl':bypass_zctrl})
			#Add position info
			pinfo['posx']=int(round(float(posx)))
			pinfo['posy']=int(round(float(posy)))
			#Add to info array
			self.plugin_info[pgraph]=pinfo
			#Set Refresh
			self.refresh_all()

	def remove_plugin_cb(self, pgraph):
		if pgraph in self.graph:
			del self.graph[pgraph]
		if pgraph in self.plugin_zctrls:
			del self.plugin_zctrls[pgraph]
		if pgraph in self.plugin_info:
			del self.plugin_info[pgraph]
		#Set Refresh
		self.refresh_all()

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

	def set_param_cb(self, pgraph, symbol, val):
		try:
			zctrl=self.plugin_zctrls[pgraph][symbol]
			zctrl.value=zctrl.get_value2label(float(val))
			#Refresh GUI controller in screen when needed ...
			if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
				self.zyngui.screens['control'].set_controller_value(zctrl)
		except Exception as err:
			logging.error("Parameter Not Found: "+pgraph+"/"+symbol+" => "+str(err))
			#TODO: catch different types of exception

	def get_parameter_address_data(self, zctrl, uri):
		if isinstance(zctrl.labels,list):
			steps=len(zctrl.labels)
		else:
			steps=127
		data={
			"uri": uri,
			"label": zctrl.short_name,
			"minimum": str(zctrl.value_min),
			"maximum": str(zctrl.value_max),
			"value": str(zctrl.value),
			"steps": str(steps)
		}
		logging.debug("Parameter Address Data => %s" % str(data))
		return data

	def midi_learn(self, zctrl):
		logging.info("MIDI Learn: %s" % zctrl.graph_path)
		res = self.api_post_request("/effect/parameter/address/"+zctrl.graph_path,json=self.get_parameter_address_data(zctrl,"/midi-learn"))

	def midi_unlearn(self, zctrl):
		logging.info("MIDI Unlearn: %s" % zctrl.graph_path)
		res = self.api_post_request("/effect/parameter/address/"+zctrl.graph_path,json=self.get_parameter_address_data(zctrl,"null"))
		if res:
			zctrl.midi_cc=None
			#Refresh GUI Controller in screen when needed ...
			if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
				try:
					self.zyngui.screens['control'].get_zgui_controller(zctrl).set_midi_icon()
				except:
					pass

	def midi_map_cb(self, pgraph, symbol, chan, cc):
		logging.info("MIDI Map: %s %s => %s, %s" % (pgraph,symbol,chan,cc))
		try:
			zctrl=self.plugin_zctrls[pgraph][symbol]
			#zctrl.midi_chan=int(chan)
			zctrl.midi_cc=int(cc)
			#Refresh GUI Controller in screen when needed ...
			if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
				try:
					self.zyngui.screens['control'].get_zgui_controller(zctrl).set_midi_icon()
				except:
					pass
		except Exception as err:
			logging.error("Parameter Not Found: "+pgraph+"/"+symbol+" => "+str(err))

	#----------------------------------------------------------------------------
	# Snapshot Managament
	#----------------------------------------------------------------------------

	def load_snapshot(self, fpath):
		self._load_snapshot(fpath)
		self.set_all_bank()
		return True

	def load_snapshot_post(self):
		try:
			#self.set_all_instr()
			self.set_all_ctrl()
			self.zyngui.refresh_screen()
			self.loading_snapshot=False
			return True
		except Exception as e:
			logging.error("%s" % e)
			return False

#******************************************************************************
