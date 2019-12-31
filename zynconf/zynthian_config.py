# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Config Library
# 
# Zynthian Config library and tools
# 
# Copyright (C) 2015-2017 Fernando Moyano <jofemodo@zynthian.org>
#
#********************************************************************
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
#********************************************************************

import os
import re
import sys
import socket
import psutil
import logging
from time import sleep
from shutil import copyfile
from subprocess import check_output
from collections import OrderedDict

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

#logging.getLogger(__name__).setLevel(logging.ERROR)

#-------------------------------------------------------------------------------
# UI Definitions
#-------------------------------------------------------------------------------

CustomSwitchActionType = [
	"NONE",
	"UI_ACTION",
	"MIDI_CC"
];


CustomUiAction = [
	"NONE",
	"POWER_OFF",
	"REBOOT",
	"RESTART_UI",

	"ALL_NOTES_OFF",
	"ALL_SOUNDS_OFF",
	"ALL_OFF",

	"START_AUDIO_RECORD",
	"STOP_AUDIO_RECORD",
	"TOGGLE_AUDIO_RECORD",
	"START_AUDIO_PLAY",
	"STOP_AUDIO_PLAY",
	"TOGGLE_AUDIO_PLAY",

	"START_MIDI_RECORD",
	"STOP_MIDI_RECORD",
	"TOGGLE_MIDI_RECORD",
	"START_MIDI_PLAY",
	"STOP_MIDI_PLAY",
	"TOGGLE_MIDI_PLAY",

	"SELECT",
	"SELECT_UP",
	"SELECT_DOWN",

	"SWITCH_LAYER_SHORT",
	"SWITCH_LAYER_BOLD",
	"SWITCH_LAYER_LONG",
	"SWITCH_BACK_SHORT",
	"SWITCH_BACK_BOLD",
	"SWITCH_BACK_LONG",
	"SWITCH_SNAPSHOT_SHORT",
	"SWITCH_SNAPSHOT_BOLD",
	"SWITCH_SNAPSHOT_LONG",
	"SWITCH_SELECT_SHORT",
	"SWITCH_SELECT_BOLD",
	"SWITCH_SELECT_LONG"
];

#-------------------------------------------------------------------------------
# Global variables
#-------------------------------------------------------------------------------

sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")

#-------------------------------------------------------------------------------
# Config related functions
#-------------------------------------------------------------------------------

def get_config_fpath():
	fpath=os.environ.get('ZYNTHIAN_CONFIG_DIR','/zynthian/zynthian-sys/scripts')+"/zynthian_envars.sh"
	if not os.path.isfile(fpath):
		fpath=os.environ.get('ZYNTHIAN_SYS_DIR')+"/scripts/zynthian_envars.sh"
	elif not os.path.isfile(fpath):
		fpath="./zynthian_envars.sh"
	return fpath


def get_midi_config_fpath(fpath=None):
	if not fpath:
		fpath=os.environ.get("ZYNTHIAN_SCRIPT_MIDI_PROFILE",
			os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/midi-profiles/default.sh")
	if not os.path.isfile(fpath):
		#Try to copy from default template
		default_src= "%s/config/default_midi_profile.sh" % os.getenv('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")
		copyfile(default_src, fpath)

	return fpath


def load_config(set_env=True, fpath=None):
	if not fpath:
		fpath=get_config_fpath()

	# Get config file content
	with open(fpath) as f:
		lines = f.readlines()

	# Load config varnames
	varnames=[]
	pattern=re.compile("^export ([^\s]*?)=")
	for line in lines:
		res=pattern.match(line)
		if res:
			varnames.append(res.group(1))
			#logging.debug("CONFIG VARNAME: %s" % res.group(1))

	# Execute config script and dump environment
	env=check_output("source \"{}\";env".format(fpath), shell=True, universal_newlines=True, executable="/bin/bash")

	# Parse environment dump
	config={}
	pattern=re.compile("^([^\=]*)=(.*)$")
	lines=env.split("\n")
	for line in lines:
		res=pattern.match(line)
		if res:
			vn=res.group(1)
			if vn in varnames:
				val=res.group(2)
				config[vn]=val
				logging.debug("CONFIG VAR: %s=%s" % (vn,val))
				# Set local environment
				if set_env:
					os.environ[vn]=val

	return config


def save_config(config, update_sys=False, fpath=None):
	if not fpath:
		fpath = get_config_fpath()

	# Get config file content
	with open(fpath) as f:
		lines = f.readlines()

	# Find and replace lines to update
	updated = []
	add_row = 0
	pattern = re.compile("^export ([^\s]*?)=")
	for i,line in enumerate(lines):
		res=pattern.match(line)
		if res:
			varname=res.group(1)
			if varname in config:
				value=config[varname].replace("\n", "\\n")
				value=value.replace("\r", "")
				os.environ[varname]=value
				lines[i]="export %s=\"%s\"\n" % (varname,value)
				updated.append(varname)
				logging.debug(lines[i])

		if line.startswith("# Directory Paths"):
			add_row = i-1

	if add_row==0:
		add_row = len(lines)

	# Add the rest
	vars_to_add=set(config.keys())-set(updated)
	for varname in vars_to_add:
		value=config[varname].replace("\n", "\\n")
		value=value.replace("\r", "")
		os.environ[varname]=value
		lines.insert(add_row,"export %s=\"%s\"\n" % (varname,value))
		logging.info(lines[add_row])

	# Write updated config file
	with open(fpath,'w') as f:
		f.writelines(lines)
		f.flush()
		os.fsync(f.fileno())

	# Update System Configuration
	if update_sys:
		try:
			check_output(os.environ.get('ZYNTHIAN_SYS_DIR')+"/scripts/update_zynthian_sys.sh", shell=True)
		except Exception as e:
			logging.error("Updating Sytem Config: %s" % e)


#-------------------------------------------------------------------------------
# MIDI Config related functions
#-------------------------------------------------------------------------------


def load_midi_config(set_env=True, fpath=None):
	return load_config(set_env, get_midi_config_fpath(fpath))


def get_disabled_midi_in_ports(midi_ports):
	#Parse DISABLED_IN ports
	disabled_in_re = re.compile("^DISABLED_IN=(.*)$",re.MULTILINE)
	m=disabled_in_re.search(midi_ports)
	if m:
		disabled_midi_in_ports=m.group(1).split(",")
		logging.debug("DISABLED_MIDI_IN = %s" % disabled_midi_in_ports)
	else:
		disabled_midi_in_ports=""
		logging.warning("Using default DISABLED MIDI IN ports")
	return disabled_midi_in_ports


def get_enabled_midi_out_ports(midi_ports):
	#Parse ENABLED_OUT ports
	enabled_out_re = re.compile("^ENABLED_OUT=(.*)$",re.MULTILINE)
	m=enabled_out_re.search(midi_ports)
	if m:
		enabled_midi_out_ports=m.group(1).split(",")
		logging.debug("ENABLED_MIDI_OUT = %s" % enabled_midi_out_ports)
	else:
		enabled_midi_out_ports=["ttymidi:MIDI_out"]
		logging.warning("Using default ENABLED MIDI OUT ports")
	return enabled_midi_out_ports


def get_enabled_midi_fb_ports(midi_ports):
	#Parse ENABLED_FeedBack ports
	enabled_fb_re = re.compile("^ENABLED_FB=(.*)$",re.MULTILINE)
	m=enabled_fb_re.search(midi_ports)
	if m:
		enabled_midi_fb_ports=m.group(1).split(",")
		logging.debug("ENABLED_MIDI_FB = %s" % enabled_midi_fb_ports)
	else:
		enabled_midi_fb_ports=[]
		logging.warning("Using default ENABLED MIDI FB ports")
	return enabled_midi_fb_ports


def update_midi_profile(params, fpath=None):
	if not fpath:
		fpath=get_midi_config_fpath()

	midi_params = OrderedDict()
	for k, v in params.items():
		if k.startswith('ZYNTHIAN_MIDI'):
			if isinstance(v, list):
				midi_params[k] = v[0]
			else:
				midi_params[k] = v

	save_config(midi_params, False, fpath)

	for k in midi_params:
		del params[k]


#-------------------------------------------------------------------------------
# Network Config related functions
#-------------------------------------------------------------------------------


def get_netinfo(exclude_down=True):
	netinfo={}
	for ifc, snics in psutil.net_if_addrs().items():
		if ifc=="lo":
			continue
		for snic in snics:
			if snic.family == socket.AF_INET:
				netinfo[ifc]=snic
		if ifc not in netinfo:
			c=0
			for snic in snics:
				if snic.family == socket.AF_INET6:
					c+=1
			if c>=2:
				netinfo[ifc]=snic
		if ifc not in netinfo and not exclude_down:
			netinfo[ifc]=None
	return netinfo


def is_wifi_active():
	for ifc in get_netinfo():
		if ifc.startswith("wlan"):
			return True


def network_info():
	logging.info("NETWORK INFO")

	res = OrderedDict()
	res["Link-Local Name"] = ["{}.local".format(os.uname().nodename),"SUCCESS"]
	for ifc, snic in get_netinfo().items():
		if snic.family==socket.AF_INET and snic.address:
			res[ifc] = [str(snic.address),"SUCCESS"]
		else:
			res[ifc] = ["connecting...","WARNING"]

	return res


def start_wifi():
	logging.info("STARTING WIFI")

	check_output(sys_dir + "/sbin/set_wifi.sh on", shell=True)
	sleep(2)

	counter=0
	success=False
	while True:
		counter += 1
		for ifc, snic in get_netinfo().items():
			#logging.debug("{} => {}, {}".format(ifc,snic.family,snic.address))
			if ifc.startswith("wlan") and snic.family==socket.AF_INET and snic.address:
				success=True
				break

		if success:
			save_config({ 
					"ZYNTHIAN_WIFI_MODE": 'on'
			})
			return True

		elif counter>20:
			return False

		sleep(1)


def start_wifi_hotspot():
	logging.info("STARTING WIFI HOTSPOT")

	check_output(sys_dir + "/sbin/set_wifi.sh hotspot", shell=True)
	sleep(2)

	counter=0
	success=False
	while True:
		counter += 1
		for ifc, snic in get_netinfo().items():
			#logging.debug("{} => {}, {}".format(ifc,snic.family,snic.address))
			if ifc.startswith("wlan") and snic.family==socket.AF_INET and snic.address:
				success=True
				break

		if success:
			save_config({ 
					"ZYNTHIAN_WIFI_MODE": 'hotspot'
			})
			return True

		elif counter>20:
			return False

		sleep(1)


def stop_wifi():
	logging.info("STOPPING WIFI")

	check_output(sys_dir + "/sbin/set_wifi.sh off", shell=True)

	counter = 0
	success = False
	while not success:
		counter += 1
		success = True
		for ifc in get_netinfo():
			#logging.debug("{} is UP".format(ifc))
			if ifc.startswith("wlan"):
				success = False
				break

		if success:
			save_config({ 
					"ZYNTHIAN_WIFI_MODE": 'off'
			})
			return True

		elif counter>10:
			return False

		sleep(1)


def wifi_up():
	logging.info("WIFI UP")
	check_output(sys_dir + "/sbin/set_wifi.sh up", shell=True)


def wifi_down():
	logging.info("WIFI DOWN")
	check_output(sys_dir + "/sbin/set_wifi.sh down", shell=True)


def get_current_wifi_mode():
	if is_wifi_active():
		if is_service_active("hostapd"):
			return "hotspot"
		else:
			return "on"

	return "off"


#-------------------------------------------------------------------------------
# Utility functions
#-------------------------------------------------------------------------------

def is_process_running(procname):
	cmd="ps -e | grep %s" % procname
	try:
		result=check_output(cmd, shell=True).decode('utf-8','ignore')
		if len(result)>3:
			return True
		else:
			return False
	except Exception as e:
		return False


def is_service_active(service):
	cmd="systemctl is-active %s" % service
	try:
		result=check_output(cmd, shell=True).decode('utf-8','ignore')
	except Exception as e:
		result="ERROR: %s" % e
	#loggin.debug("Is service "+str(service)+" active? => "+str(result))
	if result.strip()=='active':
		return True
	else:
		return False


#------------------------------------------------------------------------------

